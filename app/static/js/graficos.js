/* Helpers de Chart.js con la identidad visual de MAR E HIJAS. */
(function () {
    "use strict";
    const MH = (window.MH = window.MH || {});
    const PALETA = ["#d49a3a", "#3a444b", "#1f7f8f", "#2f7d4f", "#6a4c93", "#b33a2e", "#a9b1b6", "#8f5f18"];
    MH.PALETA = PALETA;

    if (window.Chart) {
        Chart.defaults.font.family = '"Barlow", system-ui, sans-serif';
        Chart.defaults.font.size = 12;
        Chart.defaults.color = "#56626a";
        Chart.defaults.borderColor = "#ebe7df";
        Chart.defaults.plugins.legend.labels.boxWidth = 12;
        Chart.defaults.plugins.legend.labels.usePointStyle = true;
        Chart.defaults.maintainAspectRatio = false;
    }

    const tickMoneda = (v) => {
        const n = Number(v);
        if (Math.abs(n) >= 1e6) return "$ " + (n / 1e6).toLocaleString("es-AR", { maximumFractionDigits: 1 }) + " M";
        if (Math.abs(n) >= 1e3) return "$ " + (n / 1e3).toLocaleString("es-AR", { maximumFractionDigits: 0 }) + " k";
        return "$ " + n.toLocaleString("es-AR");
    };

    function tooltip(esMoneda) {
        return {
            callbacks: {
                label: (ctx) => {
                    const v = ctx.parsed.y ?? ctx.parsed.x ?? ctx.parsed;
                    const val = esMoneda ? MH.moneda(v) : MH.cant(v);
                    return ` ${ctx.dataset.label ? ctx.dataset.label + ": " : ctx.label + ": "}${val}`;
                },
            },
        };
    }

    MH.graficoBarras = function (id, etiquetas, series, opciones = {}) {
        const el = document.getElementById(id);
        if (!el || !window.Chart) return null;
        return new Chart(el, {
            type: "bar",
            data: {
                labels: etiquetas,
                datasets: series.map((s, i) => ({
                    label: s.label, data: s.data, type: s.tipo || "bar",
                    backgroundColor: s.color || PALETA[i % PALETA.length],
                    borderColor: s.color || PALETA[i % PALETA.length],
                    borderRadius: s.tipo === "line" ? 0 : 5, borderWidth: s.tipo === "line" ? 2.5 : 0,
                    tension: 0.3, pointRadius: s.tipo === "line" ? 2 : 0, yAxisID: s.eje || "y", order: s.tipo === "line" ? 0 : 1,
                })),
            },
            options: {
                indexAxis: opciones.horizontal ? "y" : "x",
                plugins: { legend: { display: series.length > 1 }, tooltip: tooltip(opciones.moneda) },
                scales: {
                    x: { grid: { display: !!opciones.horizontal }, ticks: opciones.horizontal && opciones.moneda ? { callback: tickMoneda } : { maxRotation: 0, autoSkip: true } },
                    y: { beginAtZero: true, grid: { display: !opciones.horizontal }, ticks: !opciones.horizontal && opciones.moneda ? { callback: tickMoneda } : {} },
                    ...(opciones.ejeDerecho ? { y2: { position: "right", beginAtZero: true, grid: { display: false } } } : {}),
                },
            },
        });
    };

    MH.graficoTorta = function (id, etiquetas, datos, opciones = {}) {
        const el = document.getElementById(id);
        if (!el || !window.Chart) return null;
        return new Chart(el, {
            type: "doughnut",
            data: { labels: etiquetas, datasets: [{ data: datos, backgroundColor: PALETA, borderWidth: 2, borderColor: "#fff" }] },
            options: {
                cutout: "62%",
                plugins: {
                    legend: { position: "right" },
                    tooltip: { callbacks: { label: (ctx) => ` ${ctx.label}: ${opciones.moneda ? MH.moneda(ctx.parsed) : MH.cant(ctx.parsed)}` } },
                },
            },
        });
    };
})();
