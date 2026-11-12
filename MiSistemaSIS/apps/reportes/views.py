from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from core.fechas import limitar_rango
from empleados.decorators import permiso_requerido
from django.db.models import Sum, Count, F, DecimalField
from django.db.models.functions import Coalesce
from django.utils import timezone
from datetime import date, datetime, time
from django.http import HttpResponse
from django.template.loader import get_template
from xhtml2pdf import pisa
from ventas.models import Comanda, DetalleComanda, Pago
from empleados.models import Empleado
from inventario.models import CategoriaPlato
from .productos import (CATEGORIA_PLATO, CON_BEBIDA, CON_PLATO, NOMBRE_BEBIDA, NOMBRE_PLATO, PRECIO_PLATO,)

# --- FUNCIÓN AUXILIAR PARA FECHAS ---
def obtener_rango_fechas(request):
    hoy = timezone.localdate()
    f_desde_str, f_hasta_str = limitar_rango(
        request.GET.get("fecha_desde", hoy.replace(day=1).strftime("%Y-%m-%d")),
        request.GET.get("fecha_hasta", hoy.strftime("%Y-%m-%d")),
    )

    try:
        f_desde = datetime.strptime(f_desde_str, "%Y-%m-%d").date()
        f_hasta = datetime.strptime(f_hasta_str, "%Y-%m-%d").date()
    except ValueError:
        f_desde, f_hasta = hoy.replace(day=1), hoy
        f_desde_str, f_hasta_str = f_desde.strftime("%Y-%m-%d"), f_hasta.strftime(
            "%Y-%m-%d"
        )

    inicio = timezone.make_aware(datetime.combine(f_desde, time.min))
    fin = timezone.make_aware(datetime.combine(f_hasta, time.max))
    return inicio, fin, f_desde_str, f_hasta_str

AGRUPACIONES = {"dia": "Día", "mes": "Mes", "anio": "Año"}
MESES = [
    "Ene",
    "Feb",
    "Mar",
    "Abr",
    "May",
    "Jun",
    "Jul",
    "Ago",
    "Sep",
    "Oct",
    "Nov",
    "Dic",
]


def etiqueta_periodo(clave):
    """(año,) -> '2026'; (año, mes) -> 'Oct 2026'; (año, mes, día) -> '15/10'."""
    if len(clave) == 1:
        return str(clave[0])
    if len(clave) == 2:
        return f"{MESES[clave[1] - 1]} {clave[0]}"
    return f"{clave[2]:02d}/{clave[1]:02d}"

def obtener_comandas(request):
    inicio, fin, f_desde_str, f_hasta_str = obtener_rango_fechas(request)
    comandas = Comanda.objects.filter(
        estado_comanda__iexact="pagado", fecha_hora__range=[inicio, fin]
    )
    return comandas, f_desde_str, f_hasta_str

def obtener_totales_metodos(request):
    """Devuelve [(nombre del método, total cobrado)] del período, de mayor a menor."""
    inicio, fin, f_desde_str, f_hasta_str = obtener_rango_fechas(request)
    nombres = dict(Pago.METODOS)
    pagos = (
        Pago.objects.filter(fecha_hora__range=[inicio, fin])
        .values("metodo_pago")
        .annotate(total=Sum("monto"))
    )
    totales = [
        (nombres.get(p["metodo_pago"], p["metodo_pago"]), p["total"]) for p in pagos
    ]

    # Comandas cobradas antes de existir la tabla Pago: no tienen método guardado
    sin_registro = Comanda.objects.filter(
        estado_comanda__iexact="pagado",
        fecha_hora__range=[inicio, fin],
        pagos__isnull=True,
    ).aggregate(total=Sum("total_comanda"))["total"]
    if sin_registro:
        totales.append(("Sin método registrado", sin_registro))

    totales.sort(key=lambda fila: fila[1], reverse=True)
    return totales, f_desde_str, f_hasta_str

# --- REPORTE DE VENTAS GENERALES (KPIs y Gráfico) ---
@login_required
@permiso_requerido("reportes", "leer")
def reporte_ventas(request):
    comandas, f_desde, f_hasta = obtener_comandas(request)
    ventas_totales = comandas.aggregate(total=Sum("total_comanda"))["total"] or 0
    cant_comandas = comandas.count()
    ticket = (ventas_totales / cant_comandas) if cant_comandas > 0 else 0
    # Gráfico: evolución agrupada por día, mes o año
    agrupar = request.GET.get("agrupar", "dia")
    if agrupar not in AGRUPACIONES:
        agrupar = "dia"
    ventas_periodo = {}
    for c in comandas:
        fecha = timezone.localtime(c.fecha_hora).date()
        if agrupar == "anio":
            clave = (fecha.year,)
        elif agrupar == "mes":
            clave = (fecha.year, fecha.month)
        else:
            clave = (fecha.year, fecha.month, fecha.day)
        ventas_periodo[clave] = ventas_periodo.get(clave, 0) + float(c.total_comanda)
    claves = sorted(ventas_periodo)
    labels = [etiqueta_periodo(clave) for clave in claves]
    data = [ventas_periodo[clave] for clave in claves]

    return render(
        request,
        "reportes/ventas.html",
        {
            "ventas_totales": ventas_totales,
            "cantidad_comandas": cant_comandas,
            "ticket_promedio": ticket,
            "labels": labels,
            "data": data,
            "fecha_desde": f_desde,
            "fecha_hasta": f_hasta,
            "agrupar": agrupar,
            "agrupar_nombre": AGRUPACIONES[agrupar],
            "agrupaciones": AGRUPACIONES,
            "tab": "ventas",
        },
    )

# --- REPORTE TOP 5 (Platos y Bebidas) ---
@login_required
@permiso_requerido("reportes", "leer")
def reporte_top(request):
    comandas, f_desde, f_hasta = obtener_comandas(request)

    top_platos = (
        DetalleComanda.objects.filter(CON_PLATO, comanda__in=comandas, cant_plato__gt=0)
        .annotate(nombre=NOMBRE_PLATO)
        .values("nombre")
        .annotate(total=Sum("cant_plato"))
        .order_by("-total")[:5]
    )

    top_bebidas = (
        DetalleComanda.objects.filter(
            CON_BEBIDA, comanda__in=comandas, cant_bebida__gt=0
        )
        .annotate(nombre=NOMBRE_BEBIDA)
        .values("nombre")
        .annotate(total=Sum("cant_bebida"))
        .order_by("-total")[:5]
    )
    lista_platos = [
        {
            "nombre": p["nombre"],
            "total": p["total"],
        }
        for p in top_platos
    ]

    labels_platos = [p["nombre"] for p in lista_platos]
    data_platos = [int(p["total"]) for p in lista_platos]

    lista_bebidas = [
        {
            "nombre": b["nombre"],
            "total": b["total"],
        }
        for b in top_bebidas
    ]
    labels_bebidas = [b["nombre"] for b in lista_bebidas]
    data_bebidas = [int(b["total"]) for b in lista_bebidas]

    return render(
        request,
        "reportes/top.html",
        {
            "top_platos": [(i["nombre"], i["total"]) for i in top_platos],
            "top_bebidas": [(i["nombre"], i["total"]) for i in top_bebidas],
            "labels_platos": labels_platos,
            "data_platos": data_platos,
            "labels_bebidas": labels_bebidas,
            "data_bebidas": data_bebidas,
            "fecha_desde": f_desde,
            "fecha_hasta": f_hasta,
            "tab": "top",
        },
    )

# --- REPORTE POR CATEGORÍA (Táctico) ---
@login_required
@permiso_requerido("reportes", "leer")
def reporte_categorias(request):
    comandas, f_desde, f_hasta = obtener_comandas(request)

    categorias = (
        DetalleComanda.objects.filter(CON_PLATO, comanda__in=comandas, cant_plato__gt=0)
        .annotate(categoria_nombre=CATEGORIA_PLATO)
        .values("categoria_nombre")
        .annotate(
            ingresos=Sum(F("cant_plato") * PRECIO_PLATO, output_field=DecimalField())
        )
        .order_by("-ingresos")
    )

    return render(
        request,
        "reportes/categorias.html",
        {
            "categorias": categorias,
            "fecha_desde": f_desde,
            "fecha_hasta": f_hasta,
            "tab": "categorias",
        },
    )

# --- REPORTE DE MOZOS (Táctico) ---
@login_required
@permiso_requerido("reportes", "leer")
def reporte_mozos(request):
    comandas, f_desde, f_hasta = obtener_comandas(request)
    mozos = (
        comandas.values("empleado__nombre_empleado", "empleado__apellido_empleado")
        .annotate(total=Sum("total_comanda"), cantidad=Count("id_comanda"))
        .order_by("-total")
    )
    lista_mozos = [
        {
            "nombre": f"{m['empleado__nombre_empleado']} {m['empleado__apellido_empleado']}",
            "total": m["total"],
            "cantidad": m["cantidad"],
        }
        for m in mozos
    ]
    labels_mozos = [m["nombre"] for m in lista_mozos]
    data_mozos = [m["total"] for m in lista_mozos]
    return render(
        request,
        "reportes/mozos.html",
        {
            "lista_mozos": lista_mozos,
            "labels_mozos": labels_mozos,
            "data_mozos": data_mozos,
            "fecha_desde": f_desde,
            "fecha_hasta": f_hasta,
            "tab": "mozos",
        },
    )

# --- REPORTE DE MÉTODOS DE PAGO---
@login_required
@permiso_requerido("reportes", "leer")
def reporte_metodos(request):
    totales, f_desde, f_hasta = obtener_totales_metodos(request)
    labels_metodos = [nombre for nombre, _ in totales]
    data_metodos = [float(total) for _, total in totales]

    return render(
        request,
        "reportes/metodos.html",
        {
            "labels_metodos": labels_metodos,
            "data_metodos": data_metodos,
            "fecha_desde": f_desde,
            "fecha_hasta": f_hasta,
            "tab": "metodos",
        },
    )

@login_required
@permiso_requerido("reportes", "leer")
def exportar_pdf_ventas(request):
    comandas, f_desde, f_hasta = obtener_comandas(request)
    ventas_totales = comandas.aggregate(total=Sum("total_comanda"))["total"] or 0
    cant_comandas = comandas.count()
    ticket = (ventas_totales / cant_comandas) if cant_comandas > 0 else 0

    # Datos para la tabla del PDF
    ventas_dia = {}
    for c in comandas:
        dia = timezone.localtime(c.fecha_hora).date()
        ventas_dia[dia] = ventas_dia.get(dia, 0) + float(c.total_comanda)
    fechas = sorted(ventas_dia.keys())
    labels = [f.strftime("%d/%m/%Y") for f in fechas]
    data = [ventas_dia[f] for f in fechas]

    # Unimos las listas para el PDF
    zip_datos = zip(labels, data)

    template = get_template("reportes/pdf_ventas.html")
    context = {
        "nombre_reporte": "Ventas Generales",
        "fecha_desde": f_desde,
        "fecha_hasta": f_hasta,
        "ventas_totales": ventas_totales,
        "cantidad_comandas": cant_comandas,
        "ticket_promedio": ticket,
        "zip_labels_valores": zip_datos,
    }
    html = template.render(context)

    # Creacion del PDF
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="Reporte_Ventas_{f_desde}_{f_hasta}.pdf"'
    )
    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        return HttpResponse("Error al generar PDF", status=500)
    return response
