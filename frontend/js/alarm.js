// 스마트 알람 (담당: ada3verse) - 접속 시 오늘 1회만, 마감 임박도에 따라 팝업 강도 다르게
(function () {
  const API_BASE = "http://127.0.0.1:8000";
  const STORAGE_KEY = "cube_alarm_seen";

  function todayKey() {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  }

  function alreadyShownToday(userId) {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return false;
      const seen = JSON.parse(raw);
      return seen.date === todayKey() && seen.userId === userId;
    } catch {
      return false;
    }
  }

  function markShownToday(userId) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ date: todayKey(), userId }));
    } catch {
      /* localStorage 사용 불가 시 무시 (매 접속마다 재평가됨) */
    }
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
    return `D-${diff}`;
  }

  // 이 대역(0~7일)에서는 항상 D-DAY(빨강) 또는 임박(D-3 이내, 주황) 뱃지만 나오므로 그대로 재사용
  function urgency(diff) {
    if (diff === 0) return "today";
    return diff <= 3 ? "soon" : "safe";
  }

  async function fetchRelevantAnnouncements(user) {
    try {
      const res = await fetch(`${API_BASE}/notices`);
      if (!res.ok) throw new Error("요청 실패");
      const all = await res.json();
      return all.filter((a) => {
        if (!a.deadline) return false;
        if (!a.target_group) return true;
        return a.target_group === user.department;
      });
    } catch {
      return [];
    }
  }

  // 4주 전/2주 전: 알람 없음(캘린더 초록 뱃지만) / 1주 전(4~7일): 소프트 / 3일 전(1~3일): 경고 / 당일: 전면
  function pickBand(announcements) {
    const withDiff = announcements
      .map((a) => ({ ...a, diff: diffDays(a.deadline) }))
      .filter((a) => a.diff >= 0 && a.diff <= 7);

    const ddayItems = withDiff.filter((a) => a.diff === 0);
    if (ddayItems.length > 0) return { level: "dday", items: ddayItems };

    const warnItems = withDiff.filter((a) => a.diff >= 1 && a.diff <= 3);
    if (warnItems.length > 0) return { level: "warn", items: warnItems };

    const softItems = withDiff.filter((a) => a.diff >= 4 && a.diff <= 7);
    if (softItems.length > 0) return { level: "soft", items: softItems };

    return { level: "none", items: [] };
  }

  function itemsListHtml(items) {
    return `
      <ul class="alarm-item-list">
        ${items
          .map(
            (a) => `
          <li>
            <span class="dday-badge dday-${urgency(a.diff)}">${ddayLabel(a.diff)}</span>
            <span>${a.title}</span>
          </li>`
          )
          .join("")}
      </ul>`;
  }

  function showSoftPopup(items) {
    const popup = document.getElementById("alarm-soft-popup");
    if (!popup) return;
    popup.innerHTML = `
      <div class="popup-header">다음 주 마감 예정 일정이 있습니다</div>
      ${itemsListHtml(items)}
      <button id="alarm-soft-close">닫기</button>
    `;
    popup.classList.remove("hidden");
    document
      .getElementById("alarm-soft-close")
      ?.addEventListener("click", () => popup.classList.add("hidden"));
  }

  function showWarnPopup(items) {
    const popup = document.getElementById("alarm-warn-popup");
    if (!popup) return;
    popup.innerHTML = `
      <div class="popup-header popup-header-warn">3일 후 마감! 확인이 필요한 일정이 있습니다</div>
      ${itemsListHtml(items)}
      <button id="alarm-warn-close">닫기</button>
    `;
    popup.classList.remove("hidden");
    document
      .getElementById("alarm-warn-close")
      ?.addEventListener("click", () => popup.classList.add("hidden"));
  }

  // 확인 버튼으로만 닫힘 (X 버튼 없음, 배경 클릭으로도 닫히지 않음)
  function showDdayModal(items) {
    const modal = document.getElementById("alarm-dday-modal");
    const body = document.getElementById("alarm-dday-body");
    if (!modal || !body) return;
    body.innerHTML = `
      <p class="alarm-dday-message">오늘 마감인 일정이 있습니다!</p>
      ${itemsListHtml(items)}
      <button id="alarm-dday-confirm" class="btn btn-primary">확인</button>
    `;
    modal.classList.remove("hidden");
    document
      .getElementById("alarm-dday-confirm")
      ?.addEventListener("click", () => modal.classList.add("hidden"));
  }

  async function runSmartAlarm(user) {
    if (!user || alreadyShownToday(user.id)) return;

    const relevant = await fetchRelevantAnnouncements(user);
    const { level, items } = pickBand(relevant);

    if (level === "dday") showDdayModal(items);
    else if (level === "warn") showWarnPopup(items);
    else if (level === "soft") showSoftPopup(items);

    markShownToday(user.id);
  }

  window.runSmartAlarm = runSmartAlarm;
})();
