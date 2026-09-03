# apps/empleados/urls.py

from django.urls import path
from . import views

app_name = 'empleados'

urlpatterns = [
    path('listar/', views.empleado_listar, name='empleado_listar'),
    path('crear/', views.empleado_alta, name='empleado_alta'),
    path('detalle/<int:pk>/', views.empleado_detalle, name='empleado_detalle'),
    path('modificar/<int:pk>/', views.empleado_modificacion, name='empleado_modificacion'),
    path('baja/<int:pk>/', views.empleado_baja, name='empleado_baja'),
    path('reactivar/<int:pk>/', views.empleado_reactivar, name='empleado_reactivar'),
    path('restablecer-contrasena/<int:pk>/', views.empleado_restablecer_contrasena, name='restablecer_contrasena'),
]
