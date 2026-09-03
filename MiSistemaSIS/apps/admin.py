from django.contrib import admin
from apps.models import Categoria, Ingrediente, Plato, DetallePlato

@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'descripcion')
    list_filter = ('nombre',)
    search_fields = ('nombre', 'descripcion')
    pass

@admin.register(Ingrediente)
class IngredienteAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'unidad_medida', 'costo_unitario')
    list_filter = ('unidad_medida',)
    search_fields = ('nombre',)
    pass
class DetallePlatoInline(admin.TabularInline):
    model = DetallePlato
    extra = 1  

@admin.register(Plato)
class PlatoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'precio', 'categoria')
    list_filter = ('categoria',)
    search_fields = ('nombre', 'precio')
    fields = ('nombre', 'precio', 'categoria')  
    inlines = [DetallePlatoInline]  


