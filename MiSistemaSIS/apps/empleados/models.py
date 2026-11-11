from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.contrib.auth.hashers import make_password

# Create your models here.
#USUARIO GESTION
#Cargo
class Cargo(models.Model):
    id_cargo = models.BigAutoField(primary_key=True)
    nombre_cargo = models.CharField(max_length=100, unique=True)
    descripcion_cargo = models.TextField(blank=True)
    nivel_acceso = models.BigIntegerField(default=1)
    sueldo_cargo = models.DecimalField(max_digits=10, decimal_places=2, default=0.00) 
    def __str__(self):
        return self.nombre_cargo

    def save(self, *args, **kwargs):
        if self.nombre_cargo:
            self.nombre_cargo=self.nombre_cargo.title()
        super().save(*args, **kwargs)

#Empleado
class Empleado(models.Model):
    id_empleado = models.AutoField(primary_key=True)
    nombre_empleado = models.CharField(max_length=100)
    apellido_empleado = models.CharField ( max_length=100)
    dni = models.CharField(max_length=10, unique=True)
    telefono = models.CharField(max_length=20, blank=True, null= True)
    correo = models.EmailField(max_length=80, blank=True, unique=True)
    user_auto = models.CharField(max_length=100, unique=True, blank=True)

    fecha_ingreso = models.DateField (auto_now_add=True)
    fecha_ultima_modificacion = models.DateTimeField(auto_now=True)
    fecha_baja = models.DateField(null=True, blank=True)

    estado =models.BooleanField(default=True)

    debe_cambiar_contrasena = models.BooleanField(default=False)

    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    cargo = models.ForeignKey(Cargo, on_delete=models.PROTECT, null=True, blank=True)


    def __str__(self):
        return f"{self.nombre_empleado} - {self.apellido_empleado} - {self.user_auto}"
      

    def save(self, *args, **kwargs):
        if self.nombre_empleado:
            self.nombre_empleado = self.nombre_empleado.title()
        if self.apellido_empleado:
            self.apellido_empleado = self.apellido_empleado.title()
        
        if not self.pk:
            self.user_auto = self.generate_user_auto()
        else:
            original = Empleado.objects.get(pk=self.pk)
            if (original.nombre_empleado != self.nombre_empleado or 
                original.apellido_empleado != self.apellido_empleado):
                
                self.user_auto = self.generate_user_auto()
                if self.user:
                    self.user.username = self.user_auto
                    self.user.first_name = self.nombre_empleado
                    self.user.last_name = self.apellido_empleado
                    self.user.save()
        super().save(*args, **kwargs)

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
            qs = Empleado.objects.filter(user_auto=user_auto)
            if self.pk:
              qs = qs.exclude(pk=self.pk)
              
            while qs.exists():
                user_auto = f"{base}{contador}"
                contador += 1
                qs = Empleado.objects.filter(user_auto=user_auto)
                if self.pk:
                  qs = qs.exclude(pk=self.pk)
            
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
    id_tipo_permiso = models.AutoField(primary_key=True)
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
        ('auditoria', 'Auditoría'),
    ])
    accion = models.CharField( max_length=50, choices=[
        ('leer', 'Leer'), ('escribir', 'Escribir'), ('modificar', 'Modificar'), ('eliminar', 'Eliminar')
    ])
    descripcio_permiso = models.TextField(blank=True, null=True)

    class Meta:
        unique_together = ['modulo', 'accion']

    def __str__(self):
        return f'({self.modulo} - {self.accion})'

class PermisoXCargo(models.Model):
    id_permiso_x_cargo = models.AutoField(primary_key=True)
    cargo = models.ForeignKey(Cargo, on_delete=models.CASCADE)
    tipo_permiso = models.ForeignKey(TipoPermiso, on_delete=models.CASCADE)
    fecha_asignacion = models.DateTimeField(auto_now_add=True, blank=True)

    class Meta:
        unique_together = ['cargo', 'tipo_permiso']

    def __str__(self):
        return f'{self.cargo.nombre_cargo} - ({self.tipo_permiso.modulo} - {self.tipo_permiso.accion})'

#Tipo asistencia
class TipoAsistencia(models.Model):
  TIPOS =[
    ('completo', 'Turno Completo'),
    ('medio', 'Turno Medio'),
  ]
  id_tipo_asistencia = models.AutoField(primary_key=True)
  nombre_tipo_asis = models.CharField(max_length=50, choices=TIPOS, unique=True)
  desc_tipo_asistencia = models.TextField(blank=True)

  def __str__(self):
    return self.get_nombre_tipo_asis_display()
#Asistencia
class Asistencia(models.Model):
    id_asistencia = models.AutoField(primary_key=True)
    id_empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE, db_column='id_empleado')
    id_tipo_asistencia = models.ForeignKey(TipoAsistencia, on_delete=models.CASCADE, db_column='id_tipo_asistencia')
    fecha_asistencia = models.DateField()

    def __str__(self):
        return f"{self.id_empleado} - {self.fecha_asistencia}"

