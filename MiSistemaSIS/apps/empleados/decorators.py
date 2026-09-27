from django.shortcuts import redirect
from django.contrib import messages
from functools import wraps
from empleados.models import PermisoXCargo

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
                empleado = request.user.empleado
                cargo = empleado.cargo
            except:
                messages.error(request, 'No tienes un cargo asignado. Contacta al administrador.')
                return redirect('home')
            
            # Si el cargo es nivel 5 (Administrador), dar acceso total
            if cargo.nivel_acceso >= 5:
                return view_func(request, *args, **kwargs)
            
            # Verificar si tiene el permiso específico
            tiene_permiso = PermisoXCargo.objects.filter(
                cargo=cargo,
                tipo_permiso__modulo=modulo,
                tipo_permiso__accion=accion
            ).exists()
            
            # Si no tiene permiso, mostrar mensaje y redirigir
            if not tiene_permiso:
                messages.error(
                    request, 
                    f'No tienes permiso para acceder a esta sección. '
                    f'Tu cargo "{cargo.nombre_cargo}" no permite la acción "{accion}" en "{modulo}".'
                )
                referer = request.META.get('HTTP_REFERER')
                if referer:
                    return redirect(referer)
                return redirect('home')
            
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator