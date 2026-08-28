// 공지사항 등록 + 관리
// 담당: hbn2814

const notices = [];

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
  const matches = text.match(/@[가-힣a-zA-Z0-9_]+/g) || [];
  return matches.map((m) => m.slice(1));
}

function createNotice({
  title,
  content,
  deadline,
  author_id = null,
  target_group = null,
  mentionedTeachers = [],
}) {
  const now = new Date().toISOString();
  const notice = {
    id: Date.now(),
    title,
    content,
    author_id,
    target_group,
    deadline,
    is_pinned: 0,
    is_deleted: 0,
    // Announcement 테이블에는 없는 클라이언트 전용 필드 (Notification 대상자 표시용)
    mentionedTeachers: mentionedTeachers.length
      ? mentionedTeachers
      : extractMentions(content),
    created_at: now,
    updated_at: now,
  };
  notices.push(notice);
  return notice;
}

function getNotices() {
  return [...notices].sort((a, b) => new Date(a.deadline) - new Date(b.deadline));
}

function initNoticeForm() {
  const form = document.getElementById("notice-form");
  if (!form) return;

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const title = document.getElementById("notice-title").value.trim();
    const content = document.getElementById("notice-content").value.trim();
    const deadline = document.getElementById("notice-deadline").value;
    if (!title || !deadline) return;

    createNotice({ title, content, deadline });
    form.reset();
    renderNoticeList();
  });

  renderNoticeList();
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

export { createNotice, getNotices, calcDday, extractMentions };
