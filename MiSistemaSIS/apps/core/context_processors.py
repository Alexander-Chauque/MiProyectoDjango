from empleados.decorators import NIVEL_ADMINISTRADOR, nivel_de
from empleados.models import PermisoXCargo, TipoPermiso


def menu(request):
    """Módulos que el usuario puede leer, para mostrar solo esas opciones en el menú lateral.

    Sigue la misma regla que tiene_permiso(): el administrador ve todo y el resto,
    lo que su cargo tiene asignado. Es una sola consulta por página.
    """
    if not request.user.is_authenticated:
        return {"menu_modulos": set()}
    if nivel_de(request.user) >= NIVEL_ADMINISTRADOR:
        modulos = {clave for clave, _ in TipoPermiso._meta.get_field("modulo").choices}
    else:
        modulos = set(
            PermisoXCargo.objects.filter(
                cargo__empleado__user=request.user,
                tipo_permiso__accion="leer",
            ).values_list("tipo_permiso__modulo", flat=True)
        )
    return {"menu_modulos": modulos}
