"""Reglas de inventario que comparten la web y la API, para que siempre sean las mismas."""
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from auditoria.models import LogAuditoria

from .models import Plato


def cambiar_estado_ingrediente(ingrediente, empleado, motivo):
    """Alterna el estado del ingrediente y de los platos que lo usan, y lo registra en auditoría."""
    with transaction.atomic():
        estado_anterior = ingrediente.estado_ingrediente
        ingrediente.estado_ingrediente = not estado_anterior
        ingrediente.save()

        platos_afectados = Plato.objects.filter(
            detalleplato__ingrediente=ingrediente,
            estado_plato=estado_anterior,
        ).distinct()
        for plato in platos_afectados:
            plato.estado_plato = ingrediente.estado_ingrediente
            plato.save()

            if ingrediente.estado_ingrediente:
                actual = f"Estado: Disponible. Motivo: Ingrediente '{ingrediente.nombre_ingrediente}' vuelve a estar en stock."
            else:
                actual = f"Estado: No disponible. Motivo: Ingrediente '{ingrediente.nombre_ingrediente}' fuera de stock."
            LogAuditoria.objects.create(
                tabla="Plato",
                accion="MODIFICAR",
                registro_id=plato.id_plato,
                valores_anteriores=f"Estado: {'Disponible' if estado_anterior else 'No disponible'}",
                valores_actuales=actual,
                empleado=empleado,
            )

        LogAuditoria.objects.create(
            tabla="Ingrediente",
            accion="MODIFICAR",
            registro_id=ingrediente.id_ingrediente,
            valores_anteriores=f"Estado: {'Disponible' if estado_anterior else 'No disponible'}",
            valores_actuales=f"Estado: {'Disponible' if ingrediente.estado_ingrediente else 'No disponible'}. Motivo: {motivo}",
            empleado=empleado,
        )


# ---------- Eliminar productos ----------
# Un plato, una bebida o un ingrediente solo se elimina si está desactivado hace al menos 2 meses.
# La fecha la anota un trigger de MySQL al desactivarlo (migración inventario 0006).
DIAS_PARA_ELIMINAR = 60


def eliminable_desde(producto):
    """Fecha desde la que se puede eliminar, o None si está activo."""
    if producto.fecha_desactivacion is None:
        return None
    return producto.fecha_desactivacion + timedelta(days=DIAS_PARA_ELIMINAR)


def _validar_antiguedad(producto, nombre, activo, femenino=False):
    no_disponible = "no disponible"
    if activo:
        raise ValueError(
            f'No se puede eliminar "{nombre}": primero marcal{"a" if femenino else "o"} como {no_disponible}. '
            f"Se podrá eliminar {DIAS_PARA_ELIMINAR // 30} meses después."
        )
    desde = eliminable_desde(producto)
    if desde is None or desde > timezone.now():
        desactivado = timezone.localtime(producto.fecha_desactivacion) if producto.fecha_desactivacion else None
        cuando = f" desde el {desactivado:%d/%m/%Y}" if desactivado else ""
        fecha = f"a partir del {timezone.localtime(desde):%d/%m/%Y}" if desde else f"{DIAS_PARA_ELIMINAR // 30} meses después de desactivarl{'a' if femenino else 'o'}"
        raise ValueError(f'No se puede eliminar "{nombre}": está {no_disponible}{cuando}. Se podrá eliminar {fecha}.')


def validar_eliminar_plato(plato):
    _validar_antiguedad(plato, plato.nombre_plato, plato.estado_plato)


def validar_eliminar_bebida(bebida):
    _validar_antiguedad(bebida, bebida.nombre_bebida, bebida.disponible_bebida, femenino=True)


def validar_eliminar_ingrediente(ingrediente):
    _validar_antiguedad(ingrediente, ingrediente.nombre_ingrediente, ingrediente.estado_ingrediente)
    en_uso = Plato.objects.filter(detalleplato__ingrediente=ingrediente, estado_plato=True).distinct().count()
    if en_uso:
        raise ValueError(
            f'No se puede eliminar "{ingrediente.nombre_ingrediente}": lo usan {en_uso} plato(s) disponible(s). '
            "Quitalo de esas recetas o desactivá los platos."
        )


def eliminar_plato(plato):
    """Elimina el plato y deja su nombre, precio y categoría guardados en las comandas viejas."""
    from ventas.models import DetalleComanda

    validar_eliminar_plato(plato)
    with transaction.atomic():
        DetalleComanda.objects.filter(plato=plato).update(
            nombre_plato_guardado=plato.nombre_plato,
            precio_plato_guardado=plato.precio_plato,
            categoria_plato_guardada=plato.categoria.nombre_categoria_plato,
        )
        plato.delete()


def eliminar_bebida(bebida):
    """Elimina la bebida y deja su nombre y precio guardados en las comandas viejas."""
    from ventas.models import DetalleComanda

    validar_eliminar_bebida(bebida)
    with transaction.atomic():
        DetalleComanda.objects.filter(bebida=bebida).update(
            nombre_bebida_guardado=bebida.nombre_bebida,
            precio_bebida_guardado=bebida.precio_bebida,
        )
        bebida.delete()


def eliminar_ingrediente(ingrediente):
    """Elimina el ingrediente. No se permite si algún plato disponible todavía lo usa."""
    validar_eliminar_ingrediente(ingrediente)
    with transaction.atomic():
        # Se quita también de las recetas de los platos no disponibles
        ingrediente.delete()
