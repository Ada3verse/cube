import hashlib
import sqlite3
from pathlib import Path
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

DB_PATH = Path(__file__).resolve().parent.parent / "database.db"

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


DEPARTMENTS = ["교무부", "연구부", "과학정보부", "창의체험부", "생활안전부"]
DEFAULT_PASSWORD = "123456"


class TeacherCreate(BaseModel):
    name: str
    role: Literal["teacher", "admin"] = "teacher"
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


class RoleUpdate(BaseModel):
    role: Literal["teacher", "admin"]


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


@app.get("/")
def read_root():
    return {"message": "CUBE API 서버가 실행 중입니다."}


# ---------- 로그인 ----------
# 아이디: 교사 이름(User.name, UNIQUE). 초기 비밀번호: 123456 (seed.py와 동일한 해시 방식)
@app.post("/login")
def login(payload: LoginRequest):
    conn = get_connection()
    row = conn.execute(
        "SELECT id, name, role, department, subject, password_hash "
        "FROM User WHERE name = ?",
        (payload.name,),
    ).fetchone()
    conn.close()

    if row is None or row["password_hash"] != hash_password(payload.password):
        raise HTTPException(status_code=401, detail="이름 또는 비밀번호가 올바르지 않습니다.")

    return {
        "id": row["id"],
        "name": row["name"],
        "role": row["role"],
        "department": row["department"],
        "subject": row["subject"],
    }


# ---------- 교사 ----------
@app.get("/teachers")
def get_teachers():
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, name, role, department, subject, is_homeroom, grade, class_no, extension "
        "FROM User ORDER BY name"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


TEACHER_SELECT = (
    "SELECT id, name, role, department, subject, is_homeroom, grade, class_no, extension "
    "FROM User WHERE id = ?"
)


# ---------- 관리자: 교사 등록/수정/권한관리 (담당: yamako8119-ai) ----------
@app.post("/teachers", status_code=201)
def create_teacher(payload: TeacherCreate):
    if payload.department not in DEPARTMENTS:
        raise HTTPException(status_code=400, detail=f"department는 {DEPARTMENTS} 중 하나여야 합니다.")

    conn = get_connection()
    try:
        cur = conn.execute(
            """INSERT INTO User (name, password_hash, role, department, subject, is_homeroom, grade, class_no, extension)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                payload.name,
                hash_password(DEFAULT_PASSWORD),
                payload.role,
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
    if payload.department is not None and payload.department not in DEPARTMENTS:
        raise HTTPException(status_code=400, detail=f"department는 {DEPARTMENTS} 중 하나여야 합니다.")

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


@app.patch("/teachers/{teacher_id}/role")
def update_teacher_role(teacher_id: int, payload: RoleUpdate):
    conn = get_connection()
    existing = conn.execute("SELECT id FROM User WHERE id = ?", (teacher_id,)).fetchone()
    if existing is None:
        conn.close()
        raise HTTPException(status_code=404, detail="교사를 찾을 수 없습니다.")

    conn.execute("UPDATE User SET role = ? WHERE id = ?", (payload.role, teacher_id))
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


# ---------- 공지 (담당: hbn2814) ----------
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
    conn.commit()
    new_id = cur.lastrowid
    row = conn.execute(
        "SELECT id, title, content, deadline, target_group, is_pinned, created_at "
        "FROM Announcement WHERE id = ?",
        (new_id,),
    ).fetchone()
    conn.close()
    return dict(row)


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
