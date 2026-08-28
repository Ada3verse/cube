# cube

학교 공유 캘린더 프로토타입 (교사 전용)

## 실행 방법

1. 의존성 설치
   ```
   pip install -r requirements.txt
   ```

2. 백엔드 서버 실행 (저장소 루트에서)
   ```
   python -m uvicorn backend.main:app --reload
   ```
   `http://127.0.0.1:8000` 에서 API가 뜹니다.

3. 프론트엔드 열기
   `frontend/index.html` 파일을 브라우저로 열면 됩니다.

4. 로그인
   - 아이디: 교사 이름 (예: 방인배)
   - 초기 비밀번호: `123456`

## DB 초기화 / 가상 데이터 리셋
```
python seed.py
```
`database.db`를 초기화하고 교사 30명 + 일정/공지/그룹/메모 샘플 데이터를 다시 채워 넣습니다.
(`schema.sql`을 먼저 반영해서 `database.db`가 없는 상태에서 새로 만들어야 한다면, `seed.py` 실행 전에 `database.db` 파일을 삭제하고 `schema.sql`을 먼저 실행하세요.)
