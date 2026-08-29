import logging
import secrets
import shutil
import time
from collections import defaultdict
from datetime import datetime
from typing import List, Literal, Optional

import psutil
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from database import BASE_DIR, get_connection, get_user_by_id, get_user_by_name, hash_password, verify_password

logger = logging.getLogger("cube")

app = FastAPI(title="CUBE API", debug=False)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 예상치 못한 예외에서도 스택트레이스/쿼리 내용이 응답으로 나가지 않도록 통일 처리.
# 실제 에러는 서버 로그에만 남긴다.
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "서버 내부 오류가 발생했습니다."})


# ---------- 요청자 신원 확인 (세션 토큰 기준) ----------
# 로그인 시 발급한 불투명 토큰만으로 신원을 확인한다. 클라이언트가 임의로 값을 지어내는
# X-User-Id 헤더 방식은 로그인 없이 남의 id를 자칭할 수 있어 폐기했다.
# 서버 재시작 시 전체 세션이 초기화되는 건 알려진 제약(데모 범위 밖, 추후 DB/영속 저장으로 개선).
_sessions: dict[str, int] = {}


def _extract_token(authorization: Optional[str] = Header(default=None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="인증이 필요합니다.")
    return authorization[len("Bearer "):]


def get_requester(token: str = Depends(_extract_token)):
    user_id = _sessions.get(token)
    if user_id is None:
        raise HTTPException(status_code=401, detail="인증이 필요합니다.")

    conn = get_connection()
    user = get_user_by_id(conn, user_id)
    conn.close()
    if user is None:
        raise HTTPException(status_code=401, detail="인증이 필요합니다.")
    return user


# admin.html이 사용하는 모든 기능은 서버 PC 자기 자신에서의 요청일 때만 허용한다
# (물리적 접근을 신뢰 기준으로 삼음 - 관리자 계정이 털려도 원격에서는 관리 기능을 쓸 수 없게).
LOCAL_HOSTS = {"127.0.0.1", "::1"}


def require_admin(request: Request, user=Depends(get_requester)):
    host = request.client.host if request.client else None
    if host not in LOCAL_HOSTS:
        raise HTTPException(status_code=403, detail="관리자 페이지는 서버 컴퓨터에서만 접근할 수 있습니다.")
    if not user["is_admin"]:
        raise HTTPException(status_code=403, detail="관리자만 접근할 수 있습니다.")
    return user


# ---------- 로그인 rate limit (같은 IP, 1분에 10회 초과 시 429) ----------
RATE_LIMIT_WINDOW_SECONDS = 60
RATE_LIMIT_MAX_ATTEMPTS = 10
_login_attempts: dict = defaultdict(list)


def check_login_rate_limit(ip: str):
    now = time.time()
    attempts = _login_attempts[ip]
    attempts[:] = [t for t in attempts if now - t < RATE_LIMIT_WINDOW_SECONDS]
    if len(attempts) >= RATE_LIMIT_MAX_ATTEMPTS:
        raise HTTPException(status_code=429, detail="너무 많은 로그인 시도가 있었습니다. 잠시 후 다시 시도해주세요.")
    attempts.append(now)


class LoginRequest(BaseModel):
    name: str
    password: str


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


DEFAULT_PASSWORD = "123456"


class TeacherCreate(BaseModel):
    name: str
    is_admin: bool = False
    department: str
    subject: Optional[str] = None
    is_homeroom: bool = False
    grade: Optional[int] = Field(default=None, ge=1, le=3)
    class_no: Optional[int] = None
    extension: str


class TeacherUpdate(BaseModel):
    name: Optional[str] = None
    department: Optional[str] = None
    subject: Optional[str] = None
    is_homeroom: Optional[bool] = None
    grade: Optional[int] = Field(default=None, ge=1, le=3)
    class_no: Optional[int] = None
    extension: Optional[str] = None


# UPDATE User SET 절에 들어갈 수 있는 컬럼명 화이트리스트 (TeacherUpdate 필드와 동일하게 유지)
ALLOWED_TEACHER_UPDATE_FIELDS = {
    "name", "department", "subject", "is_homeroom", "grade", "class_no", "extension"
}


class AdminStatusUpdate(BaseModel):
    is_admin: bool


class HomeroomStatusUpdate(BaseModel):
    is_homeroom: bool


SCHEDULE_CATEGORIES = ["공휴일", "시험", "행사", "창체", "동아리", "기타"]


class ScheduleCreate(BaseModel):
    title: str
    category: Literal["공휴일", "시험", "행사", "창체", "동아리", "기타"]
    start_date: str
    end_date: Optional[str] = None
    created_by: int


class PinUpdate(BaseModel):
    is_pinned: bool


class PersonalEventCreate(BaseModel):
    teacher_name: str
    title: str
    date: str
    memo: Optional[str] = None


class NoticeCreate(BaseModel):
    title: str
    content: Optional[str] = None
    deadline: Optional[str] = None
    author_id: int
    target_group: Optional[str] = None
    recipient_user_ids: List[int] = []
    recipient_group_ids: List[int] = []


class GroupCreate(BaseModel):
    name: str
    description: Optional[str] = None
    created_by: int


class GroupMemberAdd(BaseModel):
    user_id: int


class GroupUpdate(BaseModel):
    name: str


@app.get("/")
def read_root():
    return {"message": "CUBE API 서버가 실행 중입니다."}


# ---------- 서버 상태 (담당: yamako8119-ai) ----------
@app.get("/server-status")
def get_server_status():
    disk = shutil.disk_usage(BASE_DIR)
    mem = psutil.virtual_memory()
    return {
        "disk_used_gb": round(disk.used / (1024**3), 1),
        "disk_total_gb": round(disk.total / (1024**3), 1),
        "disk_percent": round(disk.used / disk.total * 100, 1),
        "ram_used_gb": round(mem.used / (1024**3), 1),
        "ram_total_gb": round(mem.total / (1024**3), 1),
        "ram_percent": mem.percent,
        "server_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


# ---------- 로그인 ----------
# 아이디: 교사 이름(User.name, UNIQUE). 초기 비밀번호: 123456 (seed.py와 동일한 해시 방식)
@app.post("/login")
def login(payload: LoginRequest, request: Request):
    check_login_rate_limit(request.client.host if request.client else "unknown")

    conn = get_connection()
    row = get_user_by_name(conn, payload.name)
    conn.close()

    # 비밀번호 비교는 서버(bcrypt.checkpw)에서만 수행. 사용자 존재 여부와 무관하게 동일한 에러만 반환.
    if row is None or not verify_password(payload.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="이름 또는 비밀번호가 올바르지 않습니다.")

    token = secrets.token_urlsafe(32)
    _sessions[token] = row["id"]

    return {
        "id": row["id"],
        "name": row["name"],
        "is_admin": bool(row["is_admin"]),
        "department": row["department"],
        "subject": row["subject"],
        "token": token,
    }


@app.post("/logout")
def logout(authorization: Optional[str] = Header(default=None)):
    if authorization and authorization.startswith("Bearer "):
        _sessions.pop(authorization[len("Bearer "):], None)
    return {"ok": True}


@app.patch("/me/password")
def change_own_password(payload: PasswordChange, requester=Depends(get_requester)):
    if len(payload.new_password) < 4:
        raise HTTPException(status_code=400, detail="새 비밀번호는 4자 이상이어야 합니다.")

    conn = get_connection()
    row = conn.execute("SELECT password_hash FROM User WHERE id = ?", (requester["id"],)).fetchone()
    if row is None or not verify_password(payload.current_password, row["password_hash"]):
        conn.close()
        raise HTTPException(status_code=401, detail="현재 비밀번호가 올바르지 않습니다.")

    conn.execute(
        "UPDATE User SET password_hash = ? WHERE id = ?",
        (hash_password(payload.new_password), requester["id"]),
    )
    conn.commit()
    conn.close()
    return {"ok": True}


# ---------- 교사 ----------
@app.get("/teachers")
def get_teachers():
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, name, is_admin, department, subject, is_homeroom, grade, class_no, extension "
        "FROM User WHERE is_deleted = 0 ORDER BY name"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


TEACHER_SELECT = (
    "SELECT id, name, is_admin, department, subject, is_homeroom, grade, class_no, extension "
    "FROM User WHERE id = ?"
)


# ---------- 관리자: 교사 등록/수정/권한관리 (담당: yamako8119-ai) ----------
@app.post("/teachers", status_code=201)
def create_teacher(payload: TeacherCreate, _admin=Depends(require_admin)):
    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO User (name, password_hash, is_admin, department, subject, is_homeroom, grade, class_no, extension)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            payload.name,
            hash_password(DEFAULT_PASSWORD),
            int(payload.is_admin),
            payload.department,
            payload.subject,
            int(payload.is_homeroom),
            payload.grade,
            payload.class_no,
            payload.extension,
        ),
    )
    conn.commit()
    new_id = cur.lastrowid

    row = conn.execute(TEACHER_SELECT, (new_id,)).fetchone()
    conn.close()
    return dict(row)


@app.put("/teachers/{teacher_id}")
def update_teacher(teacher_id: int, payload: TeacherUpdate, _admin=Depends(require_admin)):
    fields = payload.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(status_code=400, detail="수정할 내용이 없습니다.")
    if "is_homeroom" in fields:
        fields["is_homeroom"] = int(fields["is_homeroom"])

    conn = get_connection()
    existing = conn.execute("SELECT id FROM User WHERE id = ?", (teacher_id,)).fetchone()
    if existing is None:
        conn.close()
        raise HTTPException(status_code=404, detail="교사를 찾을 수 없습니다.")

    # 컬럼명은 사용자 입력이 아니라 화이트리스트로 고정 (f-string은 값이 아닌 컬럼명 조합에만 사용)
    if not set(fields).issubset(ALLOWED_TEACHER_UPDATE_FIELDS):
        conn.close()
        raise HTTPException(status_code=400, detail="허용되지 않은 필드가 포함되어 있습니다.")

    set_clause = ", ".join(f"{k} = ?" for k in fields)
    conn.execute(f"UPDATE User SET {set_clause} WHERE id = ?", list(fields.values()) + [teacher_id])
    conn.commit()

    row = conn.execute(TEACHER_SELECT, (teacher_id,)).fetchone()
    conn.close()
    return dict(row)


@app.patch("/teachers/{teacher_id}/admin")
def update_teacher_admin_status(teacher_id: int, payload: AdminStatusUpdate, _admin=Depends(require_admin)):
    conn = get_connection()
    existing = conn.execute("SELECT id FROM User WHERE id = ?", (teacher_id,)).fetchone()
    if existing is None:
        conn.close()
        raise HTTPException(status_code=404, detail="교사를 찾을 수 없습니다.")

    conn.execute("UPDATE User SET is_admin = ? WHERE id = ?", (int(payload.is_admin), teacher_id))
    conn.commit()
    row = conn.execute(TEACHER_SELECT, (teacher_id,)).fetchone()
    conn.close()
    return dict(row)


@app.patch("/teachers/{teacher_id}/homeroom")
def update_teacher_homeroom_status(teacher_id: int, payload: HomeroomStatusUpdate, _admin=Depends(require_admin)):
    conn = get_connection()
    existing = conn.execute("SELECT id FROM User WHERE id = ?", (teacher_id,)).fetchone()
    if existing is None:
        conn.close()
        raise HTTPException(status_code=404, detail="교사를 찾을 수 없습니다.")

    conn.execute("UPDATE User SET is_homeroom = ? WHERE id = ?", (int(payload.is_homeroom), teacher_id))
    conn.commit()
    row = conn.execute(TEACHER_SELECT, (teacher_id,)).fetchone()
    conn.close()
    return dict(row)


@app.delete("/teachers/{teacher_id}", status_code=204)
def delete_teacher(teacher_id: int, _admin=Depends(require_admin)):
    conn = get_connection()
    existing = conn.execute(
        "SELECT id FROM User WHERE id = ? AND is_deleted = 0", (teacher_id,)
    ).fetchone()
    if existing is None:
        conn.close()
        raise HTTPException(status_code=404, detail="교사를 찾을 수 없습니다.")

    conn.execute("UPDATE User SET is_deleted = 1 WHERE id = ?", (teacher_id,))
    conn.commit()
    conn.close()
    return None


@app.get("/teachers/trash")
def get_deleted_teachers(_admin=Depends(require_admin)):
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, name, department, subject, extension "
        "FROM User WHERE is_deleted = 1 ORDER BY name"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.post("/teachers/{teacher_id}/restore")
def restore_teacher(teacher_id: int, _admin=Depends(require_admin)):
    conn = get_connection()
    existing = conn.execute(
        "SELECT id FROM User WHERE id = ? AND is_deleted = 1", (teacher_id,)
    ).fetchone()
    if existing is None:
        conn.close()
        raise HTTPException(status_code=404, detail="휴지통에서 해당 교사를 찾을 수 없습니다.")

    conn.execute("UPDATE User SET is_deleted = 0 WHERE id = ?", (teacher_id,))
    conn.commit()
    row = conn.execute(TEACHER_SELECT, (teacher_id,)).fetchone()
    conn.close()
    return dict(row)


# ---------- 관리자: 학사일정 (담당: yamako8119-ai) ----------
@app.get("/academic-schedule")
def get_academic_schedule():
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, title, category, start_date, end_date, created_by, created_at "
        "FROM AcademicSchedule ORDER BY start_date"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.post("/academic-schedule", status_code=201)
def create_academic_schedule(payload: ScheduleCreate, _admin=Depends(require_admin)):
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO AcademicSchedule (title, category, start_date, end_date, created_by) "
        "VALUES (?, ?, ?, ?, ?)",
        (payload.title, payload.category, payload.start_date, payload.end_date, payload.created_by),
    )
    conn.commit()
    new_id = cur.lastrowid
    row = conn.execute(
        "SELECT id, title, category, start_date, end_date, created_by, created_at "
        "FROM AcademicSchedule WHERE id = ?",
        (new_id,),
    ).fetchone()
    conn.close()
    return dict(row)


@app.delete("/academic-schedule/{schedule_id}", status_code=204)
def delete_academic_schedule(schedule_id: int, _admin=Depends(require_admin)):
    conn = get_connection()
    existing = conn.execute("SELECT id FROM AcademicSchedule WHERE id = ?", (schedule_id,)).fetchone()
    if existing is None:
        conn.close()
        raise HTTPException(status_code=404, detail="학사일정을 찾을 수 없습니다.")

    conn.execute("DELETE FROM AcademicSchedule WHERE id = ?", (schedule_id,))
    conn.commit()
    conn.close()
    return None


# ---------- 관리자: 그룹 관리 (담당: yamako8119-ai) ----------
@app.get("/groups")
def get_groups(official: Optional[bool] = None):
    conn = get_connection()
    query = (
        "SELECT g.id, g.name, g.description, g.created_by, g.is_official, g.created_at, "
        "(SELECT COUNT(*) FROM Group_Member gm WHERE gm.group_id = g.id) AS member_count, "
        "(SELECT GROUP_CONCAT(name, ', ') FROM ("
        "   SELECT u.name FROM Group_Member gm2 JOIN User u ON u.id = gm2.user_id "
        "   WHERE gm2.group_id = g.id ORDER BY u.name"
        " )) AS members "
        "FROM Groups g"
    )
    params: list = []
    if official is not None:
        query += " WHERE g.is_official = ?"
        params.append(int(official))
    query += " ORDER BY g.created_at DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.post("/groups", status_code=201)
def create_group(payload: GroupCreate):
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO Groups (name, description, created_by, is_official) VALUES (?, ?, ?, 1)",
        (payload.name, payload.description, payload.created_by),
    )
    group_id = cur.lastrowid
    conn.execute(
        "INSERT INTO Group_Member (group_id, user_id, role) VALUES (?, ?, 'owner')",
        (group_id, payload.created_by),
    )
    conn.commit()
    row = conn.execute(
        "SELECT id, name, description, created_by, is_official, created_at FROM Groups WHERE id = ?",
        (group_id,),
    ).fetchone()
    conn.close()
    result = dict(row)
    result["member_count"] = 1
    return result


@app.put("/groups/{group_id}")
def update_group(group_id: int, payload: GroupUpdate, _admin=Depends(require_admin)):
    conn = get_connection()
    existing = conn.execute("SELECT id FROM Groups WHERE id = ?", (group_id,)).fetchone()
    if existing is None:
        conn.close()
        raise HTTPException(status_code=404, detail="그룹을 찾을 수 없습니다.")

    conn.execute("UPDATE Groups SET name = ? WHERE id = ?", (payload.name, group_id))
    conn.commit()
    row = conn.execute(
        "SELECT id, name, description, created_by, is_official, created_at FROM Groups WHERE id = ?",
        (group_id,),
    ).fetchone()
    conn.close()
    return dict(row)


@app.delete("/groups/{group_id}", status_code=204)
def delete_group(group_id: int, _admin=Depends(require_admin)):
    conn = get_connection()
    existing = conn.execute("SELECT id FROM Groups WHERE id = ?", (group_id,)).fetchone()
    if existing is None:
        conn.close()
        raise HTTPException(status_code=404, detail="그룹을 찾을 수 없습니다.")

    conn.execute("DELETE FROM Group_Member WHERE group_id = ?", (group_id,))
    conn.execute("DELETE FROM Groups WHERE id = ?", (group_id,))
    conn.commit()
    conn.close()
    return None


@app.get("/groups/{group_id}/members")
def get_group_members(group_id: int):
    conn = get_connection()
    rows = conn.execute(
        """SELECT gm.id, gm.user_id, u.name, gm.role, gm.joined_at
           FROM Group_Member gm JOIN User u ON u.id = gm.user_id
           WHERE gm.group_id = ? ORDER BY gm.role, u.name""",
        (group_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.post("/groups/{group_id}/members", status_code=201)
def add_group_member(group_id: int, payload: GroupMemberAdd):
    conn = get_connection()
    group = conn.execute("SELECT id FROM Groups WHERE id = ?", (group_id,)).fetchone()
    if group is None:
        conn.close()
        raise HTTPException(status_code=404, detail="그룹을 찾을 수 없습니다.")

    existing_member = conn.execute(
        "SELECT id FROM Group_Member WHERE group_id = ? AND user_id = ?", (group_id, payload.user_id)
    ).fetchone()
    if existing_member:
        conn.close()
        raise HTTPException(status_code=409, detail="이미 그룹에 속한 교사입니다.")

    conn.execute(
        "INSERT INTO Group_Member (group_id, user_id, role) VALUES (?, ?, 'member')",
        (group_id, payload.user_id),
    )
    conn.commit()
    conn.close()
    return {"ok": True}


@app.delete("/groups/{group_id}/members/{user_id}", status_code=204)
def remove_group_member(group_id: int, user_id: int, _admin=Depends(require_admin)):
    conn = get_connection()
    conn.execute("DELETE FROM Group_Member WHERE group_id = ? AND user_id = ?", (group_id, user_id))
    conn.commit()
    conn.close()
    return None


# ---------- 공지 (담당: hbn2814) ----------
NOTICE_SELECT = (
    "SELECT id, title, content, deadline, target_group, is_pinned, created_at "
    "FROM Announcement WHERE id = ?"
)


def _resolve_recipient_ids(conn, user_ids, group_ids):
    ids = set(user_ids)
    if group_ids:
        placeholders = ",".join("?" * len(group_ids))
        rows = conn.execute(
            f"SELECT user_id FROM Group_Member WHERE group_id IN ({placeholders})",
            list(group_ids),
        ).fetchall()
        ids |= {r["user_id"] for r in rows}
    return ids


@app.post("/notices", status_code=201)
def create_notice(payload: NoticeCreate):
    conn = get_connection()
    author = conn.execute("SELECT id FROM User WHERE id = ?", (payload.author_id,)).fetchone()
    if author is None:
        conn.close()
        raise HTTPException(status_code=400, detail="존재하지 않는 작성자입니다.")

    cur = conn.execute(
        "INSERT INTO Announcement (title, content, author_id, target_group, deadline) "
        "VALUES (?, ?, ?, ?, ?)",
        (payload.title, payload.content, payload.author_id, payload.target_group, payload.deadline),
    )
    new_id = cur.lastrowid

    recipient_ids = _resolve_recipient_ids(conn, payload.recipient_user_ids, payload.recipient_group_ids)
    for user_id in recipient_ids:
        conn.execute(
            "INSERT OR IGNORE INTO Announcement_Recipient (announcement_id, user_id) VALUES (?, ?)",
            (new_id, user_id),
        )
    conn.commit()

    row = conn.execute(NOTICE_SELECT, (new_id,)).fetchone()
    recipients = []
    if recipient_ids:
        placeholders = ",".join("?" * len(recipient_ids))
        recipients = [
            dict(r)
            for r in conn.execute(
                f"SELECT id, name FROM User WHERE id IN ({placeholders})",
                sorted(recipient_ids),
            ).fetchall()
        ]
    conn.close()
    return {**dict(row), "recipients": recipients}


@app.get("/notices")
def get_notices():
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, title, content, deadline, target_group, is_pinned, created_at "
        "FROM Announcement WHERE is_deleted = 0 ORDER BY is_pinned DESC, created_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# 로그인한 사용자 기준으로 "전체 공개" + "본인이 대상자인" 공지만 반환 (작성자라고 자동으로 보이지 않음).
# 큐브 위젯의 알림/목록 탭에서 사용 (관리자 페이지의 GET /notices 전체 조회와는 별개).
@app.get("/notices/mine")
def get_my_notices(viewer_id: int):
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT DISTINCT a.id, a.title, a.content, a.deadline, a.target_group,
               a.is_pinned, a.author_id, au.name AS author_name, a.created_at,
               CASE WHEN c.id IS NULL THEN 0 ELSE 1 END AS completed,
               c.completed_at
        FROM Announcement a
        JOIN User au ON au.id = a.author_id
        LEFT JOIN Announcement_Recipient r ON r.announcement_id = a.id
        LEFT JOIN Announcement_Completion c
               ON c.announcement_id = a.id AND c.user_id = :viewer_id
        WHERE a.is_deleted = 0
          AND (
                r.id IS NULL
                OR a.id IN (
                    SELECT announcement_id FROM Announcement_Recipient WHERE user_id = :viewer_id
                )
              )
        ORDER BY a.is_pinned DESC, a.created_at DESC
        """,
        {"viewer_id": viewer_id},
    ).fetchall()

    ids = [r["id"] for r in rows]
    recipients_by_notice = {}
    if ids:
        placeholders = ",".join("?" * len(ids))
        rec_rows = conn.execute(
            f"""
            SELECT r.announcement_id, u.id AS user_id, u.name
            FROM Announcement_Recipient r JOIN User u ON u.id = r.user_id
            WHERE r.announcement_id IN ({placeholders})
            """,
            ids,
        ).fetchall()
        for r in rec_rows:
            recipients_by_notice.setdefault(r["announcement_id"], []).append(
                {"id": r["user_id"], "name": r["name"]}
            )
    conn.close()

    return [
        {**dict(r), "recipients": recipients_by_notice.get(r["id"], [])}
        for r in rows
    ]


class CompleteNotice(BaseModel):
    user_id: int


# 로그인한 사용자 본인 기준으로 해당 공지 업무를 완료 처리 (담당: hbn2814)
@app.post("/notices/{notice_id}/complete")
def complete_notice(notice_id: int, payload: CompleteNotice):
    conn = get_connection()
    existing = conn.execute("SELECT id FROM Announcement WHERE id = ?", (notice_id,)).fetchone()
    if existing is None:
        conn.close()
        raise HTTPException(status_code=404, detail="공지사항을 찾을 수 없습니다.")

    conn.execute(
        "INSERT OR IGNORE INTO Announcement_Completion (announcement_id, user_id) VALUES (?, ?)",
        (notice_id, payload.user_id),
    )
    conn.commit()
    row = conn.execute(
        "SELECT completed_at FROM Announcement_Completion WHERE announcement_id = ? AND user_id = ?",
        (notice_id, payload.user_id),
    ).fetchone()
    conn.close()
    return {"announcement_id": notice_id, "user_id": payload.user_id, "completed": True, "completed_at": row["completed_at"]}


# ---------- 관리자: 공지사항 관리 (담당: yamako8119-ai) ----------
@app.patch("/notices/{notice_id}/pin")
def update_notice_pin(notice_id: int, payload: PinUpdate, _admin=Depends(require_admin)):
    conn = get_connection()
    existing = conn.execute("SELECT id FROM Announcement WHERE id = ?", (notice_id,)).fetchone()
    if existing is None:
        conn.close()
        raise HTTPException(status_code=404, detail="공지사항을 찾을 수 없습니다.")

    conn.execute(
        "UPDATE Announcement SET is_pinned = ? WHERE id = ?",
        (int(payload.is_pinned), notice_id),
    )
    conn.commit()
    row = conn.execute(
        "SELECT id, title, content, deadline, target_group, is_pinned, created_at "
        "FROM Announcement WHERE id = ?",
        (notice_id,),
    ).fetchone()
    conn.close()
    return dict(row)


@app.delete("/notices/{notice_id}", status_code=204)
def delete_notice(notice_id: int, _admin=Depends(require_admin)):
    conn = get_connection()
    existing = conn.execute("SELECT id FROM Announcement WHERE id = ?", (notice_id,)).fetchone()
    if existing is None:
        conn.close()
        raise HTTPException(status_code=404, detail="공지사항을 찾을 수 없습니다.")

    conn.execute("UPDATE Announcement SET is_deleted = 1 WHERE id = ?", (notice_id,))
    conn.commit()
    conn.close()
    return None


# ---------- 개인 일정 (담당: ada3verse) ----------
@app.get("/personal-events")
def get_personal_events(teacher_name: str, requester=Depends(get_requester)):
    # 본인 일정만 조회 가능 (IDOR 방지) - 관리자도 예외 없음
    if requester["name"] != teacher_name:
        raise HTTPException(status_code=403, detail="본인의 개인 일정만 조회할 수 있습니다.")

    conn = get_connection()
    rows = conn.execute(
        "SELECT id, teacher_name, title, date, memo, created_at "
        "FROM PersonalEvent WHERE teacher_name = ? ORDER BY date",
        (teacher_name,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.post("/personal-events", status_code=201)
def create_personal_event(payload: PersonalEventCreate, requester=Depends(get_requester)):
    # 본인 이름으로만 개인 일정을 생성할 수 있음
    if requester["name"] != payload.teacher_name:
        raise HTTPException(status_code=403, detail="본인 이름으로만 개인 일정을 등록할 수 있습니다.")

    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO PersonalEvent (teacher_name, title, date, memo) VALUES (?, ?, ?, ?)",
        (payload.teacher_name, payload.title, payload.date, payload.memo),
    )
    conn.commit()
    new_id = cur.lastrowid
    row = conn.execute(
        "SELECT id, teacher_name, title, date, memo, created_at FROM PersonalEvent WHERE id = ?",
        (new_id,),
    ).fetchone()
    conn.close()
    return dict(row)


@app.delete("/personal-events/{event_id}", status_code=204)
def delete_personal_event(event_id: int, requester=Depends(get_requester)):
    conn = get_connection()
    existing = conn.execute(
        "SELECT id, teacher_name FROM PersonalEvent WHERE id = ?", (event_id,)
    ).fetchone()
    if existing is None:
        conn.close()
        raise HTTPException(status_code=404, detail="개인 일정을 찾을 수 없습니다.")

    # 본인 소유 일정인지 서버에서 확인 (IDOR 방지) - 다른 교사의 일정은 삭제 불가
    if existing["teacher_name"] != requester["name"]:
        conn.close()
        raise HTTPException(status_code=403, detail="본인의 개인 일정만 삭제할 수 있습니다.")

    conn.execute("DELETE FROM PersonalEvent WHERE id = ?", (event_id,))
    conn.commit()
    conn.close()
    return None


# ---------- 제출현황 ----------
@app.get("/submissions")
def get_submissions():
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT c.id, c.event_id, e.title AS event_title, e.start_at AS event_deadline,
               c.user_id, u.name AS user_name, c.is_completed, c.completed_at
        FROM Completion c
        JOIN Event e ON e.id = c.event_id
        JOIN User u ON u.id = c.user_id
        ORDER BY c.event_id, u.name
        """
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


class SubmissionStatusUpdate(BaseModel):
    is_completed: bool


# 제출현황 표에서 교사를 클릭해 제출/미제출을 직접 토글 (담당: hbn2814)
@app.patch("/submissions/{completion_id}")
def update_submission_status(completion_id: int, payload: SubmissionStatusUpdate):
    conn = get_connection()
    existing = conn.execute("SELECT id FROM Completion WHERE id = ?", (completion_id,)).fetchone()
    if existing is None:
        conn.close()
        raise HTTPException(status_code=404, detail="제출 현황을 찾을 수 없습니다.")

    if payload.is_completed:
        conn.execute(
            "UPDATE Completion SET is_completed = 1, completed_at = datetime('now'), "
            "updated_at = datetime('now') WHERE id = ?",
            (completion_id,),
        )
    else:
        conn.execute(
            "UPDATE Completion SET is_completed = 0, completed_at = NULL, "
            "updated_at = datetime('now') WHERE id = ?",
            (completion_id,),
        )
    conn.commit()
    row = conn.execute(
        "SELECT id, event_id, user_id, is_completed, completed_at FROM Completion WHERE id = ?",
        (completion_id,),
    ).fetchone()
    conn.close()
    return dict(row)


class SubmissionRemind(BaseModel):
    event_id: int
    author_id: int


# 미제출 교사 전원에게 안내 공지를 일괄 생성해서 보낸다 (담당: hbn2814)
@app.post("/submissions/remind", status_code=201)
def remind_incomplete_submissions(payload: SubmissionRemind):
    conn = get_connection()
    event = conn.execute(
        "SELECT id, title, start_at FROM Event WHERE id = ?", (payload.event_id,)
    ).fetchone()
    if event is None:
        conn.close()
        raise HTTPException(status_code=404, detail="일정을 찾을 수 없습니다.")

    incomplete = conn.execute(
        "SELECT user_id FROM Completion WHERE event_id = ? AND is_completed = 0",
        (payload.event_id,),
    ).fetchall()
    user_ids = [r["user_id"] for r in incomplete]
    if not user_ids:
        conn.close()
        raise HTTPException(status_code=400, detail="미제출자가 없습니다.")

    deadline = (event["start_at"] or "").split("T")[0].split(" ")[0] or None
    title = f"[재안내] {event['title']}"
    content = (
        f"'{event['title']}' 아직 제출하지 않으셨습니다."
        + (f" 제출 기한은 {deadline}입니다." if deadline else "")
        + " 확인 후 제출 부탁드립니다."
    )

    cur = conn.execute(
        "INSERT INTO Announcement (title, content, author_id, deadline) VALUES (?, ?, ?, ?)",
        (title, content, payload.author_id, deadline),
    )
    new_id = cur.lastrowid
    for user_id in user_ids:
        conn.execute(
            "INSERT OR IGNORE INTO Announcement_Recipient (announcement_id, user_id) VALUES (?, ?)",
            (new_id, user_id),
        )
    conn.commit()
    conn.close()
    return {"announcement_id": new_id, "recipient_count": len(user_ids)}
