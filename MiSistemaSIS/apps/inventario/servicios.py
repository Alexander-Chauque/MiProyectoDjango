"""Reglas de inventario que comparten la web y la API, para que siempre sean las mismas."""
from django.db import transaction

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
