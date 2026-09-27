from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.contrib.auth.hashers import make_password

# Create your models here.
#USUARIO GESTION
#Cargo
class Cargo(models.Model):
    nombre_cargo = models.CharField(max_length=100, unique=True)
    descripcion_cargo = models.TextField(blank=True)
    nivel_acceso = models.BigIntegerField(default=1)
    def __str__(self):
        return self.nombre_cargo

    def save(self, *args, **kwargs):
        if self.nombre_cargo:
            self.nombre_cargo=self.nombre_cargo.title()
        super().save(*args, **kwargs)

#Empleado
class Empleado(models.Model):
    nombre_empleado = models.CharField(max_length=100)
    apellido_empleado = models.CharField ( max_length=100)
    dni = models.CharField(max_length=100, unique=True)
    telefono = models.CharField(max_length=20, blank=True, unique=True)
    correo = models.EmailField(max_length=80, blank=True)
    user_auto = models.CharField(max_length=100, unique=True, blank=True)

    fecha_ingreso = models.DateField (auto_now_add=True)
    fecha_ultima_modificacion = models.DateTimeField(auto_now=True)
    fecha_baja = models.DateField(null=True, blank=True)

    estado =models.BooleanField(default=True)

    debe_cambiar_contrasena = models.BooleanField(default=False)

    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    cargo = models.ForeignKey(Cargo, on_delete=models.CASCADE, null=True, blank=True)


    def __str__(self):
        return f"{self.nombre_empleado} - {self.apellido_empleado} - {self.user_auto}"

    def generate_user_auto(self):
        if self.nombre_empleado and self.apellido_empleado:
            nombre = self.nombre_empleado.lower().strip()
            apellido = self.apellido_empleado.lower().strip()
            primera_letra = nombre[0] if nombre else ''
            
            # Base del usuario: apellido + primera letra del nombre
            base = f"{apellido}{primera_letra}"
            
            # Verificar si ya existe y agregar número si es necesario
            user_auto = base
            contador = 1
            while Empleado.objects.filter(user_auto=user_auto).exists():
                user_auto = f"{base}{contador}"
                contador += 1
            
            return user_auto
        return None

    def dar_baja(self):
        self.estado = False
        self.fecha_baja = timezone.now().date()
        if self.user:
            self.user.is_active = False
            self.user.save()
        self.save()

    def reactivar(self):
        self.estado = True
        self.fecha_baja = None
        if self.user:
            self.user.is_active = True
            self.user.save()
        self.save()

    def cambiar_contrasena(self, nueva_contrasena):
        if self.user:
            self.user.password = make_password(nueva_contrasena)
            self.debe_cambiar_contrasena = True
            self.user.save()
        self.save()

    def get_full_name(self):
        return f"{self.nombre_empleado} {self.apellido_empleado}"
    
#Tipo permiso
class TipoPermiso(models.Model):
    modulo = models.CharField(max_length=50, choices=[
        ('platos', 'Platos'),
        ('bebidas', 'Bebidas'),
        ('ingredientes', 'Ingredientes'),
        ('categorias', 'Categorías'),
        ('empleados', 'Empleados'),
        ('cargos', 'Cargos'),
        ('comandas', 'Comandas'),
        ('mesas', 'Mesas'),
        ('ventas', 'Ventas'),
        ('caja', 'Caja'),
        ('gastos', 'Gastos'),
        ('reportes', 'Reportes'),
    ])
    accion = models.CharField( max_length=50, choices=[
        ('leer', 'Leer'), ('escribir', 'Escribir'), ('modificar', 'Modificar'), ('eliminar', 'Eliminar')
    ])

    class Meta:
        unique_together = ['modulo', 'accion']

    def __str__(self):
        return f'({self.modulo} - {self.accion})'

class PermisoXCargo(models.Model):
    cargo = models.ForeignKey(Cargo, on_delete=models.CASCADE)
    tipo_permiso = models.ForeignKey(TipoPermiso, on_delete=models.CASCADE)
    fecha_asignacion = models.DateTimeField(auto_now_add=True, blank=True)

    class Meta:
        unique_together = ['cargo', 'tipo_permiso']

    def __str__(self):
        return f'{self.cargo.nombre_cargo} - ({self.tipo_permiso.modulo} - {self.tipo_permiso.accion})'

#Tipo asistencia
class TipoAsistencia(models.Model):
    nombre = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.nombre

#Asistencia
class Asistencia(models.Model):
    empleado=models.ForeignKey(Empleado, on_delete=models.CASCADE)
    tipo_asistencia=models.ForeignKey(TipoAsistencia, on_delete=models.CASCADE)
    fecha_asistencia=models.DateField()

