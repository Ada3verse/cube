// 플로팅 설정 버튼: 글자크기 / 테마 색상 / 비밀번호 변경 / 관리자 페이지 (담당: yamako8119-ai)

const FONT_SIZE_KEY = "cube_font_size";
const THEME_COLOR_KEY = "cube_theme_color";
const FONT_SIZE_PX = { small: "14px", medium: "16px", large: "18px" };

function applyFontSize(size) {
  document.documentElement.style.fontSize = FONT_SIZE_PX[size] || FONT_SIZE_PX.medium;
  document.querySelectorAll(".settings-choice-btn[data-fontsize]").forEach((b) => {
    b.classList.toggle("active", b.dataset.fontsize === size);
  });
}

function setFontSize(size) {
  localStorage.setItem(FONT_SIZE_KEY, size);
  applyFontSize(size);
}

function applyThemeColor(theme) {
  document.documentElement.classList.remove("theme-blue", "theme-lavender", "theme-peach");
  if (theme && theme !== "green") document.documentElement.classList.add(`theme-${theme}`);
  document.querySelectorAll(".theme-swatch-btn[data-theme]").forEach((b) => {
    b.classList.toggle("active", b.dataset.theme === theme);
  });
}

function setThemeColor(theme) {
  localStorage.setItem(THEME_COLOR_KEY, theme);
  applyThemeColor(theme);
}

function showSettingsMenu() {
  document.getElementById("settings-menu").classList.remove("hidden");
  document.querySelectorAll(".settings-panel").forEach((p) => p.classList.add("hidden"));
}

function showSettingsPanel(name) {
  document.getElementById("settings-menu").classList.add("hidden");
  document.querySelectorAll(".settings-panel").forEach((p) => p.classList.add("hidden"));
  document.getElementById(`settings-panel-${name}`).classList.remove("hidden");
}

function openSettingsModal() {
  showSettingsMenu();
  const msgEl = document.getElementById("pw-change-msg");
  msgEl.textContent = "";
  msgEl.style.color = "";
  document.getElementById("password-change-form").reset();
  document.getElementById("settings-modal").classList.remove("hidden");
}

function closeSettingsModal() {
  document.getElementById("settings-modal").classList.add("hidden");
}

function initSettings() {
  // 저장된 개인화 설정을 즉시 반영
  applyFontSize(localStorage.getItem(FONT_SIZE_KEY) || "medium");
  applyThemeColor(localStorage.getItem(THEME_COLOR_KEY) || "green");

  document.getElementById("settings-fab-btn").addEventListener("click", openSettingsModal);
  document.getElementById("settings-modal-close").addEventListener("click", closeSettingsModal);
  document.getElementById("settings-modal").addEventListener("click", (e) => {
    if (e.target.id === "settings-modal") closeSettingsModal();
  });

  document.getElementById("password-change-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const msgEl = document.getElementById("pw-change-msg");
    msgEl.style.color = "";
    msgEl.textContent = "";

    const current = document.getElementById("pw-current").value;
    const next = document.getElementById("pw-new").value;
    const confirm = document.getElementById("pw-confirm").value;

    if (next.length < 4) {
      msgEl.textContent = "새 비밀번호는 4자 이상이어야 합니다.";
      return;
    }
    if (next !== confirm) {
      msgEl.textContent = "새 비밀번호가 서로 일치하지 않습니다.";
      return;
    }

    try {
      const res = await fetch(`${API_BASE}/me/password`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", ...authHeader() },
        body: JSON.stringify({ current_password: current, new_password: next }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        msgEl.textContent = err.detail || "비밀번호 변경에 실패했습니다.";
        return;
      }
      msgEl.style.color = "var(--mint-dark)";
      msgEl.textContent = "비밀번호가 변경되었습니다.";
      document.getElementById("password-change-form").reset();
    } catch {
      msgEl.textContent = "서버에 연결할 수 없습니다.";
    }
  });
}

document.addEventListener("DOMContentLoaded", initSettings);
