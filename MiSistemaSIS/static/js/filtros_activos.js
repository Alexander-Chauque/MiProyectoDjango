/*
 * Filtros activos: muestra arriba de la tabla una etiqueta por cada filtro
 * aplicado, con una ✕ para quitarlo, y "Quitar todos" al final.
 *
 * Lee los filtros de la dirección (?estado=pagado&buscar=teo...) y busca en el
 * formulario de filtros el texto que corresponde a cada uno (por ejemplo, la
 * casilla con value="pagado" se muestra como "Pagado").
 * Funciona en todos los listados que tienen .filtros-panel y .tabla-panel.
 */
(function () {
  const form = document.querySelector('form.filtros-panel');
  if (!form || !document.querySelector('.tabla-panel')) return;

  // Parámetros que no son filtros
  const IGNORAR = new Set(['page', 'por_pagina']);

  function textoDelGrupo(campo) {
    const grupo = campo.closest('.filtro-grupo');
    const titulo = grupo && grupo.querySelector(':scope > label');
    return titulo ? titulo.textContent.trim() : '';
  }

  function formatearFecha(valor) {
    const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(valor);
    return m ? `${m[3]}/${m[2]}/${m[1]}` : valor;
  }

  // Arma la etiqueta de un parámetro de la dirección usando el formulario
  function describir(nombre, valor) {
    const campos = Array.from(form.elements).filter((c) => c.name === nombre);
    if (!campos.length || valor === '') return null;
    const campo = campos[0];

    if (campo.type === 'checkbox' || campo.type === 'radio') {
      const elegido = campos.find((c) => c.value === valor);
      if (!elegido) return null;
      const etiqueta = elegido.closest('label');
      const texto = etiqueta ? etiqueta.textContent.trim() : valor;
      return { texto, grupo: textoDelGrupo(elegido) };
    }

    if (campo.tagName === 'SELECT') {
      const opcion = Array.from(campo.options).find((o) => o.value === valor);
      return { texto: opcion ? opcion.textContent.trim() : valor, grupo: textoDelGrupo(campo) };
    }

    if (campo.type === 'hidden') return null;

    if (nombre === 'buscar') return { texto: `"${valor}"`, grupo: 'Buscar', icono: 'search' };

    const grupo = textoDelGrupo(campo);
    const esFecha = /^\d{4}-\d{2}-\d{2}$/.test(valor);
    const prefijo = nombre.includes('desde') ? 'Desde ' : nombre.includes('hasta') ? 'Hasta ' : '';
    return {
      texto: esFecha ? prefijo + formatearFecha(valor) : valor,
      grupo,
      icono: esFecha ? 'calendar_today' : null,
    };
  }

  // Dirección sin un valor de filtro (o sin todos) y de vuelta a la página 1
  function urlSin(nombre, valor) {
    const url = new URL(window.location.href);
    const resto = url.searchParams.getAll(nombre).filter((v) => v !== valor);
    url.searchParams.delete(nombre);
    resto.forEach((v) => url.searchParams.append(nombre, v));
    url.searchParams.delete('page');
    return url.toString();
  }

  function urlSinFiltros() {
    const actual = new URL(window.location.href);
    const url = new URL(actual.pathname, actual.origin);
    if (actual.searchParams.get('por_pagina')) {
      url.searchParams.set('por_pagina', actual.searchParams.get('por_pagina'));
    }
    return url.toString();
  }

  function crearChip(info, nombre, valor) {
    const chip = document.createElement('a');
    chip.className = 'chip-filtro';
    chip.href = urlSin(nombre, valor);
    chip.title = `Quitar filtro${info.grupo ? ' de ' + info.grupo.toLowerCase() : ''}`;
    if (info.icono) {
      const icono = document.createElement('span');
      icono.className = 'material-symbols-outlined chip-icono';
      icono.textContent = info.icono;
      chip.appendChild(icono);
    }
    if (info.grupo && !info.icono) {
      const grupo = document.createElement('span');
      grupo.className = 'chip-grupo';
      grupo.textContent = info.grupo + ':';
      chip.appendChild(grupo);
    }
    chip.appendChild(document.createTextNode(info.texto));
    const cerrar = document.createElement('span');
    cerrar.className = 'material-symbols-outlined chip-cerrar';
    cerrar.setAttribute('aria-hidden', 'true');
    cerrar.textContent = 'close';
    chip.appendChild(cerrar);
    return chip;
  }

  function mostrar() {
    const panel = document.querySelector('.tabla-panel');
    if (!panel) return;
    let barra = panel.querySelector('.filtros-activos');

    const chips = [];
    new URLSearchParams(window.location.search).forEach((valor, nombre) => {
      if (IGNORAR.has(nombre)) return;
      const info = describir(nombre, valor.trim());
      if (info) chips.push(crearChip(info, nombre, valor));
    });

    if (!chips.length) {
      if (barra) barra.remove();
      return;
    }

    if (!barra) {
      barra = document.createElement('div');
      barra.className = 'filtros-activos';
      const cabecera = panel.querySelector('.tabla-header');
      if (cabecera) cabecera.after(barra);
      else panel.prepend(barra);
    }
    barra.replaceChildren(...chips);

    const todos = document.createElement('a');
    todos.className = 'chip-quitar-todos';
    todos.href = urlSinFiltros();
    todos.textContent = 'Quitar todos';
    barra.appendChild(todos);
  }

  mostrar();
  // La búsqueda en vivo avisa cuando cambia la dirección
  document.addEventListener('filtros:actualizados', mostrar);
})();
