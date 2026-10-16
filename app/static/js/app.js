/* =====================================================================
   MAR E HIJAS — JavaScript común
   Sin dependencias. Expone window.MH con utilidades usadas por otros scripts.
   ===================================================================== */
(function () {
    "use strict";

    const MH = (window.MH = window.MH || {});
    const ICONOS = document.body.dataset.icons || "/static/img/icons.svg";

    MH.csrf = () => document.querySelector('meta[name="csrf-token"]')?.content || "";

    MH.icon = (nombre, clase = "") =>
        `<svg class="ico ${clase}" aria-hidden="true"><use href="${ICONOS}#i-${nombre}"></use></svg>`;

    MH.esc = (txt) =>
        String(txt ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

    /** fetch JSON con CSRF y manejo de errores homogéneo. */
    MH.api = async function (url, opciones = {}) {
        const cfg = {
            method: opciones.method || "GET",
            headers: { Accept: "application/json", "X-CSRFToken": MH.csrf() },
            credentials: "same-origin",
        };
        if (opciones.body !== undefined) {
            cfg.headers["Content-Type"] = "application/json";
            cfg.body = JSON.stringify(opciones.body);
        }
        const resp = await fetch(url, cfg);
        let datos = null;
        try { datos = await resp.json(); } catch (_) { datos = null; }
        if (resp.status === 401) { window.location.reload(); }
        if (!resp.ok) throw new Error((datos && datos.error) || `Error ${resp.status}`);
        return datos;
    };

    /** Formato argentino. */
    MH.num = (v, dec = 2) => {
        const n = Number(v || 0);
        return n.toLocaleString("es-AR", { minimumFractionDigits: dec, maximumFractionDigits: dec });
    };
    MH.cant = (v) => Number(v || 0).toLocaleString("es-AR", { maximumFractionDigits: 3 });
    MH.moneda = (v) => (Number(v) < 0 ? "-" : "") + "$ " + MH.num(Math.abs(Number(v || 0)), 2);
    MH.parse = (v) => {
        if (typeof v === "number") return v;
        let t = String(v || "").trim().replace(/\$|\s/g, "");
        if (t.includes(",")) t = t.replace(/\./g, "").replace(",", ".");
        const n = parseFloat(t);
        return isNaN(n) ? 0 : n;
    };
    MH.redondear = (v, dec = 2) => Math.round((Number(v) + Number.EPSILON) * 10 ** dec) / 10 ** dec;

    /** Lee datos JSON embebidos: <script type="application/json" id="...">. */
    MH.datosJSON = (id) => {
        const el = document.getElementById(id);
        try { return el ? JSON.parse(el.textContent) : null; } catch (_) { return null; }
    };

    MH.aviso = function (mensaje, tipo = "info") {
        const zona = document.getElementById("flash-zona");
        if (!zona) return alert(mensaje);
        const div = document.createElement("div");
        div.className = `alerta alerta--${tipo}`;
        div.setAttribute("role", "alert");
        div.innerHTML = `<span>${MH.esc(mensaje)}</span><button class="alerta__cerrar" aria-label="Cerrar">${MH.icon("x")}</button>`;
        zona.appendChild(div);
        programarCierre(div);
    };

    function programarCierre(alerta) {
        alerta.querySelector(".alerta__cerrar")?.addEventListener("click", () => alerta.remove());
        if (!alerta.classList.contains("alerta--danger")) {
            setTimeout(() => alerta.remove(), 6000);
        }
    }

    /* ---------------------------------------------------------- sidebar */
    const sidebar = document.getElementById("sidebar");
    const velo = document.getElementById("velo");
    document.getElementById("btn-menu")?.addEventListener("click", () => {
        sidebar.classList.add("abierto");
        velo.classList.add("visible");
    });
    velo?.addEventListener("click", () => {
        sidebar.classList.remove("abierto");
        velo.classList.remove("visible");
    });

    /* ---------------------------------------------------------- dropdowns */
    document.addEventListener("click", (ev) => {
        const disparador = ev.target.closest("[data-dropdown]");
        document.querySelectorAll(".dropdown.abierto").forEach((d) => {
            if (!disparador || d !== disparador.closest(".dropdown")) d.classList.remove("abierto");
        });
        if (disparador) {
            const dd = disparador.closest(".dropdown");
            dd.classList.toggle("abierto");
            if (dd.id === "dd-notif" && dd.classList.contains("abierto")) cargarEstado();
        }
    });

    document.querySelectorAll(".flash-zona .alerta").forEach(programarCierre);

    /* ---------------------------------------------------------- modales */
    document.addEventListener("click", (ev) => {
        const abrir = ev.target.closest("[data-abrir-modal]");
        if (abrir) {
            ev.preventDefault();
            document.getElementById(abrir.dataset.abrirModal)?.showModal();
        }
        const cerrar = ev.target.closest("[data-cerrar-modal]");
        if (cerrar) cerrar.closest("dialog")?.close();
    });

    /* Confirmación con modal propio para formularios con data-confirmar */
    const modalConf = document.getElementById("modal-confirmar");
    let formPendiente = null;
    document.addEventListener("submit", (ev) => {
        const form = ev.target;
        if (form.dataset.confirmar && !form.dataset.confirmado && modalConf) {
            ev.preventDefault();
            formPendiente = form;
            document.getElementById("confirmar-texto").textContent = form.dataset.confirmar;
            document.getElementById("confirmar-titulo").textContent = form.dataset.confirmarTitulo || "Confirmar operación";
            modalConf.showModal();
            return;
        }
        // Evita doble envío
        const btn = form.querySelector('button[type="submit"]:not([data-multi])');
        if (btn && !form.dataset.permitirReenvio) {
            setTimeout(() => { btn.disabled = true; }, 0);
            setTimeout(() => { btn.disabled = false; }, 8000);
        }
    });
    document.getElementById("confirmar-ok")?.addEventListener("click", () => {
        if (formPendiente) {
            formPendiente.dataset.confirmado = "1";
            modalConf.close();
            if (formPendiente.requestSubmit) formPendiente.requestSubmit(); else formPendiente.submit();
            formPendiente = null;
        }
    });

    /* Selects que envían el formulario al cambiar */
    document.querySelectorAll("[data-auto-submit]").forEach((el) =>
        el.addEventListener("change", () => el.form && el.form.submit())
    );

    /* ---------------------------------------------------------- estado: caja + notificaciones */
    const COLORES = { rojo: ["var(--rojo-bg)", "var(--rojo)"], ambar: ["var(--ambar-bg)", "var(--ambar)"], azul: ["var(--azul-bg)", "var(--azul)"], verde: ["var(--verde-bg)", "var(--verde)"] };
    async function cargarEstado() {
        if (!document.getElementById("notif-lista")) return;
        try {
            const d = await MH.api("/api/estado");
            const caja = document.getElementById("caja-estado");
            if (caja && d.caja) {
                caja.hidden = false;
                caja.classList.toggle("caja-estado--abierta", d.caja.abierta);
                caja.classList.toggle("caja-estado--cerrada", !d.caja.abierta);
                caja.querySelector(".txt").textContent = d.caja.abierta ? "Caja abierta" : "Caja cerrada";
                caja.title = d.caja.texto || "";
            }
            const lista = document.getElementById("notif-lista");
            const cont = document.getElementById("notif-contador");
            const items = d.notificaciones || [];
            if (!items.length) {
                lista.innerHTML = '<div class="notif-vacia">No hay novedades.</div>';
                cont.classList.add("hidden");
            } else {
                cont.textContent = items.length > 9 ? "9+" : items.length;
                cont.classList.remove("hidden");
                lista.innerHTML = items.map((n) => {
                    const [bg, fg] = COLORES[n.color] || COLORES.azul;
                    return `<a class="notif" href="${MH.esc(n.url || "#")}">
                        <span class="notif__ico" style="background:${bg};color:${fg}">${MH.icon(n.icono || "bell")}</span>
                        <span><span class="notif__titulo">${MH.esc(n.titulo)}</span><br><span class="notif__texto">${MH.esc(n.texto)}</span></span></a>`;
                }).join("");
            }
        } catch (e) {
            /* silencioso: la barra superior no debe romper la página */
        }
    }
    cargarEstado();
    setInterval(cargarEstado, 120000);

    /* ---------------------------------------------------------- autocompletar */
    MH.Autocompletar = class {
        /**
         * @param {HTMLInputElement} input
         * @param {{url:string, render?:Function, onSelect:Function, minimo?:number, extra?:Function}} cfg
         */
        constructor(input, cfg) {
            this.input = input;
            this.cfg = Object.assign({ minimo: 1 }, cfg);
            this.items = [];
            this.idx = -1;
            this.timer = null;
            const envoltura = document.createElement("div");
            envoltura.className = "autocomp";
            input.parentNode.insertBefore(envoltura, input);
            envoltura.appendChild(input);
            this.lista = document.createElement("div");
            this.lista.className = "autocomp__lista";
            envoltura.appendChild(this.lista);
            input.setAttribute("autocomplete", "off");
            input.addEventListener("input", () => this.programar());
            input.addEventListener("focus", () => { if (input.value.length >= this.cfg.minimo) this.programar(); });
            input.addEventListener("keydown", (e) => this.teclado(e));
            document.addEventListener("click", (e) => { if (!envoltura.contains(e.target)) this.cerrar(); });
        }
        programar() {
            clearTimeout(this.timer);
            this.timer = setTimeout(() => this.buscar(), 220);
        }
        async buscar() {
            const q = this.input.value.trim();
            if (q.length < this.cfg.minimo) return this.cerrar();
            const extra = this.cfg.extra ? this.cfg.extra() : "";
            try {
                const d = await MH.api(`${this.cfg.url}?q=${encodeURIComponent(q)}${extra}`);
                this.items = d.resultados || [];
                this.mostrar();
            } catch (e) { this.cerrar(); }
        }
        mostrar() {
            this.idx = -1;
            if (!this.items.length) {
                this.lista.innerHTML = '<div class="autocomp__item muted">Sin coincidencias</div>';
            } else {
                const render = this.cfg.render || ((it) => `${MH.esc(it.texto)}${it.detalle ? `<small>${MH.esc(it.detalle)}</small>` : ""}`);
                this.lista.innerHTML = this.items.map((it, i) => `<div class="autocomp__item" data-i="${i}">${render(it)}</div>`).join("");
                this.lista.querySelectorAll(".autocomp__item").forEach((el) =>
                    el.addEventListener("mousedown", (e) => { e.preventDefault(); this.elegir(Number(el.dataset.i)); })
                );
            }
            this.lista.classList.add("visible");
        }
        teclado(e) {
            if (!this.lista.classList.contains("visible")) return;
            const els = this.lista.querySelectorAll(".autocomp__item[data-i]");
            if (e.key === "ArrowDown") { e.preventDefault(); this.idx = Math.min(this.idx + 1, els.length - 1); }
            else if (e.key === "ArrowUp") { e.preventDefault(); this.idx = Math.max(this.idx - 1, 0); }
            else if (e.key === "Enter") { if (this.idx >= 0) { e.preventDefault(); this.elegir(this.idx); } return; }
            else if (e.key === "Escape") { this.cerrar(); return; }
            els.forEach((el, i) => el.classList.toggle("activo", i === this.idx));
        }
        elegir(i) {
            const it = this.items[i];
            if (!it) return;
            this.cerrar();
            this.cfg.onSelect(it);
        }
        cerrar() { this.lista.classList.remove("visible"); }
    };

    /**
     * Selector de entidad (cliente/proveedor/material) para formularios simples:
     * <div data-selector="clientes" data-name="cliente_id" data-valor="12" data-texto="Juan Pérez"></div>
     */
    MH.iniciarSelector = function (cont) {
        const tipo = cont.dataset.selector;
        const nombre = cont.dataset.name;
        const url = `/api/${tipo}/buscar`;
        cont.innerHTML = `
            <input type="hidden" name="${MH.esc(nombre)}" value="${MH.esc(cont.dataset.valor || "")}">
            <div class="autocomp__sel ${cont.dataset.valor ? "" : "hidden"}"><span class="sel-texto fw-600">${MH.esc(cont.dataset.texto || "")}</span>
                <button type="button" class="btn btn--fantasma btn--sm" aria-label="Quitar">${MH.icon("x")}</button></div>
            <input type="text" class="input ${cont.dataset.valor ? "hidden" : ""}" placeholder="${MH.esc(cont.dataset.placeholder || "Buscar…")}">`;
        const oculto = cont.querySelector('input[type="hidden"]');
        const sel = cont.querySelector(".autocomp__sel");
        const txt = cont.querySelector('input[type="text"]');
        const quitar = () => {
            oculto.value = "";
            sel.classList.add("hidden");
            txt.classList.remove("hidden");
            txt.value = "";
            txt.focus();
            cont.dispatchEvent(new CustomEvent("selector:cambio", { detail: null, bubbles: true }));
        };
        sel.querySelector("button").addEventListener("click", quitar);
        new MH.Autocompletar(txt, {
            url,
            onSelect: (it) => {
                oculto.value = it.id;
                sel.querySelector(".sel-texto").textContent = it.texto;
                sel.classList.remove("hidden");
                txt.classList.add("hidden");
                cont.dispatchEvent(new CustomEvent("selector:cambio", { detail: it, bubbles: true }));
                if (cont.dataset.autoSubmit !== undefined) cont.closest("form")?.submit();
            },
        });
    };
    document.querySelectorAll("[data-selector]").forEach(MH.iniciarSelector);

    /* Botón imprimir */
    document.querySelectorAll("[data-imprimir]").forEach((b) => b.addEventListener("click", () => window.print()));
})();
