from django.db import models
from empleados.models import Empleado
from ventas.models import Comanda, Mesa
from decimal import Decimal, InvalidOperation
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Sum
from django.db.models import Q
# Create your models here.
# metodo_pago
class metodo_pago(models.Model):
    id_metodo_pago = models.AutoField(primary_key=True)
    nombre_metodo_pago = models.CharField(max_length=50, unique= True, null=False, blank=False)
    descripcion_metodo_pago = models.TextField(blank=True)
    estado_metodo_pago = models.BooleanField(default=True)

    class Meta:
        db_table='finanzas_metodopago'

    def save(self, *args, **kwargs):
        if self.nombre_metodo_pago:
            self.nombre_metodo_pago=self.nombre_metodo_pago.title()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.nombre_metodo_pago}"

# categoria_gasto
class categoria_gasto(models.Model):
    id_categoria_gasto = models.AutoField(primary_key=True)
    nombre_categoria_gasto = models.CharField(max_length=50, unique=True, null=False, blank=False)
    descripcion_categoria_gasto = models.TextField(blank=True)
    estado_categoria_gasto = models.BooleanField(default=True)

    class Meta:
        db_table='finanzas_categoriagasto'

    def save(self, *args, **kwargs):
        if self.nombre_categoria_gasto:
            self.nombre_categoria_gasto=self.nombre_categoria_gasto.title()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.nombre_categoria_gasto}"

#caja

class caja(models.Model):
    ESTADOS = [
        ('abierto', 'Abierto'),
        ('cerrado', 'Cerrado')
    ]

    id_caja = models.AutoField(primary_key=True)
    fecha_apertura = models.DateTimeField(auto_now_add=True)

    empleado_apertura = models.ForeignKey(
        Empleado,
        on_delete=models.CASCADE,
        db_column='empleado_apertura_id',
        related_name='caja_apertura',
        verbose_name="cajero"
    )

    saldo_inicial = models.DecimalField(
        max_digits=10, decimal_places=2, default=0
    )

    fecha_cierre = models.DateTimeField(null=True, blank=True)

    empleado_cierre = models.ForeignKey(
        Empleado,
        on_delete=models.CASCADE,
        db_column='empleado_cierre_id',
        related_name='caja_cierre',
        verbose_name="cajero",
        null=True,
        blank=True
    )

    saldo_esperado = models.DecimalField(
        max_digits=10, decimal_places=2, default=0
    )
    saldo_contado = models.DecimalField(
        max_digits=10, decimal_places=2, default=0
    )
    diferencia_caja = models.DecimalField(
        max_digits=10, decimal_places=2, default=0
    )

    # Campo anterior, conservado por compatibilidad.
    observaciones_caja = models.TextField(blank=True)

    # Observaciones independientes por operación.
    observaciones_apertura = models.TextField(
        blank=True,
        default='',
        verbose_name='Observaciones de apertura'
    )

    observaciones_arqueo = models.TextField(
        blank=True,
        default='',
        verbose_name='Observaciones de arqueo'
    )

    observaciones_cierre = models.TextField(
        blank=True,
        default='',
        verbose_name='Observaciones de cierre'
    )

    estado_caja = models.CharField(
        max_length=10,
        choices=ESTADOS,
        default='abierto'
    )

    saldo_final = models.DecimalField(
        max_digits=10, decimal_places=2, default=0
    )

    empleado_arqueamiento = models.ForeignKey(
        Empleado,
        on_delete=models.CASCADE,
        db_column='empleado_arqueo_id',
        related_name='caja_arqueo',
        verbose_name="cajero",
        null=True,
        blank=True
    )

    fecha_arqueo = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'finanzas_caja'
        ordering = ['-fecha_apertura']
        verbose_name = 'Caja'
        verbose_name_plural = 'Cajas'

    def calcular_total_egresos(self):
        return (
            self.gastos.aggregate(total=Sum('monto_gasto'))['total']
            or Decimal('0.00')
        )

    def calcular_saldo_esperado(self):
        return self.saldo_inicial - self.calcular_total_egresos()

    def realizar_arqueo(
        self,
        saldo_contado,
        empleado_arqueamiento,
        observaciones_arqueo=''
    ):
        # Convertir antes de validar.
        try:
            saldo_contado = Decimal(str(saldo_contado))
        except (InvalidOperation, ValueError, TypeError):
            raise ValueError("El saldo contado debe ser un número válido.")

        if not saldo_contado.is_finite() or saldo_contado < 0:
            raise ValueError(
                "El saldo contado debe ser válido y no negativo."
            )

        if self.estado_caja != 'abierto':
            raise ValueError(
                "No se puede realizar el arqueo de una caja que no está abierta."
            )

        self.saldo_esperado = self.calcular_saldo_esperado()
        self.saldo_contado = saldo_contado
        self.diferencia_caja = saldo_contado - self.saldo_esperado
        self.observaciones_arqueo = (
            observaciones_arqueo or ''
        ).strip()
        self.empleado_arqueamiento = empleado_arqueamiento
        self.fecha_arqueo = timezone.now()

        self.save()

    def cerrar_caja(self, empleado, observaciones_cierre=''):
        if self.estado_caja != 'abierto':
            raise ValueError("La caja ya está cerrada.")

        self.fecha_cierre = timezone.now()
        self.empleado_cierre = empleado
        self.saldo_final = self.calcular_saldo_esperado()
        self.observaciones_cierre = (
            observaciones_cierre or ''
        ).strip()
        self.estado_caja = 'cerrado'

        self.save()

    def __str__(self):
        return f"Caja #{self.id_caja} - {self.estado_caja}"


#GASTOS

class gasto(models.Model):
    id_gasto = models.AutoField(primary_key=True)
    caja_gasto = models.ForeignKey(caja, on_delete=models.PROTECT, related_name='gastos')
    cat_gasto = models.ForeignKey(categoria_gasto, on_delete=models.PROTECT, related_name='gastos')
    descripcion_gasto = models.TextField(blank=True)
    monto_gasto = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    fecha_hora_gasto = models.DateTimeField(auto_now_add=True)
    empleado_gasto = models.ForeignKey(Empleado,on_delete=models.PROTECT,
        db_column='empleado_id',
        related_name='gastos',
        verbose_name="cajero"
    )
    #metodo_pago_gasto = models.ForeignKey(metodo_pago, on_delete=models.SET_NULL, null=True, blank=True, related_name='gastos')

    class Meta:
        db_table='finanzas_gasto'
        ordering = ['-fecha_hora_gasto']
        verbose_name = 'Gasto'
        verbose_name_plural = 'Gastos'

    def clean(self):
        super().clean()

        if self.monto_gasto is not None and self.monto_gasto <= 0:
            raise ValidationError(
                'El monto del gasto debe ser mayor que cero.'
            )
        if (
            self.caja_gasto_id
            and self.caja_gasto.estado_caja != 'abierto'
        ):
            raise ValidationError(
                'No se pueden registrar gastos en una caja cerrada.'
            )
        
    def __str__(self):
        return f"Gasto #{self.id_gasto} - {self.cat_gasto.nombre_categoria_gasto} - {self.monto_gasto}"

# --- VENTA ---
class Venta(models.Model):
    id_venta = models.AutoField(primary_key=True)
    fecha_venta = models.DateTimeField(auto_now_add=True, verbose_name="Fecha y Hora de Venta")
    total_venta = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Total Venta")
    monto_recibido = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Monto Recibido")
    vuelto = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Vuelto")
    
    # Relaciones
    comanda = models.ForeignKey(Comanda, on_delete=models.CASCADE, related_name='ventas', verbose_name="Comanda")
    metodo_pago_venta = models.ForeignKey(metodo_pago, on_delete=models.PROTECT, verbose_name="Método de Pago")
    caja_venta = models.ForeignKey(caja, on_delete=models.PROTECT, related_name='ventas', verbose_name="Caja Asociada")
    empleado_venta = models.ForeignKey(Empleado,on_delete=models.CASCADE,
                db_column='empleado_venta_id',
                related_name='caja_ventas',
                verbose_name="cajero",
                null=True, blank=True
        )
    class Meta:
        db_table = 'ventas_venta'
        verbose_name = 'Venta'
        verbose_name_plural = 'Ventas'
        ordering = ['-fecha_venta']
        constraints = [
            models.CheckConstraint(
                check=Q(total_venta__gte=0),
                name='venta_total_no_negativo'
            ),
            models.CheckConstraint(
                check=Q(monto_recibido__gte=0),
                name='venta_recibido_no_negativo'
            ),
            models.CheckConstraint(
                check=Q(vuelto__gte=0),
                name='venta_vuelto_no_negativo'
            ),
        ]


    def __str__(self):
        return f"Venta #{self.id_venta} - Comanda #{self.comanda.id_comanda}"