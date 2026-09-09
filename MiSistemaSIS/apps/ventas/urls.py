from django.urls import path
from . import views

app_name = 'ventas'

urlpatterns = [
    path('', views.mesa_listar, name='listar_mesa'),
    path('crear/', views.mesa_crear, name='crear_mesa'),
    path('editar/<int:pk>/', views.mesa_editar, name='editar_mesa'),
    path('eliminar/<int:pk>/', views.mesa_eliminar, name='eliminar_mesa'),
    path('estado/<int:pk>/', views.mesa_estado, name='estado_mesa'),
]