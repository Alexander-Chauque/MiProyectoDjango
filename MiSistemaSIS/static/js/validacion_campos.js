/*
 * Validación de formularios con el error junto a cada campo.
 *
 * - Antes de enviar un formulario POST revisa los campos (required, min, max,
 *   maxlength, step, type="email"...). Si alguno está mal, no envía: marca el
 *   campo en rojo, escribe el motivo debajo y lleva la pantalla al primero.
 *   Reemplaza el globito del navegador, que cambia según el navegador.
 * - Errores que manda el servidor:
 *     · Los que la plantilla ya muestra debajo del campo (.error-mensaje,
 *       .text-error, .cuenta-error...) también marcan el campo en rojo.
 *     · Los mensajes de arriba asociados a un campo (data-campo="nombre",
 *       ver core/mensajes.py) se mueven debajo de ese campo.
 * - El error se borra apenas se corrige el campo.
 */
(function () {
  'use strict';

  const CONTENEDORES = '.grupo-campo, .cuenta-campo, .filtro-grupo, .form-group';
  const ENVOLTORIOS = '.input-con-prefijo, .input-con-prefijo-bebida, .input-icono, .input-icono-mesa, ' +
    '.input-con-icono, .input-buscar, .input-buscar-fecha, .clave-campo';
  const ERRORES_DEL_SERVIDOR = '.error-mensaje, .text-error, .texto-error, .cuenta-error, .errorlist';

  function formatearNumero(valor) {
    const n = Number(valor);
    return Number.isFinite(n) ? n.toLocaleString('es-AR') : valor;
  }

  // Texto del error según lo que falló
  function mensajeDe(campo) {
    const v = campo.validity;
    if (campo.dataset.mensajeError && !v.valid) return campo.dataset.mensajeError;
    if (v.valueMissing) {
      if (campo.tagName === 'SELECT') return 'Seleccioná una opción.';
      if (campo.type === 'checkbox') return 'Marcá esta casilla para continuar.';
      if (campo.type === 'radio') return 'Elegí una de las opciones.';
      if (campo.type === 'file') return 'Elegí un archivo.';
      return 'Este campo es obligatorio.';
    }
    if (v.badInput) return 'Ingresá un número válido.';
    if (v.typeMismatch) {
      if (campo.type === 'email') return 'Ingresá un correo válido (ejemplo: nombre@correo.com).';
      if (campo.type === 'url') return 'Ingresá una dirección web válida.';
      return 'El formato no es válido.';
    }
    if (v.rangeUnderflow) {
      const min = Number(campo.min);
      if (min > 0 && min <= 0.01) return 'Ingresá un valor mayor a 0.';
      return `El valor mínimo es ${formatearNumero(campo.min)}.`;
    }
    if (v.rangeOverflow) return `El valor máximo es ${formatearNumero(campo.max)}.`;
    if (v.stepMismatch) {
      const paso = campo.step;
      if (paso === '1' || paso === '' ) return 'Ingresá un número entero.';
      const decimales = (paso.split('.')[1] || '').length;
      return decimales ? `Usá como máximo ${decimales} decimales.` : 'El valor no es válido.';
    }
    if (v.tooLong) return `Máximo ${campo.maxLength} caracteres.`;
    if (v.tooShort) return `Mínimo ${campo.minLength} caracteres (escribiste ${campo.value.length}).`;
    if (v.patternMismatch) return campo.title || 'El formato no es válido.';
    return campo.validationMessage || 'Revisá este campo.';
  }

  // El elemento que se pinta de rojo: el campo o su envoltorio ($, ícono...)
  function cajaVisible(campo) {
    const envoltorio = campo.closest(ENVOLTORIOS);
    const contenedor = campo.closest(CONTENEDORES);
    if (envoltorio && (!contenedor || contenedor.contains(envoltorio))) return envoltorio;
    return campo;
  }

  function contenedorDe(campo) {
    return campo.closest(CONTENEDORES) || cajaVisible(campo).parentElement;
  }

  function quitarError(campo) {
    campo.classList.remove('campo-invalido');
    campo.removeAttribute('aria-invalid');
    cajaVisible(campo).classList.remove('campo-invalido');
    const contenedor = contenedorDe(campo);
    if (!contenedor) return;
    contenedor.classList.remove('grupo-invalido');
    contenedor.querySelectorAll('.mensaje-campo[data-para="' + (campo.name || campo.id) + '"]')
      .forEach((m) => m.remove());
    // Los errores que vinieron del servidor también se ocultan al corregir
    contenedor.querySelectorAll(ERRORES_DEL_SERVIDOR).forEach((m) => { m.hidden = true; });
  }

  function mostrarError(campo, texto) {
    quitarError(campo);
    const caja = cajaVisible(campo);
    campo.classList.add('campo-invalido');
    caja.classList.add('campo-invalido');
    campo.setAttribute('aria-invalid', 'true');

    const mensaje = document.createElement('span');
    mensaje.className = 'mensaje-campo';
    mensaje.dataset.para = campo.name || campo.id;
    mensaje.setAttribute('role', 'alert');
    mensaje.innerHTML = '<span class="material-symbols-outlined" aria-hidden="true">error</span>';
    mensaje.appendChild(document.createTextNode(texto));

    // Grupos de casillas/opciones: un solo mensaje al final del grupo
    if (campo.type === 'radio' || campo.type === 'checkbox') {
      const grupo = campo.closest(CONTENEDORES);
      if (grupo) {
        grupo.querySelectorAll('.mensaje-campo').forEach((m) => m.remove());
        grupo.classList.add('grupo-invalido');
        grupo.appendChild(mensaje);
        return;
      }
    }
    caja.insertAdjacentElement('afterend', mensaje);
  }

  // Campos que el usuario puede ver y completar
  function esRevisable(campo) {
    if (!campo.willValidate || campo.disabled || campo.type === 'hidden') return false;
    if (campo.closest('[hidden]')) return false;
    // Oculto con display:none (por ejemplo, "monto parcial" sin elegir)
    return !!(campo.offsetParent || campo.getClientRects().length);
  }

  function validar(form) {
    let primero = null;
    const radiosVistos = new Set();
    Array.from(form.elements).forEach((campo) => {
      if (!esRevisable(campo)) return;
      if (campo.type === 'radio') {
        if (radiosVistos.has(campo.name)) return;
        radiosVistos.add(campo.name);
      }
      if (campo.checkValidity()) {
        quitarError(campo);
      } else {
        mostrarError(campo, mensajeDe(campo));
        primero = primero || campo;
      }
    });
    if (primero) {
      const caja = cajaVisible(primero);
      caja.scrollIntoView({ behavior: 'smooth', block: 'center' });
      primero.focus({ preventScroll: true });
    }
    return !primero;
  }

  function prepararFormulario(form) {
    if (form.dataset.validacionLista) return;
    if ((form.method || '').toLowerCase() !== 'post') return;
    form.dataset.validacionLista = '1';
    form.noValidate = true; // sin globito del navegador

    // Fase de captura: corre antes que los otros "submit" de la página
    form.addEventListener('submit', function (evento) {
      const boton = evento.submitter;
      if (boton && boton.formNoValidate) return;
      if (!validar(form)) {
        evento.preventDefault();
        evento.stopImmediatePropagation();
      }
    }, true);

    // El error se va apenas se corrige
    const revisar = (evento) => {
      const campo = evento.target;
      if (!campo.classList || !campo.name) return;
      const marcado = campo.classList.contains('campo-invalido') ||
        contenedorDe(campo)?.classList.contains('grupo-invalido') ||
        contenedorDe(campo)?.querySelector(ERRORES_DEL_SERVIDOR + ':not([hidden])');
      if (!marcado) return;
      if (campo.checkValidity()) {
        quitarError(campo);
        if (campo.type === 'radio' || campo.type === 'checkbox') {
          form.querySelectorAll(`[name="${CSS.escape(campo.name)}"]`).forEach(quitarError);
        }
      } else if (evento.type === 'change') {
        mostrarError(campo, mensajeDe(campo));
      }
    };
    form.addEventListener('input', revisar);
    form.addEventListener('change', revisar);
  }

  // Errores del servidor que la plantilla ya escribe debajo del campo
  function marcarErroresDelServidor() {
    document.querySelectorAll(ERRORES_DEL_SERVIDOR).forEach((error) => {
      if (!error.textContent.trim()) return;
      const contenedor = error.closest(CONTENEDORES);
      if (!contenedor) return;
      const campo = contenedor.querySelector('input:not([type="hidden"]), select, textarea');
      if (!campo) return;
      campo.classList.add('campo-invalido');
      cajaVisible(campo).classList.add('campo-invalido');
      campo.setAttribute('aria-invalid', 'true');
    });
  }

  // Mensajes de arriba asociados a un campo: se muestran debajo del campo
  function moverMensajesAlCampo() {
    let primero = null;
    document.querySelectorAll('[data-campo]').forEach((aviso) => {
      const nombre = aviso.dataset.campo;
      const campo = document.querySelector(
        `form [name="${CSS.escape(nombre)}"]:not([type="hidden"])`
      );
      if (!campo || !esRevisable(campo)) return; // si no está el campo, queda arriba
      mostrarError(campo, aviso.textContent.trim());
      aviso.remove();
      primero = primero || campo;
    });
    if (primero) {
      cajaVisible(primero).scrollIntoView({ block: 'center' });
      primero.focus({ preventScroll: true });
    }
  }

  function iniciar() {
    document.querySelectorAll('form').forEach(prepararFormulario);
    marcarErroresDelServidor();
    moverMensajesAlCampo();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', iniciar);
  } else {
    iniciar();
  }
})();
