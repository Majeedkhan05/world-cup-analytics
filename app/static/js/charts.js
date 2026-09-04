/* Small helpers around Chart.js so each template only supplies data. */
Chart.defaults.color = '#8b98a9';
Chart.defaults.borderColor = '#242e3c';
Chart.defaults.font.family = '-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif';
Chart.defaults.font.size = 12;
Chart.defaults.plugins.legend.display = false;
Chart.defaults.maintainAspectRatio = false;

const C = { accent:'#2dd4a7', gold:'#f5c451', blue:'#5aa9f5', red:'#f2686b',
            violet:'#a78bfa', grid:'#1f2833' };

function axes(opts = {}) {
  return {
    x: { grid: { display:false },
         ticks: { maxRotation:0, autoSkipPadding:14, maxTicksLimit: opts.maxTicks || 12 },
         ...opts.x },
    y: { grid: { color: C.grid }, beginAtZero: opts.zero !== false, ...opts.y },
  };
}

/* line chart */
function lineChart(id, labels, data, colour = C.accent, opts = {}) {
  const el = document.getElementById(id); if (!el) return;
  const ctx = el.getContext('2d');
  const fill = ctx.createLinearGradient(0, 0, 0, el.height || 280);
  fill.addColorStop(0, colour + '55'); fill.addColorStop(1, colour + '00');
  return new Chart(ctx, {
    type: 'line',
    data: { labels, datasets: [{ data, borderColor: colour, backgroundColor: fill,
      borderWidth: 2, fill: true, tension: 0.32,
      pointRadius: opts.points === false ? 0 : 2.5, pointBackgroundColor: colour,
      pointHoverRadius: 5 }] },
    options: { scales: axes({ zero: opts.zero, maxTicks: opts.maxTicks }),
      plugins: { tooltip: { intersect:false, mode:'index' } } },
  });
}

/* bar chart (vertical or horizontal).
   `from` sets where the value axis starts — useful for Elo ratings, where
   starting at zero would make every bar look the same length. */
function barChart(id, labels, data, colour = C.accent, horizontal = false, from = 0) {
  const el = document.getElementById(id); if (!el) return;
  const valueAxis = { grid:{ color:C.grid }, beginAtZero: from === 0, min: from || undefined };
  return new Chart(el, {
    type: 'bar',
    data: { labels, datasets: [{ data, backgroundColor: colour,
      borderRadius: 5, borderSkipped: false, barPercentage: 0.72 }] },
    options: { indexAxis: horizontal ? 'y' : 'x',
      scales: horizontal
        ? { x: valueAxis, y: { grid:{ display:false } } }
        : { x: { grid:{ display:false } }, y: valueAxis } },
  });
}

/* doughnut */
function donutChart(id, labels, data, colours) {
  const el = document.getElementById(id); if (!el) return;
  return new Chart(el, {
    type: 'doughnut',
    data: { labels, datasets: [{ data, backgroundColor: colours, borderWidth: 0 }] },
    options: { cutout: '62%',
      plugins: { legend: { display:true, position:'bottom',
        labels:{ boxWidth:9, boxHeight:9, usePointStyle:true, pointStyle:'circle', padding:14 } } } },
  });
}
