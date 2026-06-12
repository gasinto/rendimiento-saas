// ── JC-Sistema: Vista Órdenes ──────────────────────────────────

/** @type {Array} Cache de todas las órdenes para búsqueda local */
let _allOrdenes = [];

/**
 * Carga la lista de meses en el selector y el resumen general.
 * Llamada desde init() y después de agregar/eliminar órdenes.
 */
async function cargarMeses() {
  const r = await apiFetch("/api/meses");
  const data = await r.json();
  const sel = document.getElementById("mesSelector");
  sel.innerHTML = "";
  data.meses.forEach(m => {
    const opt = document.createElement("option");
    opt.value = m.mes;
    opt.textContent = m.mes + " — " + m.equipos + " eq, $" + m.ganancia.toLocaleString();
    sel.appendChild(opt);
  });
  if (data.meses.length === 0) {
    const opt = document.createElement("option");
    opt.value = "";
    opt.textContent = "Sin órdenes aún";
    sel.appendChild(opt);
  }

  const summary = document.getElementById("summary");
  summary.style.display = "none";
  summary.innerHTML = `
    <div class="card">
      <div class="label">Total meses</div>
      <div class="value blue">${data.meses.length}</div>
    </div>
    <div class="card">
      <div class="label">Total puntos</div>
      <div class="value">${data.total_puntos}</div>
    </div>
    <div class="card">
      <div class="label">Ganancia total</div>
      <div class="value green">$${data.total_ganancia.toLocaleString()}</div>
    </div>
  `;
}
window.cargarMeses = cargarMeses;

/**
 * Carga los tipos disponibles en el formulario de agregar orden.
 */
async function cargarTipos() {
  const r = await apiFetch("/api/tipos");
  const data = await r.json();
  const sel = document.getElementById("tipoInput");
  sel.innerHTML = "";
  data.tipos.forEach(t => {
    const opt = document.createElement("option");
    opt.value = t;
    opt.textContent = t;
    sel.appendChild(opt);
  });
}

/**
 * Carga las órdenes del mes seleccionado.
 */
async function cargarMes() {
  const mes = document.getElementById("mesSelector").value;
  if (!mes) return;
  const r = await apiFetch("/api/ordenes?mes=" + mes);
  const data = await r.json();
  renderOrdenes(data.ordenes, "ordenesTable", mes);
}
window.cargarMes = cargarMes;

/**
 * Carga TODAS las órdenes (sin filtro de mes).
 */
async function cargarTodas() {
  const r = await apiFetch("/api/ordenes");
  const data = await r.json();
  _allOrdenes = data.ordenes || [];
  renderOrdenes(_allOrdenes, "ordenesAllTable", null);
}
window.cargarTodas = cargarTodas;

/**
 * Renderiza una tabla de órdenes en el contenedor indicado.
 * @param {Array} ordenes - Lista de órdenes a renderizar
 * @param {string} containerId - ID del contenedor destino
 * @param {string|null} mes - Mes activo (null para "todas")
 */
function renderOrdenes(ordenes, containerId, mes) {
  const container = document.getElementById(containerId);
  if (!ordenes || ordenes.length === 0) {
    container.innerHTML = '<div class="empty">No hay órdenes en este período</div>';
    return;
  }

  let filtered = ordenes;
  if (containerId === "ordenesAllTable") {
    const term = (document.getElementById("ordenesQ")?.value || "").trim().toLowerCase();
    if (term) {
      filtered = ordenes.filter(o =>
        String(o.orden).includes(term) ||
        (o.tipo || "").toLowerCase().includes(term) ||
        (o.fecha || "").includes(term)
      );
    }
  }
  if (!filtered.length) {
    container.innerHTML = '<div class="empty">No hay órdenes que coincidan</div>';
    return;
  }

  let html = `<table>
    <thead><tr>
      <th>Fecha</th><th>Orden</th><th>Tipo</th><th>Pts</th><th>Ganancia</th><th></th>
    </tr></thead><tbody>`;

  let totalPts = 0, totalG = 0;
  filtered.forEach(o => {
    const ganancia = o.puntaje * VALOR_PUNTO;
    totalPts += o.puntaje;
    totalG += ganancia;
    html += `<tr>
      <td>${o.fecha}</td>
      <td><strong>${o.orden}</strong></td>
      <td>${o.tipo}</td>
      <td>${o.puntaje}</td>
      <td>$${ganancia.toLocaleString()}</td>
      <td class="actions">
        <button class="btn-delete" onclick="eliminarOrden(${o.id})">🗑️</button>
      </td>
    </tr>`;
  });

  if (typeof mostrarTotales !== 'undefined' && mostrarTotales) {
    html += `<tr style="font-weight:700; background:var(--surface)">
      <td colspan="3">Total</td>
      <td>${totalPts}</td>
      <td>$${totalG.toLocaleString()}</td>
      <td></td>
    </tr>`;
  }

  html += "</tbody></table>";
  container.innerHTML = html;
}

/**
 * Toggle mostrar/ocultar totales y resumen.
 */
function toggleMostrarTotal() {
  mostrarTotales = document.getElementById("toggleTotales").checked;
  document.getElementById("summary").style.display = mostrarTotales ? "grid" : "none";
  const mes = document.getElementById("mesSelector").value;
  if (mes) {
    apiFetch("/api/ordenes?mes=" + mes)
      .then(r => r.json())
      .then(data => renderOrdenes(data.ordenes, "ordenesTable", mes));
  }
  cargarTodas();
}
window.toggleMostrarTotal = toggleMostrarTotal;

/**
 * Agrega una nueva orden vía API.
 */
async function agregarOrden() {
  const fecha = document.getElementById("fechaInput").value;
  const orden = document.getElementById("ordenInput").value;
  const tipo = document.getElementById("tipoInput").value;

  if (!orden || !tipo) {
    mostrarMsg("Completá orden y tipo", "err");
    return;
  }

  const r = await apiFetch("/api/agregar", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({fecha, orden: parseInt(orden), tipo})
  });
  const data = await r.json();

  if (data.ok) {
    mostrarMsg("✅ Orden " + orden + " agregada", "ok");
    document.getElementById("ordenInput").value = "";
    await Promise.all([cargarMeses(), cargarMes()]);
  } else {
    mostrarMsg("❌ " + (data.error || "Error"), "err");
  }
}
window.agregarOrden = agregarOrden;

/**
 * Elimina una orden por ID.
 * @param {number} id
 */
async function eliminarOrden(id) {
  if (!confirm("¿Eliminar orden " + id + "?")) return;
  const r = await apiFetch("/api/ordenes/" + id + "/eliminar", {method: "DELETE"});
  const data = await r.json();
  if (data.ok) {
    mostrarMsg("🗑️ Orden eliminada", "ok");
    await Promise.all([cargarMeses(), cargarMes(), cargarTodas()]);
  } else {
    mostrarMsg("❌ " + (data.error || "Error"), "err");
  }
}
window.eliminarOrden = eliminarOrden;
