"""Pantalla por estación (cocina, bar y parrilla) para la web en React.

Usa las mismas reglas que la web de Django (ventas/views.py: estacion y estacion_listo):
cada estación ve las comandas abiertas con productos suyos sin terminar, la más vieja primero,
y los marca como listos.
"""
from django.db import transaction
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from auditoria.models import LogAuditoria
from notificaciones.reglas import leer_config
from ventas.models import Comanda, DetalleComanda
from ventas.servicios import ESTADOS_ABIERTOS
from ventas.views import _ESTACIONES_TICKET, _estacion_o_404, _estaciones_de, texto_espera

from .permisos import PermisoDeModulo


class EstacionView(APIView):
    """GET /api/estaciones/<clave>/: lo que tiene que preparar la estación."""

    permission_classes = [PermisoDeModulo]
    modulo = "comandas"

    def get(self, request, clave):
        actual = _estacion_o_404(clave)
        limite = int(leer_config("minutos_comanda_demorada", 30))
        ahora = timezone.now()
        pendientes = DetalleComanda.objects.filter(listo__isnull=True).select_related("plato__categoria", "bebida")
        comandas = (
            Comanda.objects.filter(estado_comanda__in=ESTADOS_ABIERTOS, detalles__listo__isnull=True)
            .distinct()
            .select_related("mesa", "empleado")
            .prefetch_related(Prefetch("detalles", queryset=pendientes, to_attr="sin_terminar"))
            .order_by("fecha_hora")
        )
        pedidos = []
        for comanda in comandas:
            lineas = [d for d in comanda.sin_terminar if clave in _estaciones_de(d)]
            if not lineas:
                continue
            espera = max(int((ahora - comanda.fecha_hora).total_seconds() // 60), 0)
            pedidos.append(
                {
                    "id_comanda": comanda.id_comanda,
                    "mesa": comanda.mesa.numero_mesa,
                    "mozo": comanda.empleado.nombre_empleado if comanda.empleado else "",
                    "observaciones": comanda.observaciones_comanda,
                    "espera": espera,
                    "espera_texto": texto_espera(espera),
                    "demorada": espera >= limite,
                    "productos": [
                        {
                            "nombre": d.nombre_de_la_bebida if clave == "bar" else d.nombre_del_plato,
                            "cantidad": d.cant_bebida if clave == "bar" else d.cant_plato,
                            "nota": d.observacion,
                        }
                        for d in lineas
                    ],
                }
            )
        return Response(
            {
                "estacion": actual,
                "estaciones": list(_ESTACIONES_TICKET),
                "pedidos": pedidos,
                "limite_minutos": limite,
            }
        )


class EstacionListoView(APIView):
    """POST /api/estaciones/<clave>/<id>/listo/: la estación terminó su parte de la comanda."""

    permission_classes = [PermisoDeModulo]
    modulo = "comandas"
    accion = "modificar"

    def post(self, request, clave, pk):
        _estacion_o_404(clave)
        comanda = get_object_or_404(Comanda, pk=pk)
        lineas = [
            d
            for d in comanda.detalles.filter(listo__isnull=True).select_related("plato__categoria", "bebida")
            if clave in _estaciones_de(d)
        ]
        if lineas:
            with transaction.atomic():
                DetalleComanda.objects.filter(pk__in=[d.pk for d in lineas]).update(listo=timezone.now())
                if comanda.estado_comanda == "pendiente":
                    comanda.estado_comanda = "en_preparacion"
                    comanda.save(update_fields=["estado_comanda"])
                LogAuditoria.objects.create(
                    tabla="Comanda",
                    accion="MODIFICAR",
                    registro_id=comanda.id_comanda,
                    valores_anteriores="",
                    valores_actuales=f"{clave.capitalize()}: listo ({len(lineas)} producto(s)). Mesa: {comanda.mesa.numero_mesa}. Desde la app.",
                    empleado=request.user.empleado,
                )
        return Response({"listos": len(lineas), "mesa": comanda.mesa.numero_mesa})
