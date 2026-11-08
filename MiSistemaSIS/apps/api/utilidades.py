"""Ayudas comunes de la API: páginas, fechas y montos."""
from datetime import datetime, time
from decimal import Decimal, InvalidOperation

from django.core.paginator import Paginator
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from core.fechas import limitar_rango

# Las mismas opciones que ofrecen los listados de la web de Django
OPCIONES_POR_PAGINA = (10, 25, 50, 100)


def responder_paginado(request, consulta, convertir, extra=None):
    """Responde una página de resultados. ?pagina=2&por_pagina=25"""
    try:
        por_pagina = int(request.query_params.get("por_pagina", 10))
    except (TypeError, ValueError):
        por_pagina = 10
    if por_pagina not in OPCIONES_POR_PAGINA:
        por_pagina = 10
    # get_page() corrige una página inexistente en vez de fallar
    pagina = Paginator(consulta, por_pagina).get_page(request.query_params.get("pagina"))
    datos = {
        "resultados": [convertir(fila) for fila in pagina.object_list],
        "total": pagina.paginator.count,
        "pagina": pagina.number,
        "paginas": pagina.paginator.num_pages,
        "por_pagina": por_pagina,
    }
    if extra:
        datos.update(extra)
    return Response(datos)


def rango_pedido(request):
    """Lee ?fecha_desde y ?fecha_hasta (AAAA-MM-DD), sin pasar de hoy y en orden."""
    return limitar_rango(
        request.query_params.get("fecha_desde", ""), request.query_params.get("fecha_hasta", "")
    )


def filtrar_entre_fechas(consulta, campo, desde, hasta):
    """Filtra un campo de fecha y hora por días completos, con la hora de Salta."""
    zona = timezone.get_current_timezone()
    for texto, hora, operador in ((desde, time.min, "gte"), (hasta, time.max, "lte")):
        if not texto:
            continue
        try:
            dia = datetime.strptime(texto, "%Y-%m-%d").date()
        except ValueError:
            continue
        momento = timezone.make_aware(datetime.combine(dia, hora), zona)
        consulta = consulta.filter(**{f"{campo}__{operador}": momento})
    return consulta


def leer_monto(valor, campo, mensaje, permitir_cero=False):
    """Convierte el texto en un monto con hasta 2 decimales. Acepta la coma decimal."""
    texto = str(valor if valor is not None else "").strip().replace(",", ".")
    try:
        monto = Decimal(texto)
    except InvalidOperation:
        raise ValidationError({campo: [mensaje]})
    valido = (
        monto.is_finite()
        and (monto >= 0 if permitir_cero else monto > 0)
        and monto == monto.quantize(Decimal("0.01"))
        and monto < Decimal("100000000")  # El campo de la base admite 10 dígitos
    )
    if not valido:
        raise ValidationError({campo: [mensaje]})
    return monto


def leer_texto(request, campo, maximo=None, nombre="El texto"):
    texto = str(request.data.get(campo) or "").strip()
    if maximo and len(texto) > maximo:
        raise ValidationError({campo: [f"{nombre} no puede superar los {maximo} caracteres."]})
    return texto
