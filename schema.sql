-- User: 구성원 (교사 전용, 학생 없음)
CREATE TABLE User (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL CHECK (role IN ('teacher', 'admin')) DEFAULT 'teacher',
    department    TEXT NOT NULL CHECK (department IN ('교무부', '연구부', '과학정보부', '창의체험부', '생활안전부')),
    subject       TEXT,                          -- 담당 과목 (국어/영어/수학/과학/정보/사회 등), 없으면 NULL
    is_homeroom   INTEGER NOT NULL DEFAULT 0,     -- 담임 여부
    grade         INTEGER CHECK (grade IS NULL OR grade BETWEEN 1 AND 3),  -- 담임 학년, 담임 아니면 NULL
    class_no      INTEGER,                        -- 담임 반, 담임 아니면 NULL
    extension     TEXT NOT NULL UNIQUE,            -- 내선번호
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (grade, class_no)                       -- 한 반에 담임은 한 명 (NULL끼리는 중복 허용됨)
);

-- Event: 일정 (회의/행사/제출마감)
CREATE TABLE Event (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    title         TEXT NOT NULL,
    description   TEXT,
    type          TEXT NOT NULL CHECK (type IN ('meeting', 'activity', 'deadline')),
    start_at      TEXT NOT NULL,                 -- ISO 8601
    end_at        TEXT,
    location      TEXT,
    target_group  TEXT,                          -- NULL = 전체 공개
    author_id     INTEGER NOT NULL REFERENCES User(id),
    is_cancelled  INTEGER NOT NULL DEFAULT 0,     -- soft delete
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Notification: 일정이 누구에게 전송됐는지 + 읽음 여부
CREATE TABLE Notification (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id   INTEGER NOT NULL REFERENCES Event(id),
    user_id    INTEGER NOT NULL REFERENCES User(id),
    sent_at    TEXT NOT NULL DEFAULT (datetime('now')),
    read_at    TEXT,                             -- NULL = 안 읽음
    UNIQUE (event_id, user_id)
);

-- Completion: 사용자별 완료(제출/참석) 확인, 취소(복원) 가능
CREATE TABLE Completion (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id      INTEGER NOT NULL REFERENCES Event(id),
    user_id       INTEGER NOT NULL REFERENCES User(id),
    is_completed  INTEGER NOT NULL DEFAULT 0,
    completed_at  TEXT,
    updated_at    TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (event_id, user_id)
);

-- Announcement: 공지사항
CREATE TABLE Announcement (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    title         TEXT NOT NULL,
    content       TEXT NOT NULL,
    author_id     INTEGER NOT NULL REFERENCES User(id),
    target_group  TEXT,
    deadline      TEXT,                          -- 마감일 (D-day 표시용), 없으면 NULL
    is_pinned     INTEGER NOT NULL DEFAULT 0,
    is_deleted    INTEGER NOT NULL DEFAULT 0,     -- soft delete
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Groups: 자유 그룹 (개인 또는 관리자가 생성)
CREATE TABLE Groups (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    description TEXT,
    created_by  INTEGER NOT NULL REFERENCES User(id),
    is_official INTEGER NOT NULL DEFAULT 0,      -- 0=개인 그룹, 1=관리자 공식 그룹
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Group_Member: 그룹 소속 (다대다)
CREATE TABLE Group_Member (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id  INTEGER NOT NULL REFERENCES Groups(id),
    user_id   INTEGER NOT NULL REFERENCES User(id),
    role      TEXT NOT NULL CHECK (role IN ('owner', 'member')) DEFAULT 'member',
    joined_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (group_id, user_id)
);

-- 자주 조회하는 컬럼 인덱스
CREATE INDEX idx_event_start        ON Event(start_at);
CREATE INDEX idx_notification_user  ON Notification(user_id);
CREATE INDEX idx_completion_user    ON Completion(user_id);
CREATE INDEX idx_announcement_date  ON Announcement(created_at);
CREATE INDEX idx_group_member_user  ON Group_Member(user_id);
