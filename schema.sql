-- User: 구성원 (교사 전용, 학생 없음)
CREATE TABLE User (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL UNIQUE,          -- 로그인 아이디로 사용
    password_hash TEXT NOT NULL,                  -- 초기 비밀번호: 123456 (해시 저장)
    is_admin      INTEGER NOT NULL DEFAULT 0,    -- 관리자 여부 (0=일반 교사, 1=관리자)
    department    TEXT NOT NULL CHECK (department IN ('교무부', '연구부', '과학정보부', '창의체험부', '생활안전부')),
    subject       TEXT,                          -- 담당 과목 (국어/영어/수학/과학/정보/사회 등), 없으면 NULL
    is_homeroom   INTEGER NOT NULL DEFAULT 0,     -- 담임 여부
    grade         INTEGER CHECK (grade IS NULL OR grade BETWEEN 1 AND 3),  -- 담임 학년, 담임 아니면 NULL
    class_no      INTEGER,                        -- 담임 반, 담임 아니면 NULL
    extension     TEXT NOT NULL UNIQUE,            -- 내선번호
    is_deleted    INTEGER NOT NULL DEFAULT 0,      -- 삭제(휴지통) 여부, soft delete
    metadata      TEXT,                            -- 여분 확장 필드 (JSON 문자열), 필요할 때만 사용
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (grade, class_no)                       -- 한 반에 담임은 한 명 (NULL끼리는 중복 허용됨)
);

-- Event: 일정 (회의/행사/제출마감/개인일정)
CREATE TABLE Event (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    title         TEXT NOT NULL,
    description   TEXT,
    type          TEXT NOT NULL CHECK (type IN ('meeting', 'activity', 'deadline', 'personal')),
    start_at      TEXT NOT NULL,                 -- ISO 8601
    end_at        TEXT,
    location      TEXT,
    target_group  TEXT,                          -- NULL = 전체 공개 (personal 타입은 항상 NULL, 본인만 조회)
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

-- Memo: 개인 캘린더 메모 (본인만 조회/작성, 공유되지 않음)
CREATE TABLE Memo (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES User(id),
    date       TEXT NOT NULL,                  -- 메모가 표시될 날짜 (YYYY-MM-DD)
    content    TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- AcademicSchedule: 학사일정 (학교 전체 기준 캘린더, 방학/시험기간/공휴일 등)
CREATE TABLE AcademicSchedule (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,                      -- 예: "여름방학", "1학기 기말고사"
    category    TEXT NOT NULL CHECK (category IN ('학기', '방학', '시험기간', '공휴일', '재량휴업일', '기타')),
    start_date  TEXT NOT NULL,                       -- YYYY-MM-DD
    end_date    TEXT,                                -- 기간이면 종료일, 하루짜리면 NULL
    created_by  INTEGER NOT NULL REFERENCES User(id),
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Message: 쪽지 본문 (보낸 사람 기준 1건, 여러 명에게 동시 발송 가능)
CREATE TABLE Message (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    sender_id            INTEGER NOT NULL REFERENCES User(id),
    content              TEXT NOT NULL,
    sent_at              TEXT NOT NULL DEFAULT (datetime('now')),
    is_deleted_by_sender INTEGER NOT NULL DEFAULT 0   -- 보낸사람이 보낸쪽지함에서 삭제
);

-- Message_Recipient: 쪽지 수신자 매핑 (다대다, 읽음/삭제는 수신자별로 독립)
CREATE TABLE Message_Recipient (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id  INTEGER NOT NULL REFERENCES Message(id),
    user_id     INTEGER NOT NULL REFERENCES User(id),
    read_at     TEXT,                              -- NULL = 안 읽음
    is_deleted  INTEGER NOT NULL DEFAULT 0,         -- 받은사람이 받은쪽지함에서만 삭제
    UNIQUE (message_id, user_id)
);

-- Attachment: 첨부파일 (쪽지/공지사항/일정 등에서 공용으로 사용)
CREATE TABLE Attachment (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    file_name   TEXT NOT NULL,
    file_path   TEXT NOT NULL,                      -- 서버 디스크에 저장된 실제 경로
    file_size   INTEGER,                             -- bytes
    uploaded_by INTEGER NOT NULL REFERENCES User(id),
    target_type TEXT NOT NULL CHECK (target_type IN ('message', 'announcement', 'event')),
    target_id   INTEGER NOT NULL,
    uploaded_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- 자주 조회하는 컬럼 인덱스
CREATE INDEX idx_event_start        ON Event(start_at);
CREATE INDEX idx_notification_user  ON Notification(user_id);
CREATE INDEX idx_completion_user    ON Completion(user_id);
CREATE INDEX idx_announcement_date  ON Announcement(created_at);
CREATE INDEX idx_group_member_user  ON Group_Member(user_id);
CREATE INDEX idx_memo_user_date     ON Memo(user_id, date);
CREATE INDEX idx_message_recipient_user ON Message_Recipient(user_id);
CREATE INDEX idx_attachment_target  ON Attachment(target_type, target_id);
CREATE INDEX idx_academic_schedule_date ON AcademicSchedule(start_date);
