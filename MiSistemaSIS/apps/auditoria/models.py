from django.db import models

# Create your models here.

from django.db import models
from django.contrib.auth.models import User
from empleados.models import Empleado 
class LogAuditoria(models.Model):
    ACCIONES = (
        ("CREAR", "Crear"),
        ("MODIFICAR", "Modificar"),
        ("ANULAR", "Anular"),
    )

    id_log = models.AutoField(primary_key=True)
    tabla = models.CharField(max_length=50)
    accion = models.CharField(max_length=20, choices=ACCIONES)
    registro_id = models.IntegerField()
    valores_anteriores = models.TextField(blank=True, null=True)
    valores_actuales = models.TextField(blank=True, null=True)
    fecha_hora = models.DateTimeField(auto_now_add=True)

    # Relación con Empleado en lugar de User
    empleado = models.ForeignKey(
        Empleado, on_delete=models.SET_NULL, null=True, blank=True
    )

    def __str__(self):
        fecha = self.fecha_hora.strftime("%d/%m/%Y %H:%M")
        nombre = self.empleado.nombre_empleado if self.empleado else "Sistema"
        return f"{self.accion} - {self.tabla} #{self.registro_id} ({fecha}) - {nombre}"
