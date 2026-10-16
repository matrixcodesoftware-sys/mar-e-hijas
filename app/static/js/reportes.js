/* Gráficos de la pantalla de reportes. */
(function () {
    "use strict";
    const d = MH.datosJSON("datos-reporte");
    if (!d || !d.grafico) return;
    const g = d.grafico;

    if (d.tipo === "ventas") {
        MH.graficoBarras("g-principal", g.etiquetas, [
            { label: "Facturación", data: g.total, color: "#3a444b" },
            { label: "Ganancia", data: g.ganancia, color: "#d49a3a", tipo: "line" },
        ], { moneda: true });
        if (d.mensual) MH.graficoBarras("g-mensual", d.mensual.etiquetas, [{ label: "Facturación", data: d.mensual.total, color: "#1f7f8f" }], { moneda: true });
        if (g.metodos && g.metodos.etiquetas.length) MH.graficoTorta("g-metodos", g.metodos.etiquetas, g.metodos.total, { moneda: true });
    } else if (d.tipo === "materiales") {
        MH.graficoBarras("g-principal", g.etiquetas, [{ label: "Facturación", data: g.facturacion, color: "#d49a3a" }], { horizontal: true, moneda: true });
    } else if (d.tipo === "clientes") {
        MH.graficoBarras("g-principal", g.etiquetas, [{ label: "Total comprado", data: g.total, color: "#3a444b" }], { horizontal: true, moneda: true });
    } else if (d.tipo === "entregas") {
        MH.graficoBarras("g-principal", g.etiquetas, [
            { label: "Entregadas", data: g.entregadas, color: "#2f7d4f" },
            { label: "Pendientes", data: g.pendientes, color: "#d49a3a" },
            { label: "Canceladas", data: g.canceladas, color: "#b33a2e" },
        ]);
    }

    // Al tocar fechas, pasar el período a "rango"
    const sel = document.getElementById("sel-periodo");
    document.querySelectorAll('input[name="desde"], input[name="hasta"]').forEach((i) =>
        i.addEventListener("change", () => { if (sel) sel.value = "rango"; })
    );
})();
