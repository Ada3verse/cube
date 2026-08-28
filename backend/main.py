import hashlib
import sqlite3
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

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


# ---------- 공지 ----------
@app.get("/notices")
def get_notices():
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, title, content, deadline, target_group, is_pinned, created_at "
        "FROM Announcement WHERE is_deleted = 0 ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


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
