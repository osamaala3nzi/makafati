/* Makafati — Charts & UI helpers */

/**
 * Render a Doughnut chart on the given canvas ID.
 */
function renderDoughnut(canvasId, labels, data, colors) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;

  new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: labels,
      datasets: [{
        data: data,
        backgroundColor: colors,
        borderWidth: 3,
        borderColor: '#ffffff',
        hoverBorderWidth: 4,
        hoverOffset: 8,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      cutout: '68%',
      plugins: {
        legend: { display: false },
        tooltip: {
          rtl: true,
          bodyFont: { family: 'Tajawal', size: 13 },
          titleFont: { family: 'Tajawal', size: 14, weight: 'bold' },
          callbacks: {
            label: ctx => ` ${ctx.parsed.toFixed(0)} ريال`,
          }
        }
      }
    }
  });
}

/**
 * Render a Bar chart for monthly comparison.
 */
function renderBar(canvasId, labels, data, color) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;

  new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: 'المصروف (ريال)',
        data: data,
        backgroundColor: color || '#2563eb',
        borderRadius: 8,
        borderSkipped: false,
      }]
    },
    options: {
      responsive: true,
      plugins: {
        legend: { display: false },
        tooltip: {
          rtl: true,
          bodyFont: { family: 'Tajawal' },
          titleFont: { family: 'Tajawal', weight: 'bold' },
          callbacks: { label: ctx => ` ${ctx.parsed.y.toFixed(0)} ريال` }
        }
      },
      scales: {
        x: { ticks: { font: { family: 'Tajawal' } }, grid: { display: false } },
        y: { ticks: { font: { family: 'Tajawal' } }, beginAtZero: true }
      }
    }
  });
}

/* ─── Animated number counter ─────────────────────── */
function animateCounter(el, target, duration) {
  let start = 0;
  const step = target / (duration / 16);
  const timer = setInterval(() => {
    start += step;
    if (start >= target) { start = target; clearInterval(timer); }
    el.textContent = Math.round(start).toLocaleString('ar-SA');
  }, 16);
}

/* Run counters on KPI values when page loads */
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.kpi-value').forEach(el => {
    const raw = el.textContent.replace(/[^\d.]/g, '');
    const num = parseFloat(raw);
    if (!isNaN(num) && num > 0) {
      el.dataset.target = num;
      // keep the <small> suffix
      const small = el.querySelector('small');
      const suffix = small ? small.outerHTML : '';
      animateCounter({ textContent: '' }, num, 800);
      let start = 0;
      const duration = 800;
      const step = num / (duration / 16);
      const timer = setInterval(() => {
        start += step;
        if (start >= num) { start = num; clearInterval(timer); }
        el.innerHTML = Math.round(start) + ' ' + suffix;
      }, 16);
    }
  });
});
