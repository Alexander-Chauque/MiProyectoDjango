from datetime import datetime, time

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


def filtrar_por_fecha(consulta, campo, desde, hasta):
    """Filtra un DateTimeField por días completos, en la hora de Salta.

    No usa `campo__date`: en MySQL eso se traduce a CONVERT_TZ, que devuelve
    NULL si el servidor no tiene cargadas las tablas de zonas horarias (XAMPP
    no las trae), y entonces cualquier rango de fechas sale vacío.
    """
    zona = timezone.get_current_timezone()
    for texto, extremo, operador in ((desde, time.min, "gte"), (hasta, time.max, "lte")):
        if not texto:
            continue
        try:
            dia = datetime.strptime(texto, "%Y-%m-%d").date() if isinstance(texto, str) else texto
        except ValueError:
            continue
        limite = timezone.make_aware(datetime.combine(dia, extremo), zona)
        consulta = consulta.filter(**{f"{campo}__{operador}": limite})
    return consulta
