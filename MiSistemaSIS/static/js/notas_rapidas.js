// Notas rápidas para cada producto del carrito: un toque agrega o quita la nota.
// Platos y bebidas tienen notas distintas. El campo de texto sigue libre para escribir.
(function () {
  const NOTAS = {
    plato: ["sin sal", "sin cebolla", "bien cocido", "jugoso", "sin picante"],
    bebida: ["sin hielo", "con hielo", "natural", "con limón"],
  };
  // Notas que no pueden ir juntas: al elegir una se quita la otra
  const OPUESTAS = { "sin hielo": "con hielo", "con hielo": "sin hielo", "bien cocido": "jugoso", "jugoso": "bien cocido" };

  const partes = (texto) => texto.split(",").map((p) => p.trim()).filter(Boolean);
  const tiene = (texto, nota) => partes(texto).some((p) => p.toLowerCase() === nota);

  // Recibe el input de la nota y el tipo del producto; agrega los botones debajo
  window.agregarNotasRapidas = function (input, tipo) {
    const notas = NOTAS[tipo];
    if (!notas) return;
    input.placeholder = tipo === "bebida" ? "Nota para el bar (ej: sin hielo)" : "Nota para la cocina (ej: sin sal)";

    const fila = document.createElement("div");
    fila.className = "notas-rapidas";
    fila.setAttribute("role", "group");
    fila.setAttribute("aria-label", "Notas rápidas");

    const botones = notas.map((nota) => {
      const boton = document.createElement("button");
      boton.type = "button";
      boton.className = "nota-rapida";
      boton.textContent = nota;
      boton.addEventListener("click", () => {
        let lista = partes(input.value);
        if (tiene(input.value, nota)) {
          lista = lista.filter((p) => p.toLowerCase() !== nota);
        } else {
          const opuesta = OPUESTAS[nota];
          if (opuesta) lista = lista.filter((p) => p.toLowerCase() !== opuesta);
          lista.push(nota);
        }
        input.value = lista.join(", ").slice(0, input.maxLength > 0 ? input.maxLength : 120);
        input.dispatchEvent(new Event("input", { bubbles: true }));
      });
      fila.appendChild(boton);
      return boton;
    });

    function marcar() {
      botones.forEach((b) => {
        const activa = tiene(input.value, b.textContent);
        b.classList.toggle("activa", activa);
        b.setAttribute("aria-pressed", String(activa));
      });
    }
    input.addEventListener("input", marcar);
    marcar();
    input.insertAdjacentElement("afterend", fila);
  };
})();
