"""La cuenta de quien inició sesión: sus datos y su contraseña. Usa los formularios de la web."""
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.db import transaction
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from empleados.decorators import nivel_de
from empleados.forms import CambiarContrasenaForm, MiPerfilForm, NuevaContrasenaForm
from empleados.models import Empleado

from .views import _auditar
from .vistas_empleados import _rechazar_formulario
from .vistas_login import MENSAJE_DATOS_INCORRECTOS


def _perfil(request):
    empleado = request.user.empleado
    return {
        "id_empleado": empleado.id_empleado,
        "nombre_empleado": empleado.nombre_empleado,
        "apellido_empleado": empleado.apellido_empleado,
        "dni": empleado.dni,
        "correo": empleado.correo,
        "telefono": empleado.telefono or "",
        "usuario": request.user.username,
        "cargo": empleado.cargo.nombre_cargo if empleado.cargo else None,
        "nivel": nivel_de(request.user),
        "fecha_ingreso": empleado.fecha_ingreso,
    }


class PerfilView(APIView):
    """GET /api/perfil/ devuelve mis datos. PATCH cambia el correo y el teléfono."""

    def get(self, request):
        return Response(_perfil(request))

    def patch(self, request):
        empleado = request.user.empleado
        anterior = f"Correo: {empleado.correo}, Teléfono: {empleado.telefono or ''}"
        form = MiPerfilForm(
            {
                "correo": str(request.data.get("correo", empleado.correo) or "").strip(),
                "telefono": str(request.data.get("telefono", empleado.telefono) or "").strip(),
            },
            instance=empleado,
        )
        if not form.is_valid():
            _rechazar_formulario(form)
        with transaction.atomic():
            empleado = form.save()
            request.user.email = empleado.correo
            request.user.save(update_fields=["email"])
            _auditar(
                request, "Empleado", "MODIFICAR", empleado.pk, anterior,
                f"Correo: {empleado.correo}, Teléfono: {empleado.telefono or ''}",
            )
        return Response(_perfil(request))


class CambiarContrasenaView(APIView):
    """POST /api/perfil/contrasena/ con {actual, nueva, confirmar}.

    Después del cambio, los tokens anteriores dejan de servir: hay que volver a entrar.
    """

    def post(self, request):
        form = CambiarContrasenaForm(
            request.user,
            {
                "old_password": request.data.get("actual", ""),
                "new_password1": request.data.get("nueva", ""),
                "new_password2": request.data.get("confirmar", ""),
            },
        )
        if not form.is_valid():
            _rechazar_formulario(form)
        with transaction.atomic():
            form.save()
            empleado = request.user.empleado
            if empleado.debe_cambiar_contrasena:
                empleado.debe_cambiar_contrasena = False
                empleado.save()
            _auditar(request, "Empleado", "MODIFICAR", empleado.pk, "", "Cambió su propia contraseña")
        return Response({"detail": "Tu contraseña se actualizó correctamente."})


class CambioObligatorioView(APIView):
    """POST /api/token/cambiar-clave/ con {username, password, nueva, confirmar}.

    Para quien tiene una contraseña temporal: el login no le entrega tokens hasta que la cambie.
    """

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request):
        identificador = str(request.data.get("username") or "").strip()
        # Igual que el login: se puede usar el usuario o el correo
        if not User.objects.filter(username=identificador).exists():
            empleado = Empleado.objects.filter(correo__iexact=identificador, user__isnull=False).first()
            if empleado:
                identificador = empleado.user.username
        user = authenticate(username=identificador, password=str(request.data.get("password") or ""))
        empleado = Empleado.objects.filter(user=user, estado=True).first() if user else None
        if not empleado:
            raise ValidationError({"detail": MENSAJE_DATOS_INCORRECTOS})
        if not empleado.debe_cambiar_contrasena:
            raise ValidationError({"detail": "Tu contraseña no necesita cambiarse. Iniciá sesión normalmente."})

        form = NuevaContrasenaForm(
            user,
            {"new_password1": request.data.get("nueva", ""), "new_password2": request.data.get("confirmar", "")},
        )
        if not form.is_valid():
            _rechazar_formulario(form)
        with transaction.atomic():
            form.save()
            empleado.debe_cambiar_contrasena = False
            empleado.save()
            request.user = user  # _auditar registra al empleado de request.user
            _auditar(request, "Empleado", "MODIFICAR", empleado.pk, "", "Cambió la contraseña temporal")
        return Response({"detail": "Contraseña actualizada. Ya podés ingresar."})
