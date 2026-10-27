from .models import LogAuditoria


def registrar_auditoria(
    usuario,
    entidad,
    id_registro,
    accion,
    valores_anteriores,
    valores_actuales=None
):
    return LogAuditoria.objects.create(
        usuario=(
            usuario
            if getattr(usuario, 'is_authenticated', False)
            else None
        ),
        entidad=entidad,
        id_registro=str(id_registro),
        accion=accion,
        valores_anteriores=valores_anteriores,
        valores_actuales=valores_actuales
    )
