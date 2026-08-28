// 큐브 캐릭터 위젯 — 공지 등록 / 알림 / 목록
// 담당: hbn2814

import { createNotice, getNotices, fetchNotices, calcDday, extractMentions } from './notice.js';

// ── State ──────────────────────────────────────────────
let panelOpen  = false;
let activeTab  = 'register';
let mentionedTeachers = [];
let prevUrgentCount   = 0;

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
        <button class="cw-tab active" data-ctab="register">✏️ 등록</button>
        <button class="cw-tab"        data-ctab="alerts">🔔 알림</button>
        <button class="cw-tab"        data-ctab="list">📋 목록</button>
      </div>
      <button id="cw-close-btn" class="cw-close-btn" aria-label="닫기">✕</button>
    </div>

    <div class="cw-panel-body">

      <!-- ① 등록 탭 -->
      <div class="cw-tab-content active" id="ctab-register">
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
          <div class="cw-field">
            <label>대상 교사 <span class="cw-hint">이름 입력 후 Enter</span></label>
            <input id="cw-mention-input" type="text" placeholder="예: 방인배" />
            <div id="cw-chips" class="cw-chips"></div>
          </div>
          <button type="submit" class="cw-submit-btn">공지 등록하기</button>
        </form>
        <div id="cw-success-msg" class="cw-success-msg cw-hidden">🎉 공지가 등록되었습니다!</div>
      </div>

      <!-- ② 알림 탭 -->
      <div class="cw-tab-content" id="ctab-alerts">
        <p class="cw-alert-desc">D-10 이내 마감 공지를 표시합니다.</p>
        <ul id="cw-alerts-list" class="cw-list-ui"></ul>
        <p id="cw-alerts-empty" class="cw-empty-msg cw-hidden">알림이 없습니다 😊</p>
      </div>

      <!-- ③ 목록 탭 -->
      <div class="cw-tab-content" id="ctab-list">
        <ul id="cw-all-list" class="cw-list-ui"></ul>
        <p id="cw-list-empty" class="cw-empty-msg cw-hidden">등록된 공지가 없습니다.</p>
      </div>

    </div>
  </div>
</div>`;
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
    if (!n.deadline) return false;
    const d = new Date(n.deadline); d.setHours(0, 0, 0, 0);
    return Math.round((d - today) / 86400000) <= 10;
  });
}

// ── 멘션 chips HTML ──────────────────────────────────
function mentionChipsHTML(list) {
  if (!list?.length) return '';
  return `<div class="cw-item-mentions">${list.map(t => `<span class="cw-mchip">@${t}</span>`).join('')}</div>`;
}

// ── 렌더 ──────────────────────────────────────────────
function renderAlerts() {
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
      <li class="cw-alert-item cw-urg-${urg}">
        <span class="cw-dday-chip cw-urg-${urg}">${dd}</span>
        <div class="cw-item-body">
          <div class="cw-item-title">${n.title}</div>
          ${mentionChipsHTML(n.mentionedTeachers)}
        </div>
      </li>`;
  }).join('');
}

function renderAll() {
  const list  = document.getElementById('cw-all-list');
  const empty = document.getElementById('cw-list-empty');
  const data  = getNotices();

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
      <li class="cw-list-item">
        ${dd ? `<span class="cw-dday-chip cw-urg-${urg}">${dd}</span>` : ''}
        <div class="cw-item-body">
          <div class="cw-item-title">${n.title}</div>
          ${n.content ? `<div class="cw-item-content">${n.content}</div>` : ''}
          ${mentionChipsHTML(n.mentionedTeachers)}
        </div>
      </li>`;
  }).join('');
}

// ── Mention chip 관리 ─────────────────────────────────
function renderChips() {
  const c = document.getElementById('cw-chips');
  if (!c) return;
  c.innerHTML = mentionedTeachers.map(name =>
    `<span class="cw-chip">@${name}
       <button type="button" class="cw-chip-del" data-name="${name}">×</button>
     </span>`
  ).join('');
  c.querySelectorAll('.cw-chip-del').forEach(btn => {
    btn.onclick = () => {
      mentionedTeachers = mentionedTeachers.filter(t => t !== btn.dataset.name);
      renderChips();
    };
  });
}

function addMention(raw) {
  const name = raw.trim().replace(/^@/, '');
  if (name && !mentionedTeachers.includes(name)) {
    mentionedTeachers.push(name);
    renderChips();
  }
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
    await fetchNotices();
  } catch (err) {
    console.error(err);
  }
  refreshTab();
}

function closePanel() {
  panelOpen = false;
  document.getElementById('cw-panel').classList.add('cw-panel-closed');
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

  const fromContent = extractMentions(content);
  const allMentions = [...new Set([...mentionedTeachers, ...fromContent])];

  const submitBtn = e.target.querySelector('button[type="submit"]');
  submitBtn.disabled = true;

  try {
    await createNotice({ title, content, deadline, mentionedTeachers: allMentions });
  } catch (err) {
    alert(err.message);
    submitBtn.disabled = false;
    return;
  }
  submitBtn.disabled = false;

  e.target.reset();
  document.getElementById('cw-f-deadline').value = new Date().toISOString().split('T')[0];
  mentionedTeachers = [];
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

  document.getElementById('cw-mention-input').addEventListener('keydown', e => {
    if (e.key === 'Enter') {
      e.preventDefault();
      addMention(e.target.value);
      e.target.value = '';
    }
  });

  document.getElementById('cw-form').addEventListener('submit', handleSubmit);

  watchLoginState();
});
