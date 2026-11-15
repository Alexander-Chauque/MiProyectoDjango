/*
 * Tablas como fichas en celular.
 *
 * Copia el título de cada columna en sus celdas (data-titulo). En pantallas
 * chicas, base.css muestra cada fila como una ficha con "Título: valor", así
 * la tabla no se desplaza de costado. En computadora la tabla no cambia.
 * Se vuelve a aplicar cuando la búsqueda en vivo reemplaza las filas.
 */
(function () {
  function prepararTabla(tabla) {
    const titulos = Array.from(tabla.querySelectorAll('thead th')).map(function (th) {
      return th.textContent.replace(/\s+/g, ' ').trim();
    });
    if (!titulos.length) return;
    tabla.classList.add('tabla-fichas');
    tabla.querySelectorAll('tbody tr').forEach(function (fila) {
      let columna = 0;
      Array.from(fila.cells).forEach(function (celda) {
        // Una celda que ocupa toda la fila (por ejemplo, "No hay resultados") no lleva título
        if (celda.colSpan > 1) {
          celda.classList.add('celda-completa');
        } else if (titulos[columna]) {
          celda.dataset.titulo = titulos[columna];
        }
        columna += celda.colSpan;
      });
    });
  }

  function preparar() {
    document.querySelectorAll('.tabla-panel table').forEach(prepararTabla);
  }

  preparar();
  document.addEventListener('filtros:actualizados', preparar);
})();
