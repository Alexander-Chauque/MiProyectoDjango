from django.contrib import admin
from Blog.models import Categoria, Ingrediente, Plato, DetallePlato

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

@admin.register(Plato)
class PlatoAdmin(admin.ModelAdmin):
    list_display = ('nombre', "precio")
    list_filter = ('categoria',)
    search_fields = ('nombre',"precio")
    list_per_page = 10

