// 큐브 캐릭터 위젯 — 공지 등록 / 알림 / 목록
// 담당: hbn2814

import {
  createNotice,
  getNotices,
  fetchNotices,
  fetchTeachers,
  fetchGroups,
  createGroup,
  completeNotice,
  calcDday,
  getCurrentUserId,
} from './notice.js';

// ── State ──────────────────────────────────────────────
let panelOpen  = false;
let activeTab  = 'alerts';
let prevUrgentCount = 0;

// 알림 탭에서 "확인"한(dismiss한) 공지 id 목록 — 사용자별 localStorage에 저장
let dismissedAlertIds = new Set();

// 알림/목록 탭에서 현재 상세보기 중인 공지 id (null이면 목록 화면)
let alertDetailId = null;
let listDetailId  = null;

// 대상 교사 선택 상태: {type:'user'|'group', id, name}[]
let selectedRecipients = [];

// @멘션 자동완성용 교사/그룹 캐시
let directory = { teachers: [], groups: [] };
let directoryLoaded = false;
let mentionMatches = [];
let mentionHighlight = -1;

// ── SVG 큐브 캐릭터 (조각이) ──────────────────────────
const CUBE_SVG = `
<svg id="cw-cube-svg" viewBox="0 0 60 60" xmlns="http://www.w3.org/2000/svg">
  <!-- 상단 면 -->
  <polygon points="30,3 57,18 30,33 3,18" fill="#d8f3dc" stroke="#c5ead0" stroke-width="0.8"/>
  <!-- 상단 하이라이트 -->
  <polygon points="30,3 57,18 43,25.5 16,10.5" fill="rgba(255,255,255,0.28)"/>
  <!-- 왼쪽 면 -->
  <polygon points="3,18 30,33 30,57 3,42"   fill="#6fb3b8" stroke="#5a9ea3" stroke-width="0.8"/>
  <!-- 오른쪽 면 (얼굴) -->
  <polygon points="57,18 30,33 30,57 57,42" fill="#a8dadc" stroke="#8fc9cb" stroke-width="0.8"/>
  <!-- 눈 -->
  <ellipse id="cw-eye-l" cx="42" cy="40"   rx="3" ry="3" fill="#1f4d33"/>
  <ellipse id="cw-eye-r" cx="51" cy="35.5" rx="3" ry="3" fill="#1f4d33"/>
  <!-- 눈 반짝임 -->
  <circle cx="43.2" cy="38.8" r="1.1" fill="white" opacity="0.8"/>
  <circle cx="52.2" cy="34.3" r="1.1" fill="white" opacity="0.8"/>
  <!-- 볼 -->
  <ellipse cx="40"   cy="46"  rx="3.5" ry="2" fill="#f9a0a0" opacity="0.55"/>
  <ellipse cx="54.5" cy="43"  rx="3.5" ry="2" fill="#f9a0a0" opacity="0.55"/>
  <!-- 입 -->
  <path d="M 40 48 Q 47 54 55 49" stroke="#1f4d33" stroke-width="1.8" fill="none" stroke-linecap="round"/>
</svg>`;

// ── HTML 구조 ─────────────────────────────────────────
function buildHTML() {
  const today = new Date().toISOString().split('T')[0];
  return `
<div id="cw-root" class="cw-root cw-hidden">

  <!-- 큐브 버튼 -->
  <button id="cw-btn" class="cw-btn" title="조각이 열기">
    ${CUBE_SVG}
    <span id="cw-badge" class="cw-badge cw-badge-off">0</span>
  </button>

  <!-- 패널 -->
  <div id="cw-panel" class="cw-panel cw-panel-closed">
    <div class="cw-panel-head">
      <span class="cw-char-name">📦 조각이</span>
      <div class="cw-tabs">
        <button class="cw-tab active" data-ctab="alerts">🔔 알림</button>
        <button class="cw-tab"        data-ctab="list">📋 목록</button>
        <button class="cw-tab"        data-ctab="register">✏️ 등록</button>
      </div>
      <button id="cw-close-btn" class="cw-close-btn" aria-label="닫기">✕</button>
    </div>

    <div class="cw-panel-body">

      <!-- ① 알림 탭 -->
      <div class="cw-tab-content active" id="ctab-alerts">
        <div id="cw-alerts-list-view">
          <p class="cw-alert-desc">D-10 이내 마감 공지 중 나에게 공개된 것만 표시합니다.</p>
          <ul id="cw-alerts-list" class="cw-list-ui"></ul>
          <p id="cw-alerts-empty" class="cw-empty-msg cw-hidden">알림이 없습니다 😊</p>
        </div>
        <div id="cw-alert-detail" class="cw-detail cw-hidden">
          <span id="cw-alert-detail-dday" class="cw-detail-dday"></span>
          <h3 id="cw-alert-detail-title" class="cw-detail-title"></h3>
          <div id="cw-alert-detail-author" class="cw-detail-meta"></div>
          <div id="cw-alert-detail-content" class="cw-detail-content"></div>
          <button type="button" id="cw-alert-ack-btn" class="cw-submit-btn">확인했습니다</button>
        </div>
      </div>

      <!-- ② 목록 탭 -->
      <div class="cw-tab-content" id="ctab-list">
        <div id="cw-list-list-view">
          <ul id="cw-all-list" class="cw-list-ui"></ul>
          <p id="cw-list-empty" class="cw-empty-msg cw-hidden">등록된 공지가 없습니다.</p>
        </div>
        <div id="cw-list-detail" class="cw-detail cw-hidden">
          <span id="cw-list-detail-dday" class="cw-detail-dday"></span>
          <h3 id="cw-list-detail-title" class="cw-detail-title"></h3>
          <div id="cw-list-detail-author" class="cw-detail-meta"></div>
          <div id="cw-list-detail-content" class="cw-detail-content"></div>
          <div class="cw-detail-actions">
            <button type="button" id="cw-list-back-btn" class="cw-picker-btn">← 목록으로</button>
            <button type="button" id="cw-list-complete-btn" class="cw-submit-btn">완료</button>
          </div>
        </div>
      </div>

      <!-- ③ 등록 탭 -->
      <div class="cw-tab-content" id="ctab-register">
        <form id="cw-form" autocomplete="off">
          <div class="cw-field">
            <label>제목 <span class="cw-req">*</span></label>
            <input id="cw-f-title" type="text" placeholder="공지 제목을 입력하세요" required />
          </div>
          <div class="cw-field">
            <label>내용</label>
            <textarea id="cw-f-content" rows="3" placeholder="공지 내용 (선택)"></textarea>
          </div>
          <div class="cw-field">
            <label>마감일 <span class="cw-req">*</span></label>
            <input id="cw-f-deadline" type="date" value="${today}" required />
          </div>
          <div class="cw-field cw-mention-field">
            <label>대상 교사 <span class="cw-hint">@이름 입력 후 Tab으로 선택</span></label>
            <div class="cw-mention-input-wrap">
              <input id="cw-mention-input" type="text" placeholder="@이름 또는 @그룹명" />
              <ul id="cw-mention-dropdown" class="cw-mention-dropdown cw-hidden"></ul>
            </div>
            <div class="cw-picker-actions">
              <button type="button" id="cw-load-targets-btn" class="cw-picker-btn">🎯 대상 불러오기</button>
              <button type="button" id="cw-create-group-btn" class="cw-picker-btn">➕ 그룹 만들기</button>
            </div>
            <div id="cw-chips" class="cw-chips"></div>
          </div>
          <button type="submit" class="cw-submit-btn">공지 등록하기</button>
        </form>
        <div id="cw-success-msg" class="cw-success-msg cw-hidden">🎉 공지가 등록되었습니다!</div>
      </div>

    </div>
  </div>

  <!-- 공용 모달 (교사 불러오기 / 그룹 만들기) -->
  <div id="cw-modal-overlay" class="cw-modal-overlay cw-hidden">
    <div class="cw-modal">
      <div class="cw-modal-head">
        <span id="cw-modal-title">교사 선택</span>
        <button type="button" id="cw-modal-close" class="cw-close-btn" aria-label="닫기">✕</button>
      </div>
      <div id="cw-modal-body" class="cw-modal-body"></div>
      <div class="cw-modal-foot">
        <button type="button" id="cw-modal-action" class="cw-submit-btn">완료</button>
      </div>
    </div>
  </div>
</div>`;
}

// ── 알림 확인(dismiss) 상태 ────────────────────────────
function dismissedStorageKey() {
  const userId = getCurrentUserId();
  return `cw_dismissed_alerts_${userId ?? 'anon'}`;
}

function loadDismissed() {
  try {
    const raw = localStorage.getItem(dismissedStorageKey());
    dismissedAlertIds = new Set(raw ? JSON.parse(raw) : []);
  } catch {
    dismissedAlertIds = new Set();
  }
}

function saveDismissed() {
  try {
    localStorage.setItem(dismissedStorageKey(), JSON.stringify([...dismissedAlertIds]));
  } catch {
    // localStorage 사용 불가 시 조용히 무시 (해당 세션에서만 알림이 다시 보임)
  }
}

// ── D-day 긴급도 ─────────────────────────────────────
function urgency(dday) {
  if (dday === 'D-DAY') return 'day';
  if (dday.startsWith('D-')) {
    const n = parseInt(dday.slice(2));
    if (n <= 1) return 'day';
    if (n <= 3) return 'high';
    if (n <= 7) return 'mid';
  }
  return 'low';
}

function alertNotices() {
  const today = new Date(); today.setHours(0, 0, 0, 0);
  return getNotices().filter(n => {
    if (!n.deadline || n.completed || dismissedAlertIds.has(n.id)) return false;
    const d = new Date(n.deadline); d.setHours(0, 0, 0, 0);
    return Math.round((d - today) / 86400000) <= 10;
  });
}

function findNotice(id) {
  return getNotices().find(n => n.id === id);
}

// ── 렌더: 알림 탭 ─────────────────────────────────────
function renderAlerts() {
  const listView = document.getElementById('cw-alerts-list-view');
  const detail   = document.getElementById('cw-alert-detail');

  if (alertDetailId !== null) {
    listView.classList.add('cw-hidden');
    detail.classList.remove('cw-hidden');
    renderAlertDetail();
    return;
  }
  listView.classList.remove('cw-hidden');
  detail.classList.add('cw-hidden');

  const list  = document.getElementById('cw-alerts-list');
  const empty = document.getElementById('cw-alerts-empty');
  const data  = alertNotices();

  if (!data.length) {
    list.innerHTML = '';
    empty.classList.remove('cw-hidden');
    return;
  }
  empty.classList.add('cw-hidden');

  list.innerHTML = data.map(n => {
    const dd  = calcDday(n.deadline);
    const urg = urgency(dd);
    return `
      <li class="cw-alert-item cw-urg-${urg}" data-id="${n.id}">
        <span class="cw-dday-chip cw-urg-${urg}">${dd}</span>
        <div class="cw-item-body">
          <div class="cw-item-title">${n.title}</div>
        </div>
      </li>`;
  }).join('');

  list.querySelectorAll('.cw-alert-item').forEach(li => {
    li.addEventListener('click', () => {
      alertDetailId = Number(li.dataset.id);
      renderAlerts();
    });
  });
}

function renderAlertDetail() {
  const n = findNotice(alertDetailId);
  if (!n) { alertDetailId = null; renderAlerts(); return; }

  document.getElementById('cw-alert-detail-dday').textContent = calcDday(n.deadline);
  document.getElementById('cw-alert-detail-dday').className = `cw-detail-dday cw-urg-${urgency(calcDday(n.deadline))}`;
  document.getElementById('cw-alert-detail-title').textContent = n.title;
  document.getElementById('cw-alert-detail-author').textContent = `보낸 사람: ${n.author_name || '알 수 없음'}`;
  document.getElementById('cw-alert-detail-content').textContent = n.content || '(내용 없음)';
}

function acknowledgeAlert() {
  if (alertDetailId === null) return;
  dismissedAlertIds.add(alertDetailId);
  saveDismissed();
  alertDetailId = null;
  renderAlerts();
  updateBadge();
}

// ── 렌더: 목록 탭 ─────────────────────────────────────
function sortedListNotices() {
  const data = getNotices();
  const incomplete = data.filter(n => !n.completed);
  const complete   = data.filter(n => n.completed);
  return [...incomplete, ...complete];
}

function renderAll() {
  const listView = document.getElementById('cw-list-list-view');
  const detail   = document.getElementById('cw-list-detail');

  if (listDetailId !== null) {
    listView.classList.add('cw-hidden');
    detail.classList.remove('cw-hidden');
    renderListDetail();
    return;
  }
  listView.classList.remove('cw-hidden');
  detail.classList.add('cw-hidden');

  const list  = document.getElementById('cw-all-list');
  const empty = document.getElementById('cw-list-empty');
  const data  = sortedListNotices();

  if (!data.length) {
    list.innerHTML = '';
    empty.classList.remove('cw-hidden');
    return;
  }
  empty.classList.add('cw-hidden');

  list.innerHTML = data.map(n => {
    const dd  = n.deadline ? calcDday(n.deadline) : '';
    const urg = dd ? urgency(dd) : 'low';
    return `
      <li class="cw-list-item ${n.completed ? 'cw-item-done' : ''}" data-id="${n.id}">
        ${dd ? `<span class="cw-dday-chip cw-urg-${urg}">${dd}</span>` : ''}
        <div class="cw-item-body">
          <div class="cw-item-title">${n.title}</div>
        </div>
        ${n.completed ? '<span class="cw-done-badge">완료</span>' : ''}
      </li>`;
  }).join('');

  list.querySelectorAll('.cw-list-item').forEach(li => {
    li.addEventListener('click', () => {
      listDetailId = Number(li.dataset.id);
      renderAll();
    });
  });
}

function renderListDetail() {
  const n = findNotice(listDetailId);
  if (!n) { listDetailId = null; renderAll(); return; }

  document.getElementById('cw-list-detail-dday').textContent = n.deadline ? calcDday(n.deadline) : '';
  document.getElementById('cw-list-detail-dday').className = `cw-detail-dday cw-urg-${n.deadline ? urgency(calcDday(n.deadline)) : 'low'}`;
  document.getElementById('cw-list-detail-title').textContent = n.title;
  document.getElementById('cw-list-detail-author').textContent = `보낸 사람: ${n.author_name || '알 수 없음'}`;
  document.getElementById('cw-list-detail-content').textContent = n.content || '(내용 없음)';

  const completeBtn = document.getElementById('cw-list-complete-btn');
  completeBtn.classList.toggle('cw-hidden', !!n.completed);
}

function backToList() {
  listDetailId = null;
  renderAll();
}

async function markComplete() {
  if (listDetailId === null) return;
  const btn = document.getElementById('cw-list-complete-btn');
  btn.disabled = true;
  try {
    await completeNotice(listDetailId);
  } catch (err) {
    alert(err.message);
    btn.disabled = false;
    return;
  }
  btn.disabled = false;
  listDetailId = null;
  renderAll();
  updateBadge();
}

// ── 대상 교사 선택 (chips) ─────────────────────────────
function recipientKey(r) { return `${r.type}:${r.id}`; }

function addRecipient(item) {
  const key = recipientKey(item);
  if (selectedRecipients.some(r => recipientKey(r) === key)) return;
  selectedRecipients.push(item);
  renderChips();
}

function removeRecipient(type, id) {
  selectedRecipients = selectedRecipients.filter(r => !(r.type === type && r.id === id));
  renderChips();
}

function renderChips() {
  const c = document.getElementById('cw-chips');
  if (!c) return;
  c.innerHTML = selectedRecipients.map(r => {
    const label = r.type === 'group' ? `#${r.name}` : `@${r.name}`;
    return `<span class="cw-chip cw-chip-${r.type}">${label}
       <button type="button" class="cw-chip-del" data-type="${r.type}" data-id="${r.id}">×</button>
     </span>`;
  }).join('');
  c.querySelectorAll('.cw-chip-del').forEach(btn => {
    btn.onclick = () => removeRecipient(btn.dataset.type, Number(btn.dataset.id));
  });
}

// ── 교사/그룹 디렉터리 ─────────────────────────────────
async function loadDirectory() {
  try {
    const [teachers, groups] = await Promise.all([fetchTeachers(), fetchGroups()]);
    directory = { teachers, groups };
    directoryLoaded = true;
  } catch (err) {
    console.error(err);
  }
}

// ── @멘션 자동완성 ─────────────────────────────────────
function computeMentionMatches(query) {
  const q = query.toLowerCase();
  const teacherMatches = directory.teachers
    .filter(t => t.name.toLowerCase().includes(q))
    .map(t => ({ type: 'user', id: t.id, name: t.name, sub: t.department || '' }));
  const groupMatches = directory.groups
    .filter(g => g.name.toLowerCase().includes(q))
    .map(g => ({ type: 'group', id: g.id, name: g.name, sub: `${g.member_count || 0}명` }));
  return [...teacherMatches, ...groupMatches].slice(0, 8);
}

function renderMentionDropdown() {
  const dd = document.getElementById('cw-mention-dropdown');
  if (!mentionMatches.length) {
    dd.classList.add('cw-hidden');
    dd.innerHTML = '';
    return;
  }
  dd.classList.remove('cw-hidden');
  dd.innerHTML = mentionMatches.map((m, i) => `
    <li class="cw-mention-opt ${i === mentionHighlight ? 'cw-mention-hl' : ''}" data-index="${i}">
      <span class="cw-mention-icon">${m.type === 'group' ? '👥' : '👤'}</span>
      <span class="cw-mention-name">${m.name}</span>
      <span class="cw-mention-sub">${m.sub}</span>
    </li>`).join('');

  dd.querySelectorAll('.cw-mention-opt').forEach(li => {
    li.addEventListener('mousedown', (e) => {
      e.preventDefault();
      selectMentionMatch(Number(li.dataset.index));
    });
  });
}

function selectMentionMatch(index) {
  const m = mentionMatches[index];
  if (!m) return;
  addRecipient({ type: m.type, id: m.id, name: m.name });
  const input = document.getElementById('cw-mention-input');
  input.value = '';
  mentionMatches = [];
  mentionHighlight = -1;
  renderMentionDropdown();
}

function handleMentionInput(e) {
  const value = e.target.value;
  const atIndex = value.lastIndexOf('@');
  if (atIndex === -1) {
    mentionMatches = [];
    mentionHighlight = -1;
    renderMentionDropdown();
    return;
  }
  const query = value.slice(atIndex + 1);
  mentionMatches = computeMentionMatches(query);
  mentionHighlight = mentionMatches.length ? 0 : -1;
  renderMentionDropdown();
}

function handleMentionKeydown(e) {
  if (!mentionMatches.length) return;

  if (e.key === 'Tab') {
    e.preventDefault();
    mentionHighlight = (mentionHighlight + 1) % mentionMatches.length;
    renderMentionDropdown();
  } else if (e.key === 'Enter') {
    e.preventDefault();
    selectMentionMatch(mentionHighlight >= 0 ? mentionHighlight : 0);
  } else if (e.key === 'Escape') {
    mentionMatches = [];
    mentionHighlight = -1;
    renderMentionDropdown();
  }
}

// ── 공용 모달 ─────────────────────────────────────────
function openModal(title, bodyHTML, actionLabel, onAction) {
  document.getElementById('cw-modal-title').textContent = title;
  document.getElementById('cw-modal-body').innerHTML = bodyHTML;
  const actionBtn = document.getElementById('cw-modal-action');
  actionBtn.textContent = actionLabel;
  actionBtn.onclick = onAction;
  document.getElementById('cw-modal-overlay').classList.remove('cw-hidden');
}

function closeModal() {
  document.getElementById('cw-modal-overlay').classList.add('cw-hidden');
}

function teacherChecklistHTML(idPrefix, preselectedIds = new Set()) {
  if (!directory.teachers.length) return '<p class="cw-empty-msg">등록된 교사가 없습니다.</p>';
  return `<div class="cw-checklist">${directory.teachers.map(t => `
    <label class="cw-check-row">
      <input type="checkbox" data-type="user" data-id="${t.id}" id="${idPrefix}-u-${t.id}" ${preselectedIds.has(t.id) ? 'checked' : ''} />
      <span>${t.name}</span>
      <span class="cw-check-sub">${t.department || ''}</span>
    </label>`).join('')}</div>`;
}

function groupChecklistHTML(idPrefix, preselectedIds = new Set()) {
  if (!directory.groups.length) return '<p class="cw-empty-msg">등록된 그룹이 없습니다.</p>';
  return `<div class="cw-checklist">${directory.groups.map(g => `
    <label class="cw-check-row">
      <input type="checkbox" data-type="group" data-id="${g.id}" id="${idPrefix}-g-${g.id}" ${preselectedIds.has(g.id) ? 'checked' : ''} />
      <span>#${g.name}</span>
      <span class="cw-check-sub">${g.member_count || 0}명</span>
    </label>`).join('')}</div>`;
}

// 대상 불러오기: 그룹 + 교사를 함께 보여주고, 체크한 대상을 한번에 추가
async function openTargetPicker() {
  if (!directoryLoaded) await loadDirectory();
  const preselectedGroups = new Set(selectedRecipients.filter(r => r.type === 'group').map(r => r.id));
  const preselectedUsers  = new Set(selectedRecipients.filter(r => r.type === 'user').map(r => r.id));

  const body = `
    <label class="cw-field-label">그룹</label>
    ${groupChecklistHTML('cw-pick', preselectedGroups)}
    <label class="cw-field-label">교사</label>
    ${teacherChecklistHTML('cw-pick', preselectedUsers)}
  `;

  openModal('대상 불러오기', body, '선택 완료', () => {
    const checked = document.querySelectorAll('#cw-modal-body input[type="checkbox"]:checked');
    checked.forEach(cb => {
      const id = Number(cb.dataset.id);
      if (cb.dataset.type === 'group') {
        const group = directory.groups.find(g => g.id === id);
        if (group) addRecipient({ type: 'group', id, name: group.name });
      } else {
        const teacher = directory.teachers.find(t => t.id === id);
        if (teacher) addRecipient({ type: 'user', id, name: teacher.name });
      }
    });
    closeModal();
  });
}

// 그룹 만들기: 이름 지정 + 대상 교사 선택 후 저장, 저장된 그룹은 바로 대상자로 추가됨
async function openGroupCreator() {
  if (!directoryLoaded) await loadDirectory();
  const body = `
    <div class="cw-field">
      <label>그룹 이름 <span class="cw-req">*</span></label>
      <input id="cw-group-name" type="text" placeholder="예: 3학년 담임" />
    </div>
    <label class="cw-field-label">그룹에 포함할 교사</label>
    ${teacherChecklistHTML('cw-group-pick')}
  `;
  openModal('그룹 만들기', body, '그룹 저장', async () => {
    const name = document.getElementById('cw-group-name').value.trim();
    if (!name) {
      alert('그룹 이름을 입력해주세요.');
      return;
    }
    const memberIds = [...document.querySelectorAll('#cw-modal-body input[type="checkbox"]:checked')]
      .map(cb => Number(cb.dataset.id));

    const actionBtn = document.getElementById('cw-modal-action');
    actionBtn.disabled = true;
    try {
      const group = await createGroup({ name, memberIds });
      directory.groups.push(group);
      addRecipient({ type: 'group', id: group.id, name: group.name });
      closeModal();
    } catch (err) {
      alert(err.message);
    } finally {
      actionBtn.disabled = false;
    }
  });
}

// ── 스파클 & 뱃지 ──────────────────────────────────────
const SPARK_COLORS = ['#b7e4c7', '#a8dadc', '#ffd180', '#f4c2c2', '#d4b4f0', '#ffffff'];

function spawnSparkles() {
  const btn = document.getElementById('cw-btn');
  for (let i = 0; i < 10; i++) {
    const s = document.createElement('div');
    s.className = 'cw-sparkle';
    s.style.setProperty('--angle', `${(i / 10) * 360}deg`);
    s.style.setProperty('--dist',  `${28 + Math.random() * 22}px`);
    s.style.background     = SPARK_COLORS[i % SPARK_COLORS.length];
    s.style.animationDelay = `${Math.random() * 0.25}s`;
    btn.appendChild(s);
    s.addEventListener('animationend', () => s.remove());
  }
}

function shakeBtn() {
  const btn = document.getElementById('cw-btn');
  btn.classList.add('cw-shake');
  btn.addEventListener('animationend', () => btn.classList.remove('cw-shake'), { once: true });
}

function updateBadge() {
  const data  = alertNotices();
  const badge = document.getElementById('cw-badge');
  const btn   = document.getElementById('cw-btn');
  if (!badge) return;

  if (data.length) {
    badge.textContent = data.length;
    badge.classList.remove('cw-badge-off');
    btn.classList.add('cw-has-notif');
    if (data.length > prevUrgentCount) {
      spawnSparkles();
      shakeBtn();
    }
  } else {
    badge.classList.add('cw-badge-off');
    btn.classList.remove('cw-has-notif');
  }
  prevUrgentCount = data.length;
}

// ── 눈 깜빡임 ─────────────────────────────────────────
function startBlink() {
  function blink() {
    const el = document.getElementById('cw-eye-l');
    const er = document.getElementById('cw-eye-r');
    if (!el) return;
    el.setAttribute('ry', '0.4');
    er.setAttribute('ry', '0.4');
    setTimeout(() => { el.setAttribute('ry', '3'); er.setAttribute('ry', '3'); }, 140);
    setTimeout(blink, 2800 + Math.random() * 3000);
  }
  setTimeout(blink, 1800);
}

// ── 패널 / 탭 ─────────────────────────────────────────
async function openPanel() {
  panelOpen = true;
  document.getElementById('cw-panel').classList.remove('cw-panel-closed');
  try {
    await Promise.all([fetchNotices(), directoryLoaded ? Promise.resolve() : loadDirectory()]);
  } catch (err) {
    console.error(err);
  }
  refreshTab();
}

function closePanel() {
  panelOpen = false;
  document.getElementById('cw-panel').classList.add('cw-panel-closed');
  alertDetailId = null;
  listDetailId  = null;
}

function switchTab(name) {
  activeTab = name;
  document.querySelectorAll('.cw-tab').forEach(b =>
    b.classList.toggle('active', b.dataset.ctab === name));
  document.querySelectorAll('.cw-tab-content').forEach(p =>
    p.classList.toggle('active', p.id === `ctab-${name}`));
  refreshTab();
}

function refreshTab() {
  if (activeTab === 'alerts') renderAlerts();
  if (activeTab === 'list')   renderAll();
  updateBadge();
}

// ── 폼 제출 ───────────────────────────────────────────
async function handleSubmit(e) {
  e.preventDefault();
  const title    = document.getElementById('cw-f-title').value.trim();
  const content  = document.getElementById('cw-f-content').value.trim();
  const deadline = document.getElementById('cw-f-deadline').value;

  const recipientUserIds  = selectedRecipients.filter(r => r.type === 'user').map(r => r.id);
  const recipientGroupIds = selectedRecipients.filter(r => r.type === 'group').map(r => r.id);

  const submitBtn = e.target.querySelector('button[type="submit"]');
  submitBtn.disabled = true;

  try {
    await createNotice({ title, content, deadline, recipientUserIds, recipientGroupIds });
  } catch (err) {
    alert(err.message);
    submitBtn.disabled = false;
    return;
  }
  submitBtn.disabled = false;

  e.target.reset();
  document.getElementById('cw-f-deadline').value = new Date().toISOString().split('T')[0];
  selectedRecipients = [];
  renderChips();

  const msg = document.getElementById('cw-success-msg');
  msg.classList.remove('cw-hidden');
  spawnSparkles();

  setTimeout(() => {
    msg.classList.add('cw-hidden');
    switchTab('list');
  }, 1800);

  updateBadge();
}

// ── 로그인 감시 ───────────────────────────────────────
function watchLoginState() {
  const app  = document.getElementById('app');
  const root = document.getElementById('cw-root');
  if (!app) return;

  const sync = async () => {
    if (!app.classList.contains('hidden')) {
      root.classList.remove('cw-hidden');
      loadDismissed();
      try {
        await fetchNotices();
      } catch (err) {
        console.error(err);
      }
      updateBadge();
      startBlink();
    } else {
      root.classList.add('cw-hidden');
      closePanel();
    }
  };
  new MutationObserver(sync).observe(app, { attributes: true, attributeFilter: ['class'] });
  sync();
}

// ── 초기화 ────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  document.body.insertAdjacentHTML('beforeend', buildHTML());

  document.getElementById('cw-btn').addEventListener('click', () =>
    panelOpen ? closePanel() : openPanel());

  document.getElementById('cw-close-btn').addEventListener('click', closePanel);

  document.querySelectorAll('.cw-tab').forEach(b =>
    b.addEventListener('click', () => switchTab(b.dataset.ctab)));

  const mentionInput = document.getElementById('cw-mention-input');
  mentionInput.addEventListener('input', handleMentionInput);
  mentionInput.addEventListener('keydown', handleMentionKeydown);
  mentionInput.addEventListener('blur', () => {
    setTimeout(() => { mentionMatches = []; mentionHighlight = -1; renderMentionDropdown(); }, 150);
  });
  mentionInput.addEventListener('focus', () => { if (!directoryLoaded) loadDirectory(); });

  document.getElementById('cw-load-targets-btn').addEventListener('click', openTargetPicker);
  document.getElementById('cw-create-group-btn').addEventListener('click', openGroupCreator);

  document.getElementById('cw-modal-close').addEventListener('click', closeModal);
  document.getElementById('cw-modal-overlay').addEventListener('click', (e) => {
    if (e.target.id === 'cw-modal-overlay') closeModal();
  });

  document.getElementById('cw-form').addEventListener('submit', handleSubmit);

  document.getElementById('cw-alert-ack-btn').addEventListener('click', acknowledgeAlert);
  document.getElementById('cw-list-back-btn').addEventListener('click', backToList);
  document.getElementById('cw-list-complete-btn').addEventListener('click', markComplete);

  watchLoginState();
});
