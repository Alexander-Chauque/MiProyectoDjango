document.addEventListener("DOMContentLoaded", function () {
  var campos = Array.prototype.slice.call(document.querySelectorAll('input[type="date"]'));
  function limitarConNavegador(desde, hasta) {
    var hoy = desde.max;

    function actualizarLimites() {
      hasta.min = desde.value;
      desde.max = hasta.value || hoy;
    }

    desde.addEventListener("change", actualizarLimites);
    hasta.addEventListener("change", actualizarLimites);
    actualizarLimites();
  }

  function agregarBotonBorrar(calendario) {
    var pie = document.createElement("div");
    pie.className = "calendario-pie";

    var boton = document.createElement("button");
    boton.type = "button";
    boton.className = "calendario-borrar";
    boton.textContent = "Borrar";
    boton.addEventListener("click", function () {
      calendario.clear();
      calendario.close();
    });

    pie.appendChild(boton);
    calendario.calendarContainer.appendChild(pie);
  }

  function crearCalendario(campo, alCambiar) {
    return flatpickr(campo, {
      locale: flatpickr.l10ns.es,
      dateFormat: "Y-m-d",
      altInput: true,
      altFormat: "d/m/Y",
      altInputClass: (campo.className + " fecha-calendario").trim(),
      minDate: campo.min || null,
      maxDate: campo.max || null,
      // En el teléfono también se usa este calendario, no el del sistema
      disableMobile: true,
      onReady: function (fechas, texto, calendario) {
        agregarBotonBorrar(calendario);
      },
      onChange: function (fechas, texto) {
        if (alCambiar) alCambiar(texto);
      },
    });
  }

  function campoHasta(desde) {
    return desde.form && desde.form.querySelector('input[type="date"][name="fecha_hasta"]');
  }

  // Antes de crear los calendarios, porque después los campos dejan de ser de tipo fecha
  var pares = campos
    .filter(function (campo) {
      return campo.name === "fecha_desde" && campoHasta(campo);
    })
    .map(function (desde) {
      return { desde: desde, hasta: campoHasta(desde) };
    });

  if (!window.flatpickr) {
    pares.forEach(function (par) {
      limitarConNavegador(par.desde, par.hasta);
    });
    return;
  }

  var enPar = [];
  pares.forEach(function (par) {
    var hoy = par.desde.max;
    var calendarioDesde;
    var calendarioHasta;

    // "Desde" no puede ser posterior a "Hasta", ni "Hasta" anterior a "Desde"
    calendarioDesde = crearCalendario(par.desde, function (fecha) {
      calendarioHasta.set("minDate", fecha || null);
    });
    calendarioHasta = crearCalendario(par.hasta, function (fecha) {
      calendarioDesde.set("maxDate", fecha || hoy);
    });

    if (par.desde.value) calendarioHasta.set("minDate", par.desde.value);
    if (par.hasta.value) calendarioDesde.set("maxDate", par.hasta.value);
    enPar.push(par.desde, par.hasta);
  });

  campos.forEach(function (campo) {
    if (enPar.indexOf(campo) === -1) crearCalendario(campo);
  });
});
