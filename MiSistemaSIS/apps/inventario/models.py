from django.db import models

# Create your models here.
#Categoria Plato
class CategoriaPlato(models.Model):
    nombre_categoria_plato = models.CharField(max_length=100, unique=True)
    descripcion_categoria_plato = models.TextField(default='', blank=True)
    estado_categoria_plato = models.BooleanField(default=True)
    def save(self, *args, **kwargs):
        if self.nombre_categoria_plato:
            self.nombre=self.nombre_categoria_plato.title()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre_categoria_plato

#Ingrediente
class Ingrediente(models.Model):
    nombre_ingrediente = models.CharField(max_length=100)
    unidad_medida = models.CharField(max_length=50, choices=[
        ("kg", 'Kilogramo'), ('g', 'Gramos'), ('l', 'Litros'), ('ml', 'mililitros'), ('u', 'Unidades'),
    ])
    costo_unitario = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    estado_ingrediente = models.BooleanField(default=True)
    def save(self, *args, **kwargs):
            if self.nombre_ingrediente:
                self.nombre_ingrediente=self.nombre_ingrediente.title()
            super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre_ingrediente

#Plato
class Plato(models.Model):
    nombre_plato = models.CharField(max_length=100)
    precio_plato = models.DecimalField(max_digits=10, decimal_places=2)
    categoria = models.ForeignKey(CategoriaPlato, on_delete=models.CASCADE)
    
    ingredientes = models.ManyToManyField(Ingrediente, through='DetallePlato')
    descripcion_plato = models.TextField(default="", blank=True)
    estado_plato = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
            if self.nombre_plato:
                self.nombre_plato=self.nombre_plato.title()
            super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.nombre_plato} - ${self.precio_plato}"

#DetallePlato
class DetallePlato(models.Model):
    plato = models.ForeignKey(Plato, on_delete=models.CASCADE)
    ingrediente = models.ForeignKey(Ingrediente, on_delete=models.CASCADE)
    cantidad = models.IntegerField(default=1)

#Tipo de bebidas
class TipoBebida(models.Model):
    nombre_tipo_bebida = models.CharField(max_length=50)
    descripcion_tipo_bebida=models.TextField(blank=True)
    estado_tipo_bebida = models.BooleanField(default=True)

    class Meta:
        db_table='inventario_tipobebida'

    def save(self, *args, **kwargs):
        if self.nombre_tipo_bebida:
            self.nombre_tipo_bebida=self.nombre_tipo_bebida.title()
        super().save(*args, **kwargs)
    def __str__(self):
        return f"{self.nombre_tipo_bebida}"

#Bebidas
class Bebida(models.Model):
    nombre_bebida = models.CharField(max_length=50, unique= True)
    id_tipo_bebida = models.ForeignKey(TipoBebida, on_delete=models.CASCADE,db_column='tipo_id')
    precio_bebida = models.DecimalField(max_digits=10, decimal_places=2)
    descripcion_bebida = models.TextField(blank=True)
    disponible_bebida = models.BooleanField(default=True)

    class Meta:
        db_table='inventario_bebida'

    def save(self, *args, **kwargs):
            if self.nombre_bebida:
                self.nombre_bebida=self.nombre_bebida.title()
            super().save(*args, **kwargs)
    def __str__(self):
        return f'{self.nombre_bebida} - ${self.precio_bebida}'

#Mesa
class Mesa(models.Model):
    numero_mesa = models.IntegerField(unique=True)
    capacidad = models.IntegerField()
    estado_mewasdo = models.CharField(max_length=20, choices=[
        ('disponible', 'Disponible'), ('ocupada', 'Ocupada'), ('reservada', 'Reservada')
    ], default='disponible')

    def __str__(self):
        return f"Mesa {self.numero_mesa}"