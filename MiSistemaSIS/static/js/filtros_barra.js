/*
 * Filtros en barra: en los listados marcados con .listado-layout--barra, el
 * formulario de filtros va arriba de la tabla en una sola fila.
 *
 * Este archivo convierte cada grupo de casillas o de fechas en un desplegable
 * (un botón que abre su lista), sin cambiar los campos del formulario: se
 * envían los mismos datos que antes. En celular, la barra se pliega detrás
 * del título "Filtros".
 */
(function () {
  const form = document.querySelector('.listado-layout--barra form.filtros-panel');
  if (!form) return;

  const desplegables = [];

  function cerrarTodos(excepto) {
    desplegables.forEach(function (d) {
      if (d !== excepto) d.abrir(false);
    });
  }

  // Cuántos filtros tiene elegidos el grupo (casillas marcadas o fechas cargadas)
  function contarElegidos(grupo) {
    let cantidad = 0;
    grupo.querySelectorAll('input[name]').forEach(function (campo) {
      if (campo.type === 'checkbox' || campo.type === 'radio') {
        if (campo.checked && campo.value !== '') cantidad += 1;
      } else if (campo.type !== 'hidden' && campo.value.trim() !== '') {
        cantidad += 1;
      }
    });
    return cantidad;
  }

  function convertir(grupo, indice) {
    const titulo = grupo.querySelector(':scope > label');
    const contenido = grupo.querySelector(':scope > .checkboxes, :scope > .filtro-fecha');
    if (!titulo || !contenido) return;

    grupo.classList.add('filtro-desplegable');
    contenido.classList.add('filtro-desplegable-lista');
    contenido.id = contenido.id || 'filtro-lista-' + indice;
    contenido.hidden = true;

    const boton = document.createElement('button');
    boton.type = 'button';
    boton.className = 'filtro-desplegable-boton';
    boton.setAttribute('aria-expanded', 'false');
    boton.setAttribute('aria-controls', contenido.id);

    const nombre = document.createElement('span');
    nombre.textContent = titulo.textContent.trim();
    const contador = document.createElement('span');
    contador.className = 'filtro-desplegable-contador';
    const flecha = document.createElement('span');
    flecha.className = 'material-symbols-outlined';
    flecha.setAttribute('aria-hidden', 'true');
    flecha.textContent = 'expand_more';
    boton.append(nombre, contador, flecha);

    // El título original queda en la página (lo usan las etiquetas de filtros activos)
    titulo.classList.add('filtro-desplegable-titulo');
    grupo.insertBefore(boton, contenido);

    const desplegable = {
      abrir: function (abierto) {
        contenido.hidden = !abierto;
        boton.setAttribute('aria-expanded', String(abierto));
      },
      actualizar: function () {
        const cantidad = contarElegidos(grupo);
        contador.textContent = cantidad ? String(cantidad) : '';
        contador.hidden = !cantidad;
        boton.classList.toggle('con-filtros', cantidad > 0);
      },
    };
    desplegables.push(desplegable);

    boton.addEventListener('click', function () {
      const abrir = contenido.hidden;
      cerrarTodos(desplegable);
      desplegable.abrir(abrir);
    });
    grupo.addEventListener('change', function () {
      // Espera a que terminen los demás scripts (por ejemplo, "Todos" desmarca el resto)
      setTimeout(desplegable.actualizar, 0);
    });
    desplegable.actualizar();
  }

  form.querySelectorAll('.filtro-grupo').forEach(convertir);

  // Cerrar al pulsar afuera (el calendario de fechas se dibuja fuera del formulario)
  document.addEventListener('click', function (evento) {
    if (evento.target.closest('.filtro-desplegable, .flatpickr-calendar')) return;
    cerrarTodos();
  });
  document.addEventListener('keydown', function (evento) {
    if (evento.key === 'Escape') cerrarTodos();
  });
  // Las fechas se cargan con el calendario: se actualiza el contador al elegir
  document.addEventListener('filtros:actualizados', function () {
    desplegables.forEach(function (d) { d.actualizar(); });
  });

  // En celular, el título "Filtros" abre y cierra la barra
  const cabecera = form.querySelector('.filtros-header');
  if (cabecera) {
    cabecera.setAttribute('role', 'button');
    cabecera.setAttribute('tabindex', '0');
    cabecera.setAttribute('aria-expanded', 'false');
    function alternar() {
      const abierta = form.classList.toggle('filtros-abiertos');
      cabecera.setAttribute('aria-expanded', String(abierta));
    }
    cabecera.addEventListener('click', alternar);
    cabecera.addEventListener('keydown', function (evento) {
      if (evento.key === 'Enter' || evento.key === ' ') {
        evento.preventDefault();
        alternar();
      }
    });
  }
})();
