# 큐브 (CUBE) - 교무행정 통합 플랫폼

## 프로젝트 개요
중·고등학교 교무/연구행정 담당자를 위한 통합 행정 플랫폼.
나이스, 메신저, 엑셀 등 분산된 시스템을 하나로 통합한다.
슬로건: "흩어진 공지와 마감, 이제 한 곳에서!"

## 문제 정의
- 자료 요청 후 회신 없음 (쪽지, 포스트잇, 구두 요청 반복)
- 캘린더·시간표·공지가 각기 다른 툴에 흩어져 있음
- 시험감독 배정, 연수 이수 확인, 동의서 수합 등 수작업 관리
- 제출 현황을 한눈에 파악하기 어려움

## 기술 스택
- **프론트엔드**: HTML + CSS + JavaScript
- **백엔드**: Python + FastAPI
- **데이터베이스**: SQLite
- **추후**: 설치형(데스크탑 앱)으로 전환 예정

## Git 레포지토리
- URL: https://github.com/ada3verse/cube
- 브랜치 전략: 각자 feature 브랜치에서 작업 후 PR → main merge
  - ada3verse → `feature/calendar`
  - hbn2814 → `feature/notice`
  - yamako8119-ai → `feature/submission`

## 역할 분담

### AJ (ada3verse) - 캘린더 메인화면 + 전체 레이아웃
- 앱 실행 시 첫 화면: 월간 캘린더
- 공유 캘린더 + 개인 캘린더 동시 작동
- 전체 페이지 레이아웃 및 네비게이션
- 담당 파일: `frontend/index.html`, `frontend/css/`, `frontend/js/calendar.js`

### hbn2814 - 공지 등록 + 알림 화면
- 공지사항 등록 폼
- 특정 교사 @멘션 기능
- 마감일 설정 및 D-day 표시 (D-10, D-7, D-5, D-3, D-1, D-DAY)
- 접속 시 오늘 할 일 팝업
- 담당 파일: `frontend/js/notice.js`, `frontend/js/notification.js`

### yamako8119-ai - 제출현황 + DB/백엔드 전체
- FastAPI 서버 설정
- SQLite DB 설계 및 연결
- 제출 현황 화면 (제출완료 / 미제출 / 부분제출 태그)
- 전체 API 엔드포인트 제공
- 담당 파일: `backend/main.py`, `backend/database.py`, `backend/models.py`, `frontend/js/submission.js`

## 핵심 기능 (토요일 발표용)
1. **캘린더** - 첫 화면, 공유+개인 동시 작동
2. **공지사항 등록** - 대상 교사 지정, 마감일 설정
3. **알림** - 화면 내 표시, D-day 카운트다운
4. **제출 현황** - 담당자가 한눈에 확인

## 상태 태그 시스템
- 마감: D-10 / D-7 / D-5 / D-3 / D-1 / D-DAY
- 업무: 예정 / 진행중 / 임박 / 완료 / 보류 / 취소
- 알림: NEW / 확인됨 / 미확인 / 연장됨
- 제출: 제출완료 / 미제출 / 부분제출

## 추가 기능 (시간 되면)
- @멘션으로 교사 지정 채팅/쪽지
- 팝업 알림
- 아카이빙

## 보류 항목
- 외부 알림 (카카오톡 등 메신저 연동)
- 설치형 전환
- UI/UX 세부 디자인

## 프로젝트 폴더 구조
```
cube/
├── CLAUDE.md
├── backend/
│   ├── main.py          # FastAPI 서버
│   ├── database.py      # SQLite 연결
│   └── models.py        # DB 모델
└── frontend/
    ├── index.html       # 메인 페이지
    ├── css/
    │   └── style.css
    └── js/
        ├── calendar.js
        ├── notice.js
        ├── notification.js
        └── submission.js
```

## 발표 일정
- **2026년 8월 29일 (토요일)**: 웹 시연 발표
- 추후 설치형으로 전환 예정임을 발표 시 언급

## 디자인 컨셉
- 메인 컬러: 초록색 계열
- 캐릭터: 조각이 (데이터 수집이 취미인 환경미화원)
- 톤: 깔끔하고 실용적인 행정 UI
