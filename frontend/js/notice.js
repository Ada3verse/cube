// 공지사항 등록 + 관리
// 담당: hbn2814

const API_BASE = "http://127.0.0.1:8000";
const AUTH_STORAGE_KEY = "cube_user";

let notices = [];

function calcDday(deadline) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const target = new Date(deadline);
  target.setHours(0, 0, 0, 0);
  const diffDays = Math.round((target - today) / (1000 * 60 * 60 * 24));
  if (diffDays === 0) return "D-DAY";
  if (diffDays > 0) return `D-${diffDays}`;
  return `D+${Math.abs(diffDays)}`;
}

function extractMentions(text) {
  const matches = (text || "").match(/@[가-힣a-zA-Z0-9_]+/g) || [];
  return matches.map((m) => m.slice(1));
}

function getCurrentUserId() {
  try {
    const raw = localStorage.getItem(AUTH_STORAGE_KEY);
    return raw ? JSON.parse(raw).id : null;
  } catch {
    return null;
  }
}

// 서버에서 공지 목록을 불러와 로컬 캐시(notices)를 채운다.
// mentionedTeachers는 DB 컬럼이 아니라서 content에서 매번 다시 추출한다.
async function fetchNotices() {
  const res = await fetch(`${API_BASE}/notices`);
  if (!res.ok) throw new Error("공지 목록을 불러오지 못했습니다.");
  const rows = await res.json();
  notices = rows.map((r) => ({
    ...r,
    mentionedTeachers: extractMentions(r.content),
  }));
  return notices;
}

async function createNotice({ title, content, deadline, mentionedTeachers = [] }) {
  const res = await fetch(`${API_BASE}/notices`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      title,
      content,
      deadline,
      author_id: getCurrentUserId(),
    }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "공지 등록에 실패했습니다.");
  }

  const created = await res.json();
  const notice = {
    ...created,
    mentionedTeachers: mentionedTeachers.length
      ? mentionedTeachers
      : extractMentions(content),
  };
  notices.unshift(notice);
  return notice;
}

function getNotices() {
  return [...notices].sort((a, b) => new Date(a.deadline) - new Date(b.deadline));
}

async function initNoticeForm() {
  const form = document.getElementById("notice-form");
  if (!form) return;

  try {
    await fetchNotices();
  } catch (err) {
    console.error(err);
  }
  renderNoticeList();

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const title = document.getElementById("notice-title").value.trim();
    const content = document.getElementById("notice-content").value.trim();
    const deadline = document.getElementById("notice-deadline").value;
    if (!title || !deadline) return;

    try {
      await createNotice({ title, content, deadline });
      form.reset();
      renderNoticeList();
    } catch (err) {
      alert(err.message);
    }
  });
}

function renderNoticeList() {
  const list = document.getElementById("notice-list");
  if (!list) return;

  list.innerHTML = getNotices()
    .map(
      (n) => `
      <li class="notice-item">
        <span class="notice-dday">${calcDday(n.deadline)}</span>
        <span class="notice-title">${n.title}</span>
        ${n.mentionedTeachers.map((t) => `<span class="notice-mention">@${t}</span>`).join("")}
      </li>`
    )
    .join("");
}

document.addEventListener("DOMContentLoaded", initNoticeForm);

export { createNotice, getNotices, fetchNotices, calcDday, extractMentions };
