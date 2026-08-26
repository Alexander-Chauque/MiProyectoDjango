from django.db import models


# Create your models here.

class Categoria(models.Model):
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(default='', blank=True)

    def __str__(self):
        return self.nombre

class Ingrediente(models.Model):
    nombre = models.CharField(max_length=100)
    unidad_medida = models.CharField(max_length=50, default='unidad')  # Ejemplo: gramos, litros, unidades
    costo_unitario = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def __str__(self):
        return self.nombre

class Plato(models.Model):
    nombre = models.CharField(max_length=100)
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    categoria = models.ForeignKey(Categoria, on_delete=models.CASCADE)
    # Django crea automáticamente la tabla intermedia (tu DETALLE_PLATOS)
    ingredientes = models.ManyToManyField(Ingrediente, through='DetallePlato')

    def __str__(self):
        return f"{self.nombre} - ${self.precio}"

class DetallePlato(models.Model):
    plato = models.ForeignKey(Plato, on_delete=models.CASCADE)
    ingrediente = models.ForeignKey(Ingrediente, on_delete=models.CASCADE)
    cantidad = models.IntegerField(default=1)


