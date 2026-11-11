from django.contrib import admin
from .models import Notificacion, Configuracion
# Register your models here.

@admin.register(Notificacion)
class NotificacionAdmin(admin.ModelAdmin):
    list_display = ('id_notificacion', 'fecha', 'destino_perfil', 'leida')
    list_filter = ('tipo', 'leida')
    search_fields = ('mensaje', 'referencia')

@admin.register(Configuracion)
class ConfiguracionAdmin(admin.ModelAdmin):
    list_display = ('clave_configuracion', 'valor_configuracion', 'descripcion_configuracion')
    search_fields = ('clave_configuracion', 'valor_configuracion')