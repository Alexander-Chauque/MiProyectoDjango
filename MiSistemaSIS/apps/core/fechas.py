from datetime import datetime

from django.utils import timezone


def limitar_a_hoy(texto):
    if not texto:
        return texto
    try:
        fecha = datetime.strptime(texto, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return ""
    # localdate() usa la hora de Salta. timezone.now().date() daría la fecha UTC: después de las 21:00, mañana.
    return min(fecha, timezone.localdate()).strftime("%Y-%m-%d")


def limitar_rango(desde, hasta):
    desde, hasta = limitar_a_hoy(desde), limitar_a_hoy(hasta)
    # Con el formato AAAA-MM-DD, comparar los textos equivale a comparar las fechas
    if desde and hasta and desde > hasta:
        return hasta, desde
    return desde, hasta
