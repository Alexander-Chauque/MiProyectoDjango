from empleados.decorators import NIVEL_ADMINISTRADOR, nivel_de
from empleados.models import PermisoXCargo, TipoPermiso


def menu(request):
    """Módulos que el usuario puede leer, para mostrar solo esas opciones en el menú lateral.

    Sigue la misma regla que tiene_permiso(): el administrador ve todo y el resto,
    lo que su cargo tiene asignado. Es una sola consulta por página.
    """
    if not request.user.is_authenticated:
        return {"menu_modulos": set(), "menu_tomar_pedido": False}
    if nivel_de(request.user) >= NIVEL_ADMINISTRADOR:
        modulos = {clave for clave, _ in TipoPermiso._meta.get_field("modulo").choices}
        return {"menu_modulos": modulos, "menu_tomar_pedido": True}
    permisos = set(
        PermisoXCargo.objects.filter(
            cargo__empleado__user=request.user,
            tipo_permiso__accion__in=["leer", "escribir"],
        ).values_list("tipo_permiso__modulo", "tipo_permiso__accion")
    )
    return {
        "menu_modulos": {modulo for modulo, accion in permisos if accion == "leer"},
        # "Comandas" abre directamente la toma de pedido si el cargo puede crear comandas
        "menu_tomar_pedido": ("comandas", "escribir") in permisos,
    }
