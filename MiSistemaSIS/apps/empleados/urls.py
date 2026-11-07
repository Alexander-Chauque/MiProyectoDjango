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

    # ===== CUENTA DEL USUARIO =====
    path('mi-perfil/', views.mi_perfil, name='mi_perfil'),
    path('cambiar-contrasena/', views.cambiar_contrasena, name='cambiar_contrasena'),
    path('mis-permisos/', views.mis_permisos, name='mis_permisos'),

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

    path('asistencias/', views.listar_asistencias, name='listar_asistencias'),
    path('asistencias/editar/<int:pk>/', views.editar_asistencia, name='editar_asistencia'),
    path('asistencias/anular/<int:pk>/', views.anular_asistencia, name='anular_asistencia'),

    
        # CRUD Tipos de Asistencia
    path('tipos-asistencia/', views.listar_tipos_asistencia, name='listar_tipos_asistencia'),
    path('tipos-asistencia/crear/', views.crear_tipo_asistencia, name='crear_tipo_asistencia'),
    path('tipos-asistencia/editar/<int:pk>/', views.editar_tipo_asistencia, name='editar_tipo_asistencia'),
    path('tipos-asistencia/eliminar/<int:pk>/', views.eliminar_tipo_asistencia, name='eliminar_tipo_asistencia'),
    
]
