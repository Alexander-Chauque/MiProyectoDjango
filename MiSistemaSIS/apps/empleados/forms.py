from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
from .models import Empleado, Cargo, TipoPermiso, PermisoXCargo
import re
class EmpleadoAltaForm(forms.ModelForm):

    contrasena = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}), label='Contraseña', required=True, min_length=8)
    confirmar_contrasena = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}), label='Confirmar Contraseña', required=True, min_length=8)

    class Meta:
        model = Empleado
        fields = ['nombre_empleado', 'apellido_empleado', 'dni', 'telefono', 'correo', 'cargo', 'contrasena', 'confirmar_contrasena']
        widgets = {
            'nombre_empleado': forms.TextInput(attrs={'class': 'form-control'}),
            'apellido_empleado': forms.TextInput(attrs={'class': 'form-control'}),
            'dni': forms.TextInput(attrs={'class': 'form-control'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control'}),
            'correo': forms.EmailInput(attrs={'class': 'form-control'}),
            'cargo': forms.Select(attrs={'class': 'form-control'}),
        }

    def clean_dni(self):
        dni = self.cleaned_data.get('dni')
        if not dni.isdigit():
            raise forms.ValidationError("El DNI debe contener solo números.")
        if len(dni) < 7 or len(dni) > 8:
            raise forms.ValidationError("El DNI debe tener entre 7 y 8 dígitos.")
        if Empleado.objects.filter(dni=dni).exists():
            raise forms.ValidationError("El DNI ya está registrado.")
        return dni

    def clean_nombre_empleado(self):
        nombre = self.cleaned_data.get('nombre_empleado')
        if not re.match(r'^[a-zA-ZáéíóúÁÉÍÓÚñÑ\s]+$', nombre):
            raise forms.ValidationError("El nombre solo puede contener letras y espacios.")
        return nombre

    def clean_apellido_empleado(self):
        apellido = self.cleaned_data.get('apellido_empleado')
        if not re.match(r'^[a-zA-ZáéíóúÁÉÍÓÚñÑ\s]+$', apellido):
            raise forms.ValidationError("El apellido solo puede contener letras y espacios.")
        return apellido

    def clean_contrasenas(self):
        cleaned_data = super().clean()
        contrasena = cleaned_data.get("contrasena")
        confirmar_contrasena = cleaned_data.get("confirmar_contrasena")

        if contrasena and confirmar_contrasena and contrasena != confirmar_contrasena:
            self.add_error('confirmar_contrasena', "Las contraseñas no coinciden.")

        return cleaned_data
#guardar el empleado y crear el usuario asociado
    def save(self, commit=True):
        empleado = super().save(commit=False) #no guardar aún el empleado
        empleado.user_auto = empleado.generate_user_auto()
        user = User.objects.create_user(username=empleado.user_auto, password=self.cleaned_data['contrasena'])

        user.first_name = empleado.nombre_empleado
        user.last_name = empleado.apellido_empleado
        user.save()
    #registrar el usuario en el empleado
        empleado.user = user
        empleado.debe_cambiar_contrasena = True

        if commit: #recien guardar el empleado si commit es True
            empleado.save()
        self.usuario_generado = empleado.user_auto
        return empleado

class EmpleadoModificacionForm(forms.ModelForm):
    class Meta:
        model = Empleado
        fields = ['correo']
        widgets = {
            'correo':forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'correo@ejemplo.com'}),
            }

    def clean_correo(self):
        correo =self.cleaned_data.get('correo')
        if Empleado.objects.filter(correo=correo).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Este correo ya está registrado.")
        return correo

    def save(self, commit=True):
        empleado =super().save(commit=False)
        if commit:
            empleado.save()
            if empleado.user:
                empleado.user.email = empleado.correo
                empleado.user.save()
        return empleado

class RestablecerContrasenaForm(forms.Form):
    nueva_contrasena = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}), label='Nueva Contraseña', required=True, min_length=8)
    confirmar_contrasena = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}), label='Confirmar Contraseña', required=True, min_length=8)

    def clean(self):
        cleaned_data = super().clean()
        nueva = cleaned_data.get('nueva_contrasena')
        confirmar = cleaned_data.get('confirmar_contrasena')

        if nueva and confirmar and nueva != confirmar:
            raise forms.ValidationError('La contraseña y la confirmación no coinciden')

        return cleaned_data


#CARGOS
class CargoForm(forms.ModelForm):
    class Meta:
        model = Cargo
        fields = ['nombre_cargo', 'descripcion_cargo', 'nivel_acceso']
        widgets = {
            'nombre_cargo': forms.TextInput(attrs={'class': 'form-control'}),
            'descripcion_cargo': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'nivel_acceso': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 5}),
        }
    
    def clean_nombre_cargo(self):
        nombre = self.cleaned_data.get('nombre_cargo')
        
        # Buscar cargos con el mismo nombre, excluyendo el actual si estamos editando
        cargos_existentes = Cargo.objects.filter(nombre_cargo__iexact=nombre)
        if self.instance and self.instance.pk:
            cargos_existentes = cargos_existentes.exclude(pk=self.instance.pk)
        
        if cargos_existentes.exists():
            raise forms.ValidationError('Este cargo ya existe')
        
        return nombre.title()

    NIVELES_ACCESO = [
        (1, '1 - Básico (Solo lectura)'),
        (2, '2 - Operador (Lectura y creación)'),
        (3, '3 - Supervisor (Lectura, creación y modificación)'),
        (4, '4 - Gerente (Todos excepto eliminar)'),
        (5, '5 - Administrador (Todos los permisos)'),
    ]

    nivel_acceso = forms.ChoiceField(
        choices=NIVELES_ACCESO,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Nivel de Acceso'
    )
#PERMISO X CARGO
class PermisoXCargoForm(forms.ModelForm):
    class Meta:
        model = PermisoXCargo
        fields = ['cargo', 'tipo_permiso']
        widgets = {
            'cargo': forms.Select(attrs={'class': 'form-control'}),
            'tipo_permiso': forms.Select(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['cargo'].empty_label = "Seleccione un cargo"
        self.fields['tipo_permiso'].empty_label = "Seleccione un permiso"

# FORMULARIO PARA ASIGNAR PERMISOS A UN CARGO (Múltiple)
class AsignarPermisosCargoForm(forms.Form):
    cargo = forms.ModelChoiceField(
        queryset=Cargo.objects.all().order_by('nombre_cargo'),
        widget=forms.Select(attrs={'class': 'form-control'}),
        label="Cargo"
    )
    permisos = forms.ModelMultipleChoiceField(
        queryset=TipoPermiso.objects.all().order_by('modulo', 'accion'),
        widget=forms.SelectMultiple(attrs={'class': 'form-control', 'size': 10}),
        label="Permisos",
        required=False
    )

