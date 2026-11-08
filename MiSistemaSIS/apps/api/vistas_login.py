"""Login de la web en React. Entrega tokens JWT, con las mismas reglas que el login de Django."""
from django.contrib.auth.models import User
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView

from empleados.models import Empleado

MENSAJE_DATOS_INCORRECTOS = "Usuario, correo o contraseña incorrectos."


class LoginSerializer(TokenObtainPairSerializer):
    default_error_messages = {"no_active_account": MENSAJE_DATOS_INCORRECTOS}

    def validate(self, datos):
        identificador = datos[self.username_field].strip()
        # Se puede entrar con el usuario o con el correo del empleado
        if not User.objects.filter(username=identificador).exists():
            empleado = (
                Empleado.objects.filter(correo__iexact=identificador, user__isnull=False)
                .select_related("user")
                .first()
            )
            if empleado:
                identificador = empleado.user.username
        datos[self.username_field] = identificador

        # Comprueba la contraseña y genera los tokens. Si falla, responde 401.
        respuesta = super().validate(datos)

        empleado = Empleado.objects.filter(user=self.user, estado=True).first()
        if not empleado:
            raise AuthenticationFailed(MENSAJE_DATOS_INCORRECTOS)
        # No entrega tokens hasta que cambie la contraseña temporal en /api/token/cambiar-clave/.
        # "codigo" le indica a la web que muestre el formulario de cambio.
        if empleado.debe_cambiar_contrasena:
            raise AuthenticationFailed(
                {
                    "detail": "Tenés que cambiar tu contraseña temporal antes de continuar.",
                    "codigo": "debe_cambiar_contrasena",
                }
            )
        return respuesta


class LoginView(TokenObtainPairView):
    """POST /api/token/ con {username, password}: devuelve los tokens access y refresh."""

    serializer_class = LoginSerializer
    # Limita los intentos para dificultar que se adivine una contraseña
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"
