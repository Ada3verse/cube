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

// 로그인한 사용자에게 공개된(전체공개 + 본인이 대상자인) 공지만 불러온다.
async function fetchNotices() {
  const viewerId = getCurrentUserId();
  if (!viewerId) {
    notices = [];
    return notices;
  }

  const res = await fetch(`${API_BASE}/notices/mine?viewer_id=${viewerId}`);
  if (!res.ok) throw new Error("공지 목록을 불러오지 못했습니다.");
  const rows = await res.json();
  notices = rows.map((r) => ({
    ...r,
    mentionedTeachers: [
      ...new Set([
        ...(r.recipients || []).map((u) => u.name),
        ...extractMentions(r.content),
      ]),
    ],
  }));
  return notices;
}

async function fetchTeachers() {
  const res = await fetch(`${API_BASE}/teachers`);
  if (!res.ok) throw new Error("교사 목록을 불러오지 못했습니다.");
  return res.json();
}

async function fetchGroups() {
  const res = await fetch(`${API_BASE}/groups`);
  if (!res.ok) throw new Error("그룹 목록을 불러오지 못했습니다.");
  return res.json();
}

// 그룹 생성 API(POST /groups)는 생성자만 owner로 넣어준다 (팀원 구현).
// 나머지 멤버는 POST /groups/{id}/members 로 한 명씩 추가한다.
async function createGroup({ name, description = null, memberIds = [] }) {
  const res = await fetch(`${API_BASE}/groups`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name,
      description,
      created_by: getCurrentUserId(),
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "그룹 생성에 실패했습니다.");
  }
  const group = await res.json();

  const creatorId = getCurrentUserId();
  const others = memberIds.filter((id) => id !== creatorId);
  await Promise.all(others.map((userId) => addGroupMember(group.id, userId)));

  group.member_count = 1 + others.length;
  return group;
}

async function addGroupMember(groupId, userId) {
  const res = await fetch(`${API_BASE}/groups/${groupId}/members`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: userId }),
  });
  if (!res.ok && res.status !== 409) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "그룹원 추가에 실패했습니다.");
  }
}

async function createNotice({
  title,
  content,
  deadline,
  recipientUserIds = [],
  recipientGroupIds = [],
}) {
  const res = await fetch(`${API_BASE}/notices`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      title,
      content,
      deadline,
      author_id: getCurrentUserId(),
      recipient_user_ids: recipientUserIds,
      recipient_group_ids: recipientGroupIds,
    }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "공지 등록에 실패했습니다.");
  }

  const created = await res.json();
  const notice = {
    ...created,
    mentionedTeachers: [
      ...new Set([
        ...(created.recipients || []).map((u) => u.name),
        ...extractMentions(content),
      ]),
    ],
  };
  notices.unshift(notice);
  return notice;
}

function getNotices() {
  return [...notices].sort((a, b) => new Date(a.deadline) - new Date(b.deadline));
}

async function completeNotice(noticeId) {
  const userId = getCurrentUserId();
  const res = await fetch(`${API_BASE}/notices/${noticeId}/complete`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: userId }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "완료 처리에 실패했습니다.");
  }
  const result = await res.json();
  const notice = notices.find((n) => n.id === noticeId);
  if (notice) {
    notice.completed = true;
    notice.completed_at = result.completed_at;
  }
  return notice;
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

export {
  createNotice,
  getNotices,
  fetchNotices,
  fetchTeachers,
  fetchGroups,
  createGroup,
  completeNotice,
  calcDday,
  extractMentions,
  getCurrentUserId,
};
