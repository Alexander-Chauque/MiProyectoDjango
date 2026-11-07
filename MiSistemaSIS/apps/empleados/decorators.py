from django.shortcuts import redirect
from django.contrib import messages
from functools import wraps
from empleados.models import Empleado, PermisoXCargo

NIVEL_ADMINISTRADOR = 5


def nivel_de(user):
    """Nivel de acceso del usuario, o 0 si no tiene empleado o cargo."""
    try:
        cargo = user.empleado.cargo
    except Empleado.DoesNotExist:
        return 0
    return cargo.nivel_acceso if cargo else 0


def puede_gestionar(user, nivel_objetivo):
    """Solo se gestiona a quien tiene un nivel menor al propio. El administrador gestiona a todos."""
    nivel = nivel_de(user)
    return nivel >= NIVEL_ADMINISTRADOR or nivel > nivel_objetivo


def tiene_permiso(user, modulo, accion):
    """El administrador tiene todos los permisos; el resto, los asignados a su cargo."""
    if nivel_de(user) >= NIVEL_ADMINISTRADOR:
        return True
    return PermisoXCargo.objects.filter(
        cargo__empleado__user=user,
        tipo_permiso__modulo=modulo,
        tipo_permiso__accion=accion,
    ).exists()


def permiso_requerido(modulo, accion):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            # Si no está logueado, redirigir al login
            if not request.user.is_authenticated:
                messages.warning(request, 'Debes iniciar sesión para acceder.')
                return redirect('login')

            # Obtener el empleado y su cargo
            try:
                cargo = request.user.empleado.cargo
            except Empleado.DoesNotExist:
                cargo = None
            if cargo is None:
                messages.error(request, 'No tienes un cargo asignado. Contacta al administrador.')
                return redirect('home')

            if tiene_permiso(request.user, modulo, accion):
                return view_func(request, *args, **kwargs)

            # Si no tiene permiso, mostrar mensaje y redirigir
            messages.error(
                request,
                f'No tienes permiso para acceder a esta sección. '
                f'Tu cargo "{cargo.nombre_cargo}" no permite la acción "{accion}" en "{modulo}".'
            )
            referer = request.META.get('HTTP_REFERER')
            if referer:
                return redirect(referer)
            return redirect('home')
        return _wrapped_view
    return decorator
