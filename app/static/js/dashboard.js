/* Gráficos del dashboard: se cargan por la API para no demorar la página. */
(async function () {
    "use strict";
    let d;
    try {
        d = await MH.api("/api/dashboard/graficos");
    } catch (e) {
        return;
    }
    if (d.por_dia.total) {
        MH.graficoBarras("g-dia", d.por_dia.etiquetas, [
            { label: "Facturación", data: d.por_dia.total, color: "#d49a3a" },
        ], { moneda: true });
    } else {
        MH.graficoBarras("g-dia", d.por_dia.etiquetas, [{ label: "Ventas", data: d.por_dia.cantidad, color: "#d49a3a" }]);
    }
    if (d.por_mes) {
        MH.graficoBarras("g-mes", d.por_mes.etiquetas, [
            { label: "Facturación", data: d.por_mes.total, color: "#3a444b" },
            { label: "Ganancia bruta", data: d.por_mes.ganancia, color: "#d49a3a", tipo: "line" },
        ], { moneda: true });
    }
    if (d.materiales.etiquetas.length) {
        if (d.materiales.facturacion) {
            MH.graficoBarras("g-materiales", d.materiales.etiquetas, [
                { label: "Facturación", data: d.materiales.facturacion, color: "#1f7f8f" },
            ], { horizontal: true, moneda: true });
        } else {
            MH.graficoBarras("g-materiales", d.materiales.etiquetas.map((e, i) => `${e} (${d.materiales.unidades[i]})`), [
                { label: "Cantidad", data: d.materiales.cantidad, color: "#1f7f8f" },
            ], { horizontal: true });
        }
    }
    if (d.metodos && d.metodos.etiquetas.length) {
        MH.graficoTorta("g-metodos", d.metodos.etiquetas, d.metodos.total, { moneda: true });
    }
})();
