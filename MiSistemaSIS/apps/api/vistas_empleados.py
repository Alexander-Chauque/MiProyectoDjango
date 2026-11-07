"""Empleados en la API. Usa los mismos formularios y reglas de nivel que el sistema web."""
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from empleados.decorators import puede_gestionar, tiene_permiso
from empleados.forms import EmpleadoAltaForm, EmpleadoModificacionForm, RestablecerContrasenaForm
from empleados.models import Cargo, Empleado

from .permisos import PermisoDeModulo
from .views import _auditar

SIN_NIVEL_EMPLEADO = "No podés gestionar a un empleado con un nivel de acceso igual o superior al tuyo."
SIN_NIVEL_CARGO = "No podés asignar un cargo con un nivel de acceso igual o superior al tuyo."

# Lo único que la app puede enviar al crear o editar. Evita que cambie otros campos, como el estado.
CAMPOS_EDITABLES = ("nombre_empleado", "apellido_empleado", "dni", "telefono", "correo", "cargo")


def _nivel_empleado(empleado):
    return empleado.cargo.nivel_acceso if empleado.cargo else 0


class EmpleadoSerializer(serializers.ModelSerializer):
    """Solo sirve para responder. Nunca incluye la contraseña ni el sueldo."""

    cargo_nombre = serializers.CharField(source="cargo.nombre_cargo", default=None)
    # Le indica a la app qué botones mostrar. Django vuelve a comprobarlo en cada acción.
    puede_gestionar = serializers.SerializerMethodField()
    es_yo = serializers.SerializerMethodField()

    class Meta:
        model = Empleado
        fields = [
            "id_empleado",
            "nombre_empleado",
            "apellido_empleado",
            "dni",
            "telefono",
            "correo",
            "user_auto",
            "fecha_ingreso",
            "fecha_baja",
            "estado",
            "cargo",
            "cargo_nombre",
            "puede_gestionar",
            "es_yo",
        ]
        read_only_fields = fields

    def get_puede_gestionar(self, empleado):
        return puede_gestionar(self.context["request"].user, _nivel_empleado(empleado))

    def get_es_yo(self, empleado):
        return empleado.user_id == self.context["request"].user.pk


def _responder(request, empleado, codigo=status.HTTP_200_OK):
    return Response(EmpleadoSerializer(empleado, context={"request": request}).data, status=codigo)


def _rechazar_formulario(form):
    """Devuelve los errores del formulario con el formato que entiende la app."""
    raise ValidationError({campo: [str(error) for error in lista] for campo, lista in form.errors.items()})


def _datos_desde_pedido(request, empleado=None):
    """Arma los datos del formulario solo con los campos permitidos."""
    datos = {}
    if empleado:
        datos = {
            "nombre_empleado": empleado.nombre_empleado,
            "apellido_empleado": empleado.apellido_empleado,
            "dni": empleado.dni,
            "telefono": empleado.telefono or "",
            "correo": empleado.correo,
            "cargo": empleado.cargo_id or "",
        }
    for campo in CAMPOS_EDITABLES:
        if campo in request.data:
            valor = request.data[campo]
            datos[campo] = "" if valor is None else str(valor).strip()

    if not datos.get("correo"):
        raise ValidationError({"correo": ["Ingresá el correo: la app lo usa para reconocer al empleado."]})
    if not datos.get("cargo"):
        raise ValidationError({"cargo": ["Seleccioná un cargo."]})

    # La app une la cuenta de Firebase con el empleado por correo, sin distinguir mayúsculas.
    repetidos = Empleado.objects.filter(correo__iexact=datos["correo"])
    if empleado:
        repetidos = repetidos.exclude(pk=empleado.pk)
    if repetidos.exists():
        raise ValidationError({"correo": ["Este correo ya está registrado en otro empleado."]})
    return datos


def _exigir_nivel(request, empleado):
    if not puede_gestionar(request.user, _nivel_empleado(empleado)):
        raise PermissionDenied(SIN_NIVEL_EMPLEADO)


def _exigir_nivel_cargo(request, form):
    cargo = form.cleaned_data.get("cargo")
    if cargo and not puede_gestionar(request.user, cargo.nivel_acceso):
        raise PermissionDenied(SIN_NIVEL_CARGO)


class CargosParaEmpleadoView(APIView):
    """GET /api/empleados/cargos/: los cargos para elegir en el formulario, sin el sueldo."""

    permission_classes = [PermisoDeModulo]
    modulo = "empleados"
    accion = "leer"

    def get(self, request):
        return Response(
            [
                {
                    "id_cargo": cargo.pk,
                    "nombre_cargo": cargo.nombre_cargo,
                    "gestionable": puede_gestionar(request.user, cargo.nivel_acceso),
                }
                for cargo in Cargo.objects.order_by("nombre_cargo")
            ]
        )


class EmpleadoListaView(APIView):
    """GET /api/empleados/ lista los empleados. POST /api/empleados/ crea uno y su usuario."""

    permission_classes = [PermisoDeModulo]
    modulo = "empleados"

    def get(self, request):
        empleados = Empleado.objects.select_related("cargo").order_by("apellido_empleado", "nombre_empleado")
        return Response(EmpleadoSerializer(empleados, many=True, context={"request": request}).data)

    def post(self, request):
        datos = _datos_desde_pedido(request)
        datos["contrasena"] = request.data.get("contrasena", "")
        datos["confirmar_contrasena"] = request.data.get("confirmar_contrasena", "")
        form = EmpleadoAltaForm(datos)
        if not form.is_valid():
            _rechazar_formulario(form)
        _exigir_nivel_cargo(request, form)
        try:
            # atomic(): si algo falla, no queda un usuario sin empleado
            with transaction.atomic():
                empleado = form.save()
                _auditar(
                    request, "Empleado", "CREAR", empleado.pk, "",
                    f"Empleado creado: {empleado.get_full_name()}. Usuario: {empleado.user_auto}",
                )
        except IntegrityError:
            raise ValidationError({"detail": "Ya existe un usuario con esos datos. Revisá el nombre, el apellido y el correo."})
        return _responder(request, empleado, status.HTTP_201_CREATED)


class EmpleadoDetalleView(APIView):
    """GET /api/empleados/5/ devuelve uno. PATCH /api/empleados/5/ lo edita. No se elimina: se da de baja."""

    permission_classes = [PermisoDeModulo]
    modulo = "empleados"

    def get(self, request, pk):
        return _responder(request, get_object_or_404(Empleado.objects.select_related("cargo"), pk=pk))

    def patch(self, request, pk):
        empleado = get_object_or_404(Empleado.objects.select_related("cargo"), pk=pk)
        _exigir_nivel(request, empleado)
        form = EmpleadoModificacionForm(_datos_desde_pedido(request, empleado), instance=empleado)
        # El formulario modifica la instancia al validar: el texto anterior se arma antes
        anterior = f"Nombre: {empleado.nombre_empleado}, Apellido: {empleado.apellido_empleado}, Correo: {empleado.correo}"
        if not form.is_valid():
            _rechazar_formulario(form)
        _exigir_nivel_cargo(request, form)
        try:
            with transaction.atomic():
                guardado = form.save()
                if guardado.user:
                    # El mismo dato en la tabla de usuarios, como hace la web
                    guardado.user.first_name = guardado.nombre_empleado
                    guardado.user.last_name = guardado.apellido_empleado
                    guardado.user.email = guardado.correo
                    guardado.user.save()
                _auditar(
                    request, "Empleado", "MODIFICAR", guardado.pk, anterior,
                    f"Nombre: {guardado.nombre_empleado}, Apellido: {guardado.apellido_empleado}, Correo: {guardado.correo}",
                )
        except IntegrityError:
            raise ValidationError({"detail": "Ya existe un usuario con esos datos. Revisá el nombre, el apellido y el correo."})
        return _responder(request, guardado)


class EmpleadoEstadoView(APIView):
    """POST /api/empleados/5/estado/: da de baja o reactiva, según su estado actual."""

    permission_classes = [PermisoDeModulo]
    modulo = "empleados"
    accion = "leer"  # El permiso real depende de si es baja o reactivación: se controla abajo

    def post(self, request, pk):
        empleado = get_object_or_404(Empleado.objects.select_related("cargo"), pk=pk)
        es_baja = empleado.estado
        if not tiene_permiso(request.user, "empleados", "eliminar" if es_baja else "modificar"):
            raise PermissionDenied("No tenés permiso para realizar esta acción.")
        if es_baja and empleado.user_id == request.user.pk:
            raise ValidationError({"detail": "No podés darte de baja a vos mismo."})
        _exigir_nivel(request, empleado)

        with transaction.atomic():
            if es_baja:
                empleado.dar_baja()
                _auditar(request, "Empleado", "MODIFICAR", empleado.pk, "Estado: Activo", "Estado: Dado de baja.")
            else:
                empleado.reactivar()
                _auditar(request, "Empleado", "MODIFICAR", empleado.pk, "Estado: Inactivo", "Estado: Reactivado.")
        return _responder(request, empleado)


class EmpleadoContrasenaView(APIView):
    """POST /api/empleados/5/contrasena/: define una contraseña temporal para la web."""

    permission_classes = [PermisoDeModulo]
    modulo = "empleados"
    accion = "modificar"

    def post(self, request, pk):
        empleado = get_object_or_404(Empleado.objects.select_related("cargo"), pk=pk)
        _exigir_nivel(request, empleado)
        if not empleado.user:
            raise ValidationError({"detail": "Este empleado no tiene un usuario para iniciar sesión."})
        form = RestablecerContrasenaForm(
            {
                "nueva_contrasena": request.data.get("nueva_contrasena", ""),
                "confirmar_contrasena": request.data.get("confirmar_contrasena", ""),
            }
        )
        if not form.is_valid():
            _rechazar_formulario(form)
        with transaction.atomic():
            empleado.cambiar_contrasena(form.cleaned_data["nueva_contrasena"])
            _auditar(request, "Empleado", "MODIFICAR", empleado.pk, "", f"Contraseña restablecida para {empleado.user_auto}")
        return Response({"detail": f"Contraseña restablecida para {empleado.user_auto}."})
