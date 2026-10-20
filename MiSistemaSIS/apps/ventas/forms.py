from django import forms
from .models import Comanda, DetalleComanda, Mesa
from empleados.models import Empleado
from inventario.models import Plato, Bebida
from django.db.models import Q
class MesaForm(forms.ModelForm):
    class Meta:
        model = Mesa
        fields = ['numero_mesa', 'ubicacion', 'estado_mesa']
        widgets = {
            'numero_mesa': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'ubicacion': forms.Select(attrs={'class': 'form-control'}),
            'estado_mesa': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

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

    def clean_mesa(self):
        mesa = self.cleaned_data.get('mesa')

        if self.instance and self.instance.pk:
            return mesa  # No validar si estamos editando la comanda existente
        
        comandas_existentes = Comanda.objects.filter(mesa=mesa, estado_comanda__in=['pendiente', 'en_preparacion'])
        if comandas_existentes.exists():
            raise forms.ValidationError('Esta mesa ya tiene una comanda en curso')
        return mesa

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['mesa'].empty_label = "Seleccione una mesa"
        
        if self.instance and self.instance.pk:
            # Editar: mesa actual + disponibles
            self.fields['mesa'].queryset = Mesa.objects.filter(
                Q(estado_mesa=True) | Q(id_mesa=self.instance.mesa.id_mesa)
            ).order_by('numero_mesa')
        else:
            # Crear: solo disponibles
            self.fields['mesa'].queryset = Mesa.objects.filter(
                estado_mesa=True
            ).order_by('numero_mesa')

class DetalleComandaForm(forms.ModelForm):
    class Meta:
        model = DetalleComanda
        fields = [ 'plato', 'cant_plato', 'bebida', 'cant_bebida'] 
        widgets = {
            'plato': forms.Select(attrs={'class': 'form-control'}),
            'cant_plato': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'value': 0}),
            'bebida': forms.Select(attrs={'class': 'form-control'}),
            'cant_bebida': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'value': 0}),
        }
    def clean(self):
        cleaned_data = super().clean()
        plato = cleaned_data.get('plato')
        bebida = cleaned_data.get('bebida')
        cant_plato = cleaned_data.get('cant_plato') or 0
        cant_bebida = cleaned_data.get('cant_bebida') or 0
        
        if plato and bebida:
            raise forms.ValidationError('Seleccione un plato O una bebida, no ambos.')
        if plato and cant_plato <= 0:
            raise forms.ValidationError('Si selecciona un plato, la cantidad debe ser mayor a 0.')
        if bebida and cant_bebida <= 0:
            raise forms.ValidationError('Si selecciona una bebida, la cantidad debe ser mayor a 0.')
        if not plato and not bebida and (cant_plato > 0 or cant_bebida > 0):
            raise forms.ValidationError('Debe seleccionar un plato o una bebida.')
    
        return cleaned_data
    
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