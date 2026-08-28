import hashlib
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Literal, Optional

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


class GroupCreate(BaseModel):
    name: str
    description: Optional[str] = None
    created_by: int


class GroupMemberAdd(BaseModel):
    user_id: int


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
    conn.execute(f"UPDATE User SET {set_clause} WHERE id = ?", list(fields.values()) + [teacher_id])
    conn.commit()

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


@app.patch("/teachers/{teacher_id}/homeroom")
def update_teacher_homeroom_status(teacher_id: int, payload: HomeroomStatusUpdate):
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


@app.delete("/academic-schedule/{schedule_id}", status_code=204)
def delete_academic_schedule(schedule_id: int):
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
        "(SELECT COUNT(*) FROM Group_Member gm WHERE gm.group_id = g.id) AS member_count "
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


@app.delete("/groups/{group_id}", status_code=204)
def delete_group(group_id: int):
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
def remove_group_member(group_id: int, user_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM Group_Member WHERE group_id = ? AND user_id = ?", (group_id, user_id))
    conn.commit()
    conn.close()
    return None


# ---------- 공지 ----------
@app.get("/notices")
def get_notices():
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, title, content, deadline, target_group, is_pinned, created_at "
        "FROM Announcement WHERE is_deleted = 0 ORDER BY is_pinned DESC, created_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


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
