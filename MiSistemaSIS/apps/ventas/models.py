from django.db import models

# Create your models here.

class Mesa(models.Model):
    id_mesa = models.AutoField(primary_key=True)
    capacidad = models.IntegerField(verbose_name="Capacidad")
    numero_mesa = models.IntegerField(unique=True, verbose_name="Número de Mesa")
    estado_mesa = models.BooleanField(default=True, verbose_name="Estado")
    
    class Meta:
        db_table = 'mesas'
        verbose_name = 'Mesa'
        verbose_name_plural = 'Mesas'
        ordering = ['numero_mesa']
    
    def __str__(self):
        estado = "Activa" if self.estado_mesa else "Inactiva"
        return f"Mesa {self.numero_mesa} - {estado}"