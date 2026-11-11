from django.db import models
from empleados.models import Cargo
# Create your models here.
TIPOS = [
        ("VENTA_INUSUAL", "Venta inusual"),
        ("COMANDA_DEMORADA", "Comanda demorada"),
        ("CAJA_ABIERTA", "Caja abierta demasiado tiempo"),
    ]

class Notificacion(models.Model):
  id_notificacion = models.AutoField(primary_key=True)
  fecha = models.DateTimeField(auto_now_add=True)
  tipo = models.CharField(max_length=50, choices=TIPOS)
  fecha_lectura = models.DateTimeField(null=True, blank=True)
  mensaje = models.TextField()
  destino_perfil = models.ForeignKey(Cargo, on_delete=models.SET_NULL, null=True, blank=True)
  leida = models.BooleanField(default=False)
  referencia = models.CharField(max_length=100, null=True, blank=True, unique=True)  
  
  class Meta:
    db_table = 'notificacion'
    verbose_name = 'Notificación'
    verbose_name_plural = 'Notificaciones'
    ordering = ['-fecha']
    
  def __str__(self):
    return f"{self.get_tipo_display()} - {self.fecha} - {self.mensaje[:30]}..." 

class Configuracion(models.Model):
  clave_configuracion = models.CharField(max_length=100, unique=True)    
  valor_configuracion = models.CharField(max_length=100)
  descripcion_configuracion = models.TextField(null=True, blank=True)  
  
  class Meta:
    db_table = 'configuracion'
    verbose_name = 'Configuración'
    verbose_name_plural = 'Configuraciones'

  def __str__(self):
    return f"{self.clave_configuracion} - {self.valor_configuracion}"