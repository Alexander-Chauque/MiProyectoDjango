"""Datos de productos para los reportes, aunque el producto ya se haya eliminado del inventario.

Cuando se elimina un plato o una bebida, la línea de la comanda guarda su nombre, precio y categoría
(ver inventario/servicios.py). Estas expresiones usan el dato del inventario o, si ya no está, el guardado.
"""
from django.db.models import F, Q, Value
from django.db.models.functions import Coalesce, NullIf

NOMBRE_PLATO = Coalesce("plato__nombre_plato", NullIf("nombre_plato_guardado", Value("")))
NOMBRE_BEBIDA = Coalesce("bebida__nombre_bebida", NullIf("nombre_bebida_guardado", Value("")))
CATEGORIA_PLATO = Coalesce("plato__categoria__nombre_categoria_plato", NullIf("categoria_plato_guardada", Value("")))
PRECIO_PLATO = Coalesce("plato__precio_plato", "precio_plato_guardado")

# Líneas que tienen un plato (o una bebida), exista todavía o no
CON_PLATO = Q(plato__isnull=False) | ~Q(nombre_plato_guardado="")
CON_BEBIDA = Q(bebida__isnull=False) | ~Q(nombre_bebida_guardado="")

__all__ = ["NOMBRE_PLATO", "NOMBRE_BEBIDA", "CATEGORIA_PLATO", "PRECIO_PLATO", "CON_PLATO", "CON_BEBIDA", "F"]
