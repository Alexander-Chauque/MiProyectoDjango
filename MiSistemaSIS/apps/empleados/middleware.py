from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect

from .decorators import motivo_sin_acceso

# La API valida el acceso con su propio token (empleados/autenticacion.py)
RUTAS_LIBRES = ("/api/", "/static/", "/media/", "/admin/")


class AccesoPorCargoMiddleware:
    """
    Cierra la sesión de quien ya no puede usar el sistema.

    El login ya rechaza a los cargos sin acceso. Esto cubre el caso de una
    sesión abierta cuando el administrador le cambia el cargo al empleado
    (por ejemplo, de Mozo a Cocinero): en el siguiente clic sale del sistema.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        usuario = getattr(request, "user", None)
        if (
            usuario is not None
            and usuario.is_authenticated
            and not request.path.startswith(RUTAS_LIBRES)
        ):
            motivo = motivo_sin_acceso(usuario)
            if motivo:
                logout(request)
                messages.error(request, motivo)
                return redirect("login")
        return self.get_response(request)
