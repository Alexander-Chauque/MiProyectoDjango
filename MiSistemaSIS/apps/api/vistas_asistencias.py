"""Asistencias y turnos en la API. Piden los permisos del módulo "empleados", como la web."""
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from empleados.models import Asistencia, Empleado, TipoAsistencia

from .permisos import PermisoDeModulo
from .utilidades import leer_texto, rango_pedido, responder_paginado
from .views import _auditar

TURNOS = dict(TipoAsistencia.TIPOS)


def _tipo_a_dict(tipo):
    return {
        "id_tipo_asistencia": tipo.id_tipo_asistencia,
        "nombre_tipo_asis": tipo.nombre_tipo_asis,
        "nombre": tipo.get_nombre_tipo_asis_display(),
        "desc_tipo_asistencia": tipo.desc_tipo_asistencia,
    }


def _asistencia_a_dict(asistencia):
    return {
        "id_asistencia": asistencia.id_asistencia,
        "empleado": asistencia.id_empleado_id,
        "empleado_nombre": asistencia.id_empleado.get_full_name(),
        "tipo": asistencia.id_tipo_asistencia_id,
        "tipo_nombre": asistencia.id_tipo_asistencia.get_nombre_tipo_asis_display(),
        "fecha_asistencia": asistencia.fecha_asistencia,
    }


def _describir(asistencia):
    return (
        f"Empleado: {asistencia.id_empleado.get_full_name()}, Fecha: {asistencia.fecha_asistencia}, "
        f"Turno: {asistencia.id_tipo_asistencia.nombre_tipo_asis}"
    )


def _leer_tipo(request):
    identificador = str(request.data.get("tipo") or "")
    tipo = TipoAsistencia.objects.filter(pk=int(identificador)).first() if identificador.isdigit() else None
    if not tipo:
        raise ValidationError({"tipo": ["Seleccioná un turno."]})
    return tipo


class AsistenciaListaView(APIView):
    """GET /api/asistencias/ lista por páginas (?buscar, ?tipo, ?fecha_desde, ?fecha_hasta).

    POST registra la asistencia de hoy de un empleado activo. Una por día.
    """

    permission_classes = [PermisoDeModulo]
    modulo = "empleados"

    def get(self, request):
        asistencias = Asistencia.objects.select_related("id_empleado", "id_tipo_asistencia").order_by(
            "-fecha_asistencia", "-id_asistencia"
        )
        buscar = request.query_params.get("buscar", "").strip()
        if buscar:
            asistencias = asistencias.filter(
                Q(id_empleado__nombre_empleado__icontains=buscar) | Q(id_empleado__apellido_empleado__icontains=buscar)
            )
        tipo = request.query_params.get("tipo", "")
        if tipo.isdigit():
            asistencias = asistencias.filter(id_tipo_asistencia_id=int(tipo))
        desde, hasta = rango_pedido(request)
        if desde:
            asistencias = asistencias.filter(fecha_asistencia__gte=desde)
        if hasta:
            asistencias = asistencias.filter(fecha_asistencia__lte=hasta)
        return responder_paginado(
            request, asistencias, _asistencia_a_dict,
            {
                "hoy": timezone.localdate(),
                "tipos": [_tipo_a_dict(t) for t in TipoAsistencia.objects.order_by("nombre_tipo_asis")],
                "empleados_activos": [
                    {"id": e.id_empleado, "nombre": e.get_full_name()}
                    for e in Empleado.objects.filter(estado=True).order_by("nombre_empleado", "apellido_empleado")
                ],
            },
        )

    def post(self, request):
        identificador = str(request.data.get("empleado") or "")
        empleado = (
            Empleado.objects.filter(pk=int(identificador), estado=True).first() if identificador.isdigit() else None
        )
        if not empleado:
            raise ValidationError({"empleado": ["Seleccioná un empleado activo."]})
        tipo = _leer_tipo(request)
        # La fecha de Salta: la de timezone.now() ya es mañana después de las 21:00
        hoy = timezone.localdate()
        with transaction.atomic():
            if Asistencia.objects.select_for_update().filter(id_empleado=empleado, fecha_asistencia=hoy).exists():
                raise ValidationError({"detail": "Este empleado ya tiene una asistencia registrada hoy."})
            asistencia = Asistencia.objects.create(id_empleado=empleado, id_tipo_asistencia=tipo, fecha_asistencia=hoy)
            _auditar(request, "Asistencia", "CREAR", asistencia.pk, "", f"Asistencia registrada. {_describir(asistencia)}")
        return Response(_asistencia_a_dict(asistencia), status=status.HTTP_201_CREATED)


class AsistenciaDetalleView(APIView):
    """PATCH /api/asistencias/5/ cambia el turno. DELETE la anula."""

    permission_classes = [PermisoDeModulo]
    modulo = "empleados"

    def patch(self, request, pk):
        asistencia = get_object_or_404(Asistencia.objects.select_related("id_empleado", "id_tipo_asistencia"), pk=pk)
        tipo = _leer_tipo(request)
        anterior = _describir(asistencia)
        with transaction.atomic():
            asistencia.id_tipo_asistencia = tipo
            asistencia.save()
            _auditar(request, "Asistencia", "MODIFICAR", asistencia.pk, anterior, _describir(asistencia))
        return Response(_asistencia_a_dict(asistencia))

    def delete(self, request, pk):
        asistencia = get_object_or_404(Asistencia.objects.select_related("id_empleado", "id_tipo_asistencia"), pk=pk)
        anterior = f"Asistencia anulada. {_describir(asistencia)}"
        with transaction.atomic():
            _auditar(request, "Asistencia", "ANULAR", asistencia.pk, anterior, "")
            asistencia.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


def _leer_turno(request, tipo=None):
    nombre = str(request.data.get("nombre_tipo_asis") or "").strip().lower()
    if nombre not in TURNOS:
        raise ValidationError({"nombre_tipo_asis": ["Seleccioná un turno válido."]})
    repetidos = TipoAsistencia.objects.filter(nombre_tipo_asis=nombre)
    if tipo:
        repetidos = repetidos.exclude(pk=tipo.pk)
    if repetidos.exists():
        raise ValidationError({"nombre_tipo_asis": [f'El turno "{TURNOS[nombre]}" ya existe.']})
    return nombre, leer_texto(request, "desc_tipo_asistencia")


class TipoAsistenciaListaView(APIView):
    """GET /api/tipos-asistencia/ lista los turnos y las opciones. POST crea uno."""

    permission_classes = [PermisoDeModulo]
    modulo = "empleados"

    def get(self, request):
        return Response(
            {
                "tipos": [_tipo_a_dict(t) for t in TipoAsistencia.objects.order_by("nombre_tipo_asis")],
                "opciones": [{"valor": valor, "nombre": nombre} for valor, nombre in TipoAsistencia.TIPOS],
            }
        )

    def post(self, request):
        nombre, descripcion = _leer_turno(request)
        with transaction.atomic():
            tipo = TipoAsistencia.objects.create(nombre_tipo_asis=nombre, desc_tipo_asistencia=descripcion)
            _auditar(
                request, "TipoAsistencia", "CREAR", tipo.pk, "",
                f"Tipo de turno creado: {tipo.nombre_tipo_asis}. Descripción: {descripcion}",
            )
        return Response(_tipo_a_dict(tipo), status=status.HTTP_201_CREATED)


class TipoAsistenciaDetalleView(APIView):
    """PATCH /api/tipos-asistencia/5/ lo edita. DELETE lo elimina si no tiene asistencias."""

    permission_classes = [PermisoDeModulo]
    modulo = "empleados"

    def patch(self, request, pk):
        tipo = get_object_or_404(TipoAsistencia, pk=pk)
        nombre, descripcion = _leer_turno(request, tipo)
        anterior = f"Nombre: {tipo.nombre_tipo_asis}, Descripción: {tipo.desc_tipo_asistencia}"
        with transaction.atomic():
            tipo.nombre_tipo_asis = nombre
            tipo.desc_tipo_asistencia = descripcion
            tipo.save()
            _auditar(
                request, "TipoAsistencia", "MODIFICAR", tipo.pk, anterior,
                f"Nombre: {tipo.nombre_tipo_asis}, Descripción: {tipo.desc_tipo_asistencia}",
            )
        return Response(_tipo_a_dict(tipo))

    def delete(self, request, pk):
        tipo = get_object_or_404(TipoAsistencia, pk=pk)
        if tipo.asistencia_set.exists():
            raise ValidationError(
                {"detail": f'No se puede eliminar el turno "{tipo.get_nombre_tipo_asis_display()}" porque tiene asistencias registradas.'}
            )
        with transaction.atomic():
            _auditar(request, "TipoAsistencia", "ANULAR", tipo.pk, f"Turno eliminado: {tipo.nombre_tipo_asis}", "")
            tipo.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
