// 알림 + 접속 시 오늘 할 일 팝업
// 담당: hbn2814

import { getNotices, calcDday } from "./notice.js";

const DDAY_ALERT_THRESHOLDS = [10, 7, 5, 3, 1, 0];

function getTodayTasks() {
  return getNotices().filter((n) => {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const deadline = new Date(n.deadline);
    deadline.setHours(0, 0, 0, 0);
    const diffDays = Math.round((deadline - today) / (1000 * 60 * 60 * 24));
    return DDAY_ALERT_THRESHOLDS.includes(diffDays);
  });
}

function showTodayPopup() {
  const tasks = getTodayTasks();
  const popup = document.getElementById("today-popup");
  if (!popup) return;

  if (tasks.length === 0) {
    popup.classList.add("hidden");
    return;
  }

  popup.innerHTML = `
    <div class="popup-header">오늘 확인할 공지</div>
    <ul class="popup-list">
      ${tasks
        .map(
          (t) =>
            `<li><span class="popup-dday">${calcDday(t.deadline)}</span> ${t.title}</li>`
        )
        .join("")}
    </ul>
    <button id="popup-close">닫기</button>
  `;
  popup.classList.remove("hidden");

  document
    .getElementById("popup-close")
    ?.addEventListener("click", () => popup.classList.add("hidden"));
}

document.addEventListener("DOMContentLoaded", showTodayPopup);

export { getTodayTasks, showTodayPopup };
