from django.db.models import Count, DecimalField, F, Q, Sum
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from auditoria.models import LogAuditoria
from empleados.models import Empleado
from reportes.productos import CATEGORIA_PLATO, CON_BEBIDA, CON_PLATO, NOMBRE_BEBIDA, NOMBRE_PLATO, PRECIO_PLATO
from reportes.views import obtener_comandas, obtener_totales_metodos
from ventas.models import DetalleComanda

from .permisos import PermisoDeModulo
from .utilidades import rango_pedido, responder_paginado

MAXIMO_EXPORTAR = 10000


class ReporteView(APIView):
    permission_classes = [PermisoDeModulo]
    modulo = "reportes"

    def get(self, request):
        # Las funciones de la web leen request.GET, que también existe en el pedido de la API
        comandas, desde, hasta = obtener_comandas(request)
        comandas = comandas.select_related("mesa", "empleado")

        total = comandas.aggregate(total=Sum("total_comanda"))["total"] or 0
        cantidad = comandas.count()

        por_dia = {}
        detalle = []
        for comanda in comandas.order_by("fecha_hora"):
            momento = timezone.localtime(comanda.fecha_hora)
            por_dia[momento.date()] = por_dia.get(momento.date(), 0) + comanda.total_comanda
            detalle.append(
                {
                    "id_comanda": comanda.id_comanda,
                    "fecha_hora": comanda.fecha_hora,
                    "mesa": comanda.mesa.numero_mesa,
                    "mozo": comanda.empleado.get_full_name() if comanda.empleado else "N/A",
                    "total": str(comanda.total_comanda),
                }
            )

        detalles = DetalleComanda.objects.filter(comanda__in=comandas)
        top_platos = (
            detalles.filter(CON_PLATO, cant_plato__gt=0)
            .annotate(nombre=NOMBRE_PLATO)
            .values("nombre")
            .annotate(total=Sum("cant_plato"))
            .order_by("-total")[:5]
        )
        top_bebidas = (
            detalles.filter(CON_BEBIDA, cant_bebida__gt=0)
            .annotate(nombre=NOMBRE_BEBIDA)
            .values("nombre")
            .annotate(total=Sum("cant_bebida"))
            .order_by("-total")[:5]
        )
        categorias = (
            detalles.filter(CON_PLATO, cant_plato__gt=0)
            .annotate(categoria_nombre=CATEGORIA_PLATO)
            .values("categoria_nombre")
            .annotate(ingresos=Sum(F("cant_plato") * PRECIO_PLATO, output_field=DecimalField()))
            .order_by("-ingresos")
        )
        mozos = (
            comandas.values("empleado__nombre_empleado", "empleado__apellido_empleado")
            .annotate(total=Sum("total_comanda"), cantidad=Count("id_comanda"))
            .order_by("-total")
        )
        metodos, _, _ = obtener_totales_metodos(request)

        return Response(
            {
                "fecha_desde": desde,
                "fecha_hasta": hasta,
                "ventas_totales": str(total),
                "cantidad_comandas": cantidad,
                "ticket_promedio": str(round(total / cantidad, 2) if cantidad else 0),
                "por_dia": [{"fecha": dia, "total": str(monto)} for dia, monto in sorted(por_dia.items())],
                "top_platos": [{"nombre": f["nombre"], "cantidad": f["total"]} for f in top_platos],
                "top_bebidas": [{"nombre": f["nombre"], "cantidad": f["total"]} for f in top_bebidas],
                "categorias": [
                    {"nombre": f["categoria_nombre"], "ingresos": str(f["ingresos"])}
                    for f in categorias
                ],
                "mozos": [
                    {
                        "nombre": f"{f['empleado__nombre_empleado']} {f['empleado__apellido_empleado']}",
                        "cantidad": f["cantidad"],
                        "total": str(f["total"]),
                    }
                    for f in mozos
                ],
                "metodos": [{"nombre": nombre, "total": str(monto)} for nombre, monto in metodos],
                "comandas": detalle,
            }
        )


def _log_a_dict(log):
    return {
        "id_log": log.id_log,
        "fecha_hora": log.fecha_hora,
        "usuario": log.empleado.get_full_name() if log.empleado else "Sistema",
        "tabla": log.tabla,
        "accion": log.accion,
        "registro_id": log.registro_id,
        "valores_anteriores": log.valores_anteriores,
        "valores_actuales": log.valores_actuales,
    }


class AuditoriaView(APIView):
    """GET /api/auditoria/: el registro de cambios, por páginas.

    Filtros: ?tabla, ?accion, ?usuario (id de empleado), ?detalle, ?fecha_desde, ?fecha_hasta.
    Con ?exportar=1 devuelve todas las filas filtradas (hasta 10.000), sin páginas.
    """

    permission_classes = [PermisoDeModulo]
    modulo = "auditoria"

    def get(self, request):
        logs = LogAuditoria.objects.select_related("empleado").order_by("-fecha_hora")
        parametros = request.query_params
        if parametros.get("tabla"):
            logs = logs.filter(tabla=parametros["tabla"])
        if parametros.get("accion"):
            logs = logs.filter(accion=parametros["accion"])
        if parametros.get("usuario", "").isdigit():
            logs = logs.filter(empleado_id=int(parametros["usuario"]))
        detalle = parametros.get("detalle", "").strip()
        if detalle:
            logs = logs.filter(Q(valores_actuales__icontains=detalle) | Q(valores_anteriores__icontains=detalle))
        # Igual que la web: compara solo la fecha, sin la hora
        desde, hasta = rango_pedido(request)
        if desde:
            logs = logs.filter(fecha_hora__date__gte=desde)
        if hasta:
            logs = logs.filter(fecha_hora__date__lte=hasta)

        if parametros.get("exportar") == "1":
            return Response({"resultados": [_log_a_dict(log) for log in logs[:MAXIMO_EXPORTAR]]})

        return responder_paginado(
            request, logs, _log_a_dict,
            {
                "tablas": list(
                    LogAuditoria.objects.order_by("tabla").values_list("tabla", flat=True).distinct()
                ),
                "acciones": [{"valor": valor, "nombre": nombre} for valor, nombre in LogAuditoria.ACCIONES],
                "empleados": [
                    {"id": empleado.id_empleado, "nombre": empleado.get_full_name()}
                    for empleado in Empleado.objects.order_by("nombre_empleado", "apellido_empleado")
                ],
            },
        )
