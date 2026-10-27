from django.db import models
from empleados.models import Empleado
from inventario.models import Plato, Bebida
from empleados.models import Empleado 

# Create your models here.

class Mesa(models.Model):
    UBICACIONES = [
        ('salon', 'Salón'),
        ('patio', 'Patio'),
    ]
    id_mesa = models.AutoField(primary_key=True)
    numero_mesa = models.IntegerField(unique=True, verbose_name="Número de Mesa")
    ubicacion = models.CharField(max_length=20, choices=UBICACIONES, verbose_name="Ubicación")
    estado_mesa = models.BooleanField(default=True, verbose_name="Estado")  # True: Disponible, False: Ocupada

    class Meta:
        db_table = 'mesas'
        verbose_name = 'Mesa'
        verbose_name_plural = 'Mesas'
        ordering = ['numero_mesa']

    @property
    def estado_texto(self):
        return "Disponible" if self.estado_mesa == True else "Ocupada"
    
    def __str__(self):
        estado = "Disponible" if self.estado_mesa == True else "Ocupada"
        return f"Mesa {self.numero_mesa} - ({estado}) - Ubicación: {self.get_ubicacion_display()}"

#COMANDA

class Comanda(models.Model):
    ESTADOS = [
        ('pendiente', 'Pendiente'),
        ('en_preparacion', 'En Preparación'),
        ('entregado', 'Entregado'),
        ('pagado', 'Pagado'),
        ('cancelado', 'Cancelado'),
    ]
    
    id_comanda = models.AutoField(primary_key=True)
    fecha_hora = models.DateTimeField(auto_now_add=True, verbose_name="Fecha y Hora")
    estado_comanda = models.CharField(max_length=20, choices=ESTADOS, default='pendiente', verbose_name="Estado")
    observaciones_comanda = models.TextField(blank=True, verbose_name="Observaciones")
    total_comanda = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Total")
    
    # Relaciones
    mesa = models.ForeignKey(Mesa,on_delete=models.CASCADE,
        db_column='mesa_id',
        related_name='comandas',
        verbose_name="Mesa")
    
    empleado = models.ForeignKey(Empleado,on_delete=models.CASCADE,
        db_column='empleado_id',
        related_name='comandas',
        verbose_name="Mozo"
    )
    fecha_anulacion = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de Anulación")
    motivo_anulacion = models.TextField(blank=True, verbose_name="Motivo de Anulación")
    usuario_anulacion = models.ForeignKey(Empleado, on_delete=models.SET_NULL, null=True, blank=True,
        db_column='usuario_anulacion_id',
        verbose_name="Usuario de Anulación"
    )

    class Meta:
        db_table = 'ventas_comanda'
        verbose_name = 'Comanda'
        verbose_name_plural = 'Comandas'
        ordering = ['-fecha_hora']

    def __str__(self):
        return f"Comanda #{self.id_comanda} - Mesa {self.mesa.numero_mesa}"
    
    def calcular_total(self):
        total = 0
        for detalle in self.detalles.all():
            total += detalle.subtotal
        self.total_comanda = total
        self.save()
        return total

class DetalleComanda(models.Model):
    id_detalle_com = models.AutoField(primary_key=True)
        # Relación con Comanda
    comanda = models.ForeignKey(Comanda, on_delete=models.CASCADE,
        db_column='comanda_id',
        related_name='detalles',
        verbose_name="Comanda"
    )
    
    # Relaciones opcionales (puede ser plato o bebida)
    plato = models.ForeignKey(Plato, on_delete=models.SET_NULL, null=True, blank=True,
        db_column='plato_id',
        verbose_name="Plato"
    )

    cant_plato= models.IntegerField(default=1, verbose_name="Cantidad Platos")

    bebida = models.ForeignKey(Bebida, on_delete=models.SET_NULL, null=True, blank=True,
        db_column='bebida_id',
        verbose_name="Bebida"
    )

    cant_bebida= models.IntegerField(default=1, verbose_name="Cantidad Bebida")
    
    class Meta:
        db_table = 'ventas_detallecomanda'
        verbose_name = 'Detalle de Comanda'
        verbose_name_plural = 'Detalles de Comandas'

    @property
    def subtotal_plato(self):
        """Calcula solo el subtotal del plato"""
        if self.plato and self.cant_plato:
            return self.plato.precio_plato * self.cant_plato
        return 0

    @property
    def subtotal_bebida(self):
        """Calcula solo el subtotal de la bebida"""
        if self.bebida and self.cant_bebida:
            return self.bebida.precio_bebida * self.cant_bebida
        return 0

    @property
    def subtotal(self):
            """Calcula el subtotal sumando platos Y bebidas"""
            total = 0
            # Sumar plato
            if self.plato and self.cant_plato:
                total += self.plato.precio_plato * self.cant_plato
            # Sumar bebida
            if self.bebida and self.cant_bebida:
                total += self.bebida.precio_bebida * self.cant_bebida
            return total
    
    def __str__(self):
        if self.plato:
            return f"{self.cant_plato}x {self.plato.nombre_plato}"
        elif self.bebida:
            return f"{self.cant_bebida}x {self.bebida.nombre_bebida}"
        return "Detalle vacío"
