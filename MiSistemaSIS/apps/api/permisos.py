"""Aplica en la API los mismos permisos que usa el sistema web."""
from rest_framework.permissions import BasePermission

from empleados.decorators import tiene_permiso

# Qué permiso del sistema necesita cada tipo de pedido
ACCION_POR_METODO = {
    "GET": "leer",
    "HEAD": "leer",
    "OPTIONS": "leer",
    "POST": "escribir",
    "PUT": "modificar",
    "PATCH": "modificar",
    "DELETE": "eliminar",
}


class PermisoDeModulo(BasePermission):
    """Cada vista indica su módulo con `modulo`, y opcionalmente fija la acción con `accion`."""

    message = "No tenés permiso para realizar esta acción."

    def has_permission(self, request, view):
        accion = getattr(view, "accion", None) or ACCION_POR_METODO.get(request.method)
        return bool(
            request.user
            and request.user.is_authenticated
            and accion
            and tiene_permiso(request.user, view.modulo, accion)
        )
