from django import forms
from .models import Comanda, DetalleComanda, Mesa
from empleados.models import Empleado
from inventario.models import Plato, Bebida
from django.db.models import Q
class MesaForm(forms.ModelForm):
    class Meta:
        model = Mesa
        fields = ['numero_mesa', 'capacidad', 'estado_mesa']
        widgets = {
            'numero_mesa': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'capacidad': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'estado_mesa': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def clean_numero_mesa(self):
        numero = self.cleaned_data.get('numero_mesa')
        mesas_existentes = Mesa.objects.filter(numero_mesa=numero)
        if self.instance and self.instance.pk:
            mesas_existentes = mesas_existentes.exclude(pk=self.instance.pk)
        if mesas_existentes.exists():
            raise forms.ValidationError('Este número de mesa ya existe')
        return numero

#COMANDA
class EmpleadoChoiceField(forms.ModelChoiceField):
    """Campo que muestra solo el nombre del empleado"""
    def label_from_instance(self, obj):
        return f"{obj.nombre_empleado} {obj.apellido_empleado}"
    
class ComandaForm(forms.ModelForm):
    class Meta:
        model = Comanda
        fields = ['mesa', 'observaciones_comanda']
        widgets = {
            'mesa': forms.Select(attrs={'class': 'form-control'}),
            'observaciones_comanda': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 3,
                'placeholder': 'Ej: sin cebolla, bien cocida...'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['mesa'].empty_label = "Seleccione una mesa"
        
        # Si estamos editando, mostrar la mesa actual + las disponibles
        if self.instance and self.instance.pk:
            self.fields['mesa'].queryset = Mesa.objects.filter(
                Q(estado_mesa=True) | Q(id_mesa=self.instance.mesa.id_mesa)
            ).order_by('numero_mesa')
        else:
            self.fields['mesa'].queryset = Mesa.objects.filter(estado_mesa=True).order_by('numero_mesa')

class DetalleComandaForm(forms.ModelForm):
    class Meta:
        model = DetalleComanda#
        fields = ['plato', 'cant_plato', 'bebida', 'cant_bebida'] 
        widgets = {
            'plato': forms.Select(attrs={'class': 'form-control'}),
            'cant_plato': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'value': 0}),
            'bebida': forms.Select(attrs={'class': 'form-control'}),
            'cant_bebida': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'value': 0}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['plato'].queryset = Plato.objects.filter(estado_plato=True)
        self.fields['bebida'].queryset = Bebida.objects.filter(disponible_bebida=True)
        self.fields['plato'].empty_label = "Seleccione un plato"
        self.fields['bebida'].empty_label = "Seleccione una bebida"
        self.fields['plato'].required = False
        self.fields['bebida'].required = False
        self.fields['cant_plato'].required = False
        self.fields['cant_bebida'].required = False