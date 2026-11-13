from django import template

from reportes.consolidados import REPORTES

register = template.Library()


@register.simple_tag(takes_context=True)
def consolidados_visibles(context):
    """Pestañas de reportes consolidados que el usuario puede abrir según su perfil."""
    # Importado acá para evitar una importación circular con views
    from reportes.views import puede_ver_consolidado

    user = context["request"].user
    return [
        {"clave": clave, "nombre": r["nombre"], "icono": r["icono"]}
        for clave, r in REPORTES.items()
        if puede_ver_consolidado(user, clave)
    ]
