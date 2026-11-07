"""Cargos y permisos en la API. Usa los mismos formularios y reglas que el sistema web."""
from django.db import transaction
from django.db.models import Count, ProtectedError
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from empleados.decorators import puede_gestionar
from empleados.forms import CargoForm, PermisoForm
from empleados.models import Cargo, PermisoXCargo, TipoPermiso
from empleados.servicios import asignar_permisos_a_cargo, es_administrador

from .permisos import PermisoDeModulo
from .views import _auditar
from .vistas_empleados import SIN_NIVEL_CARGO, _rechazar_formulario

MODULOS = TipoPermiso._meta.get_field("modulo").choices
ACCIONES = TipoPermiso._meta.get_field("accion").choices
NOMBRE_MODULO = dict(MODULOS)
NOMBRE_ACCION = dict(ACCIONES)

CAMPOS_CARGO = ("nombre_cargo", "descripcion_cargo", "nivel_acceso", "sueldo_cargo")


def _cargos_con_totales():
    # distinct=True: sin esto, contar dos relaciones a la vez multiplica los resultados
    return Cargo.objects.annotate(
        total_empleados=Count("empleado", distinct=True),
        total_permisos=Count("permisoxcargo", distinct=True),
    )


def _cargo_a_dict(request, cargo):
    return {
        "id_cargo": cargo.pk,
        "nombre_cargo": cargo.nombre_cargo,
        "descripcion_cargo": cargo.descripcion_cargo,
        "nivel_acceso": cargo.nivel_acceso,
        "sueldo_cargo": str(cargo.sueldo_cargo),
        "total_empleados": cargo.total_empleados,
        "total_permisos": cargo.total_permisos,
        # Le indica a la app qué botones mostrar. Django vuelve a comprobarlo en cada acción.
        "gestionable": puede_gestionar(request.user, cargo.nivel_acceso),
    }


def _permiso_a_dict(permiso):
    return {
        "id_tipo_permiso": permiso.pk,
        "modulo": permiso.modulo,
        "modulo_nombre": NOMBRE_MODULO.get(permiso.modulo, permiso.modulo),
        "accion": permiso.accion,
        "accion_nombre": NOMBRE_ACCION.get(permiso.accion, permiso.accion),
    }


def _describir(cargo):
    return f"Nombre: {cargo.nombre_cargo}, Nivel: {cargo.nivel_acceso}, Sueldo: {cargo.sueldo_cargo}"


def _exigir_nivel(request, nivel):
    if not puede_gestionar(request.user, int(nivel)):
        raise PermissionDenied(SIN_NIVEL_CARGO)


def _datos_cargo(request, cargo=None):
    """Arma los datos del formulario solo con los campos permitidos."""
    datos = {}
    if cargo:
        datos = {
            "nombre_cargo": cargo.nombre_cargo,
            "descripcion_cargo": cargo.descripcion_cargo,
            "nivel_acceso": cargo.nivel_acceso,
            "sueldo_cargo": cargo.sueldo_cargo,
        }
    for campo in CAMPOS_CARGO:
        if campo in request.data:
            valor = request.data[campo]
            datos[campo] = "" if valor is None else str(valor).strip()
    return datos


class CargoListaView(APIView):
    """GET /api/cargos/ lista los cargos. POST /api/cargos/ crea uno."""

    permission_classes = [PermisoDeModulo]
    modulo = "cargos"

    def get(self, request):
        cargos = _cargos_con_totales().order_by("nombre_cargo")
        return Response([_cargo_a_dict(request, cargo) for cargo in cargos])

    def post(self, request):
        form = CargoForm(_datos_cargo(request))
        if not form.is_valid():
            _rechazar_formulario(form)
        _exigir_nivel(request, form.cleaned_data["nivel_acceso"])
        with transaction.atomic():
            cargo = form.save()
            _auditar(request, "Cargo", "CREAR", cargo.pk, "", f"Cargo creado. {_describir(cargo)}")
        return Response(
            _cargo_a_dict(request, _cargos_con_totales().get(pk=cargo.pk)),
            status=status.HTTP_201_CREATED,
        )


class CargoDetalleView(APIView):
    """GET devuelve el cargo y sus permisos. PATCH lo edita. DELETE lo elimina si no tiene empleados."""

    permission_classes = [PermisoDeModulo]
    modulo = "cargos"

    def get(self, request, pk):
        cargo = get_object_or_404(_cargos_con_totales(), pk=pk)
        datos = _cargo_a_dict(request, cargo)
        datos["permisos"] = list(
            PermisoXCargo.objects.filter(cargo=cargo).values_list("tipo_permiso_id", flat=True)
        )
        return Response(datos)

    def patch(self, request, pk):
        cargo = get_object_or_404(Cargo, pk=pk)
        _exigir_nivel(request, cargo.nivel_acceso)
        anterior = _describir(cargo)
        form = CargoForm(_datos_cargo(request, cargo), instance=cargo)
        if not form.is_valid():
            _rechazar_formulario(form)
        _exigir_nivel(request, form.cleaned_data["nivel_acceso"])
        with transaction.atomic():
            guardado = form.save()
            _auditar(request, "Cargo", "MODIFICAR", guardado.pk, anterior, _describir(guardado))
        return Response(_cargo_a_dict(request, _cargos_con_totales().get(pk=guardado.pk)))

    def delete(self, request, pk):
        cargo = get_object_or_404(Cargo, pk=pk)
        _exigir_nivel(request, cargo.nivel_acceso)
        if cargo.empleado_set.exists():
            raise ValidationError(
                {"detail": f'No se puede eliminar "{cargo.nombre_cargo}" porque tiene empleados asignados.'}
            )
        anterior = _describir(cargo)
        identificador = cargo.pk
        try:
            with transaction.atomic():
                cargo.delete()
                _auditar(request, "Cargo", "ELIMINAR", identificador, anterior, "Cargo eliminado")
        except ProtectedError:
            # Un empleado pudo recibir este cargo justo después de la comprobación
            raise ValidationError({"detail": "No se puede eliminar porque tiene empleados asignados."})
        return Response(status=status.HTTP_204_NO_CONTENT)


class CargoPermisosView(APIView):
    """POST /api/cargos/5/permisos/ con {"permisos": [1, 2]}: deja al cargo con esos permisos."""

    permission_classes = [PermisoDeModulo]
    modulo = "cargos"
    accion = "modificar"

    def post(self, request, pk):
        cargo = get_object_or_404(Cargo, pk=pk)
        _exigir_nivel(request, cargo.nivel_acceso)
        ids = request.data.get("permisos")
        if not isinstance(ids, list) or not all(isinstance(i, int) and not isinstance(i, bool) for i in ids):
            raise ValidationError({"permisos": ["La lista de permisos no es válida."]})
        try:
            with transaction.atomic():
                anteriores, nuevos = asignar_permisos_a_cargo(request.user, cargo, ids)
                _auditar(request, "Cargo", "MODIFICAR", cargo.pk, f"Permisos: {anteriores}", f"Permisos: {nuevos}")
        except ValueError as error:
            raise ValidationError({"detail": str(error)})
        except PermissionError as error:
            raise PermissionDenied(str(error))
        return Response({"permisos": sorted(set(ids))})


class PermisoListaView(APIView):
    """GET /api/permisos/ lista los permisos y las opciones. POST crea uno. Crearlo no se lo da a nadie."""

    permission_classes = [PermisoDeModulo]
    modulo = "cargos"

    def get(self, request):
        return Response(
            {
                "permisos": [_permiso_a_dict(p) for p in TipoPermiso.objects.order_by("modulo", "accion")],
                "modulos": [{"valor": valor, "nombre": nombre} for valor, nombre in MODULOS],
                "acciones": [{"valor": valor, "nombre": nombre} for valor, nombre in ACCIONES],
                "es_administrador": es_administrador(request.user),
            }
        )

    def post(self, request):
        form = PermisoForm({"modulo": request.data.get("modulo", ""), "accion": request.data.get("accion", "")})
        if not form.is_valid():
            _rechazar_formulario(form)
        with transaction.atomic():
            permiso = form.save()
            _auditar(
                request, "Permiso", "CREAR", permiso.pk, "",
                f"Permiso creado: Módulo {permiso.modulo} - Acción {permiso.accion}",
            )
        return Response(_permiso_a_dict(permiso), status=status.HTTP_201_CREATED)


class PermisoDetalleView(APIView):
    """DELETE /api/permisos/5/: lo quita de todos los cargos, por eso solo lo hace un administrador."""

    permission_classes = [PermisoDeModulo]
    modulo = "cargos"

    def delete(self, request, pk):
        permiso = get_object_or_404(TipoPermiso, pk=pk)
        if not es_administrador(request.user):
            raise PermissionDenied("Solo un administrador puede eliminar permisos.")
        descripcion = str(permiso)
        identificador = permiso.pk
        with transaction.atomic():
            permiso.delete()
            _auditar(request, "Permiso", "ELIMINAR", identificador, descripcion, "Permiso eliminado")
        return Response(status=status.HTTP_204_NO_CONTENT)
