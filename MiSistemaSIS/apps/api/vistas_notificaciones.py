"""Notificaciones del usuario para la web en React (Parcial Nº 2, módulo M3).

Las reglas que crean las notificaciones están en notificaciones/reglas.py. Acá solo se leen
y se marcan como leídas, siempre las dirigidas al cargo de quien inició sesión.
"""
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from notificaciones.models import TIPOS
from notificaciones.views import mis_notificaciones

from .utilidades import responder_paginado


def _notificacion_a_dict(notificacion):
    return {
        "id": notificacion.id_notificacion,
        "fecha": notificacion.fecha,
        "tipo": notificacion.tipo,
        "tipo_nombre": notificacion.get_tipo_display(),
        "mensaje": notificacion.mensaje,
        "destino": notificacion.destino_perfil.nombre_cargo if notificacion.destino_perfil else None,
        "leida": notificacion.leida,
        "fecha_lectura": notificacion.fecha_lectura,
    }


def _sin_leer(request):
    return mis_notificaciones(request).filter(leida=False).count()


class NotificacionListaView(APIView):
    """GET /api/notificaciones/: la bandeja, por páginas.

    Filtros: ?buscar (texto del mensaje), ?tipo (uno o varios) y ?estado (sin_leer o leida).
    """

    def get(self, request):
        notificaciones = mis_notificaciones(request).select_related("destino_perfil")
        parametros = request.query_params

        buscar = parametros.get("buscar", "").strip()
        if buscar:
            notificaciones = notificaciones.filter(mensaje__icontains=buscar)
        # ?tipo=A&tipo=B o ?tipo=A,B (la web en React manda las casillas separadas por coma)
        tipos = [tipo for valor in parametros.getlist("tipo") for tipo in valor.split(",") if tipo]
        if tipos:
            notificaciones = notificaciones.filter(tipo__in=tipos)
        estado = parametros.get("estado", "")
        if estado == "sin_leer":
            notificaciones = notificaciones.filter(leida=False)
        elif estado == "leida":
            notificaciones = notificaciones.filter(leida=True)

        return responder_paginado(
            request,
            notificaciones,
            _notificacion_a_dict,
            {
                "tipos": [{"valor": valor, "nombre": nombre} for valor, nombre in TIPOS],
                "sin_leer": _sin_leer(request),
            },
        )


class NotificacionEvaluarView(APIView):
    """POST /api/notificaciones/evaluar/: revisa ahora las reglas de comandas demoradas y cajas
    abiertas (lo mismo que el comando programado evaluar_alertas). Las alertas nuevas se guardan
    y se mandan por correo. Solo el Administrador.
    """

    def post(self, request):
        from empleados.decorators import NIVEL_ADMINISTRADOR, nivel_de
        from notificaciones.reglas import evaluar_cajas_abiertas, evaluar_comandas_demoradas

        if nivel_de(request.user) < NIVEL_ADMINISTRADOR:
            raise PermissionDenied("Solo el Administrador puede revisar las alertas.")
        comandas = evaluar_comandas_demoradas()
        cajas = evaluar_cajas_abiertas()
        return Response({"comandas_demoradas": comandas, "cajas_abiertas": cajas, "sin_leer": _sin_leer(request)})


class NotificacionSinLeerView(APIView):
    """GET /api/notificaciones/sin-leer/: el número de la campana del encabezado."""

    def get(self, request):
        return Response({"sin_leer": _sin_leer(request)})


class NotificacionLeidaView(APIView):
    """POST /api/notificaciones/<id>/leida/: marca una notificación como leída."""

    def post(self, request, pk):
        notificacion = get_object_or_404(mis_notificaciones(request), id_notificacion=pk)
        if not notificacion.leida:
            notificacion.leida = True
            notificacion.fecha_lectura = timezone.now()
            notificacion.save(update_fields=["leida", "fecha_lectura"])
        return Response(_notificacion_a_dict(notificacion))


class NotificacionMarcarTodasView(APIView):
    """POST /api/notificaciones/marcar-todas/: marca como leídas todas las del usuario."""

    def post(self, request):
        sin_leer = mis_notificaciones(request).filter(leida=False)
        cantidad = sin_leer.update(leida=True, fecha_lectura=timezone.now())
        return Response({"cantidad": cantidad})
