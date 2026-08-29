// 제출현황 화면 로직 (원 담당: yamako8119-ai, 탭/구분/재안내 기능 추가: hbn2814)
(function () {
  const API_BASE = "http://127.0.0.1:8000";
  const container = document.getElementById("submission-app");
  if (!container) return;

  let allRows = [];
  let activeEventId = null;

  function escapeHtml(value) {
    if (value == null) return "";
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function getCurrentUserId() {
    try {
      const raw = localStorage.getItem("cube_user");
      return raw ? JSON.parse(raw).id : null;
    } catch {
      return null;
    }
  }

  async function loadSubmissions() {
    container.innerHTML = `<p class="submission-msg">불러오는 중...</p>`;
    try {
      const res = await fetch(`${API_BASE}/submissions`);
      if (!res.ok) throw new Error("요청 실패");
      allRows = await res.json();
      if (activeEventId === null && allRows.length) {
        activeEventId = allRows[0].event_id;
      }
      render();
    } catch {
      container.innerHTML = `<p class="submission-msg">제출현황을 불러오지 못했습니다.</p>`;
    }
  }

  function eventGroups() {
    const map = new Map();
    for (const r of allRows) {
      if (!map.has(r.event_id)) {
        map.set(r.event_id, { event_id: r.event_id, title: r.event_title, rows: [] });
      }
      map.get(r.event_id).rows.push(r);
    }
    return [...map.values()];
  }

  function render() {
    const groups = eventGroups();
    if (!groups.length) {
      container.innerHTML = `<p class="submission-msg">표시할 제출현황이 없습니다.</p>`;
      return;
    }
    if (!groups.some((g) => g.event_id === activeEventId)) {
      activeEventId = groups[0].event_id;
    }
    const activeGroup = groups.find((g) => g.event_id === activeEventId);

    const tabsHTML = groups
      .map(
        (g) => `
      <button class="submission-tab ${g.event_id === activeEventId ? "active" : ""}" data-event-id="${g.event_id}">
        ${escapeHtml(g.title)}
      </button>`
      )
      .join("");

    const done = activeGroup.rows.filter((r) => r.is_completed);
    const pending = activeGroup.rows.filter((r) => !r.is_completed);

    container.innerHTML = `
      <div class="submission-tabs">${tabsHTML}</div>
      <div class="submission-toolbar">
        <span class="submission-count">제출 ${done.length} / 전체 ${activeGroup.rows.length}</span>
        <button id="submission-remind-btn" class="btn btn-primary" ${pending.length === 0 ? "disabled" : ""}>
          미제출자에게 재안내 공지 보내기 (${pending.length}명)
        </button>
      </div>
      <div class="submission-columns">
        <div class="submission-col">
          <h3 class="submission-col-title submission-col-pending">미제출 (${pending.length})</h3>
          <ul class="submission-list">
            ${pending.map((r) => rowHTML(r)).join("") || '<li class="submission-empty">없음</li>'}
          </ul>
        </div>
        <div class="submission-col">
          <h3 class="submission-col-title submission-col-done">제출완료 (${done.length})</h3>
          <ul class="submission-list">
            ${done.map((r) => rowHTML(r)).join("") || '<li class="submission-empty">없음</li>'}
          </ul>
        </div>
      </div>
    `;

    container.querySelectorAll(".submission-tab").forEach((btn) => {
      btn.addEventListener("click", () => {
        activeEventId = Number(btn.dataset.eventId);
        render();
      });
    });

    container.querySelectorAll(".submission-row").forEach((li) => {
      li.addEventListener("click", () =>
        toggleStatus(Number(li.dataset.completionId), li.dataset.completed !== "true")
      );
    });

    const remindBtn = document.getElementById("submission-remind-btn");
    if (remindBtn) remindBtn.addEventListener("click", sendReminder);
  }

  function rowHTML(r) {
    return `
      <li class="submission-row" data-completion-id="${r.id}" data-completed="${r.is_completed ? "true" : "false"}" title="클릭하면 상태가 바뀝니다">
        <span class="submission-name">${escapeHtml(r.user_name)}</span>
        <span class="${r.is_completed ? "status-done" : "status-pending"}">${r.is_completed ? "완료" : "미완료"}</span>
      </li>`;
  }

  async function toggleStatus(completionId, nextCompleted) {
    try {
      const res = await fetch(`${API_BASE}/submissions/${completionId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_completed: nextCompleted }),
      });
      if (!res.ok) throw new Error("상태 변경 실패");
      const row = allRows.find((r) => r.id === completionId);
      if (row) row.is_completed = nextCompleted;
      render();
    } catch {
      alert("상태 변경에 실패했습니다.");
    }
  }

  async function sendReminder() {
    const authorId = getCurrentUserId();
    if (!authorId) {
      alert("로그인이 필요합니다.");
      return;
    }
    const btn = document.getElementById("submission-remind-btn");
    btn.disabled = true;
    try {
      const res = await fetch(`${API_BASE}/submissions/remind`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ event_id: activeEventId, author_id: authorId }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "재안내 공지 전송에 실패했습니다.");
      }
      const result = await res.json();
      alert(`${result.recipient_count}명에게 재안내 공지를 보냈습니다.`);
    } catch (err) {
      alert(err.message);
      btn.disabled = false;
    }
  }

  loadSubmissions();
})();
