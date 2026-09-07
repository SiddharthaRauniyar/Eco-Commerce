(() => {
  const range = document.querySelector("[data-report-range]");
  range?.addEventListener("change", () => range.form.requestSubmit());

  const chart = document.getElementById("daily-sales-chart");
  const source = document.getElementById("daily-sales-data");
  if (!chart || !source || !window.Chart) return;

  const rows = JSON.parse(source.textContent);
  new window.Chart(chart, {
    type: "line",
    data: {
      labels: rows.map((row) => row.label),
      datasets: [{
        label: "Paid revenue (USD)",
        data: rows.map((row) => Number(row.revenue)),
        borderColor: "#635bff",
        backgroundColor: "rgba(99, 91, 255, 0.14)",
        borderWidth: 2,
        tension: 0.3,
        fill: true,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        y: { beginAtZero: true, ticks: { callback: (value) => `USD ${value}` } },
        x: { grid: { display: false } },
      },
    },
  });
})();
