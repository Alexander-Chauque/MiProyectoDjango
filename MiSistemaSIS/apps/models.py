from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal

# Create your models here.

#USUARIO GESTION
#Cargo
class Cargo(models.Model):
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True)
    def __str__(self):
        return self.nombre

#Empleado
class Empleado(models.Model):
    nombre = models.CharField(max_length=100)
    apellido = models.CharField ( max_length=100)
    dni = models.CharField(max_length=100)
    telefono = models.CharField(max_length=20, blank=True)
    email = models.EmailField(max_length=80, blank=True)
    fecha_ingreso = models.DateField (auto_now_add=True)
    estado =models.BooleanField(default=True)
    cargo = models.ForeignKey(Cargo, on_delete=models.CASCADE)
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    def __str__(self):
        return self.nombre
    @property
    def usernombre(self):
        return self.user.username if self.user else None

#Tipo permiso
class TipoPermiso(models.Model):
    cargo = models.ForeignKey(Cargo, on_delete=models.CASCADE)
    modulo = models.CharField(max_length=50)
    accion = models.CharField( max_length=50, choices=[
        ('leer', 'Leer'), ('escribir', 'Escribir'), ('modificar', 'Modificar'), ('eliminar', 'Eliminar')
    ])

    def __str__(self):
        return f'{self.cargo.nombre} - {self.modulo} - {self.accion}'

    