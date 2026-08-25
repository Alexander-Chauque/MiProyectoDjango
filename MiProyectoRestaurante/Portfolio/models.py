from django.db import models

# Create your models here.
class Proyecto(models.Model):
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField()
    tecnologias = models.CharField(max_length=200, default="")
    link = models.CharField(max_length=200, default="")
    imagen = models.FilePathField(path='/img')
    fecha_creacion = models.DateTimeField(auto_now_add=True)

def __str__(self):
    return self.nombre, self.descripcion, self.tecnologias, self.link, self.imagen, self.fecha_creacion