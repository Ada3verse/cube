import hashlib
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Literal, Optional

import psutil
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "database.db"

app = FastAPI(title="CUBE API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def hash_password(password: str) -> str:
    # 프로토타입용 해시. 운영 전환 시 bcrypt 등으로 교체 필요.
    return hashlib.sha256(password.encode()).hexdigest()


class LoginRequest(BaseModel):
    name: str
    password: str


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


class AdminStatusUpdate(BaseModel):
    is_admin: bool


SCHEDULE_CATEGORIES = ["학기", "방학", "시험기간", "공휴일", "재량휴업일", "기타"]


class ScheduleCreate(BaseModel):
    title: str
    category: Literal["학기", "방학", "시험기간", "공휴일", "재량휴업일", "기타"]
    start_date: str
    end_date: Optional[str] = None
    created_by: int


class PinUpdate(BaseModel):
    is_pinned: bool


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
    member_ids: List[int] = []


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
        "server_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


# ---------- 로그인 ----------
# 아이디: 교사 이름(User.name, UNIQUE). 초기 비밀번호: 123456 (seed.py와 동일한 해시 방식)
@app.post("/login")
def login(payload: LoginRequest):
    conn = get_connection()
    row = conn.execute(
        "SELECT id, name, is_admin, department, subject, password_hash "
        "FROM User WHERE name = ? AND is_deleted = 0",
        (payload.name,),
    ).fetchone()
    conn.close()

    if row is None or row["password_hash"] != hash_password(payload.password):
        raise HTTPException(status_code=401, detail="이름 또는 비밀번호가 올바르지 않습니다.")

    return {
        "id": row["id"],
        "name": row["name"],
        "is_admin": bool(row["is_admin"]),
        "department": row["department"],
        "subject": row["subject"],
    }


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
def create_teacher(payload: TeacherCreate):
    conn = get_connection()
    try:
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
    except sqlite3.IntegrityError as e:
        conn.close()
        raise HTTPException(status_code=409, detail=f"저장 실패 (이름/내선번호/학년-반 중복 가능성): {e}")

    row = conn.execute(TEACHER_SELECT, (new_id,)).fetchone()
    conn.close()
    return dict(row)


@app.put("/teachers/{teacher_id}")
def update_teacher(teacher_id: int, payload: TeacherUpdate):
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

    set_clause = ", ".join(f"{k} = ?" for k in fields)
    try:
        conn.execute(f"UPDATE User SET {set_clause} WHERE id = ?", list(fields.values()) + [teacher_id])
        conn.commit()
    except sqlite3.IntegrityError as e:
        conn.close()
        raise HTTPException(status_code=409, detail=f"수정 실패 (이름/내선번호/학년-반 중복 가능성): {e}")

    row = conn.execute(TEACHER_SELECT, (teacher_id,)).fetchone()
    conn.close()
    return dict(row)


@app.patch("/teachers/{teacher_id}/admin")
def update_teacher_admin_status(teacher_id: int, payload: AdminStatusUpdate):
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


@app.delete("/teachers/{teacher_id}", status_code=204)
def delete_teacher(teacher_id: int):
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
def get_deleted_teachers():
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, name, department, subject, extension "
        "FROM User WHERE is_deleted = 1 ORDER BY name"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.post("/teachers/{teacher_id}/restore")
def restore_teacher(teacher_id: int):
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
def create_academic_schedule(payload: ScheduleCreate):
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


# ---------- 그룹 (담당: hbn2814) ----------
@app.get("/groups")
def get_groups():
    conn = get_connection()
    groups = conn.execute(
        "SELECT id, name, description, created_by, is_official, created_at "
        "FROM Groups ORDER BY is_official DESC, name"
    ).fetchall()
    members = conn.execute(
        "SELECT gm.group_id, u.id, u.name "
        "FROM Group_Member gm JOIN User u ON u.id = gm.user_id "
        "WHERE u.is_deleted = 0"
    ).fetchall()
    conn.close()

    members_by_group = {}
    for m in members:
        members_by_group.setdefault(m["group_id"], []).append({"id": m["id"], "name": m["name"]})

    return [
        {**dict(g), "members": members_by_group.get(g["id"], [])}
        for g in groups
    ]


@app.post("/groups", status_code=201)
def create_group(payload: GroupCreate):
    conn = get_connection()
    creator = conn.execute("SELECT id FROM User WHERE id = ?", (payload.created_by,)).fetchone()
    if creator is None:
        conn.close()
        raise HTTPException(status_code=400, detail="존재하지 않는 생성자입니다.")

    cur = conn.execute(
        "INSERT INTO Groups (name, description, created_by, is_official) VALUES (?, ?, ?, 0)",
        (payload.name, payload.description, payload.created_by),
    )
    new_id = cur.lastrowid

    member_ids = set(payload.member_ids) | {payload.created_by}
    for user_id in member_ids:
        role = "owner" if user_id == payload.created_by else "member"
        conn.execute(
            "INSERT OR IGNORE INTO Group_Member (group_id, user_id, role) VALUES (?, ?, ?)",
            (new_id, user_id, role),
        )
    conn.commit()

    row = conn.execute(
        "SELECT id, name, description, created_by, is_official, created_at FROM Groups WHERE id = ?",
        (new_id,),
    ).fetchone()
    member_rows = conn.execute(
        "SELECT u.id, u.name FROM Group_Member gm JOIN User u ON u.id = gm.user_id WHERE gm.group_id = ?",
        (new_id,),
    ).fetchall()
    conn.close()
    return {**dict(row), "members": [dict(m) for m in member_rows]}


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
def update_notice_pin(notice_id: int, payload: PinUpdate):
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
def delete_notice(notice_id: int):
    conn = get_connection()
    existing = conn.execute("SELECT id FROM Announcement WHERE id = ?", (notice_id,)).fetchone()
    if existing is None:
        conn.close()
        raise HTTPException(status_code=404, detail="공지사항을 찾을 수 없습니다.")

    conn.execute("UPDATE Announcement SET is_deleted = 1 WHERE id = ?", (notice_id,))
    conn.commit()
    conn.close()
    return None


# ---------- 제출현황 ----------
@app.get("/submissions")
def get_submissions():
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT c.id, c.event_id, e.title AS event_title, c.user_id, u.name AS user_name,
               c.is_completed, c.completed_at
        FROM Completion c
        JOIN Event e ON e.id = c.event_id
        JOIN User u ON u.id = c.user_id
        ORDER BY c.event_id, u.name
        """
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
