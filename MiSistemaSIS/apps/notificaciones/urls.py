from django.urls import path
from . import views

app_name = 'notificaciones'

urlpatterns = [
    path('', views.bandeja_notificaciones, name='bandeja'),
    path('<int:id_notificacion>/leida/', views.marcar_como_leida, name="marcar_leida"),
    path('marcar-todas/', views.marcar_todas_como_leidas, name="marcar_todas"),
    
]