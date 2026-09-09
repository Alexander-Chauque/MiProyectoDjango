from django import forms
from .models import TipoBebida, Bebida

#Formulario Tipo de bebida
class TipoBebidaForm(forms.ModelForm):
    class Meta:
        model = TipoBebida
        fields = ['nombre_tipo_bebida', 'descripcion_tipo_bebida']
        widgets = {
            'nombre_tipo_bebida': forms.TextInput(attrs={'class': 'form-control'}),
            'descripcion_tipo_bebida': forms.Textarea( attrs={'class': 'form-control', 'rows': 3}),
            'estado_tipo_bebida': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }
    def clean_nombre_tipo(self):
        nombre = self.cleaned_data.get('nombre_tipo_bebida')
        if TipoBebida.objects.filter(nombre_tipo_bebida_iexat=nombre).exists():
            raise forms.ValidationError('Este tipo de bebida ya existe')
        return nombre.title()

#Form. Bebida

class BebidaForm(forms.ModelForm):
    class Meta:
        model = Bebida
        fields = ['nombre_bebida', 'descripcion_bebida', 'precio_bebida', 'id_tipo_bebida']
        widgets = {
            'nombre_bebida': forms.TextInput(attrs={'class': 'form-control'}),
            'descripcion_bebida': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'precio_bebida': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'tipo': forms.Select(attrs={'class': 'form-control'}),
            'disponible_bebida': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_nombre_bebida(self):
        nombre = self.cleaned_data.get('nombre_bebida')
        if Bebida.objects.filter(nombre_bebida__iexact=nombre).exists():
            raise forms.ValidationError('Este bebida ya existe')
        return nombre.title()

    def clean_precio_bebida(self):
        precio = self.cleaned_data.get('precio_bebida')
        if precio <= 0:
            raise forms.ValidationError('El precio debe ser mayor a 0')
        return precio