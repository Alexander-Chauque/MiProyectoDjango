from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.db.models.functions import (
    TruncDate,
)  # <-- IMPORTANTE: Agregado para el gráfico
from datetime import date, timedelta, datetime
from django.utils import timezone
from datetime import datetime, time
from ventas.models import Comanda, DetalleComanda
from empleados.models import Empleado
import csv
from django.http import HttpResponse
@login_required
def reportes_home(request):
    hoy = date.today()

    fecha_desde_str = request.GET.get(
        "fecha_desde", hoy.replace(day=1).strftime("%Y-%m-%d")
    )
    fecha_hasta_str = request.GET.get("fecha_hasta", hoy.strftime("%Y-%m-%d"))

    try:
        fecha_desde = datetime.strptime(fecha_desde_str, "%Y-%m-%d").date()
        fecha_hasta = datetime.strptime(fecha_hasta_str, "%Y-%m-%d").date()
    except ValueError:
        fecha_desde = hoy.replace(day=1)
        fecha_hasta = hoy

    # Convertimos a fechas con hora local (00:00:00 a 23:59:59)
    inicio = timezone.make_aware(datetime.combine(fecha_desde, time.min))
    fin = timezone.make_aware(datetime.combine(fecha_hasta, time.max))

    # Filtramos por rango de tiempo exacto
    comandas_pagadas = Comanda.objects.filter(
        estado_comanda__iexact="pagado", fecha_hora__range=[inicio, fin]
    )

    # KPIs
    ventas_totales = (
        comandas_pagadas.aggregate(total=Sum("total_comanda"))["total"] or 0
    )
    cantidad_comandas = comandas_pagadas.count()
    ticket_promedio = (
        (ventas_totales / cantidad_comandas) if cantidad_comandas > 0 else 0
    )

    # Top 5 Platos
    top_platos_qs = (
        DetalleComanda.objects.filter(
            comanda__in=comandas_pagadas, plato__isnull=False, cant_plato__gt=0
        )
        .values("plato__nombre_plato")
        .annotate(total_vendidos=Sum("cant_plato"))
        .order_by("-total_vendidos")[:5]
    )
    top_platos = [
        (item["plato__nombre_plato"], item["total_vendidos"]) for item in top_platos_qs
    ]

    # Top 5 Bebidas
    top_bebidas_qs = (
        DetalleComanda.objects.filter(
            comanda__in=comandas_pagadas, bebida__isnull=False, cant_bebida__gt=0
        )
        .values("bebida__nombre_bebida")
        .annotate(total_vendidos=Sum("cant_bebida"))
        .order_by("-total_vendidos")[:5]
    )
    top_bebidas = [
        (item["bebida__nombre_bebida"], item["total_vendidos"])
        for item in top_bebidas_qs
    ]

    # Gráfico
    ventas_por_dia_dict = {}
    
    for comanda in comandas_pagadas:
        # Convertimos la fecha a la zona horaria local y sacamos solo el día
        fecha_local = timezone.localtime(comanda.fecha_hora).date()
        
        # Sumamos el total al día correspondiente
        if fecha_local in ventas_por_dia_dict:
            ventas_por_dia_dict[fecha_local] += float(comanda.total_comanda)
        else:
            ventas_por_dia_dict[fecha_local] = float(comanda.total_comanda)

    # Ordenamos por fecha
    fechas_ordenadas = sorted(ventas_por_dia_dict.keys())
    
    # Creamos las listas para el gráfico
    labels_semana = [f.strftime('%d/%m') for f in fechas_ordenadas]
    ventas_semana = [ventas_por_dia_dict[f] for f in fechas_ordenadas]
    # Extras
    comandas_activas = Comanda.objects.exclude(
        estado_comanda__in=["pagado", "anulado", "cancelado"]
    ).count()
    total_empleados = Empleado.objects.filter(estado=True).count()

    return render(
        request,
        "reportes_home.html",
        {
            "ventas_totales": ventas_totales,
            "cantidad_comandas": cantidad_comandas,
            "ticket_promedio": ticket_promedio,
            "comandas_activas": comandas_activas,
            "top_platos": top_platos,
            "top_bebidas": top_bebidas,
            "ventas_semana": ventas_semana,
            "labels_semana": labels_semana,
            "total_empleados": total_empleados,
            "fecha_desde": fecha_desde_str,
            "fecha_hasta": fecha_hasta_str,
        },
    )


@login_required
def exportar_reporte_csv(request):
    fecha_desde_str = request.GET.get("fecha_desde")
    fecha_hasta_str = request.GET.get("fecha_hasta")

    comandas = Comanda.objects.filter(estado_comanda__iexact="pagado").order_by(
        "-fecha_hora"
    )

    if fecha_desde_str and fecha_hasta_str:
        try:
            fecha_desde = datetime.strptime(fecha_desde_str, "%Y-%m-%d").date()
            fecha_hasta = datetime.strptime(fecha_hasta_str, "%Y-%m-%d").date()
            comandas = comandas.filter(
                fecha_hora__date__range=[fecha_desde, fecha_hasta]
            )
        except ValueError:
            pass

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="reporte_ventas.csv"'

    writer = csv.writer(response)
    writer.writerow(["ID Comanda", "Fecha", "Mesa", "Mozo", "Total"])

    for comanda in comandas:
        mozo = comanda.empleado.get_full_name() if comanda.empleado else "Sin asignar"
        mesa = comanda.mesa.numero_mesa if comanda.mesa else "N/A"
        writer.writerow(
            [
                comanda.id_comanda,
                comanda.fecha_hora.strftime("%d/%m/%Y %H:%M"),
                mesa,
                mozo,
                comanda.total_comanda,
            ]
        )

    return response
