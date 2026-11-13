"""Mensajes de error asociados a un campo del formulario.

error_campo(request, "nombre", "Ya existe una categoría con ese nombre.")

Se guarda como un mensaje de error común con la etiqueta "campo:nombre".
base.html lo pinta con data-campo="nombre" y validacion_campos.js lo muestra
debajo del campo name="nombre", con el borde en rojo. Si la página no tiene
ese campo (por ejemplo, después de redirigir a otra), queda arriba como
cualquier otro mensaje.
"""
from django.contrib import messages


def error_campo(request, campo, texto):
    messages.error(request, texto, extra_tags=f"campo:{campo}")


class ErrorDeCampo(ValueError):
    """ValueError que sabe a qué campo del formulario corresponde.

    raise ErrorDeCampo("precio", "El precio debe ser mayor a 0.")
    Como hereda de ValueError, los "except ValueError" que ya existen lo atrapan.
    """

    def __init__(self, campo, texto):
        super().__init__(texto)
        self.campo = campo


def informar_error(request, error):
    """Muestra un ValueError: junto a su campo si es ErrorDeCampo, si no arriba."""
    campo = getattr(error, "campo", None)
    if campo:
        error_campo(request, campo, str(error))
    else:
        messages.error(request, str(error))
