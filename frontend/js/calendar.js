// 캘린더 메인화면 (담당: ada3verse)
(function () {
  const titleEl = document.getElementById("calendar-title");
  const bodyEl = document.getElementById("calendar-body");
  const prevBtn = document.getElementById("prev-month");
  const nextBtn = document.getElementById("next-month");

  if (!titleEl || !bodyEl || !prevBtn || !nextBtn) return;

  const today = new Date();
  let viewYear = today.getFullYear();
  let viewMonth = today.getMonth(); // 0-11

  function render() {
    titleEl.textContent = `${viewYear}년 ${viewMonth + 1}월`;

    const firstDay = new Date(viewYear, viewMonth, 1).getDay();
    const lastDate = new Date(viewYear, viewMonth + 1, 0).getDate();

    bodyEl.innerHTML = "";

    let date = 1;
    for (let week = 0; week < 6 && date <= lastDate; week++) {
      const row = document.createElement("tr");

      for (let day = 0; day < 7; day++) {
        const cell = document.createElement("td");

        if (week === 0 && day < firstDay) {
          cell.classList.add("empty");
        } else if (date > lastDate) {
          cell.classList.add("empty");
        } else {
          cell.textContent = date;

          const isToday =
            date === today.getDate() &&
            viewMonth === today.getMonth() &&
            viewYear === today.getFullYear();
          if (isToday) {
            cell.classList.add("today");
          }

          date++;
        }

        row.appendChild(cell);
      }

      bodyEl.appendChild(row);
    }
  }

  prevBtn.addEventListener("click", () => {
    viewMonth--;
    if (viewMonth < 0) {
      viewMonth = 11;
      viewYear--;
    }
    render();
  });

  nextBtn.addEventListener("click", () => {
    viewMonth++;
    if (viewMonth > 11) {
      viewMonth = 0;
      viewYear++;
    }
    render();
  });

  render();
})();
