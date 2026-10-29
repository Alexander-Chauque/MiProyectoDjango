from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.core.paginator import Paginator
from datetime import datetime
from .models import LogAuditoria
from empleados.models import Empleado
import csv
from django.http import HttpResponse
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment

@login_required
def log_auditoria_listar(request):
    logs = LogAuditoria.objects.all().select_related("empleado").order_by("-fecha_hora")

    # Capturamos los filtros
    tabla = request.GET.get("tabla", "")
    accion = request.GET.get("accion", "")
    usuario = request.GET.get("usuario", "")
    fecha_desde = request.GET.get("fecha_desde", "")
    fecha_hasta = request.GET.get("fecha_hasta", "")
    detalle = request.GET.get("detalle", "")

    if tabla:
        logs = logs.filter(tabla=tabla)
    if accion:
        logs = logs.filter(accion=accion)
    if usuario:
        logs = logs.filter(empleado_id=usuario)
    if detalle:
        logs = logs.filter(
            Q(valores_actuales__icontains=detalle)
            | Q(valores_anteriores__icontains=detalle)
        )
    if fecha_desde:
        try:
            fecha_desde_dt = datetime.strptime(fecha_desde, "%Y-%m-%d")
            logs = logs.filter(fecha_hora__date__gte=fecha_desde_dt)
        except ValueError:
            pass
    if fecha_hasta:
        try:
            fecha_hasta_dt = datetime.strptime(fecha_hasta, "%Y-%m-%d")
            logs = logs.filter(fecha_hora__date__lte=fecha_hasta_dt)
        except ValueError:
            pass

    # Paginación
    por_pagina = request.GET.get("por_pagina", 10)
    try:
        por_pagina = int(por_pagina)
        if por_pagina not in [10, 25, 50, 100]:
            por_pagina = 10
    except (ValueError, TypeError):
        por_pagina = 10

    paginator = Paginator(logs, por_pagina)
    page_number = request.GET.get("page")
    logs_paginados = paginator.get_page(page_number)

    empleados = Empleado.objects.all().order_by("nombre_empleado")

    return render(
        request,
        "auditoria/log_auditoria.html",
        {
            "logs": logs_paginados,
            "empleados": empleados,
            "por_pagina": por_pagina,
            "filtros": {
                "tabla": tabla,
                "accion": accion,
                "usuario": usuario,
                "fecha_desde": fecha_desde,
                "fecha_hasta": fecha_hasta,
                "detalle": detalle,
            },
        },
    )


@login_required
def exportar_auditoria_csv(request):
    logs = LogAuditoria.objects.all().select_related("empleado").order_by("-fecha_hora")

    # Capturamos los mismos filtros que en el listado
    tabla = request.GET.get("tabla", "")
    accion = request.GET.get("accion", "")
    usuario = request.GET.get("usuario", "")
    fecha_desde = request.GET.get("fecha_desde", "")
    fecha_hasta = request.GET.get("fecha_hasta", "")
    detalle = request.GET.get("detalle", "")

    if tabla:
        logs = logs.filter(tabla=tabla)
    if accion:
        logs = logs.filter(accion=accion)
    if usuario:
        logs = logs.filter(empleado_id=usuario)
    if detalle:
        logs = logs.filter(
            Q(valores_actuales__icontains=detalle)
            | Q(valores_anteriores__icontains=detalle)
        )
    if fecha_desde:
        try:
            fecha_desde_dt = datetime.strptime(fecha_desde, "%Y-%m-%d")
            logs = logs.filter(fecha_hora__date__gte=fecha_desde_dt)
        except ValueError:
            pass
    if fecha_hasta:
        try:
            fecha_hasta_dt = datetime.strptime(fecha_hasta, "%Y-%m-%d")
            logs = logs.filter(fecha_hora__date__lte=fecha_hasta_dt)
        except ValueError:
            pass
    # Crear libro de Excel
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Log de Auditoría"

    # ESTILOS PARA EL ENCABEZADO
    header_font = Font(bold=True, color="FFFFFF", size=12)
    header_fill = PatternFill(
        start_color="3D3D3D", end_color="3D3D3D", fill_type="solid"
    )  # Gris oscuro
    header_alignment = Alignment(horizontal="center", vertical="center")

    # Encabezados
    headers = [
        "Fecha y Hora",
        "Usuario",
        "Tabla",
        "Acción",
        "ID Registro",
        "Valores Anteriores",
        "Valores Actuales",
    ]
    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_num, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment

    # ESTILOS PARA LAS FILAS
    fill_disponible = PatternFill(
        start_color="D1FAE5", end_color="D1FAE5", fill_type="solid"
    )  # Verde
    fill_modificar = PatternFill(
        start_color="FEF3C7", end_color="FEF3C7", fill_type="solid"
    )  # Amarillo
    fill_anular = PatternFill(
        start_color="FEE2E2", end_color="FEE2E2", fill_type="solid"
    )  # Rojo

    # Llenar datos
    for row_num, log in enumerate(logs, 2):
        usuario_nombre = (
            f"{log.empleado.nombre_empleado} {log.empleado.apellido_empleado}"
            if log.empleado
            else "Sistema"
        )

        ws.cell(
            row=row_num, column=1, value=log.fecha_hora.strftime("%d/%m/%Y %H:%M:%S")
        )
        ws.cell(row=row_num, column=2, value=usuario_nombre)
        ws.cell(row=row_num, column=3, value=log.tabla)

        # Celda de acción con color
        accion_cell = ws.cell(row=row_num, column=4, value=log.accion)
        if log.accion == "CREAR":
            accion_cell.fill = fill_disponible
        elif log.accion == "MODIFICAR":
            accion_cell.fill = fill_modificar
        elif log.accion == "ANULAR":
            accion_cell.fill = fill_anular

        ws.cell(row=row_num, column=5, value=log.registro_id)
        ws.cell(row=row_num, column=6, value=log.valores_anteriores)
        ws.cell(row=row_num, column=7, value=log.valores_actuales)

    # Ajustar el ancho de las columnas
    ws.column_dimensions["A"].width = 20
    ws.column_dimensions["B"].width = 25
    ws.column_dimensions["C"].width = 15
    ws.column_dimensions["D"].width = 15
    ws.column_dimensions["E"].width = 12
    ws.column_dimensions["F"].width = 40
    ws.column_dimensions["G"].width = 50

    # Crear respuesta
    fecha_actual = datetime.now().strftime("%Y-%m-%d")
    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = (
        f'attachment; filename="log_auditoria_{fecha_actual}.xlsx"'
    )

    wb.save(response)
    return response
