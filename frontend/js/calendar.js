// 캘린더 메인화면 (담당: ada3verse) - 4주 단위 뷰(현재 주가 둘째 줄) + 공유/개인 일정 + 날짜 클릭 상세 모달
(function () {
  const API_BASE = "http://127.0.0.1:8000";
  const WEEKS_VISIBLE = 4;
  const CURRENT_ROW_INDEX = 1; // 둘째 줄 = 현재 주
  const WEEKDAY_LABELS = ["일", "월", "화", "수", "목", "금", "토"];
  const SCROLL_DEBOUNCE_MS = 300;

  const rangeEl = document.getElementById("calendar-range");
  const bodyEl = document.getElementById("calendar-body");
  const wrapEl = document.getElementById("calendar-scroll-area");
  const prevBtn = document.getElementById("prev-week");
  const nextBtn = document.getElementById("next-week");
  const modal = document.getElementById("day-modal");
  const modalTitle = document.getElementById("modal-date-title");
  const modalBody = document.getElementById("modal-body");
  const modalClose = document.getElementById("modal-close");

  if (!rangeEl || !bodyEl || !prevBtn || !nextBtn) return;

  function startOfWeek(date) {
    const d = new Date(date);
    d.setHours(0, 0, 0, 0);
    d.setDate(d.getDate() - d.getDay());
    return d;
  }

  // viewStart = 첫째 줄(1주 전)의 시작일. viewStart + 7일 = 둘째 줄(현재 주 표시 위치).
  let viewStart = startOfWeek(new Date());
  viewStart.setDate(viewStart.getDate() - 7);

  let announcements = [];
  let personalEvents = [];
  let scrollLock = false;
  let openDateKey = null; // 현재 모달에 열려 있는 날짜 (재조회 후 다시 그리기 위함)

  function getTeacherName() {
    const user = typeof getCurrentUser === "function" ? getCurrentUser() : null;
    return user ? user.name : null;
  }

  function toDateKey(d) {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return `${y}-${m}-${day}`;
  }

  function toDisplayDate(d) {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return `${y}.${m}.${day}`;
  }

  function diffDays(dateStr) {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const target = new Date(dateStr);
    target.setHours(0, 0, 0, 0);
    return Math.round((target - today) / (1000 * 60 * 60 * 24));
  }

  function ddayLabel(diff) {
    if (diff === 0) return "D-DAY";
    if (diff > 0) return `D-${diff}`;
    return `D+${Math.abs(diff)}`;
  }

  // D-DAY: 빨강 / 임박(D-3 이내): 주황 / 그 외 여유: 초록 / 지난 마감: 회색
  function urgency(diff) {
    if (diff < 0) return "past";
    if (diff === 0) return "today";
    if (diff <= 3) return "soon";
    return "safe";
  }

  function statusTag(deadline) {
    if (!deadline) return "진행중";
    const diff = diffDays(deadline);
    if (diff < 0) return "완료";
    if (diff <= 3) return "임박";
    return "예정";
  }

  async function loadAnnouncements() {
    try {
      const res = await fetch(`${API_BASE}/notices`);
      if (!res.ok) throw new Error("요청 실패");
      const all = await res.json();

      const user = typeof getCurrentUser === "function" ? getCurrentUser() : null;
      announcements = all.filter((a) => {
        if (!a.deadline) return false; // 캘린더에는 마감일 있는 항목만 표시
        if (!a.target_group) return true; // 전체 공개
        return !!user && a.target_group === user.department;
      });
    } catch {
      announcements = [];
    }
    render();
  }

  async function loadPersonalEvents() {
    const teacherName = getTeacherName();
    if (!teacherName) {
      personalEvents = [];
      render();
      return;
    }
    try {
      const res = await fetch(
        `${API_BASE}/personal-events?teacher_name=${encodeURIComponent(teacherName)}`
      );
      if (!res.ok) throw new Error("요청 실패");
      personalEvents = await res.json();
    } catch {
      personalEvents = [];
    }
    render();
  }

  function announcementsOn(dateKey) {
    return announcements.filter((a) => a.deadline === dateKey);
  }

  function personalEventsOn(dateKey) {
    return personalEvents.filter((p) => p.date === dateKey);
  }

  function render() {
    const focusWeekStart = new Date(viewStart);
    focusWeekStart.setDate(focusWeekStart.getDate() + CURRENT_ROW_INDEX * 7);
    const focusWeekEnd = new Date(focusWeekStart);
    focusWeekEnd.setDate(focusWeekEnd.getDate() + 6);
    rangeEl.textContent = `${toDisplayDate(focusWeekStart)} - ${toDisplayDate(focusWeekEnd)}`;

    const today = new Date();
    today.setHours(0, 0, 0, 0);

    bodyEl.innerHTML = "";

    for (let week = 0; week < WEEKS_VISIBLE; week++) {
      const row = document.createElement("tr");

      for (let day = 0; day < 7; day++) {
        const cellDate = new Date(viewStart);
        cellDate.setDate(cellDate.getDate() + week * 7 + day);
        const dateKey = toDateKey(cellDate);

        const cell = document.createElement("td");
        if (cellDate.getTime() === today.getTime()) {
          cell.classList.add("today");
        }

        const dayNumber = document.createElement("div");
        dayNumber.className = "day-number";
        dayNumber.textContent = cellDate.getDate();
        cell.appendChild(dayNumber);

        const sharedItems = announcementsOn(dateKey);
        const personalItems = personalEventsOn(dateKey);
        if (sharedItems.length > 0 || personalItems.length > 0) {
          const dotRow = document.createElement("div");
          dotRow.className = "day-dot-row";

          if (sharedItems.length > 0) {
            const dot = document.createElement("span");
            dot.className = "day-dot day-dot-shared";
            dot.title = `공유 일정 ${sharedItems.length}건`;
            dotRow.appendChild(dot);
          }
          if (personalItems.length > 0) {
            const dot = document.createElement("span");
            dot.className = "day-dot day-dot-personal";
            dot.title = `개인 일정 ${personalItems.length}건`;
            dotRow.appendChild(dot);
          }

          cell.appendChild(dotRow);
        }

        cell.addEventListener("click", () => openModal(cellDate, dateKey));
        row.appendChild(cell);
      }

      bodyEl.appendChild(row);
    }
  }

  function sharedSectionHtml(dateKey) {
    const items = announcementsOn(dateKey);
    if (items.length === 0) {
      return `<p class="modal-empty-small">공유 일정이 없습니다.</p>`;
    }

    // 같은 날짜 = 같은 마감일/남은 기한이므로 뱃지·상태는 그룹 상단에 한 번만 표시
    const diff = diffDays(dateKey);
    const status = statusTag(dateKey);

    return `
      <div class="modal-group-header">
        <span class="dday-badge dday-${urgency(diff)}">${ddayLabel(diff)}</span>
        <span class="status-tag status-tag-${status}">${status}</span>
        <span class="modal-group-count">${items.length}건</span>
      </div>
      <div class="modal-group-list">
        ${items
          .map(
            (a) => `
          <div class="modal-item">
            <div class="modal-item-title">${a.title}</div>
            ${a.content ? `<div class="modal-item-content">${a.content}</div>` : ""}
          </div>`
          )
          .join("")}
      </div>`;
  }

  function personalSectionHtml(dateKey) {
    const items = personalEventsOn(dateKey);
    const list =
      items.length === 0
        ? `<p class="modal-empty-small">개인 일정이 없습니다.</p>`
        : items
            .map(
              (p) => `
          <div class="personal-event-item" data-id="${p.id}">
            <div class="personal-event-text">
              <div class="personal-event-title">${p.title}</div>
              ${p.memo ? `<div class="personal-event-memo">${p.memo}</div>` : ""}
            </div>
            <button class="personal-event-delete" data-id="${p.id}" title="삭제">&times;</button>
          </div>`
            )
            .join("");

    return `
      ${list}
      <button id="personal-event-add-btn" class="personal-event-add-btn">+ 개인 일정 추가</button>
      <form id="personal-event-form" class="personal-event-form hidden">
        <input id="personal-event-title" type="text" placeholder="제목" required />
        <textarea id="personal-event-memo" rows="2" placeholder="메모 (선택)"></textarea>
        <div class="personal-event-form-actions">
          <button type="submit" class="btn btn-primary">저장</button>
          <button type="button" id="personal-event-cancel" class="btn btn-ghost">취소</button>
        </div>
      </form>`;
  }

  function renderModalBody(dateKey) {
    modalBody.innerHTML = `
      <div class="modal-section">
        <div class="modal-section-title"><span class="modal-section-dot shared"></span>공유 일정</div>
        ${sharedSectionHtml(dateKey)}
      </div>
      <div class="modal-section">
        <div class="modal-section-title"><span class="modal-section-dot personal"></span>개인 일정</div>
        ${personalSectionHtml(dateKey)}
      </div>`;

    bindPersonalEventHandlers(dateKey);
  }

  function bindPersonalEventHandlers(dateKey) {
    modalBody.querySelectorAll(".personal-event-delete").forEach((btn) => {
      btn.addEventListener("click", async () => {
        await deletePersonalEvent(btn.dataset.id);
      });
    });

    const addBtn = document.getElementById("personal-event-add-btn");
    const form = document.getElementById("personal-event-form");
    const cancelBtn = document.getElementById("personal-event-cancel");

    addBtn?.addEventListener("click", () => {
      addBtn.classList.add("hidden");
      form.classList.remove("hidden");
      document.getElementById("personal-event-title")?.focus();
    });

    cancelBtn?.addEventListener("click", () => {
      form.classList.add("hidden");
      addBtn.classList.remove("hidden");
      form.reset();
    });

    form?.addEventListener("submit", async (e) => {
      e.preventDefault();
      const title = document.getElementById("personal-event-title").value.trim();
      const memo = document.getElementById("personal-event-memo").value.trim();
      if (!title) return;
      await createPersonalEvent(dateKey, title, memo);
    });
  }

  async function createPersonalEvent(dateKey, title, memo) {
    const teacherName = getTeacherName();
    if (!teacherName) return;

    try {
      await fetch(`${API_BASE}/personal-events`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ teacher_name: teacherName, title, date: dateKey, memo: memo || null }),
      });
    } catch {
      /* 네트워크 오류 시 조용히 무시 (프로토타입) */
    }

    await loadPersonalEvents();
    if (openDateKey === dateKey) renderModalBody(dateKey);
  }

  async function deletePersonalEvent(id) {
    try {
      await fetch(`${API_BASE}/personal-events/${id}`, { method: "DELETE" });
    } catch {
      /* 네트워크 오류 시 조용히 무시 (프로토타입) */
    }

    await loadPersonalEvents();
    if (openDateKey) renderModalBody(openDateKey);
  }

  function openModal(cellDate, dateKey) {
    if (!modal) return;

    openDateKey = dateKey;
    modalTitle.textContent = `${toDisplayDate(cellDate)} (${WEEKDAY_LABELS[cellDate.getDay()]})`;
    renderModalBody(dateKey);
    modal.classList.remove("hidden");
  }

  function closeModal() {
    modal.classList.add("hidden");
    openDateKey = null;
  }

  function goToWeek(deltaWeeks) {
    viewStart.setDate(viewStart.getDate() + deltaWeeks * 7);
    render();
  }

  prevBtn.addEventListener("click", () => goToWeek(-1));
  nextBtn.addEventListener("click", () => goToWeek(1));

  // 위로 스크롤 = 과거 주, 아래로 스크롤 = 미래 주 (한 번 스크롤 = 한 주 이동)
  const scrollTarget = wrapEl || bodyEl;
  scrollTarget.addEventListener(
    "wheel",
    (e) => {
      e.preventDefault();
      if (scrollLock) return;
      scrollLock = true;
      goToWeek(e.deltaY > 0 ? 1 : -1);
      setTimeout(() => {
        scrollLock = false;
      }, SCROLL_DEBOUNCE_MS);
    },
    { passive: false }
  );

  modalClose?.addEventListener("click", closeModal);
  modal?.addEventListener("click", (e) => {
    if (e.target === modal) closeModal();
  });

  render();
  loadAnnouncements();
  loadPersonalEvents();
})();
