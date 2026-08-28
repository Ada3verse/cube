// 제출현황 화면 로직 (담당: yamako8119-ai)
(function () {
  const API_BASE = "http://127.0.0.1:8000";
  const bodyEl = document.getElementById("submission-body");

  if (!bodyEl) return;

  async function loadSubmissions() {
    bodyEl.innerHTML = `<tr><td colspan="3">불러오는 중...</td></tr>`;

    try {
      const res = await fetch(`${API_BASE}/submissions`);
      if (!res.ok) throw new Error("요청 실패");
      const rows = await res.json();
      render(rows);
    } catch {
      bodyEl.innerHTML = `<tr><td colspan="3">제출현황을 불러오지 못했습니다.</td></tr>`;
    }
  }

  function render(rows) {
    if (rows.length === 0) {
      bodyEl.innerHTML = `<tr><td colspan="3">표시할 제출현황이 없습니다.</td></tr>`;
      return;
    }

    bodyEl.innerHTML = rows
      .map(
        (r) => `
        <tr>
          <td>${r.event_title}</td>
          <td>${r.user_name}</td>
          <td>
            ${
              r.is_completed
                ? `<span class="status-done">완료</span>`
                : `<span class="status-pending">미완료</span>`
            }
          </td>
        </tr>`
      )
      .join("");
  }

  loadSubmissions();
})();
