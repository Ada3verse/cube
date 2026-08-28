// 로그인 / 로그아웃 / 세션 유지 (담당: ada3verse)
const API_BASE = "http://127.0.0.1:8000";
const AUTH_STORAGE_KEY = "cube_user";

function getCurrentUser() {
  try {
    const raw = localStorage.getItem(AUTH_STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function setCurrentUser(user) {
  localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(user));
}

function clearCurrentUser() {
  localStorage.removeItem(AUTH_STORAGE_KEY);
}

// 관리자 전용/본인 소유 확인이 필요한 API 호출 시 요청자 식별용 헤더.
// 이름은 중복 가능 + 비-ASCII라 헤더로 못 옮기므로 로그인 응답의 정수 id를 사용한다.
function authHeader() {
  const user = getCurrentUser();
  return user ? { "X-User-Id": String(user.id) } : {};
}

function showApp(user) {
  document.getElementById("login-screen").classList.add("hidden");
  document.getElementById("app").classList.remove("hidden");
  document.getElementById("current-user-name").textContent = `${user.name}님`;
  if (typeof showGreetingPopup === "function") showGreetingPopup(user);
  if (typeof runSmartAlarm === "function") runSmartAlarm(user);
}

function showLogin() {
  document.getElementById("app").classList.add("hidden");
  document.getElementById("login-screen").classList.remove("hidden");
}

function initAuth() {
  const existingUser = getCurrentUser();
  if (existingUser) {
    showApp(existingUser);
  } else {
    showLogin();
  }

  const form = document.getElementById("login-form");
  const errorEl = document.getElementById("login-error");

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    errorEl.textContent = "";

    const name = document.getElementById("login-name").value.trim();
    const password = document.getElementById("login-password").value;

    try {
      const res = await fetch(`${API_BASE}/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, password }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        errorEl.textContent = err.detail || "로그인에 실패했습니다.";
        return;
      }

      const user = await res.json();
      setCurrentUser(user);
      form.reset();
      showApp(user);
    } catch {
      errorEl.textContent = "서버에 연결할 수 없습니다.";
    }
  });

  document.getElementById("logout-btn").addEventListener("click", () => {
    clearCurrentUser();
    showLogin();
  });
}

document.addEventListener("DOMContentLoaded", initAuth);
