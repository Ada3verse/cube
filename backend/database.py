import sqlite3
from pathlib import Path

import bcrypt

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "database.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        # 옛 형식(sha256 등) 해시가 남아있는 경우 등 - 비교 불가는 곧 인증 실패로 처리
        return False


def get_user_by_name(conn, name: str):
    # 로그인 전용 조회. name은 UNIQUE가 아니므로(중복 허용) 동명이인이 있으면
    # 여러 행 중 하나만 반환될 수 있음 - 요청자 신원 확인에는 get_user_by_id를 사용할 것.
    return conn.execute(
        "SELECT id, name, is_admin, department, subject, password_hash "
        "FROM User WHERE name = ? AND is_deleted = 0",
        (name,),
    ).fetchone()


def get_user_by_id(conn, user_id: int):
    return conn.execute(
        "SELECT id, name, is_admin, department, subject "
        "FROM User WHERE id = ? AND is_deleted = 0",
        (user_id,),
    ).fetchone()
