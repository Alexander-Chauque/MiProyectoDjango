from .views import mis_notificaciones
def sin_leer(request):
    """Cantidad de notificaciones sin leer, disponible en todas las plantillas."""
    if not request.user.is_authenticated:
        return {"notificaciones_sin_leer": 0}
    return {
        "notificaciones_sin_leer": mis_notificaciones(request)
        .filter(leida=False)
        .count()
    }
