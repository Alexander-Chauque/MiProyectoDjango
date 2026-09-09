from django import forms
from .models import Mesa

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
        if Mesa.objects.filter(numero_mesa=numero).exists():
            raise forms.ValidationError('Este número de mesa ya existe')
        return numero