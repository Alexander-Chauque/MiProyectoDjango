from .models import Configuracion, Notificacion
from django.db.models import Count, Avg, StdDev
from ventas.models import Comanda
from empleados.models import Cargo
from datetime import timedelta
from django.utils import timezone
from finanzas.models import caja

MINIMO_VENTAS = 10

def leer_config(clave, por_defecto):
    try:
      valor = Configuracion.objects.get(clave_configuracion=clave).valor_configuracion
      return  float(valor)
    except (Configuracion.DoesNotExist, ValueError):
      return por_defecto

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
    notificacion, _ = Notificacion.objects.get_or_create(
    referencia=f"venta_inusual:comanda_{comanda.id_comanda}",
    defaults={
        "tipo": "VENTA_INUSUAL",
        "mensaje": f"Se ha registrado una venta inusual: Comanda #{comanda.id_comanda} con total ${total_text}, por encima del limite de ${limite_text} (media + {n:g} desviaciones).",
        "destino_perfil": Cargo.objects.filter(nombre_cargo="Administrador").first(),
    },
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
        _, nueva = Notificacion.objects.get_or_create(
            referencia=f"comanda_demorada:comanda_{comanda.id_comanda}",
            defaults={
                "tipo": "COMANDA_DEMORADA",
                "mensaje": (
                    f"La comanda #{comanda.id_comanda} de la mesa {comanda.mesa.numero_mesa} "
                    f"lleva {espera} minutos en estado '{comanda.get_estado_comanda_display()}' "
                    f"(límite: {minutos:g} minutos)."
                ),
                "destino_perfil": destino("Mozo"),
            },
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
        _, nueva = Notificacion.objects.get_or_create(
            referencia=f"caja_abierta:caja_{c.id_caja}",
            defaults={
                "tipo": "CAJA_ABIERTA",
                "mensaje": (
                    f"La caja #{c.id_caja}, abierta por {cajero}, lleva {abierta_hace} horas "
                    f"sin cerrarse (límite: {horas:g} horas)."
                ),
                "destino_perfil": destino("Administrador"),
            },
        )
        creadas += nueva
    return creadas
