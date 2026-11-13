import logging
from .models import Configuracion, Notificacion
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.db.models import Count, Avg, StdDev
from ventas.models import Comanda
from empleados.models import Cargo, Empleado
from datetime import timedelta
from django.utils import timezone
from finanzas.models import caja

MINIMO_VENTAS = 10
logger = logging.getLogger(__name__)

def leer_config(clave, por_defecto):
    try:
      valor = Configuracion.objects.get(clave_configuracion=clave).valor_configuracion
      return  float(valor)
    except (Configuracion.DoesNotExist, ValueError):
      return por_defecto


def enviar_por_correo(notificacion):
    """Canal externo: manda la alerta por correo a los empleados activos del cargo destino.

    Se activa o desactiva desde la tabla configuracion (enviar_correo_alertas = 1 o 0).
    Un fallo del correo no debe impedir que la alerta quede en la bandeja: se registra y sigue.
    Devuelve cuántos correos se enviaron.
    """
    if not leer_config("enviar_correo_alertas", 1) or notificacion.destino_perfil is None:
        return 0
    correos = list(
        Empleado.objects.filter(cargo=notificacion.destino_perfil, estado=True)
        .exclude(correo="")
        .exclude(correo__isnull=True)
        .values_list("correo", flat=True)
    )
    if not correos:
        return 0
    fecha = timezone.localtime(notificacion.fecha)
    enlace = settings.SITIO_URL + "/notificaciones/"
    # Versión con diseño (HTML). La de texto queda para los programas que no muestran HTML.
    html = render_to_string("notificaciones/correo_alerta.html", {
        "tipo": notificacion.get_tipo_display(),
        "mensaje": notificacion.mensaje,
        "fecha": fecha,
        "cargo": notificacion.destino_perfil.nombre_cargo,
        "enlace": enlace,
    })
    try:
        return send_mail(
            subject=f"[Los Cardones] Alerta: {notificacion.get_tipo_display()}",
            message=(
                f"{notificacion.mensaje}\n\n"
                f"Fecha: {fecha:%d/%m/%Y %H:%M}\n"
                f"Podés verla en la bandeja de notificaciones: {enlace}"
            ),
            html_message=html,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=correos,
        )
    except Exception:  # SMTP caído, credenciales mal cargadas, sin internet...
        logger.exception("No se pudo enviar por correo la notificación %s", notificacion.pk)
        return 0


def registrar_notificacion(referencia, tipo, mensaje, cargo):
    """Crea la notificación una sola vez y, si es nueva, la manda también por correo.

    La referencia (única en la tabla) identifica el hecho que dispara la alerta, por ejemplo
    "caja_abierta:caja_7". Si la regla vuelve a evaluarse, get_or_create encuentra la existente
    y no crea otra ni reenvía el correo: así la alerta no se dispara dos veces.
    """
    notificacion, nueva = Notificacion.objects.get_or_create(
        referencia=referencia,
        defaults={"tipo": tipo, "mensaje": mensaje, "destino_perfil": cargo},
    )
    if nueva:
        enviar_por_correo(notificacion)
    return notificacion, nueva

def evaluar_venta_inusual(comanda):
    datos =(
    Comanda.objects.filter(estado_comanda='pagado')
    .exclude(id_comanda=comanda.id_comanda)
    .aggregate(cantidad=Count("id_comanda"), media=Avg("total_comanda"), desviacion=StdDev("total_comanda"))
  )

    if datos['cantidad'] < MINIMO_VENTAS:
        return None

    n = leer_config("desvio_venta_inusual", 3)
    limite = float (datos['media']) + n * float(datos['desviacion'] or 0)
    total = float(comanda.total_comanda)
    if total <= limite:  
        return None

    total_text =f"{total:,.0f}".replace(",",".")
    limite_text = f"{limite:,.0f}".replace(",", ".")
    notificacion, _ = registrar_notificacion(
        referencia=f"venta_inusual:comanda_{comanda.id_comanda}",
        tipo="VENTA_INUSUAL",
        mensaje=f"Se ha registrado una venta inusual: Comanda #{comanda.id_comanda} con total ${total_text}, por encima del limite de ${limite_text} (media + {n:g} desviaciones).",
        cargo=destino("Administrador"),
    )
    return notificacion


def destino(nombre_cargo):
    """El cargo que recibe el aviso. Si no existe, la notificación queda sin destino."""
    return Cargo.objects.filter(nombre_cargo=nombre_cargo).first()


def evaluar_comandas_demoradas():
    """Avisa a cocina por cada comanda pendiente o en preparación hace más de N minutos.

    Se ejecuta desde el comando programado evaluar_alertas. Devuelve cuántas alertas nuevas creó.
    """
    minutos = leer_config("minutos_comanda_demorada", 30)
    limite = timezone.now() - timedelta(minutes=minutos)

    demoradas = Comanda.objects.filter(
        estado_comanda__in=["pendiente", "en_preparacion"],
        fecha_hora__lt=limite,
    ).select_related("mesa")

    creadas = 0
    for comanda in demoradas:
        espera = int((timezone.now() - comanda.fecha_hora).total_seconds() // 60)
        # La referencia única evita repetir el aviso cada vez que corre el comando
        _, nueva = registrar_notificacion(
            referencia=f"comanda_demorada:comanda_{comanda.id_comanda}",
            tipo="COMANDA_DEMORADA",
            mensaje=(
                f"La comanda #{comanda.id_comanda} de la mesa {comanda.mesa.numero_mesa} "
                f"lleva {espera} minutos en estado '{comanda.get_estado_comanda_display()}' "
                f"(límite: {minutos:g} minutos)."
            ),
            cargo=destino("Mozo"),
        )
        creadas += nueva
    return creadas


def evaluar_cajas_abiertas():
    """Avisa al Administrador por cada caja abierta hace más de N horas sin cerrar.

    Se ejecuta desde el comando programado evaluar_alertas. Devuelve cuántas alertas nuevas creó.
    """
    horas = leer_config("horas_caja_abierta", 12)
    limite = timezone.now() - timedelta(hours=horas)

    abiertas = caja.objects.filter(
        estado_caja="abierto",
        fecha_apertura__lt=limite,
    ).select_related("empleado_apertura")

    creadas = 0
    for c in abiertas:
        abierta_hace = int((timezone.now() - c.fecha_apertura).total_seconds() // 3600)
        cajero = f"{c.empleado_apertura.nombre_empleado} {c.empleado_apertura.apellido_empleado}"
        _, nueva = registrar_notificacion(
            referencia=f"caja_abierta:caja_{c.id_caja}",
            tipo="CAJA_ABIERTA",
            mensaje=(
                f"La caja #{c.id_caja}, abierta por {cajero}, lleva {abierta_hace} horas "
                f"sin cerrarse (límite: {horas:g} horas)."
            ),
            cargo=destino("Administrador"),
        )
        creadas += nueva
    return creadas
