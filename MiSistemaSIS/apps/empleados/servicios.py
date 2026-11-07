"""Reglas de permisos que comparten el sistema web y la API de la app."""
from django.db import transaction

from .decorators import NIVEL_ADMINISTRADOR, nivel_de, tiene_permiso
from .models import PermisoXCargo, TipoPermiso


def es_administrador(usuario):
    return nivel_de(usuario) >= NIVEL_ADMINISTRADOR


def _describir(cargo):
    filas = PermisoXCargo.objects.filter(cargo=cargo).values_list(
        "tipo_permiso__modulo", "tipo_permiso__accion"
    )
    return ", ".join(f"{modulo}-{accion}" for modulo, accion in filas) or "Sin permisos"


def asignar_permisos_a_cargo(usuario, cargo, ids_permisos):
    """
    Deja al cargo exactamente con estos permisos y devuelve (permisos_anteriores, permisos_nuevos).
    ValueError: algún permiso no existe. PermissionError: agrega un permiso que el usuario no tiene.
    """
    ids = {int(identificador) for identificador in ids_permisos}
    nuevos = list(TipoPermiso.objects.filter(pk__in=ids))
    if len(nuevos) != len(ids):
        raise ValueError("Uno de los permisos elegidos ya no existe.")

    actuales = set(PermisoXCargo.objects.filter(cargo=cargo).values_list("tipo_permiso_id", flat=True))
    # Solo el administrador puede repartir permisos que no tiene.
    # Quitar sí se permite: nunca le da más acceso a nadie.
    if not es_administrador(usuario):
        for permiso in nuevos:
            if permiso.pk not in actuales and not tiene_permiso(usuario, permiso.modulo, permiso.accion):
                raise PermissionError(
                    f"No podés asignar el permiso {permiso.modulo}-{permiso.accion} porque no lo tenés."
                )

    # atomic(): si algo falla, el cargo conserva los permisos que tenía
    with transaction.atomic():
        anteriores = _describir(cargo)
        PermisoXCargo.objects.filter(cargo=cargo).exclude(tipo_permiso_id__in=ids).delete()
        for permiso in nuevos:
            PermisoXCargo.objects.get_or_create(cargo=cargo, tipo_permiso=permiso)
    return anteriores, _describir(cargo)
