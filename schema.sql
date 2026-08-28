-- User: 구성원
CREATE TABLE User (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL CHECK (role IN ('student', 'teacher', 'admin')) DEFAULT 'student',
    group_name    TEXT,                          -- 소속 (학년/반/부서), 없으면 NULL
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
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

-- 자주 조회하는 컬럼 인덱스
CREATE INDEX idx_event_start        ON Event(start_at);
CREATE INDEX idx_notification_user  ON Notification(user_id);
CREATE INDEX idx_completion_user    ON Completion(user_id);
CREATE INDEX idx_announcement_date  ON Announcement(created_at);
