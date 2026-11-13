"""Módulo de Analítica y Visualización - Los Cardones (Parcial Nº 2, módulo M1).

Lee las tablas transaccionales de la misma base MySQL del sistema (conector nativo PyMySQL),
transforma los datos con pandas, calcula indicadores con numpy y genera gráficos con matplotlib,
exportados como PNG en la carpeta de salida.

Gráficos (cada uno responde una pregunta de negocio):
  1. Barras agrupadas  ¿Cómo se venden las categorías de la carta mes a mes?
  2. Donut             ¿Qué categorías concentran la facturación? (y Pareto de productos)
  3. Líneas            ¿Cumplimos el objetivo mensual de facturación? ¿Cuál es la tendencia?
  4. Heatmap           ¿En qué días y horarios se concentra la operación?
  5. Dashboard         Tablero ejecutivo que resume los indicadores clave (opcional en la consigna).

Uso (desde la carpeta del proyecto, con el entorno virtual):
  python analitica/analitica.py
  python analitica/analitica.py --desde 2026-03-01 --hasta 2026-11-12
  python analitica/analitica.py --objetivo 2500000 --top 6 --mozo "Teo"

La conexión usa las mismas variables del .env que Django (DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT).
"""
import argparse
import os
from datetime import date, timedelta
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # Genera los PNG sin abrir ventanas: funciona igual en consola o en un servidor

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pymysql
from dotenv import load_dotenv
from matplotlib import gridspec
from matplotlib.ticker import FuncFormatter

ZONA = "America/Argentina/Salta"  # Django guarda las fechas en UTC; los gráficos usan la hora local
CARPETA = Path(__file__).resolve().parent
DIAS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]

# Paleta: el naranja de la marca primero y luego colores bien distinguibles entre sí
NARANJA = "#F5A623"
GRIS = "#3D3D3D"
VERDE = "#2E8B57"
ROJO = "#C2543A"
PALETA = [NARANJA, "#2E6F95", VERDE, ROJO, "#8E6CC3", "#8C6D46", "#9AA5B1"]

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.titleweight": "bold",
    "axes.titlesize": 13,
    "axes.titlecolor": GRIS,
    "axes.grid": True,
    "grid.alpha": 0.25,
    "figure.dpi": 100,
})


# ---------------------------------------------------------------------------
# Parámetros
# ---------------------------------------------------------------------------

def leer_parametros():
    hoy = date.today()
    p = argparse.ArgumentParser(description="Analítica de ventas de Los Cardones")
    p.add_argument("--desde", default=(hoy - timedelta(days=365)).isoformat(),
                   help="Fecha inicial AAAA-MM-DD (por defecto, hace un año)")
    p.add_argument("--hasta", default=hoy.isoformat(), help="Fecha final AAAA-MM-DD (por defecto, hoy)")
    p.add_argument("--mozo", default="", help="Filtra por mozo (parte del nombre o apellido)")
    p.add_argument("--objetivo", type=float, default=None,
                   help="Objetivo mensual de facturación en $. Por defecto, el percentil 75 de los meses del período")
    p.add_argument("--top", type=int, default=6, help="Cantidad de productos/categorías a mostrar antes de agrupar en 'Otros'")
    p.add_argument("--salida", default=str(CARPETA / "graficos"), help="Carpeta donde se guardan los PNG")
    return p.parse_args()


# ---------------------------------------------------------------------------
# Lectura de la base
# ---------------------------------------------------------------------------

def conectar():
    """Conexión directa a MySQL con PyMySQL, usando las variables del .env del proyecto."""
    # El mismo .env que usa Django, que está junto a settings.py
    load_dotenv(CARPETA.parent / "MiSistemaSIS" / ".env")
    return pymysql.connect(
        host=os.getenv("DB_HOST") or "localhost",
        port=int(os.getenv("DB_PORT") or 3306),
        user=os.getenv("DB_USER") or "root",
        password=os.getenv("DB_PASSWORD") or "",
        database=os.getenv("DB_NAME"),
        charset="utf8mb4",
    )


def consultar(conexion, sql, parametros):
    """Ejecuta la consulta y devuelve un DataFrame con los nombres de columna de la consulta."""
    with conexion.cursor() as cursor:
        cursor.execute(sql, parametros)
        columnas = [c[0] for c in cursor.description]
        return pd.DataFrame(cursor.fetchall(), columns=columnas)


def limite_utc(texto_fecha, fin_del_dia=False):
    """Fecha local (Salta) -> instante UTC sin zona, que es como Django la guarda en MySQL."""
    instante = pd.Timestamp(texto_fecha)
    if fin_del_dia:
        instante += pd.Timedelta(days=1)
    return instante.tz_localize(ZONA).tz_convert("UTC").tz_localize(None).to_pydatetime()


SQL_COMANDAS = """
    SELECT c.id_comanda, c.fecha_hora, c.total_comanda AS total,
           CONCAT(e.nombre_empleado, ' ', e.apellido_empleado) AS mozo
    FROM ventas_comanda c
    JOIN empleados_empleado e ON e.id_empleado = c.empleado_id
    WHERE c.estado_comanda = 'pagado'
      AND c.fecha_hora >= %s AND c.fecha_hora < %s
"""

# Si un producto se eliminó del inventario, la línea conserva una copia de su nombre, precio y categoría
SQL_LINEAS = """
    SELECT d.comanda_id, c.fecha_hora,
           CONCAT(e.nombre_empleado, ' ', e.apellido_empleado) AS mozo,
           COALESCE(p.nombre_plato, NULLIF(d.nombre_plato_guardado, '')) AS plato,
           COALESCE(cp.nombre_categoria_plato, NULLIF(d.categoria_plato_guardada, '')) AS categoria,
           d.cant_plato,
           COALESCE(p.precio_plato, d.precio_plato_guardado) AS precio_plato,
           COALESCE(b.nombre_bebida, NULLIF(d.nombre_bebida_guardado, '')) AS bebida,
           d.cant_bebida,
           COALESCE(b.precio_bebida, d.precio_bebida_guardado) AS precio_bebida
    FROM ventas_detallecomanda d
    JOIN ventas_comanda c ON c.id_comanda = d.comanda_id
    JOIN empleados_empleado e ON e.id_empleado = c.empleado_id
    LEFT JOIN inventario_plato p ON p.id_plato = d.plato_id
    LEFT JOIN inventario_categoriaplato cp ON cp.id_categoria_plato = p.categoria_id
    LEFT JOIN inventario_bebida b ON b.id_bebida = d.bebida_id
    WHERE c.estado_comanda = 'pagado'
      AND c.fecha_hora >= %s AND c.fecha_hora < %s
"""


def a_hora_local(serie):
    return pd.to_datetime(serie).dt.tz_localize("UTC").dt.tz_convert(ZONA)


def cargar_datos(args):
    rango = (limite_utc(args.desde), limite_utc(args.hasta, fin_del_dia=True))
    conexion = conectar()
    try:
        comandas = consultar(conexion, SQL_COMANDAS, rango)
        lineas = consultar(conexion, SQL_LINEAS, rango)
    finally:
        conexion.close()

    # MySQL devuelve DECIMAL como Decimal de Python: se pasan a float para operar con numpy
    comandas["total"] = comandas["total"].astype(float)
    comandas["fecha_hora"] = a_hora_local(comandas["fecha_hora"])
    lineas["fecha_hora"] = a_hora_local(lineas["fecha_hora"])

    if args.mozo:
        comandas = comandas[comandas["mozo"].str.contains(args.mozo, case=False)]
        lineas = lineas[lineas["mozo"].str.contains(args.mozo, case=False)]

    return comandas, productos_vendidos(lineas)


def productos_vendidos(lineas):
    """Pasa las líneas de comanda (un plato y/o una bebida por fila) a una fila por producto vendido."""
    columnas = ["comanda_id", "fecha_hora", "producto", "categoria", "unidades", "importe"]
    platos = lineas[lineas["plato"].notna() & (lineas["cant_plato"] > 0)].assign(
        producto=lambda d: d["plato"],
        categoria=lambda d: d["categoria"].fillna("Sin categoría"),
        unidades=lambda d: d["cant_plato"].astype(int),
        importe=lambda d: d["cant_plato"].astype(float) * d["precio_plato"].astype(float),
    )
    bebidas = lineas[lineas["bebida"].notna() & (lineas["cant_bebida"] > 0)].assign(
        producto=lambda d: d["bebida"],
        categoria="Bebidas",
        unidades=lambda d: d["cant_bebida"].astype(int),
        importe=lambda d: d["cant_bebida"].astype(float) * d["precio_bebida"].astype(float),
    )
    return pd.concat([platos[columnas], bebidas[columnas]], ignore_index=True)


# ---------------------------------------------------------------------------
# Utilidades de formato
# ---------------------------------------------------------------------------

def pesos(valor):
    return "$ " + f"{valor:,.0f}".replace(",", ".")


def pesos_cortos(valor, _posicion=None):
    """Para los ejes: 1.250.000 -> '$1,3M'; 85.000 -> '$85k'."""
    if abs(valor) >= 1_000_000:
        return f"${valor / 1_000_000:.1f}M".replace(".", ",")
    if abs(valor) >= 1_000:
        return f"${valor / 1_000:.0f}k"
    return f"${valor:.0f}"


def etiqueta_mes(periodo):
    return f"{MESES[periodo.month - 1]} {str(periodo.year)[2:]}"


def agrupar_resto(serie, top, nombre="Otros"):
    """Deja los `top` valores más grandes y suma el resto en una sola categoría."""
    serie = serie.sort_values(ascending=False)
    if len(serie) <= top:
        return serie
    principales = serie.iloc[:top].copy()
    principales[nombre] = serie.iloc[top:].sum()
    return principales


def guardar(fig, carpeta, nombre):
    ruta = Path(carpeta) / nombre
    fig.savefig(ruta, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  ✔ {ruta}")
    return ruta


# ---------------------------------------------------------------------------
# 1. Comparativo categórico - barras agrupadas
# ---------------------------------------------------------------------------

def grafico_barras_categorias(productos, args):
    """¿Cómo se venden las categorías de la carta mes a mes? (unidades vendidas)"""
    datos = productos.assign(mes=productos["fecha_hora"].dt.tz_localize(None).dt.to_period("M"))

    # Las categorías con más unidades en todo el período; el resto se agrupa en "Otras"
    principales = datos.groupby("categoria")["unidades"].sum().nlargest(min(args.top, 5)).index
    datos["categoria"] = datos["categoria"].where(datos["categoria"].isin(principales), "Otras")

    tabla = datos.pivot_table(index="mes", columns="categoria", values="unidades",
                              aggfunc="sum", fill_value=0)
    orden = [c for c in principales if c in tabla.columns] + (["Otras"] if "Otras" in tabla.columns else [])
    tabla = tabla[orden]

    fig, ax = plt.subplots(figsize=(12, 5.5))
    x = np.arange(len(tabla))
    ancho = 0.8 / len(tabla.columns)
    for i, categoria in enumerate(tabla.columns):
        ax.bar(x + i * ancho - 0.4 + ancho / 2, tabla[categoria], width=ancho,
               label=categoria, color=PALETA[i % len(PALETA)])

    ax.set_xticks(x, [etiqueta_mes(p) for p in tabla.index])
    ax.set_ylabel("Unidades vendidas")
    ax.set_title("Unidades vendidas por categoría y mes")
    ax.grid(axis="x", visible=False)
    ax.legend(ncol=min(len(tabla.columns), 6), frameon=False, loc="upper left", bbox_to_anchor=(0, -0.08))
    return guardar(fig, args.salida, "1_barras_categorias_por_mes.png")


# ---------------------------------------------------------------------------
# 2. Participación - donut
# ---------------------------------------------------------------------------

def grafico_donut_participacion(productos, args):
    """¿Qué parte de la carta concentra la facturación? (participación % por categoría)"""
    por_producto = productos.groupby("producto")["importe"].sum()
    por_categoria = productos.groupby("categoria")["importe"].sum()
    total = por_categoria.sum()

    # Pareto con numpy: cuántos productos explican el 80 % de la facturación
    acumulado = np.cumsum(np.sort(por_producto.to_numpy())[::-1]) / total
    productos_80 = int(np.searchsorted(acumulado, 0.80) + 1)

    serie = agrupar_resto(por_categoria, args.top, nombre="Otras")
    colores = PALETA[: len(serie)]
    if "Otras" in serie.index:
        colores[-1] = "#D0D5DB"

    fig, ax = plt.subplots(figsize=(9, 7))
    ax.pie(serie.to_numpy(), labels=serie.index, colors=colores, startangle=90, counterclock=False,
           autopct=lambda p: f"{p:.1f}%" if p >= 3 else "", pctdistance=0.8,
           wedgeprops={"width": 0.4, "edgecolor": "white", "linewidth": 2},
           textprops={"fontsize": 10, "color": GRIS})
    ax.text(0, 0.08, pesos_cortos(total), ha="center", fontsize=20, fontweight="bold", color=GRIS)
    ax.text(0, -0.12, "facturado", ha="center", fontsize=10, color="#6B7280")
    ax.set_title("Participación de cada categoría en la facturación")
    ax.annotate(
        f"Pareto: {productos_80} de {len(por_producto)} productos generan el 80 % de la facturación",
        xy=(0.5, -0.07), xycoords="axes fraction", ha="center", fontsize=10, color="#6B7280",
    )
    ax.axis("equal")
    return guardar(fig, args.salida, "2_donut_participacion_categorias.png")


# ---------------------------------------------------------------------------
# 3. Evolución temporal - líneas con objetivo y tendencia
# ---------------------------------------------------------------------------

def facturacion_mensual(comandas, args):
    """Facturación por mes, separada en meses completos y el último mes si quedó a medias.

    Si el rango termina antes de fin de mes (por ejemplo, hoy), ese mes está en curso:
    compararlo con el objetivo o usarlo en la tendencia lo haría parecer una caída.
    """
    mensual = comandas.set_index("fecha_hora")["total"].resample("MS").sum()
    hasta = pd.Timestamp(args.hasta)
    ultimo = mensual.index[-1]
    if len(mensual) > 1 and not hasta.is_month_end and (ultimo.year, ultimo.month) == (hasta.year, hasta.month):
        return mensual.iloc[:-1], mensual.iloc[-1:]
    return mensual, mensual.iloc[0:0]


def objetivo_mensual(completos, args):
    """El objetivo del parámetro o, si no se indica, el percentil 75: lo que logra un mes bueno."""
    if args.objetivo:
        return args.objetivo
    return float(np.percentile(completos.to_numpy(), 75))


def grafico_lineas_objetivo(comandas, args):
    """¿Cumplimos el objetivo mensual de facturación? ¿Cuál es la tendencia?"""
    completos, en_curso = facturacion_mensual(comandas, args)
    objetivo = objetivo_mensual(completos, args)
    x = np.arange(len(completos))
    y = completos.to_numpy()
    meta = np.full_like(y, objetivo)

    fig, ax = plt.subplots(figsize=(12, 5.5))
    ax.fill_between(x, y, meta, where=y >= meta, interpolate=True, color=VERDE, alpha=0.18, label="Sobrecumplimiento")
    ax.fill_between(x, y, meta, where=y < meta, interpolate=True, color=ROJO, alpha=0.15, label="Déficit")
    ax.plot(x, meta, "--", color=GRIS, linewidth=1.5, label=f"Objetivo ({pesos_cortos(objetivo)})")
    ax.plot(x, y, "-o", color=NARANJA, linewidth=2.5, markersize=7, label="Facturación real")

    # Tendencia lineal (mínimos cuadrados con numpy.polyfit), solo con meses completos
    if len(x) >= 2:
        pendiente, ordenada = np.polyfit(x, y, 1)
        ax.plot(x, pendiente * x + ordenada, ":", color="#2E6F95", linewidth=2,
                label=f"Tendencia ({pesos_cortos(pendiente)} por mes)")

    for xi, yi in zip(x, y):
        ax.annotate(pesos_cortos(yi), (xi, yi), textcoords="offset points", xytext=(0, 9),
                    ha="center", fontsize=8.5, color=GRIS)

    # El mes en curso se muestra aparte, con marcador hueco, sin entrar en la comparación
    meses = completos.index
    if len(en_curso):
        xp, yp = len(x), float(en_curso.iloc[0])
        ax.plot([x[-1], xp], [y[-1], yp], ":", color=NARANJA, linewidth=1.5)
        ax.plot(xp, yp, "o", markersize=8, markerfacecolor="white", markeredgecolor=NARANJA,
                markeredgewidth=2, label="Mes en curso (parcial)")
        ax.annotate(pesos_cortos(yp), (xp, yp), textcoords="offset points", xytext=(0, 9),
                    ha="center", fontsize=8.5, color=GRIS)
        meses = meses.append(en_curso.index)

    cumplidos = int((y >= objetivo).sum())
    ax.set_title(f"Facturación mensual vs. objetivo · {cumplidos} de {len(y)} meses cumplidos")
    ax.set_xticks(range(len(meses)), [etiqueta_mes(p) for p in meses.tz_localize(None).to_period("M")])
    ax.yaxis.set_major_formatter(FuncFormatter(pesos_cortos))
    ax.set_ylabel("Facturación")
    ax.legend(frameon=False, ncol=3, loc="upper left", bbox_to_anchor=(0, -0.08))
    return guardar(fig, args.salida, "3_lineas_facturacion_vs_objetivo.png")


# ---------------------------------------------------------------------------
# 4. Densidad - heatmap día x hora
# ---------------------------------------------------------------------------

def grafico_heatmap_dia_hora(comandas, args):
    """¿En qué días y horarios se concentra la operación? (comandas registradas)"""
    datos = comandas.assign(dia=comandas["fecha_hora"].dt.day_of_week, hora=comandas["fecha_hora"].dt.hour)
    horas = range(datos["hora"].min(), datos["hora"].max() + 1)
    matriz = (
        datos.pivot_table(index="dia", columns="hora", values="id_comanda", aggfunc="count")
        .reindex(index=range(7), columns=horas)
        .fillna(0)
    )
    valores = matriz.to_numpy()

    fig, ax = plt.subplots(figsize=(13, 4.8))
    imagen = ax.imshow(valores, cmap="Oranges", aspect="auto")
    fig.colorbar(imagen, ax=ax, label="Comandas", pad=0.01)

    umbral = valores.max() * 0.6  # Texto blanco sobre las celdas oscuras
    for i in range(valores.shape[0]):
        for j in range(valores.shape[1]):
            if valores[i, j]:
                ax.text(j, i, int(valores[i, j]), ha="center", va="center", fontsize=9,
                        color="white" if valores[i, j] > umbral else GRIS)

    ax.set_xticks(range(len(horas)), [f"{h:02d}h" for h in horas])
    ax.set_yticks(range(7), DIAS)
    ax.grid(False)
    for lado in ("left", "bottom"):
        ax.spines[lado].set_visible(False)

    pico_dia, pico_hora = np.unravel_index(np.argmax(valores), valores.shape)
    ax.set_title(f"Comandas por día y hora · pico: {DIAS[pico_dia]} a las {list(horas)[pico_hora]:02d}h")
    return guardar(fig, args.salida, "4_heatmap_dia_hora.png")


# ---------------------------------------------------------------------------
# 5. Dashboard ejecutivo (GridSpec)
# ---------------------------------------------------------------------------

def tarjeta_kpi(ax, titulo, valor, detalle=""):
    ax.axis("off")
    ax.add_patch(plt.Rectangle((0, 0), 1, 1, transform=ax.transAxes, facecolor="#FFF8E7",
                               edgecolor=NARANJA, linewidth=1.2))
    ax.text(0.5, 0.68, valor, ha="center", va="center", fontsize=17, fontweight="bold", color=GRIS)
    ax.text(0.5, 0.36, titulo, ha="center", va="center", fontsize=10, color="#6B7280")
    if detalle:
        ax.text(0.5, 0.15, detalle, ha="center", va="center", fontsize=8, color="#9CA3AF")


def grafico_dashboard(comandas, args, resumen):
    completos, _ = facturacion_mensual(comandas, args)
    objetivo = objetivo_mensual(completos, args)
    # El último mes completo: el mes en curso todavía no puede compararse con el objetivo
    mes_ref = completos.index[-1]
    fin_mes = mes_ref + pd.offsets.MonthBegin(1)
    del_mes = comandas[(comandas["fecha_hora"] >= mes_ref) & (comandas["fecha_hora"] < fin_mes)]

    fig = plt.figure(figsize=(15, 9))
    fig.subplots_adjust(top=0.9)
    gs = gridspec.GridSpec(3, 4, figure=fig, height_ratios=[0.45, 1, 1], hspace=0.55, wspace=0.35)
    fig.suptitle(f"Dashboard ejecutivo · Los Cardones · {args.desde} a {args.hasta}",
                 fontsize=16, fontweight="bold", color=GRIS)

    # Fila 1: indicadores calculados con numpy
    tarjeta_kpi(fig.add_subplot(gs[0, 0]), "Facturación del período", pesos_cortos(resumen["total"]))
    tarjeta_kpi(fig.add_subplot(gs[0, 1]), "Comandas pagadas", f"{resumen['comandas']:,}".replace(",", "."))
    tarjeta_kpi(fig.add_subplot(gs[0, 2]), "Ticket promedio", pesos(resumen["media"]),
                f"mediana {pesos(resumen['mediana'])}")
    tarjeta_kpi(fig.add_subplot(gs[0, 3]), "Ticket P90", pesos(resumen["p90"]),
                f"desvío {pesos(resumen['desvio'])}")

    # Facturación acumulada día a día en el último mes
    ax = fig.add_subplot(gs[1, :3])
    dias_del_mes = pd.date_range(mes_ref, fin_mes - pd.Timedelta(days=1), freq="D")
    diario = (
        del_mes.set_index("fecha_hora")["total"].resample("D").sum()
        .reindex(dias_del_mes, fill_value=0)  # Los días sin ventas cuentan como 0
        .cumsum()
    )
    ax.fill_between(diario.index.day, diario.to_numpy(), color=NARANJA, alpha=0.25)
    ax.plot(diario.index.day, diario.to_numpy(), color=NARANJA, linewidth=2.5)
    ax.axhline(objetivo, linestyle="--", color=GRIS, linewidth=1.2)
    ax.text(1, objetivo, " objetivo", va="bottom", fontsize=9, color=GRIS)
    ax.set_title(f"Facturación acumulada · {etiqueta_mes(mes_ref)} (último mes completo)", fontsize=11)
    ax.set_xlabel("Día del mes")
    ax.set_xlim(1, len(dias_del_mes))
    ax.yaxis.set_major_formatter(FuncFormatter(pesos_cortos))

    # Cumplimiento del objetivo en ese mes
    ax = fig.add_subplot(gs[1, 3])
    cumplimiento = completos.iloc[-1] / objetivo if objetivo else 0
    lleno = min(cumplimiento, 1)
    ax.pie([lleno, 1 - lleno], colors=[VERDE if cumplimiento >= 1 else NARANJA, "#E5E7EB"],
           startangle=90, counterclock=False, wedgeprops={"width": 0.3})
    ax.text(0, 0, f"{cumplimiento:.0%}", ha="center", va="center", fontsize=20, fontweight="bold", color=GRIS)
    ax.set_title("Cumplimiento del objetivo", fontsize=11)

    # Top 5 mozos por facturación
    ax = fig.add_subplot(gs[2, :2])
    top_mozos = comandas.groupby("mozo")["total"].sum().nlargest(5).sort_values()
    barras = ax.barh(top_mozos.index, top_mozos.to_numpy(), color=NARANJA)
    ax.bar_label(barras, labels=[pesos_cortos(v) for v in top_mozos.to_numpy()], padding=4, fontsize=9)
    ax.set_title("Facturación por mozo (top 5)", fontsize=11)
    ax.xaxis.set_major_formatter(FuncFormatter(pesos_cortos))
    ax.grid(axis="y", visible=False)

    # Ticket promedio por mes
    ax = fig.add_subplot(gs[2, 2:])
    ticket = comandas.set_index("fecha_hora")["total"].resample("MS").mean().dropna()
    etiquetas = [etiqueta_mes(p) for p in ticket.index.tz_localize(None).to_period("M")]
    ax.bar(etiquetas, ticket.to_numpy(), color="#2E6F95")
    ax.axhline(resumen["media"], linestyle="--", color=GRIS, linewidth=1)
    ax.set_title("Ticket promedio por mes", fontsize=11)
    ax.yaxis.set_major_formatter(FuncFormatter(pesos_cortos))
    ax.grid(axis="x", visible=False)
    ax.tick_params(axis="x", labelsize=8)

    return guardar(fig, args.salida, "5_dashboard_ejecutivo.png")


# ---------------------------------------------------------------------------
# Indicadores con numpy
# ---------------------------------------------------------------------------

def calcular_resumen(comandas):
    tickets = comandas["total"].to_numpy()
    media = float(np.mean(tickets))
    return {
        "comandas": int(tickets.size),
        "total": float(np.sum(tickets)),
        "media": media,
        "mediana": float(np.median(tickets)),
        "desvio": float(np.std(tickets, ddof=1)) if tickets.size > 1 else 0.0,
        "p25": float(np.percentile(tickets, 25)),
        "p75": float(np.percentile(tickets, 75)),
        "p90": float(np.percentile(tickets, 90)),
        "coef_variacion": float(np.std(tickets) / media) if media else 0.0,
    }


def escribir_resumen(resumen, args, comandas, productos):
    lineas = [
        "RESUMEN ANALÍTICO - LOS CARDONES",
        f"Período: {args.desde} a {args.hasta}" + (f" · Mozo: {args.mozo}" if args.mozo else ""),
        "",
        f"Comandas pagadas:      {resumen['comandas']}",
        f"Facturación total:     {pesos(resumen['total'])}",
        f"Ticket promedio:       {pesos(resumen['media'])}",
        f"Ticket mediano:        {pesos(resumen['mediana'])}",
        f"Desvío estándar:       {pesos(resumen['desvio'])}",
        f"Percentiles 25/75/90:  {pesos(resumen['p25'])} / {pesos(resumen['p75'])} / {pesos(resumen['p90'])}",
        f"Coef. de variación:    {resumen['coef_variacion']:.2f}",
        f"Unidades vendidas:     {int(productos['unidades'].sum())}",
        f"Productos distintos:   {productos['producto'].nunique()}",
        f"Mozos con ventas:      {comandas['mozo'].nunique()}",
    ]
    texto = "\n".join(lineas)
    (Path(args.salida) / "resumen.txt").write_text(texto, encoding="utf-8")
    print("\n" + texto + "\n")


# ---------------------------------------------------------------------------

def main():
    args = leer_parametros()
    Path(args.salida).mkdir(parents=True, exist_ok=True)

    print(f"Leyendo la base de datos ({args.desde} a {args.hasta})...")
    comandas, productos = cargar_datos(args)
    if comandas.empty:
        print("No hay comandas pagadas en el período elegido. Probá con otro rango de fechas.")
        return

    resumen = calcular_resumen(comandas)
    escribir_resumen(resumen, args, comandas, productos)

    print("Generando gráficos:")
    grafico_barras_categorias(productos, args)
    grafico_donut_participacion(productos, args)
    grafico_lineas_objetivo(comandas, args)
    grafico_heatmap_dia_hora(comandas, args)
    grafico_dashboard(comandas, args, resumen)
    print(f"\nListo. Los PNG están en: {Path(args.salida).resolve()}")


if __name__ == "__main__":
    main()
