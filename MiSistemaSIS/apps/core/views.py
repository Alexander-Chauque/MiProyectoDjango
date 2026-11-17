from django.db.models import Avg, Count, Sum
from django.shortcuts import render
from django.utils import timezone

from empleados.decorators import tiene_permiso
from finanzas.models import caja as Caja
from inventario.models import Plato, Bebida
from notificaciones.views import mis_notificaciones
from ventas.models import Mesa, Comanda, Pago
from .fechas import filtrar_por_fecha

# Comandas que todavía no se cobraron ni se anularon
ESTADOS_ACTIVOS = ['pendiente', 'en_preparacion', 'entregado']
# Cuántas filas muestra cada lista del inicio; el resto se ve en su listado
MAX_COMANDAS_INICIO = 8
MAX_AVISOS_INICIO = 4


def _resumen_mesas():
    """Mesas ocupadas y disponibles, en total y por ubicación (una sola consulta)."""
    # order_by() vacío: sin el orden por defecto del modelo, que rompería el agrupado
    filas = (
        Mesa.objects.order_by()
        .values('ubicacion', 'estado_mesa')
        .annotate(cantidad=Count('id_mesa'))
    )
    por_ubicacion = {
        clave: {'nombre': nombre, 'ocupadas': 0, 'disponibles': 0}
        for clave, nombre in Mesa.UBICACIONES
    }
    for fila in filas:
        zona = por_ubicacion.setdefault(
            fila['ubicacion'],
            {'nombre': fila['ubicacion'] or 'Sin ubicación', 'ocupadas': 0, 'disponibles': 0},
        )
        # estado_mesa: True = disponible, False = ocupada
        zona['disponibles' if fila['estado_mesa'] else 'ocupadas'] += fila['cantidad']

    zonas = list(por_ubicacion.values())
    for zona in zonas:
        zona['total'] = zona['ocupadas'] + zona['disponibles']
        zona['porcentaje'] = round(zona['ocupadas'] * 100 / zona['total']) if zona['total'] else 0

    ocupadas = sum(zona['ocupadas'] for zona in zonas)
    total = sum(zona['total'] for zona in zonas)
    return {
        'zonas': zonas,
        'ocupadas': ocupadas,
        'disponibles': total - ocupadas,
        'total': total,
        'porcentaje': round(ocupadas * 100 / total) if total else 0,
    }


def _por_cobrar():
    """Comandas ya entregadas que faltan cobrar y cuánto suman (lo que falta de cada una)."""
    entregadas = Comanda.objects.filter(estado_comanda='entregado').annotate(pagado=Sum('pagos__monto'))
    saldos = [max(c.total_comanda - (c.pagado or 0), 0) for c in entregadas]
    saldos = [s for s in saldos if s > 0]
    return {'cantidad': len(saldos), 'monto': sum(saldos)}


def _comandas_de_hoy(hoy):
    """Comandas tomadas hoy (sin las anuladas) y su ticket promedio."""
    datos = (
        filtrar_por_fecha(Comanda.objects.exclude(estado_comanda='anulado'), 'fecha_hora', hoy, hoy)
        .aggregate(cantidad=Count('id_comanda'), promedio=Avg('total_comanda'))
    )
    return {'cantidad': datos['cantidad'], 'ticket_promedio': datos['promedio'] or 0}


def _resumen_comandas():
    """Cantidad de comandas activas por estado y las más recientes (dos consultas)."""
    por_estado = dict(
        Comanda.objects.order_by()
        .filter(estado_comanda__in=ESTADOS_ACTIVOS)
        .values_list('estado_comanda')
        .annotate(cantidad=Count('id_comanda'))
    )
    recientes = (
        Comanda.objects.filter(estado_comanda__in=ESTADOS_ACTIVOS)
        .select_related('mesa', 'empleado')
        .order_by('-fecha_hora')[:MAX_COMANDAS_INICIO]
    )
    en_preparacion = por_estado.get('en_preparacion', 0)
    return {
        'recientes': recientes,
        'activas': sum(por_estado.values()),
        'pendientes': por_estado.get('pendiente', 0) + en_preparacion,
        'en_preparacion': en_preparacion,
        # Las tarjetas de arriba no repiten los paneles: lo de hoy y lo que falta cobrar
        'hoy': _comandas_de_hoy(timezone.localdate()),
        'por_cobrar': _por_cobrar(),
    }


def _resumen_caja(hoy):
    """Lo cobrado hoy y la caja abierta, si hay una."""
    cobrado_hoy = filtrar_por_fecha(Pago.objects.all(), 'fecha_hora', hoy, hoy).aggregate(
        total=Sum('monto'), cantidad=Count('id_pago')
    )
    return {
        'ventas_hoy': cobrado_hoy['total'] or 0,
        'cobros_hoy': cobrado_hoy['cantidad'],
        'abierta': Caja.objects.filter(estado_caja='abierto').order_by('-fecha_apertura').first(),
    }


def home(request):
    # Sin sesión iniciada: pantalla de bienvenida
    if not request.user.is_authenticated:
        return render(request, 'bienvenida.html')

    # Con sesión: panel con la información del día.
    # Cada bloque se arma solo si el cargo del usuario puede leer ese módulo.
    usuario = request.user
    contexto = {}

    if tiene_permiso(usuario, 'platos', 'leer') or tiene_permiso(usuario, 'bebidas', 'leer'):
        contexto['total_productos'] = (
            Plato.objects.filter(estado_plato=True).count()
            + Bebida.objects.filter(disponible_bebida=True).count()
        )
        contexto['ver_productos'] = True

    if tiene_permiso(usuario, 'mesas', 'leer'):
        contexto['mesas'] = _resumen_mesas()

    if tiene_permiso(usuario, 'comandas', 'leer'):
        contexto['comandas'] = _resumen_comandas()

    if tiene_permiso(usuario, 'caja', 'leer'):
        # localdate(): la fecha de Salta, no la UTC
        contexto['caja'] = _resumen_caja(timezone.localdate())

    # Avisos: las notificaciones sin leer dirigidas al cargo del usuario
    contexto['avisos'] = mis_notificaciones(request).filter(leida=False)[:MAX_AVISOS_INICIO]

    return render(request, 'home.html', contexto)
