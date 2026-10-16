/* =====================================================================
   Editor de documentos: ventas, presupuestos y pedidos.
   - Cliente con autocompletado (muestra saldo de cuenta corriente).
   - Ítems con material, unidad (según conversiones), cantidad, precio y descuento.
   - Flete por zona (API), totales y cobro.
   Los totales son orientativos: el servidor recalcula todo al guardar.
   ===================================================================== */
(function () {
    "use strict";
    const form = document.getElementById("form-doc");
    if (!form) return;
    const modo = form.dataset.modo;
    const datos = MH.datosJSON("datos-doc") || { items: [], cliente: null };
    const tbody = document.getElementById("items");
    const vacio = document.getElementById("items-vacio");
    const $ = (id) => document.getElementById(id);

    let cliente = null;
    let montoEditado = !!($("monto_pagado") && $("monto_pagado").value);

    /* ------------------------------------------------ cliente */
    function mostrarCliente(c) {
        cliente = c;
        $("cliente_id").value = c ? c.id : "";
        $("cliente-sel").classList.toggle("hidden", !c);
        $("cliente-buscar").classList.toggle("hidden", !!c);
        if (!c) return recalcular();
        $("cliente-nombre").textContent = c.texto;
        $("cliente-detalle").textContent = c.detalle || "";
        const saldo = Number(c.saldo || 0);
        const el = $("cliente-saldo");
        el.textContent = saldo > 0 ? `Saldo deudor: ${MH.moneda(saldo)}` + (Number(c.limite) > 0 ? ` · límite ${MH.moneda(c.limite)}` : "")
            : saldo < 0 ? `Saldo a favor: ${MH.moneda(-saldo)}` : "Cuenta corriente al día";
        el.className = "text-sm " + (saldo > 0 ? "text-rojo fw-600" : "text-verde");
        // Completar datos de entrega si están vacíos
        const dir = $("direccion_entrega");
        if (dir && !dir.value && c.direccion) dir.value = [c.direccion, c.localidad].filter(Boolean).join(", ");
        const zona = $("zona_id");
        if (zona && !zona.value && c.zona_id) zona.value = c.zona_id;
        ["localidad", "referencia"].forEach((k) => { const inp = form.querySelector(`[name="${k}"]`); if (inp && !inp.value && c[k]) inp.value = c[k]; });
        recalcular();
    }
    new MH.Autocompletar($("cliente-buscar"), { url: "/api/clientes/buscar", onSelect: mostrarCliente });
    $("cliente-quitar").addEventListener("click", () => { mostrarCliente(null); $("cliente-buscar").value = ""; $("cliente-buscar").focus(); });
    if (datos.cliente) mostrarCliente(datos.cliente);

    /* ------------------------------------------------ ítems */
    function opcionesUnidades(unidades, seleccion) {
        return unidades.map((u) =>
            `<option value="${u.id}" data-factor="${u.factor}" data-precio="${u.precio}" ${String(u.id) === String(seleccion) ? "selected" : ""}>${MH.esc(u.nombre)}</option>`
        ).join("");
    }

    function agregarFila(it = {}) {
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td class="material">
                <input type="hidden" name="item_material_id" value="${MH.esc(it.material_id || "")}">
                <input type="text" class="input inp-material" placeholder="Buscar material…" value="${MH.esc(it.material || "")}">
                <div class="info-linea"></div>
            </td>
            <td><span class="etq-movil">Unidad</span><select class="input sel-unidad" name="item_unidad_id">${opcionesUnidades(it.unidades || [], it.unidad_id)}</select></td>
            <td><span class="etq-movil">Cantidad</span><input class="input num inp-cant" type="number" name="item_cantidad" step="0.001" min="0.001" value="${MH.esc(it.cantidad || "")}"></td>
            <td><span class="etq-movil">Precio unit.</span><input class="input num inp-precio" type="number" name="item_precio" step="0.01" min="0" value="${MH.esc(it.precio || "")}"></td>
            <td><span class="etq-movil">Desc. %</span><input class="input num inp-desc" type="number" name="item_descuento" step="0.01" min="0" max="100" value="${MH.esc(it.descuento && Number(it.descuento) ? it.descuento : "")}"></td>
            <td class="right num fw-600 td-sub">$ 0,00</td>
            <td class="right"><button type="button" class="btn btn--fantasma btn-icono btn-quitar" title="Quitar">${MH.icon("trash")}</button></td>`;
        tbody.appendChild(tr);
        tr._stock = it.stock !== undefined && it.stock !== "" ? Number(it.stock) : null;
        tr._unidadStock = it.unidad_stock || "";
        const inpMat = tr.querySelector(".inp-material");
        new MH.Autocompletar(inpMat, {
            url: "/api/materiales/buscar",
            render: (m) => `<strong>${MH.esc(m.texto)}</strong><small>${MH.esc(m.detalle)}</small>`,
            onSelect: (m) => {
                tr.querySelector('[name="item_material_id"]').value = m.id;
                inpMat.value = m.texto;
                tr._stock = Number(m.stock);
                tr._unidadStock = m.unidad_stock;
                const sel = tr.querySelector(".sel-unidad");
                sel.innerHTML = opcionesUnidades(m.unidades, m.unidad_id);
                aplicarPrecioUnidad(tr);
                const cant = tr.querySelector(".inp-cant");
                if (!cant.value) cant.value = 1;
                cant.focus();
                cant.select();
                recalcular();
            },
        });
        tr.querySelector(".sel-unidad").addEventListener("change", () => { aplicarPrecioUnidad(tr); recalcular(); });
        tr.querySelectorAll(".inp-cant, .inp-precio, .inp-desc").forEach((i) => i.addEventListener("input", recalcular));
        tr.querySelector(".btn-quitar").addEventListener("click", () => { tr.remove(); recalcular(); });
        actualizarVacio();
        return tr;
    }

    function aplicarPrecioUnidad(tr) {
        const op = tr.querySelector(".sel-unidad").selectedOptions[0];
        if (op) tr.querySelector(".inp-precio").value = Number(op.dataset.precio).toFixed(2);
    }

    function actualizarVacio() {
        vacio.classList.toggle("hidden", tbody.children.length > 0);
    }

    $("btn-agregar").addEventListener("click", () => agregarFila().querySelector(".inp-material").focus());
    (datos.items || []).forEach((it) => agregarFila(it));
    if (!datos.items || !datos.items.length) agregarFila();

    /* ------------------------------------------------ entrega / flete */
    const radiosEntrega = form.querySelectorAll('[name="tipo_entrega"]');
    function esEnvio() { return form.querySelector('[name="tipo_entrega"]:checked')?.value === "envio"; }
    function actualizarEntrega() {
        const envio = esEnvio();
        $("bloque-envio").classList.toggle("hidden", !envio);
        $("fila-envio").classList.toggle("hidden", !envio);
        const extra = $("bloque-crear-entrega");
        if (extra) extra.hidden = !envio;
        document.querySelectorAll("[data-solo-envio]").forEach((el) => el.classList.toggle("hidden", !envio));
        recalcular();
    }
    radiosEntrega.forEach((r) => r.addEventListener("change", actualizarEntrega));

    $("btn-cotizar")?.addEventListener("click", async () => {
        const zona = $("zona_id").value;
        if (!zona) return MH.aviso("Elegí una zona de entrega.", "warning");
        // Carga total en unidades de stock (aprox. m³/t) para el costo por unidad de la zona
        let carga = 0;
        tbody.querySelectorAll("tr").forEach((tr) => {
            const op = tr.querySelector(".sel-unidad").selectedOptions[0];
            carga += MH.parse(tr.querySelector(".inp-cant").value) * (op ? Number(op.dataset.factor) : 1);
        });
        const params = new URLSearchParams({ zona_id: zona, cantidad: MH.redondear(carga, 3) });
        if ($("distancia").value) params.set("distancia", $("distancia").value);
        if ($("tipo_vehiculo").value) params.set("tipo_vehiculo_id", $("tipo_vehiculo").value);
        try {
            const r = await MH.api("/api/transporte/cotizar?" + params.toString());
            $("costo_envio").value = Number(r.total).toFixed(2);
            $("flete-detalle").textContent = r.detalle.map((d) => `${d.concepto}: ${MH.moneda(d.importe)}`).join(" · ") + ` → ${MH.moneda(r.total)}`;
            recalcular();
        } catch (e) { MH.aviso(e.message, "danger"); }
    });

    /* ------------------------------------------------ totales */
    function recalcular() {
        let subtotal = 0;
        tbody.querySelectorAll("tr").forEach((tr) => {
            const cant = MH.parse(tr.querySelector(".inp-cant").value);
            const precio = MH.parse(tr.querySelector(".inp-precio").value);
            const desc = MH.parse(tr.querySelector(".inp-desc").value);
            const sub = MH.redondear(cant * precio * (100 - desc) / 100);
            subtotal += sub;
            tr.querySelector(".td-sub").textContent = MH.moneda(sub);
            const info = tr.querySelector(".info-linea");
            const op = tr.querySelector(".sel-unidad").selectedOptions[0];
            if (op && tr._stock !== null) {
                const factor = Number(op.dataset.factor);
                const enStock = cant * factor;
                let txt = factor !== 1 && cant ? `= ${MH.cant(enStock)} ${tr._unidadStock} · ` : "";
                txt += `stock ${MH.cant(tr._stock)} ${tr._unidadStock}`;
                info.textContent = txt;
                info.classList.toggle("alerta-stock", modo !== "presupuesto" && enStock > tr._stock);
                if (modo !== "presupuesto" && enStock > tr._stock) info.textContent += " — stock insuficiente";
            } else if (!tr.querySelector('[name="item_material_id"]').value) {
                info.textContent = "";
            }
        });
        const descGen = MH.parse($("descuento_general").value);
        const envio = esEnvio() ? MH.parse($("costo_envio").value) : 0;
        const total = Math.max(0, MH.redondear(subtotal - descGen + envio));
        $("t-subtotal").textContent = MH.moneda(subtotal);
        $("t-total").textContent = MH.moneda(total);
        if (modo === "venta") actualizarCobro(total);
    }
    ["descuento_general", "costo_envio"].forEach((id) => $(id)?.addEventListener("input", recalcular));

    /* ------------------------------------------------ cobro (sólo ventas) */
    function actualizarCobro(total) {
        const sel = $("metodo_pago_id");
        const grupo = sel.selectedOptions[0]?.dataset.grupo;
        const esCC = grupo === "cuenta_corriente";
        $("campo-monto").classList.toggle("hidden", esCC);
        $("campo-ref").classList.toggle("hidden", esCC || grupo === "efectivo");
        const monto = $("monto_pagado");
        if (!montoEditado && !esCC) monto.value = total.toFixed(2);
        const pagado = esCC ? 0 : Math.min(MH.parse(monto.value), total);
        const cc = Math.max(0, MH.redondear(total - pagado));
        $("t-cc").textContent = MH.moneda(cc);
        const excedente = MH.parse(monto.value) - total;
        $("fila-vuelto").classList.toggle("hidden", !(grupo === "efectivo" && excedente > 0));
        $("t-vuelto").textContent = MH.moneda(excedente);
        const aviso = $("aviso-limite");
        if (cliente && cc > 0) {
            const limite = Number(cliente.limite || 0);
            const saldoNuevo = Number(cliente.saldo || 0) + cc;
            if (limite > 0 && saldoNuevo > limite) {
                $("aviso-limite-txt").textContent = `Supera el límite de crédito (${MH.moneda(limite)}): el saldo quedaría en ${MH.moneda(saldoNuevo)}.`;
                aviso.classList.remove("hidden");
            } else {
                $("aviso-limite-txt").textContent = `Quedan ${MH.moneda(cc)} a cuenta corriente. Saldo resultante: ${MH.moneda(saldoNuevo)}.`;
                aviso.classList.remove("hidden");
            }
        } else aviso.classList.add("hidden");
    }
    if (modo === "venta") {
        $("metodo_pago_id").addEventListener("change", () => { montoEditado = false; recalcular(); });
        $("monto_pagado").addEventListener("input", () => { montoEditado = true; recalcular(); });
    }

    /* ------------------------------------------------ envío */
    form.addEventListener("submit", (ev) => {
        // Quitar filas vacías
        tbody.querySelectorAll("tr").forEach((tr) => {
            if (!tr.querySelector('[name="item_material_id"]').value && !tr.querySelector(".inp-cant").value) tr.remove();
        });
        const conMaterial = [...tbody.querySelectorAll('[name="item_material_id"]')].filter((i) => i.value).length;
        if (!$("cliente_id").value) { ev.preventDefault(); ev.stopImmediatePropagation(); MH.aviso("Seleccioná un cliente.", "danger"); return; }
        if (!conMaterial) { ev.preventDefault(); ev.stopImmediatePropagation(); MH.aviso("Agregá al menos un material.", "danger"); if (!tbody.children.length) agregarFila(); return; }
        const sinMat = [...tbody.querySelectorAll("tr")].find((tr) => !tr.querySelector('[name="item_material_id"]').value);
        if (sinMat) { ev.preventDefault(); ev.stopImmediatePropagation(); MH.aviso("Hay una fila sin material seleccionado de la lista.", "danger"); sinMat.querySelector(".inp-material").focus(); }
    }, true);

    actualizarEntrega();
})();
