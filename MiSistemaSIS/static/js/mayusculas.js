/*
 * Mayúscula automática en los campos de nombre, mientras se escribe.
 *
 * - Nombres de personas (nombre_empleado, apellido_empleado):
 *   cada palabra con mayúscula -> "Juan Carlos", "De La Fuente".
 * - El resto de los nombres (platos, bebidas, categorías, métodos de pago...):
 *   solo la primera letra -> "Milanesa con puré".
 *
 * Se aplica solo a los <input type="text"> cuyo name es "nombre" o empieza
 * con "nombre_" / "apellido_". Para excluir un campo: data-sin-mayuscula.
 * Para forzarlo en otro campo: data-mayuscula="primera" o "palabras".
 * El cursor queda donde estaba, así se puede corregir en el medio del texto.
 */
(function () {
  'use strict';

  const ES_NOMBRE = /^(nombre|nombre_[a-z_]+|apellido_[a-z_]+)$/;
  const DE_PERSONA = /^(nombre|apellido)_empleado$/;

  function modoDe(campo) {
    if (campo.dataset.sinMayuscula !== undefined) return null;
    if (campo.dataset.mayuscula) return campo.dataset.mayuscula;
    if (campo.type !== 'text' || !ES_NOMBRE.test(campo.name || '')) return null;
    return DE_PERSONA.test(campo.name) ? 'palabras' : 'primera';
  }

  function convertir(texto, modo) {
    if (modo === 'palabras') {
      // Primera letra después del inicio, un espacio, un guion o un apóstrofo
      return texto.replace(/(^|[\s\-'])(\p{Ll})/gu, (_, antes, letra) => antes + letra.toUpperCase());
    }
    // Solo la primera letra del texto (se saltean espacios iniciales)
    return texto.replace(/^(\s*)(\p{Ll})/u, (_, espacios, letra) => espacios + letra.toUpperCase());
  }

  function aplicar(campo) {
    const modo = modoDe(campo);
    if (!modo) return;
    const nuevo = convertir(campo.value, modo);
    if (nuevo === campo.value) return;
    // Pasar a mayúscula no cambia el largo, así que el cursor queda igual
    const inicio = campo.selectionStart;
    const fin = campo.selectionEnd;
    campo.value = nuevo;
    if (document.activeElement === campo && inicio !== null) {
      campo.setSelectionRange(inicio, fin);
    }
  }

  document.addEventListener('input', (evento) => {
    const campo = evento.target;
    if (campo instanceof HTMLInputElement && !evento.isComposing) aplicar(campo);
  });

  // Los valores que ya vienen cargados (al editar) también se corrigen
  function iniciar() {
    document.querySelectorAll('input[type="text"]').forEach(aplicar);
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', iniciar);
  } else {
    iniciar();
  }
})();
