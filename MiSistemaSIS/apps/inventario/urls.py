from django.urls import path
from . import views
app_name = 'inventario'

urlpatterns = [
        path('platos/listar/', views.listar_platos, name='listar_platos'),
        path('platos/crear/', views.crear_plato, name='crear_plato'),
        path('platos/editar/<int:pk>/', views.editar_plato, name='editar_plato'),
        path('platos/eliminar/<int:pk>/', views.eliminar_plato, name='eliminar_plato'),
        path('platos/detalle/<int:pk>/', views.detalle_plato, name='detalle_plato'),
        path('plato/estado/<int:pk>/', views.estado_plato, name="estado_plato"),
    
    
    #rutas para listar, crear, editar y eliminar ingredientes
        path('ingredientes/', views.listar_ingredientes, name='listar_ingredientes'),
        path('ingredientes/crear/', views.crear_ingrediente, name='crear_ingrediente'),
        path('ingredientes/editar/<int:pk>/', views.editar_ingrediente, name='editar_ingrediente'),
        path('ingredientes/eliminar/<int:pk>/', views.eliminar_ingrediente, name='eliminar_ingrediente'),
        path('ingredientes/detalle/<int:pk>/', views.detalle_ingrediente, name='detalle_ingrediente'),
        path('ingredientes/estado/<int:pk>/', views.estado_ingrediente, name="estado_ingrediente"),
    #rutas para listar, crear, editar y eliminar categorias
        path('categorias/', views.listar_categorias, name='listar_categorias'),
        path('categorias/crear/', views.crear_categoria, name='crear_categoria'),
        path('categorias/editar/<int:pk>/', views.editar_categoria, name='editar_categoria'),
        path('categorias/eliminar/<int:pk>/', views.eliminar_categoria, name='eliminar_categoria'),
        path('categorias/detalle/<int:pk>/', views.detalle_categoria, name='detalle_categoria'),
        path('categorias/estado/<int:pk>/', views.estado_categoria, name='estado_categoria'),

    #TIPOS BEBIDAS
    path('tipos-bebida/', views.listar_tipo_bebida, name='listar_tipo_bebida'),
    path('tipos-bebida/crear/', views.crear_tipo_bebida, name='crear_tipo_bebida'),
    path('tipos-bebida/editar/<int:pk>/', views.editar_tipo_bebida, name='editar_tipo_bebida'),
    path('tipos-bebida/eliminar/<int:pk>/', views.eliminar_tipo_bebida, name='eliminar_tipo_bebida'),
    path('tipos-bebida/estado/<int:pk>/', views.estado_tipo_bebida, name='estado_tipo_bebida'),
    
    #BEBIDAS 
    path('bebidas/', views.bebida_listar, name='listar_bebida'),
    path('bebidas/crear/', views.bebida_crear, name='crear_bebida'),
    path('bebidas/editar/<int:pk>/', views.bebida_editar, name='editar_bebida'),
    path('bebidas/eliminar/<int:pk>/', views.bebida_eliminar, name='eliminar_bebida'),
    path('bebidas/detalle/<int:pk>/', views.bebida_detalle, name='detalle_bebida'),
    path('bebidas/estado/<int:pk>/', views.bebida_estado, name='estado_bebida'),
]