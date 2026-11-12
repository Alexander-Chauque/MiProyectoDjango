import random
from datetime import datetime, timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from empleados.models import Empleado
from inventario.models import Bebida, Plato
from ventas.models import Comanda, DetalleComanda, Mesa, Pago

MARCA = "[DATO DE PRUEBA]"
# (año, mes, cantidad de comandas): crece hacia las vacaciones de invierno
MESES = [(2026, 3, 8), (2026, 4, 10), (2026, 5, 12), (2026, 6, 16), (2026, 7, 22), (2026, 8, 14), (2026, 9, 18)]
METODOS = ["efectivo", "efectivo", "tarjeta", "transferencia", "mercadopago"]

random.seed(2026)  # siempre genera los mismos datos

if Comanda.objects.filter(observaciones_comanda__startswith=MARCA).exists():
    print("Los datos de prueba ya estaban cargados. No se cargó nada.")
else:
    platos = list(Plato.objects.filter(estado_plato=True))
    bebidas = list(Bebida.objects.filter(disponible_bebida=True))
    mesas = list(Mesa.objects.all())
    mozos = list(Empleado.objects.filter(estado=True))
    if not (platos and bebidas and mesas and mozos):
        print("Faltan platos, bebidas, mesas o empleados activos para cargar las comandas.")
    else:
        zona = timezone.get_current_timezone()
        creadas = 0
        with transaction.atomic():
            for anio, mes, cantidad in MESES:
                for _ in range(cantidad):
                    dia = random.randint(1, 28)
                    hora = random.choice([20, 21, 21, 22, 22, 23])
                    momento = timezone.make_aware(datetime(anio, mes, dia, hora, random.randint(0, 59)), zona)
                    mozo = random.choice(mozos)

                    comanda = Comanda.objects.create(
                        mesa=random.choice(mesas),
                        empleado=mozo,
                        estado_comanda="pagado",
                        observaciones_comanda=MARCA,
                    )
                    total = Decimal("0")
                    for plato in random.sample(platos, k=min(len(platos), random.randint(1, 3))):
                        cant = random.randint(1, 3)
                        DetalleComanda.objects.create(comanda=comanda, plato=plato, cant_plato=cant, bebida=None, cant_bebida=0)
                        total += plato.precio_plato * cant
                    for bebida in random.sample(bebidas, k=min(len(bebidas), random.randint(1, 2))):
                        cant = random.randint(1, 4)
                        DetalleComanda.objects.create(comanda=comanda, plato=None, cant_plato=0, bebida=bebida, cant_bebida=cant)
                        total += bebida.precio_bebida * cant

                    pago = Pago.objects.create(comanda=comanda, monto=total, metodo_pago=random.choice(METODOS), empleado=mozo)
                    # fecha_hora es auto_now_add: se corrige con update() para ubicarla en el mes elegido
                    Comanda.objects.filter(pk=comanda.pk).update(fecha_hora=momento, total_comanda=total)
                    Pago.objects.filter(pk=pago.pk).update(fecha_hora=momento + timedelta(hours=1, minutes=random.randint(0, 50)))
                    creadas += 1
        print("Comandas de prueba cargadas: " + str(creadas))

# ============================================================
# PARA BORRARLAS (copiar y pegar en python manage.py shell):
#
# from ventas.models import Comanda, Pago
# prueba = Comanda.objects.filter(observaciones_comanda__startswith="[DATO DE PRUEBA]")
# Pago.objects.filter(comanda__in=prueba).delete()
# prueba.delete()
# ============================================================
