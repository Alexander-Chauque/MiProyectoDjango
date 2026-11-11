from datetime import datetime
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import render
from django.template.loader import get_template
from xhtml2pdf import pisa

from core.fechas import filtrar_por_fecha, limitar_rango
from empleados.decorators import permiso_requerido
from empleados.models import Empleado
from .models import LogAuditoria

# Un PDF con miles de filas tarda mucho en generarse y nadie lo lee entero
MAXIMO_PDF = 1000


def _filtrar_logs(request):
    """Aplica los filtros del GET. La usan el listado y la exportación, para que coincidan."""
    logs = LogAuditoria.objects.select_related("empleado").order_by("-fecha_hora")

    tabla = request.GET.get("tabla", "")
    accion = request.GET.get("accion", "")
    usuario = request.GET.get("usuario", "")
    detalle = request.GET.get("detalle", "").strip()
    fecha_desde, fecha_hasta = limitar_rango(
        request.GET.get("fecha_desde", ""), request.GET.get("fecha_hasta", "")
    )

    if tabla:
        logs = logs.filter(tabla=tabla)
    if accion:
        logs = logs.filter(accion=accion)
    if usuario.isdigit():
        logs = logs.filter(empleado_id=int(usuario))
    if detalle:
        logs = logs.filter(
            Q(valores_actuales__icontains=detalle)
            | Q(valores_anteriores__icontains=detalle)
        )
    logs = filtrar_por_fecha(logs, "fecha_hora", fecha_desde, fecha_hasta)

    filtros = {
        "tabla": tabla,
        "accion": accion,
        "usuario": usuario,
        "fecha_desde": fecha_desde,
        "fecha_hasta": fecha_hasta,
        "detalle": detalle,
    }
    return logs, filtros


@login_required
@permiso_requerido("auditoria", "leer")
def log_auditoria_listar(request):
    logs, filtros = _filtrar_logs(request)

    try:
        por_pagina = int(request.GET.get("por_pagina", 10))
    except (ValueError, TypeError):
        por_pagina = 10
    if por_pagina not in (10, 25, 50, 100):
        por_pagina = 10

    paginator = Paginator(logs, por_pagina)
    logs_paginados = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "auditoria/log_auditoria.html",
        {
            "logs": logs_paginados,
            "empleados": Empleado.objects.all().order_by("nombre_empleado"),
            "por_pagina": por_pagina,
            "filtros": filtros,
            # Con urlencode, un texto con & o espacios no rompe los enlaces
            "query_filtros": urlencode({k: v for k, v in filtros.items() if v}),
        },
    )


@login_required
@permiso_requerido("auditoria", "leer")
def exportar_auditoria_pdf(request):
    logs, filtros = _filtrar_logs(request)
    total = logs.count()

    usuario_nombre = ""
    if filtros["usuario"].isdigit():
        empleado = Empleado.objects.filter(id_empleado=int(filtros["usuario"])).first()
        if empleado:
            usuario_nombre = f"{empleado.nombre_empleado} {empleado.apellido_empleado}"

    html = get_template("auditoria/pdf_auditoria.html").render(
        {
            "logs": logs[:MAXIMO_PDF],
            "total": total,
            "recortado": total > MAXIMO_PDF,
            "maximo": MAXIMO_PDF,
            "filtros": filtros,
            "usuario_nombre": usuario_nombre,
        }
    )

    fecha_actual = datetime.now().strftime("%Y-%m-%d")
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="log_auditoria_{fecha_actual}.pdf"'
    )
    if pisa.CreatePDF(html, dest=response, encoding="utf-8").err:
        return HttpResponse("Error al generar el PDF", status=500)
    return response
