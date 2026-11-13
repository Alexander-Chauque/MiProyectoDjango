"""Reportes consolidados (Parcial Nº 2, módulo M2).

Cada reporte cruza datos de dos o más procesos del sistema y devuelve la misma estructura,
de modo que una sola plantilla muestra cualquiera de ellos en pantalla y otra lo exporta a PDF:

    titulo, descripcion, procesos   textos del encabezado
    columnas                        [(nombre, es_numero)]
    filas                           [[celda, ...]] ya formateadas
    totales                         [celda, ...] para el pie de la grilla
    filtro_extra                    el filtro propio del reporte (además del rango de fechas)
    filtros                         {nombre del parámetro GET: valor}, para paginar y exportar
    filtros_texto                   los filtros en palabras, para el pie del PDF
"""
from decimal import Decimal

from django.db.models import Count, DecimalField, F, OuterRef, Q, Subquery, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from core.fechas import filtrar_por_fecha, limitar_rango
from empleados.models import Asistencia, Empleado
from finanzas.models import caja, gasto
from inventario.models import CategoriaPlato, DetallePlato
from ventas.models import Comanda, DetalleComanda, Pago
from .productos import CATEGORIA_PLATO, CON_PLATO, NOMBRE_PLATO, PRECIO_PLATO

DINERO = DecimalField(max_digits=14, decimal_places=2)
CERO = Value(Decimal("0"), output_field=DINERO)
ESTADOS_ANULADOS = ["anulado", "cancelado"]


# --- Formato ---------------------------------------------------------------

def pesos(valor):
    """1234.5 -> '$ 1.234,50' (formato argentino)."""
    texto = f"{float(valor or 0):,.2f}"
    return "$ " + texto.replace(",", "X").replace(".", ",").replace("X", ".")


def entero(valor):
    return f"{int(valor or 0):,}".replace(",", ".")


def porcentaje(parte, total):
    if not total:
        return "—"
    return f"{float(parte) / float(total) * 100:.1f} %".replace(".", ",")


def fecha_hora(valor):
    return timezone.localtime(valor).strftime("%d/%m/%Y %H:%M") if valor else "—"


def fecha_es(texto):
    """'2026-11-01' -> '01/11/2026'."""
    if not texto:
        return "—"
    anio, mes, dia = texto.split("-")
    return f"{dia}/{mes}/{anio}"


# --- Filtros comunes -------------------------------------------------------

def rango_fechas(request):
    """Rango del GET, por defecto desde el primer día del mes hasta hoy. Nunca supera hoy."""
    hoy = timezone.localdate()
    inicio_mes, hoy_texto = hoy.replace(day=1).strftime("%Y-%m-%d"), hoy.strftime("%Y-%m-%d")
    desde, hasta = limitar_rango(
        request.GET.get("fecha_desde") or inicio_mes,
        request.GET.get("fecha_hasta") or hoy_texto,
    )
    # Una fecha mal escrita vuelve vacía: se usa la de por defecto
    return desde or inicio_mes, hasta or hoy_texto


def texto_rango(desde, hasta):
    return f"Desde {fecha_es(desde)} hasta {fecha_es(hasta)}"


# --- 1. Rentabilidad por plato (Comandas + Recetas/Ingredientes) -----------

def costos_de_recetas():
    """{id del plato: costo de una porción}, según la receta y el costo actual de cada ingrediente."""
    filas = DetallePlato.objects.values("plato_id").annotate(
        costo=Sum(F("cantidad") * F("ingrediente__costo_unitario"), output_field=DINERO)
    )
    return {f["plato_id"]: f["costo"] or Decimal("0") for f in filas}


def rentabilidad(request):
    desde, hasta = rango_fechas(request)
    categoria = request.GET.get("categoria", "")

    lineas = DetalleComanda.objects.filter(
        CON_PLATO, cant_plato__gt=0, comanda__estado_comanda="pagado"
    ).annotate(nombre=NOMBRE_PLATO, cat=CATEGORIA_PLATO)
    lineas = filtrar_por_fecha(lineas, "comanda__fecha_hora", desde, hasta)
    if categoria:
        lineas = lineas.filter(cat=categoria)

    vendidos = lineas.values("plato_id", "nombre", "cat").annotate(
        unidades=Sum("cant_plato"),
        ingresos=Sum(F("cant_plato") * PRECIO_PLATO, output_field=DINERO),
    )

    costos = costos_de_recetas()
    datos = []
    for v in vendidos:
        costo = (costos.get(v["plato_id"]) or Decimal("0")) * v["unidades"]
        datos.append({**v, "costo": costo, "margen": v["ingresos"] - costo})
    datos.sort(key=lambda d: d["margen"], reverse=True)

    filas = [
        [
            d["nombre"] + ("" if d["plato_id"] in costos else " (sin receta)"),
            d["cat"] or "—",
            entero(d["unidades"]),
            pesos(d["ingresos"]),
            pesos(d["costo"]),
            pesos(d["margen"]),
            porcentaje(d["margen"], d["ingresos"]),
        ]
        for d in datos
    ]
    t_unidades = sum(d["unidades"] for d in datos)
    t_ingresos = sum((d["ingresos"] for d in datos), Decimal("0"))
    t_costo = sum((d["costo"] for d in datos), Decimal("0"))
    t_margen = t_ingresos - t_costo

    return {
        "titulo": "Rentabilidad por plato",
        "descripcion": "Ingresos de cada plato vendido menos el costo de sus ingredientes según la receta.",
        "procesos": "Comandas (venta) + Recetas e ingredientes (inventario)",
        "columnas": [
            ("Plato", False), ("Categoría", False), ("Unidades", True), ("Ingresos", True),
            ("Costo ingredientes", True), ("Margen", True), ("Margen %", True),
        ],
        "filas": filas,
        "totales": [
            "Totales", "", entero(t_unidades), pesos(t_ingresos),
            pesos(t_costo), pesos(t_margen), porcentaje(t_margen, t_ingresos),
        ],
        "filtro_extra": {
            "nombre": "categoria",
            "etiqueta": "Categoría",
            "valor": categoria,
            "opciones": [
                (c, c) for c in CategoriaPlato.objects.order_by("nombre_categoria_plato")
                .values_list("nombre_categoria_plato", flat=True)
            ],
        },
        "filtros": {"fecha_desde": desde, "fecha_hasta": hasta, "categoria": categoria},
        "filtros_texto": f"{texto_rango(desde, hasta)} · Categoría: {categoria or 'todas'}",
        "nota": "El costo usa el costo unitario actual de cada ingrediente.",
    }


# --- 2. Consolidado de cajas (Caja + Cobros + Gastos) ----------------------

def total_por_caja(modelo, campo_caja, campo_monto, **filtros):
    """Subconsulta: suma de `campo_monto` de las filas de `modelo` que pertenecen a cada caja.

    Con una subconsulta por total, cobros y gastos no se multiplican entre sí,
    como pasaría al unir las dos tablas en un mismo JOIN.
    """
    suma = (
        modelo.objects.filter(**{campo_caja: OuterRef("pk")}, **filtros)
        .values(campo_caja)
        .annotate(total=Sum(campo_monto))
        .values("total")
    )
    return Coalesce(Subquery(suma, output_field=DINERO), CERO)


def cierre_cajas(request):
    desde, hasta = rango_fechas(request)
    estado = request.GET.get("estado", "")

    cajas = caja.objects.select_related("empleado_apertura").order_by("-fecha_apertura")
    cajas = filtrar_por_fecha(cajas, "fecha_apertura", desde, hasta)
    if estado in ("abierto", "cerrado"):
        cajas = cajas.filter(estado_caja=estado)
    cajas = cajas.annotate(
        total_cobros=total_por_caja(Pago, "caja", "monto"),
        total_efectivo=total_por_caja(
            Pago, "caja", "monto", metodo_pago__nombre_metodo_pago__iexact="Efectivo"
        ),
        total_gastos=total_por_caja(gasto, "caja_gasto", "monto_gasto"),
        cantidad_cobros=Coalesce(
            Subquery(
                Pago.objects.filter(caja=OuterRef("pk")).values("caja")
                .annotate(n=Count("id_pago")).values("n")
            ),
            Value(0),
        ),
    )

    filas, totales = [], {"inicial": 0, "cobros": 0, "efectivo": 0, "gastos": 0, "esperado": 0, "diferencia": 0}
    for c in cajas:
        esperado = c.saldo_inicial + c.total_cobros - c.total_gastos
        arqueada = c.fecha_arqueo is not None
        cajero = c.empleado_apertura
        filas.append([
            f"#{c.id_caja}",
            fecha_hora(c.fecha_apertura),
            fecha_hora(c.fecha_cierre),
            f"{cajero.nombre_empleado} {cajero.apellido_empleado}",
            pesos(c.saldo_inicial),
            f"{pesos(c.total_cobros)} ({c.cantidad_cobros})",
            pesos(c.total_efectivo),
            pesos(c.total_gastos),
            pesos(esperado),
            pesos(c.saldo_contado) if arqueada else "—",
            pesos(c.diferencia_caja) if arqueada else "—",
            c.get_estado_caja_display(),
        ])
        totales["inicial"] += c.saldo_inicial
        totales["cobros"] += c.total_cobros
        totales["efectivo"] += c.total_efectivo
        totales["gastos"] += c.total_gastos
        totales["esperado"] += esperado
        if arqueada:
            totales["diferencia"] += c.diferencia_caja

    return {
        "titulo": "Consolidado de cajas",
        "descripcion": "Cada caja con sus cobros, sus gastos y el resultado del arqueo.",
        "procesos": "Caja + Cobros de comandas (venta) + Gastos",
        "columnas": [
            ("Caja", False), ("Apertura", False), ("Cierre", False), ("Cajero", False),
            ("Saldo inicial", True), ("Cobros (cant.)", True), ("En efectivo", True),
            ("Gastos", True), ("Saldo esperado", True), ("Contado", True),
            ("Diferencia", True), ("Estado", False),
        ],
        "filas": filas,
        "totales": [
            "Totales", f"{len(filas)} cajas", "", "", pesos(totales["inicial"]),
            pesos(totales["cobros"]), pesos(totales["efectivo"]), pesos(totales["gastos"]),
            pesos(totales["esperado"]), "", pesos(totales["diferencia"]), "",
        ],
        "filtro_extra": {
            "nombre": "estado",
            "etiqueta": "Estado",
            "valor": estado,
            "opciones": list(caja.ESTADOS),
        },
        "filtros": {"fecha_desde": desde, "fecha_hasta": hasta, "estado": estado},
        "filtros_texto": (
            f"{texto_rango(desde, hasta)} (fecha de apertura) · "
            f"Estado: {dict(caja.ESTADOS).get(estado, 'todos')}"
        ),
        "nota": "Saldo esperado = saldo inicial + cobros - gastos.",
    }


# --- 3. Desempeño del personal (Comandas + Anulaciones + Asistencia) -------

def desempeno_personal(request):
    desde, hasta = rango_fechas(request)
    empleado = request.GET.get("empleado", "")

    comandas = filtrar_por_fecha(Comanda.objects.all(), "fecha_hora", desde, hasta)
    asistencias = Asistencia.objects.filter(
        fecha_asistencia__gte=desde, fecha_asistencia__lte=hasta
    )
    if empleado.isdigit():
        comandas = comandas.filter(empleado_id=int(empleado))
        asistencias = asistencias.filter(id_empleado_id=int(empleado))

    pagado = Q(estado_comanda="pagado")
    por_empleado = {
        c["empleado_id"]: c
        for c in comandas.values("empleado_id").annotate(
            atendidas=Count("id_comanda"),
            pagadas=Count("id_comanda", filter=pagado),
            anuladas=Count("id_comanda", filter=Q(estado_comanda__in=ESTADOS_ANULADOS)),
            facturado=Coalesce(Sum("total_comanda", filter=pagado), CERO),
        )
    }
    dias = {
        a["id_empleado_id"]: a["dias"]
        for a in asistencias.values("id_empleado_id").annotate(dias=Count("id_asistencia"))
    }

    ids = set(por_empleado) | set(dias)
    empleados = Empleado.objects.filter(id_empleado__in=ids).select_related("cargo")

    datos = []
    for e in empleados:
        c = por_empleado.get(e.id_empleado, {})
        datos.append({
            "nombre": f"{e.nombre_empleado} {e.apellido_empleado}",
            "cargo": e.cargo.nombre_cargo if e.cargo else "—",
            "dias": dias.get(e.id_empleado, 0),
            "atendidas": c.get("atendidas", 0),
            "pagadas": c.get("pagadas", 0),
            "anuladas": c.get("anuladas", 0),
            "facturado": c.get("facturado", Decimal("0")),
        })
    datos.sort(key=lambda d: d["facturado"], reverse=True)

    filas = [
        [
            d["nombre"], d["cargo"], entero(d["dias"]), entero(d["atendidas"]),
            entero(d["pagadas"]), entero(d["anuladas"]),
            porcentaje(d["anuladas"], d["atendidas"]), pesos(d["facturado"]),
            pesos(d["facturado"] / d["pagadas"]) if d["pagadas"] else "—",
            pesos(d["facturado"] / d["dias"]) if d["dias"] else "—",
        ]
        for d in datos
    ]
    t = {k: sum(d[k] for d in datos) for k in ("dias", "atendidas", "pagadas", "anuladas", "facturado")}

    nombre_filtro = "todos"
    opciones = [
        (str(e.id_empleado), f"{e.nombre_empleado} {e.apellido_empleado}")
        for e in Empleado.objects.filter(estado=True).order_by("nombre_empleado")
    ]
    for valor, etiqueta in opciones:
        if valor == empleado:
            nombre_filtro = etiqueta

    return {
        "titulo": "Desempeño del personal",
        "descripcion": "Comandas atendidas, anuladas y facturación de cada empleado, frente a sus días trabajados.",
        "procesos": "Comandas (venta) + Anulaciones + Asistencia",
        "columnas": [
            ("Empleado", False), ("Cargo", False), ("Días trabajados", True),
            ("Comandas", True), ("Pagadas", True), ("Anuladas", True), ("% anulación", True),
            ("Facturado", True), ("Ticket promedio", True), ("Facturado por día", True),
        ],
        "filas": filas,
        "totales": [
            "Totales", f"{len(filas)} empleados", entero(t["dias"]), entero(t["atendidas"]),
            entero(t["pagadas"]), entero(t["anuladas"]), porcentaje(t["anuladas"], t["atendidas"]),
            pesos(t["facturado"]),
            pesos(t["facturado"] / t["pagadas"]) if t["pagadas"] else "—",
            pesos(t["facturado"] / t["dias"]) if t["dias"] else "—",
        ],
        "filtro_extra": {
            "nombre": "empleado",
            "etiqueta": "Empleado",
            "valor": empleado,
            "opciones": opciones,
        },
        "filtros": {"fecha_desde": desde, "fecha_hasta": hasta, "empleado": empleado},
        "filtros_texto": f"{texto_rango(desde, hasta)} · Empleado: {nombre_filtro}",
        "nota": "Días trabajados según el registro de asistencia.",
    }


# --- Registro de reportes --------------------------------------------------

SOLO_ADMINISTRADOR = "solo_administrador"

# clave de la URL: función, permiso necesario e ícono de la pestaña
REPORTES = {
    "rentabilidad": {
        "funcion": rentabilidad,
        "nombre": "Rentabilidad",
        "icono": "savings",
        # Reporte sensible: muestra costos y márgenes, solo lo ve el Administrador
        "permiso": SOLO_ADMINISTRADOR,
    },
    "cajas": {
        "funcion": cierre_cajas,
        "nombre": "Cajas",
        "icono": "point_of_sale",
        "permiso": ("caja", "leer"),
    },
    "personal": {
        "funcion": desempeno_personal,
        "nombre": "Personal",
        "icono": "badge",
        "permiso": ("reportes", "leer"),
    },
}
