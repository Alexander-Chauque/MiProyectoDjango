from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
from .models import Empleado, Cargo
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

    def limpiar_dni(self):
        dni = self.cleaned_data.get('dni')
        if not dni.isdigit():
            raise forms.ValidationError("El DNI debe contener solo números.")
        if len(dni) < 7 or len(dni) > 8:
            raise forms.ValidationError("El DNI debe tener entre 7 y 8 dígitos.")
        if Empleado.objects.filter(dni=dni).exists():
            raise forms.ValidationError("El DNI ya está registrado.")
        return dni

    def limpiar_nombre_empleado(self):
        nombre = self.cleaned_data.get('nombre_empleado')
        if not re.match(r'^[a-zA-ZáéíóúÁÉÍÓÚñÑ\s]+$', nombre):
            raise forms.ValidationError("El nombre solo puede contener letras y espacios.")
        return nombre

    def limpiar_apellido_empleado(self):
        apellido = self.cleaned_data.get('apellido_empleado')
        if not re.match(r'^[a-zA-ZáéíóúÁÉÍÓÚñÑ\s]+$', apellido):
            raise forms.ValidationError("El apellido solo puede contener letras y espacios.")
        return apellido

    def limpiar(self):
        cleaned_data = super().clean()
        contrasena = cleaned_data.get("contrasena")
        confirmar_contrasena = cleaned_data.get("confirmar_contrasena")

        if contrasena and confirmar_contrasena and contrasena != confirmar_contrasena:
            self.add_error('confirmar_contrasena', "Las contraseñas no coinciden.")

        return cleaned_data

    def save(self, commit=True):
        empleado = super().save(commit=False)
        empleado.user_auto = empleado.generate_user_auto()
        user = User.objects.create_user(username=empleado.user_auto, password=self.cleaned_data['contrasena'])

        user.first_name = empleado.nombre_empleado
        user.last_name = empleado.apellido_empleado
        user.save()

        empleado.user = user
        empleado.debe_cambiar_contrasena = True

        if commit:
            empleado.save()
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
            empleado.user.email = empleado.correo
            empleado.user.save()

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