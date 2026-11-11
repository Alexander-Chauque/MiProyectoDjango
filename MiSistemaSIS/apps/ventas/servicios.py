from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from auditoria.models import LogAuditoria
from inventario.models import Bebida, Plato
from .models import Comanda, DetalleComanda, Mesa, Pago
from decimal import Decimal, InvalidOperation
from notificaciones.reglas import evaluar_venta_inusual

ESTADOS_ABIERTOS = ["pendiente", "en_preparacion", "entregado"]
CANTIDAD_MAXIMA = 999


def registrar_pago(id_comanda, tipo_pago, metodo_pago, monto_texto, empleado):
    """Guarda el pago y cierra la comanda si queda sin saldo.

    Debe llamarse dentro de transaction.atomic(). Devuelve (comanda, monto, saldo_restante).
    """
    # select_for_update bloquea la fila para que dos cobros simultáneos no se pisen
    comanda = get_object_or_404(Comanda.objects.select_for_update(), id_comanda=id_comanda)
    if comanda.estado_comanda not in ESTADOS_ABIERTOS:
        raise ValueError(f"La comanda #{comanda.id_comanda} ya está cerrada.")

    if metodo_pago not in dict(Pago.METODOS):
        raise ValueError("Seleccioná un método de pago válido.")

    saldo = comanda.saldo_pendiente
    if tipo_pago == "total":
        monto = saldo
    elif tipo_pago == "parcial":
        try:
            monto = Decimal(str(monto_texto or ""))
        except InvalidOperation:
            raise ValueError("Ingresá un monto válido.")
        if not monto.is_finite() or monto <= 0 or monto != monto.quantize(Decimal("0.01")):
            raise ValueError("Ingresá un monto válido, mayor a 0 y con hasta 2 decimales.")
        if monto > saldo:
            raise ValueError(f"El monto no puede superar el saldo pendiente de ${saldo}.")
    else:
        raise ValueError("Seleccioná cómo se va a pagar la comanda.")

    if monto > 0:
        Pago.objects.create(comanda=comanda, monto=monto, metodo_pago=metodo_pago, empleado=empleado)

    estado_anterior = comanda.estado_comanda
    saldo_restante = saldo - monto
    if saldo_restante == 0:
        comanda.estado_comanda = "pagado"
        comanda.save()
        comanda.mesa.estado_mesa = True
        comanda.mesa.save()
        evaluar_venta_inusual(comanda)  # Crea notificación si corresponde

    LogAuditoria.objects.create(
        tabla="Comanda",
        accion="MODIFICAR",
        registro_id=comanda.id_comanda,
        valores_anteriores=f"Estado: {estado_anterior}. Saldo: ${saldo}",
        valores_actuales=f"Estado: {comanda.estado_comanda}. Pago: ${monto} ({metodo_pago}). Saldo: ${saldo_restante}",
        empleado=empleado,
    )
    return comanda, monto, saldo_restante


def _leer_items(items):
    """Convierte [{"tipo": "plato", "id": 3, "cantidad": 2}] en {producto: cantidad}."""
    if not isinstance(items, list) or not items:
        raise ValueError("Agregá al menos un plato o una bebida.")

    modelos = {"plato": Plato, "bebida": Bebida}
    cantidades = {}
    for item in items:
        if not isinstance(item, dict) or item.get("tipo") not in modelos:
            raise ValueError("Hay un producto inválido en la comanda.")
        try:
            id_producto = int(item.get("id"))
            cantidad = int(item.get("cantidad"))
        except (TypeError, ValueError):
            raise ValueError("Hay un producto o una cantidad inválida en la comanda.")
        if not 1 <= cantidad <= CANTIDAD_MAXIMA:
            raise ValueError(f"La cantidad debe estar entre 1 y {CANTIDAD_MAXIMA}.")

        producto = modelos[item["tipo"]].objects.filter(pk=id_producto).first()
        if not producto:
            raise ValueError("Hay un producto que ya no existe.")
        cantidades[producto] = cantidades.get(producto, 0) + cantidad
    return cantidades


def _disponible(producto):
    return producto.estado_plato if isinstance(producto, Plato) else producto.disponible_bebida


def _nombre(producto):
    return producto.nombre_plato if isinstance(producto, Plato) else producto.nombre_bebida


def _guardar_detalles(comanda, cantidades):
    """Reemplaza los productos de la comanda y recalcula el total."""
    comanda.detalles.all().delete()
    for producto, cantidad in cantidades.items():
        if isinstance(producto, Plato):
            DetalleComanda.objects.create(comanda=comanda, plato=producto, cant_plato=cantidad, cant_bebida=0)
        else:
            DetalleComanda.objects.create(comanda=comanda, bebida=producto, cant_bebida=cantidad, cant_plato=0)
    comanda.calcular_total()


def _cantidades_actuales(comanda):
    cantidades = {}
    for detalle in comanda.detalles.select_related("plato", "bebida"):
        if detalle.plato:
            cantidades[detalle.plato] = cantidades.get(detalle.plato, 0) + detalle.cant_plato
        if detalle.bebida:
            cantidades[detalle.bebida] = cantidades.get(detalle.bebida, 0) + detalle.cant_bebida
    return cantidades


@transaction.atomic
def crear_comanda(id_mesa, empleado, observaciones, items):
    try:
        mesa = Mesa.objects.select_for_update().filter(pk=int(id_mesa)).first()
    except (TypeError, ValueError):
        mesa = None
    if not mesa:
        raise ValueError("Seleccioná una mesa válida.")
    if not mesa.estado_mesa or mesa.comandas.filter(estado_comanda__in=ESTADOS_ABIERTOS).exists():
        raise ValueError(f"La mesa {mesa.numero_mesa} no está disponible.")

    cantidades = _leer_items(items)
    no_disponibles = [_nombre(p) for p in cantidades if not _disponible(p)]
    if no_disponibles:
        raise ValueError(f"No está disponible: {', '.join(no_disponibles)}.")

    comanda = Comanda.objects.create(
        mesa=mesa, empleado=empleado, observaciones_comanda=observaciones or ""
    )
    _guardar_detalles(comanda, cantidades)
    mesa.estado_mesa = False
    mesa.save()

    LogAuditoria.objects.create(
        tabla="Comanda",
        accion="CREAR",
        registro_id=comanda.id_comanda,
        valores_anteriores="",
        valores_actuales=f"Desde la app. Mesa: {mesa.numero_mesa}. Total: ${comanda.total_comanda}",
        empleado=empleado,
    )
    return comanda


@transaction.atomic
def actualizar_comanda(id_comanda, empleado, observaciones, items):
    """Aplica las mismas reglas que la web: con pagos solo se puede agregar."""
    comanda = get_object_or_404(Comanda.objects.select_for_update(), id_comanda=id_comanda)
    if not comanda.esta_abierta:
        raise ValueError(f"La comanda #{comanda.id_comanda} está cerrada: no se puede editar.")

    nuevas = _leer_items(items)
    anteriores = _cantidades_actuales(comanda)

    if comanda.pagos.exists():
        for producto, cantidad in anteriores.items():
            if nuevas.get(producto, 0) < cantidad:
                raise ValueError(
                    "La comanda tiene pagos registrados: podés agregar productos, pero no quitar ni reducir los que ya tenía."
                )
    for producto, cantidad in nuevas.items():
        if not _disponible(producto) and cantidad > anteriores.get(producto, 0):
            raise ValueError(f"{_nombre(producto)} no está disponible: no se puede agregar ni aumentar.")

    total_anterior = comanda.total_comanda
    if observaciones is not None:
        comanda.observaciones_comanda = observaciones
    comanda.save()
    _guardar_detalles(comanda, nuevas)

    # Al recalcular con precios actuales, el total podría quedar debajo de lo cobrado
    if comanda.total_comanda < comanda.total_pagado:
        raise ValueError(
            f"El nuevo total (${comanda.total_comanda}) no puede ser menor a lo ya cobrado (${comanda.total_pagado})."
        )

    LogAuditoria.objects.create(
        tabla="Comanda",
        accion="MODIFICAR",
        registro_id=comanda.id_comanda,
        valores_anteriores=f"Total: ${total_anterior}",
        valores_actuales=f"Desde la app. Total: ${comanda.total_comanda}",
        empleado=empleado,
    )
    return comanda


@transaction.atomic
def cambiar_estado_comanda(id_comanda, nuevo_estado, empleado, motivo=""):
    """Cambia entre pendiente, en preparación y entregado, o anula la comanda."""
    comanda = get_object_or_404(Comanda.objects.select_for_update(), id_comanda=id_comanda)
    if not comanda.esta_abierta:
        raise ValueError(f"La comanda #{comanda.id_comanda} ya está cerrada.")

    estado_anterior = comanda.estado_comanda
    if nuevo_estado == "anulado":
        if not comanda.puede_modificarse:
            raise ValueError("La comanda tiene pagos registrados: no se puede anular.")
        motivo = (motivo or "").strip()
        if not motivo:
            raise ValueError("Escribí el motivo de la anulación.")
        comanda.estado_comanda = "anulado"
        comanda.fecha_anulacion = timezone.now()
        comanda.motivo_anulacion = motivo[:250]
        comanda.usuario_anulacion = empleado
        comanda.mesa.estado_mesa = True
        accion, detalle = "ANULAR", f"Estado: anulado. Motivo: {motivo[:250]}"
    elif nuevo_estado in ESTADOS_ABIERTOS:
        comanda.estado_comanda = nuevo_estado
        comanda.mesa.estado_mesa = False
        accion, detalle = "MODIFICAR", f"Estado: {nuevo_estado}"
    else:
        raise ValueError("Estado no válido.")

    comanda.save()
    comanda.mesa.save()
    LogAuditoria.objects.create(
        tabla="Comanda",
        accion=accion,
        registro_id=comanda.id_comanda,
        valores_anteriores=f"Estado: {estado_anterior}",
        valores_actuales=f"Desde la app. {detalle}",
        empleado=empleado,
    )
    return comanda


@transaction.atomic
def cambiar_estado_mesa(id_mesa, empleado):
    """Alterna disponible y ocupada. No libera una mesa con una comanda abierta."""
    mesa = get_object_or_404(Mesa.objects.select_for_update(), pk=id_mesa)
    if not mesa.estado_mesa:
        abiertas = mesa.comandas.filter(estado_comanda__in=ESTADOS_ABIERTOS)
        if abiertas.exists():
            # El mismo texto que muestra la web de Django
            ids = ",".join(f"#{c.id_comanda}" for c in abiertas)
            raise ValueError(f"No se puede liberar la Mesa {mesa.numero_mesa} porque tiene comandas activas: {ids}")

    anterior = mesa.estado_texto
    mesa.estado_mesa = not mesa.estado_mesa
    mesa.save()
    LogAuditoria.objects.create(
        tabla="Mesa",
        accion="MODIFICAR",
        registro_id=mesa.id_mesa,
        valores_anteriores=f"Estado: {anterior}",
        valores_actuales=f"Desde la app. Estado: {mesa.estado_texto}",
        empleado=empleado,
    )
    return mesa
