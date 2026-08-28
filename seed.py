"""
가상 데이터 시딩 스크립트 (프로토타입용)
실행: python seed.py
- 8~9월(2026) 기준 학교 일정/공지사항
- 교사 30명 + 관리자 1명
"""

import random
import sqlite3
from datetime import datetime, timedelta

import bcrypt

random.seed(42)

SURNAMES = ["김", "이", "박", "최", "정", "강", "조", "윤", "장", "임"]
GIVEN = [
    "민준", "서연", "지호", "지우", "하은", "예준", "수빈", "다은", "지훈", "서준",
    "유진", "은서", "현우", "채원", "도윤", "소율", "우진", "나윤", "시우", "지안",
    "준서", "예은", "민서", "재원", "다연", "성민", "혜원", "동현", "가은", "태윤",
]
DEPARTMENTS = ["교무부", "연구부", "과학정보부", "창의체험부", "생활안전부"]
SUBJECTS = ["국어", "영어", "수학", "과학", "정보", "사회", "도덕", "음악", "미술", "체육", "기술가정"]

DEFAULT_PASSWORD_HASH = bcrypt.hashpw("123456".encode(), bcrypt.gensalt()).decode()

conn = sqlite3.connect("database.db")
cur = conn.cursor()

# 기존 데이터 초기화 (재실행 대비)
for table in ["AcademicSchedule", "Attachment", "Message_Recipient", "Message", "Memo", "Group_Member", "Groups", "Completion", "Notification", "Announcement", "Event", "User"]:
    cur.execute(f"DELETE FROM {table}")
    cur.execute(f"DELETE FROM sqlite_sequence WHERE name='{table}'")

# ── User: 관리자 1명 + 교사 30명 (아이디 = 이름, 초기 비밀번호 = 123456) ──
FIXED_TEACHER_NAMES = ["방인배", "황병남", "정경원"]

all_name_combos = [s + g for s in SURNAMES for g in GIVEN if s + g not in FIXED_TEACHER_NAMES]
random.shuffle(all_name_combos)
teacher_names = FIXED_TEACHER_NAMES + all_name_combos[: 30 - len(FIXED_TEACHER_NAMES)]

users = []
users.append(("정교장", True))  # id 1
for name in teacher_names:
    users.append((name, False))

extensions = random.sample(range(1001, 1100), k=len(users))

user_ids = {}
for (name, is_admin), ext in zip(users, extensions):
    dept = random.choice(DEPARTMENTS)
    subject = None if is_admin else random.choice(SUBJECTS)
    cur.execute(
        "INSERT INTO User (name, password_hash, is_admin, department, subject, extension) VALUES (?, ?, ?, ?, ?, ?)",
        (name, DEFAULT_PASSWORD_HASH, int(is_admin), dept, subject, str(ext)),
    )
    user_ids[name] = cur.lastrowid

teacher_ids = [uid for name, uid in user_ids.items() if name != "정교장"]
admin_id = user_ids["정교장"]

# ── 담임 배정: 학년(1~3) x 반(1~8) 중 중복 없이 랜덤 배정 ────────
GRADES = [1, 2, 3]
CLASSES_PER_GRADE = 8
all_slots = [(g, c) for g in GRADES for c in range(1, CLASSES_PER_GRADE + 1)]
random.shuffle(all_slots)

HOMEROOM_COUNT = 18
homeroom_teachers = random.sample(teacher_ids, k=HOMEROOM_COUNT)
for uid, (grade, class_no) in zip(homeroom_teachers, all_slots[:HOMEROOM_COUNT]):
    cur.execute(
        "UPDATE User SET is_homeroom = 1, grade = ?, class_no = ? WHERE id = ?",
        (grade, class_no, uid),
    )

# ── Event: 8~9월 학사일정 ────────────────────────────────────
events = [
    ("2학기 개학식", "activity", "2026-08-18T09:00:00", "2026-08-18T10:00:00", "강당", None),
    ("전체 교직원 회의", "meeting", "2026-08-18T13:00:00", "2026-08-18T14:00:00", "회의실 A", None),
    ("2학기 교육과정 워크숍", "meeting", "2026-08-20T09:00:00", "2026-08-20T16:00:00", "강당", None),
    ("수행평가 계획서 제출", "deadline", "2026-08-25T18:00:00", None, None, None),
    ("학부모 상담주간 안내", "activity", "2026-08-24T00:00:00", "2026-08-28T00:00:00", "각 교실", None),
    ("체육대회", "activity", "2026-09-04T09:00:00", "2026-09-04T15:00:00", "운동장", None),
    ("1차 지필고사 출제 마감", "deadline", "2026-09-08T18:00:00", None, None, "수학"),
    ("교과협의회", "meeting", "2026-09-10T15:00:00", "2026-09-10T16:00:00", "교과실", "국어"),
    ("공개수업 주간", "activity", "2026-09-14T00:00:00", "2026-09-18T00:00:00", "각 교실", None),
    ("생활기록부 1차 점검 마감", "deadline", "2026-09-19T18:00:00", None, None, None),
    ("추석 연휴 전 안전교육", "meeting", "2026-09-22T08:30:00", "2026-09-22T09:00:00", "강당", None),
    ("2학기 동아리 발표회", "activity", "2026-09-25T13:00:00", "2026-09-25T16:00:00", "강당", None),
    ("성적 입력 마감", "deadline", "2026-09-30T18:00:00", None, None, None),
    # 개인일정 (본인만 조회, 알림 발송 없음)
    ("치과 예약", "personal", "2026-08-21T15:00:00", "2026-08-21T16:00:00", "서울치과", None),
    ("자녀 학부모 상담", "personal", "2026-09-03T10:00:00", "2026-09-03T11:00:00", None, None),
    ("연차 - 개인 사유", "personal", "2026-09-17T00:00:00", "2026-09-17T00:00:00", None, None),
]

event_ids = []
for title, type_, start_at, end_at, location, target_group in events:
    author = admin_id if type_ == "meeting" else random.choice(teacher_ids)
    cur.execute(
        """INSERT INTO Event (title, description, type, start_at, end_at, location, target_group, author_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (title, f"{title} 관련 일정입니다.", type_, start_at, end_at, location, target_group, author),
    )
    event_ids.append((cur.lastrowid, type_, target_group))

# ── Notification: 대상 그룹에 맞는 교사들에게 알림 생성 (개인일정 제외) ─
for event_id, type_, target_group in event_ids:
    if type_ == "personal":
        continue
    recipients = list(teacher_ids)
    if target_group:
        recipients = [uid for uid in recipients if True]  # group_name 매칭은 조회 시 처리, 시드는 전체 대상 유지
    recipients = random.sample(recipients, k=random.randint(15, len(teacher_ids)))
    for uid in recipients:
        read = random.random() < 0.6
        read_at = "2026-08-15T09:00:00" if read else None
        cur.execute(
            "INSERT INTO Notification (event_id, user_id, sent_at, read_at) VALUES (?, ?, ?, ?)",
            (event_id, uid, "2026-08-15T08:00:00", read_at),
        )

# ── Completion: deadline 유형 이벤트만 완료 여부 기록 ───────────
for event_id, type_, target_group in event_ids:
    if type_ != "deadline":
        continue
    recipients = random.sample(teacher_ids, k=random.randint(15, 25))
    for uid in recipients:
        done = random.random() < 0.5
        completed_at = "2026-08-24T17:00:00" if done else None
        cur.execute(
            "INSERT INTO Completion (event_id, user_id, is_completed, completed_at) VALUES (?, ?, ?, ?)",
            (event_id, uid, int(done), completed_at),
        )

# ── Announcement: 공지사항 ───────────────────────────────────
announcements = [
    ("2학기 교과서 반납 안내", "미사용 교과서는 행정실로 반납해주세요.", None, "2026-08-29", 1),
    ("여름방학 중 시설 점검 결과 공유", "냉방기 점검이 완료되었습니다.", None, None, 0),
    ("학부모 상담주간 신청서 제출", "상담 가능 시간을 신청서에 기재해 제출해주세요. @김민준 @이서연 확인 부탁드립니다.", None, "2026-08-22", 1),
    ("체육대회 물품 신청", "각 반별 필요 물품을 신청해주세요.", "창의체험부", "2026-08-30", 0),
    ("2학기 방과후학교 강사 모집", "신규 강사 지원 서류를 제출해주세요.", None, "2026-09-05", 0),
    ("생활기록부 작성 연수 자료 공유", "첨부된 자료를 참고해 작성해주세요.", None, None, 0),
    ("교내 화재 대피 훈련 안내", "9월 셋째 주 중 실시 예정입니다.", None, "2026-09-15", 1),
]

for title, content, target_group, deadline, is_pinned in announcements:
    author = random.choice(teacher_ids + [admin_id])
    cur.execute(
        """INSERT INTO Announcement (title, content, author_id, target_group, deadline, is_pinned)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (title, content, author, target_group, deadline, is_pinned),
    )

# ── Groups: 예시 그룹 5개 (공식 3 + 개인 2) ──────────────────
groups = [
    ("체육대회 준비 TF", "체육대회 기획 및 운영을 담당하는 임시 조직입니다.", admin_id, 1),
    ("학교폭력대책위원회", "학교폭력 관련 사안을 심의합니다.", admin_id, 1),
    ("방과후학교 운영진", "방과후학교 프로그램 운영 담당 교사 모임입니다.", admin_id, 1),
    ("동아리 지도교사 모임", "동아리 담당 교사들끼리 정보를 공유하는 모임입니다.", random.choice(teacher_ids), 0),
    ("등산 동호회", "주말마다 등산하는 친목 모임입니다.", random.choice(teacher_ids), 0),
]

for name, description, created_by, is_official in groups:
    cur.execute(
        "INSERT INTO Groups (name, description, created_by, is_official) VALUES (?, ?, ?, ?)",
        (name, description, created_by, is_official),
    )
    group_id = cur.lastrowid

    # 만든 사람은 owner로 자동 등록
    cur.execute(
        "INSERT INTO Group_Member (group_id, user_id, role) VALUES (?, ?, 'owner')",
        (group_id, created_by),
    )

    # 나머지 멤버 랜덤 배정 (본인 제외)
    candidates = [uid for uid in teacher_ids if uid != created_by]
    members = random.sample(candidates, k=random.randint(4, 9))
    for uid in members:
        cur.execute(
            "INSERT INTO Group_Member (group_id, user_id, role) VALUES (?, ?, 'member')",
            (group_id, uid),
        )

# ── Memo: 개인 캘린더 메모 (일부 교사만 샘플로 작성) ─────────
memo_samples = [
    ("2026-08-18", "개학식 준비물 미리 챙기기"),
    ("2026-08-25", "수행평가 계획서 제출 전 동학년과 검토"),
    ("2026-09-04", "체육대회 반티 사이즈 확인"),
    ("2026-09-08", "출제 문제 오탈자 재확인"),
    ("2026-09-30", "성적 입력 전 엑셀 백업"),
]

memo_authors = random.sample(teacher_ids, k=len(memo_samples))
for uid, (date, content) in zip(memo_authors, memo_samples):
    cur.execute(
        "INSERT INTO Memo (user_id, date, content) VALUES (?, ?, ?)",
        (uid, date, content),
    )

# ── Message: 쪽지 (1명 또는 여러 명에게 발송) ─────────────────
message_samples = [
    ("체육대회 관련해서 잠깐 얘기 가능하실까요?", 1),      # 1명에게
    ("이번 주 교과협의회 자료 공유드립니다.", 3),          # 3명에게
    ("생활기록부 점검 관련 안내드립니다.", 5),             # 5명에게
]

for content, recipient_count in message_samples:
    sender = random.choice(teacher_ids)
    cur.execute(
        "INSERT INTO Message (sender_id, content) VALUES (?, ?)",
        (sender, content),
    )
    message_id = cur.lastrowid

    candidates = [uid for uid in teacher_ids if uid != sender]
    recipients = random.sample(candidates, k=recipient_count)
    for uid in recipients:
        read = random.random() < 0.5
        read_at = "2026-08-20T09:00:00" if read else None
        cur.execute(
            "INSERT INTO Message_Recipient (message_id, user_id, read_at) VALUES (?, ?, ?)",
            (message_id, uid, read_at),
        )

# ── Attachment: 공지사항 1건에 샘플 첨부파일 ───────────────────
cur.execute("SELECT id FROM Announcement ORDER BY id LIMIT 1")
first_announcement_id = cur.fetchone()[0]
cur.execute(
    """INSERT INTO Attachment (file_name, file_path, file_size, uploaded_by, target_type, target_id)
       VALUES (?, ?, ?, ?, ?, ?)""",
    ("교과서_반납_안내.pdf", "uploads/announcement/1/교과서_반납_안내.pdf", 245000, admin_id, "announcement", first_announcement_id),
)

# ── AcademicSchedule: 학사일정 (학교 전체 기준 캘린더) ─────────
academic_schedule = [
    ("2학기 개학식", "행사", "2026-08-18", None),
    ("2학기 중간고사", "시험", "2026-09-08", "2026-09-10"),
    ("재량휴업일", "공휴일", "2026-09-21", None),
    ("추석 연휴", "공휴일", "2026-09-24", "2026-09-27"),
    ("체육대회", "행사", "2026-09-04", None),
    ("동아리의 날", "동아리", "2026-09-25", None),
    ("창체 활동 - 진로체험", "창체", "2026-09-15", None),
]

for title, category, start_date, end_date in academic_schedule:
    cur.execute(
        "INSERT INTO AcademicSchedule (title, category, start_date, end_date, created_by) VALUES (?, ?, ?, ?, ?)",
        (title, category, start_date, end_date, admin_id),
    )

conn.commit()

cur.execute("SELECT COUNT(*) FROM User")
print("User:", cur.fetchone()[0])
cur.execute("SELECT COUNT(*) FROM Event")
print("Event:", cur.fetchone()[0])
cur.execute("SELECT COUNT(*) FROM Notification")
print("Notification:", cur.fetchone()[0])
cur.execute("SELECT COUNT(*) FROM Completion")
print("Completion:", cur.fetchone()[0])
cur.execute("SELECT COUNT(*) FROM Announcement")
print("Announcement:", cur.fetchone()[0])
cur.execute("SELECT COUNT(*) FROM Groups")
print("Groups:", cur.fetchone()[0])
cur.execute("SELECT COUNT(*) FROM Group_Member")
print("Group_Member:", cur.fetchone()[0])
cur.execute("SELECT COUNT(*) FROM Memo")
print("Memo:", cur.fetchone()[0])
cur.execute("SELECT COUNT(*) FROM Message")
print("Message:", cur.fetchone()[0])
cur.execute("SELECT COUNT(*) FROM Message_Recipient")
print("Message_Recipient:", cur.fetchone()[0])
cur.execute("SELECT COUNT(*) FROM Attachment")
print("Attachment:", cur.fetchone()[0])
cur.execute("SELECT COUNT(*) FROM AcademicSchedule")
print("AcademicSchedule:", cur.fetchone()[0])

conn.close()
