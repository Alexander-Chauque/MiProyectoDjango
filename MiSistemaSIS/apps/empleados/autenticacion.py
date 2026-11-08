"""Permite que la web en React use la API con el token JWT del empleado."""
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication

from empleados.models import Empleado


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
