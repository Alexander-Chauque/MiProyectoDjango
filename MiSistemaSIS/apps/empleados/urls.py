from django.urls import path
from . import views

app_name = 'empleados'

urlpatterns = [
    path('', views.empleados_home, name='empleados_home'),
    path('listar/', views.empleado_listar, name='empleado_listar'),
    path('crear/', views.empleado_alta, name='empleado_alta'),
    path('detalle/<int:pk>/', views.empleado_detalle, name='empleado_detalle'),
    path('modificar/<int:pk>/', views.empleado_modificacion, name='empleado_modificacion'),
    path('baja/<int:pk>/', views.empleado_baja, name='empleado_baja'),
    path('reactivar/<int:pk>/', views.empleado_reactivar, name='empleado_reactivar'),
    path('restablecer-contrasena/<int:pk>/', views.empleado_restablecer_contrasena, name='restablecer_contrasena'),
    path('cambiar_clave_obligatorio', views.cambiar_clave_obligatorio, name='cambiar_clave_obligatorio'),

    # ===== CARGOS =====
    path('cargos/', views.cargo_listar, name='listar_cargo'),
    path('cargos/crear/', views.cargo_crear, name='crear_cargo'),
    path('cargos/editar/<int:pk>/', views.cargo_editar, name='editar_cargo'),
    path('cargos/eliminar/<int:pk>/', views.cargo_eliminar, name='eliminar_cargo'),
    
    # ===== PERMISOS =====
    path('permisos/', views.permiso_listar, name='listar_permiso'),
    path('permisos/crear/', views.permiso_crear, name='crear_permiso'),
    path('permisos/eliminar/<int:pk>/', views.permiso_eliminar, name='eliminar_permiso'),
    
    # ===== ASIGNAR PERMISOS A CARGOS =====
    path('asignar-permisos/', views.asignar_permisos, name='asignar_permisos'),
    path('ver-permisos/<int:pk>/', views.ver_permisos_cargo, name='ver_permisos_cargo'),

]
