"""Permite que la app móvil use la API con la cuenta de Firebase del empleado."""
import logging

from django.conf import settings
from google.auth.exceptions import GoogleAuthError
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication

from empleados.models import Empleado

# Escribe avisos en la terminal donde corre Django
logger = logging.getLogger(__name__)


class FirebaseAuthentication(BaseAuthentication):
    """Django REST Framework ejecuta esta clase sola, en cada pedido a la API."""

    def authenticate(self, request):
        # La app envía el token en esta cabecera: "Authorization: Bearer <token>"
        cabecera = request.headers.get("Authorization", "")
        if not cabecera.startswith("Bearer "):
            return None  # Sin token: la API responde 401

        proyecto = settings.FIREBASE_PROJECT_ID
        try:
            # Comprueba la firma, el vencimiento y que el token sea de nuestro proyecto.
            # Descarga los certificados públicos de Google, así que necesita internet.
            datos = id_token.verify_firebase_token(
                cabecera[7:],
                google_requests.Request(),
                audience=proyecto,
                # Tolera una pequeña diferencia de hora entre esta PC y Google.
                # Sin esto, un token recién creado puede parecer "del futuro".
                clock_skew_in_seconds=10,
            )
        except (ValueError, GoogleAuthError) as error:
            # Muestra el motivo real en la terminal de Django, sin mostrar el token
            logger.warning("Token de Firebase rechazado: %s", error)
            raise AuthenticationFailed("Token inválido")

        if datos.get("iss") != f"https://securetoken.google.com/{proyecto}":
            raise AuthenticationFailed("Token inválido")

        # Sin esto, alguien podría registrarse en Firebase con el correo de un
        # empleado, sin ser el dueño del correo, y entrar en su lugar.
        if not datos.get("email_verified"):
            raise AuthenticationFailed("Verificá tu correo para continuar.")

        # El correo es lo que une la cuenta de Firebase con el empleado de Django
        empleado = (
            Empleado.objects.filter(
                correo__iexact=datos["email"], estado=True, user__is_active=True
            )
            .select_related("user")
            .first()
        )
        if not empleado:
            raise AuthenticationFailed("Tu correo no corresponde a un empleado activo.")

        # A partir de acá, request.user es el usuario de Django del empleado
        return (empleado.user, datos)

    def authenticate_header(self, request):
        # Hace que la API responda 401 (no autenticado) en vez de 403 (sin permiso)
        return "Bearer"


class JWTEmpleadoAuthentication(JWTAuthentication):
    """Permite que la web en React use la API. La cabecera es "Authorization: JWT <token>"."""

    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        # Un token ya entregado deja de servir si dan de baja al empleado
        # o si tiene un cambio de contraseña pendiente
        activo = Empleado.objects.filter(
            user=user, estado=True, debe_cambiar_contrasena=False
        ).exists()
        if not activo:
            raise AuthenticationFailed("Tu usuario ya no tiene acceso al sistema.")
        return user
