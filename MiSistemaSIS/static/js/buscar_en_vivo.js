/*
 * Búsqueda en vivo para los listados.
 *
 * Mientras se escribe en el campo "Buscar", espera una pausa corta,
 * pide la misma página al servidor con el texto nuevo y reemplaza
 * solo la tabla y la paginación. Así se respetan los filtros, la
 * paginación y la búsqueda que ya hace cada vista de Django.
 */
(function () {
  const ESPERA_MS = 300; // pausa después de la última tecla

  const campo = document.querySelector('form input[name="buscar"]');
  const panel = document.querySelector('.tabla-panel');
  if (!campo || !panel || !campo.form) return;

  const form = campo.form;
  if ((form.method || 'get').toLowerCase() !== 'get') return;

  let temporizador = null;
  let pedidoAnterior = null;

  // Arma la dirección con los datos del formulario.
  // Conserva lo que no está en el formulario (por ejemplo "por_pagina")
  // y vuelve a la página 1, porque cambian los resultados.
  function armarUrl() {
    const url = new URL(form.action || window.location.href, window.location.href);
    const actuales = new URLSearchParams(window.location.search);
    const datos = new FormData(form);

    for (const clave of new Set(datos.keys())) actuales.delete(clave);
    for (const [clave, valor] of datos) actuales.append(clave, valor);
    actuales.delete('page');

    url.search = actuales.toString();
    return url;
  }

  // Cambia una parte del panel por la misma parte de la página nueva
  function reemplazar(nuevoPanel, selector) {
    const viejo = panel.querySelector(selector);
    const nuevo = nuevoPanel.querySelector(selector);
    if (!viejo || !nuevo) return false;
    viejo.replaceWith(nuevo);
    return true;
  }

  async function buscar() {
    const url = armarUrl();

    // Si había un pedido sin terminar, se cancela: solo importa el último
    if (pedidoAnterior) pedidoAnterior.abort();
    pedidoAnterior = new AbortController();

    panel.classList.add('buscando');
    try {
      const respuesta = await fetch(url, { signal: pedidoAnterior.signal });
      if (!respuesta.ok) return;
      const html = await respuesta.text();
      const pagina = new DOMParser().parseFromString(html, 'text/html');
      const nuevoPanel = pagina.querySelector('.tabla-panel');
      if (!nuevoPanel) return;

      // Primero intenta cambiar solo las filas y la paginación.
      // Si la estructura cambió (por ejemplo, aparece "No hay resultados"),
      // cambia el panel completo.
      const filas = reemplazar(nuevoPanel, 'table tbody');
      reemplazar(nuevoPanel, '.paginacion');
      if (!filas) panel.innerHTML = nuevoPanel.innerHTML;

      // La barra de direcciones muestra la búsqueda, así funcionan
      // "Mostrar N registros", recargar la página y el botón Atrás.
      history.replaceState(null, '', url);
      // Para que la barra de filtros activos se actualice
      document.dispatchEvent(new CustomEvent('filtros:actualizados'));
    } catch (error) {
      if (error.name !== 'AbortError') console.error('Búsqueda en vivo:', error);
    } finally {
      panel.classList.remove('buscando');
    }
  }

  campo.addEventListener('input', function () {
    clearTimeout(temporizador);
    temporizador = setTimeout(buscar, ESPERA_MS);
  });
})();
