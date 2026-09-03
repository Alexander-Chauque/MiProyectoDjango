from django.urls import path
from . import views

urlpatterns = [

#ruta login
    path('', views.login_view, name='login'),

    path('home/', views.home, name='home'),

    path('listar/', views.listar_platos, name='listar_platos'),
    path('crear/', views.crear_plato, name='crear_plato'),
    path('editar/<int:pk>/', views.editar_plato, name='editar_plato'),
    path('eliminar/<int:pk>/', views.eliminar_plato, name='eliminar_plato'),
    path('detalle/<int:pk>/', views.detalle_plato, name='detalle_plato'),
    path('estado/<int:pk>/', views.estado_plato, name="estado_plato"),


#rutas para listar, crear, editar y eliminar ingredientes
    path('./inventario/ingredientes/', views.listar_ingredientes, name='listar_ingredientes'),
    path('./inventario/ingredientes/crear/', views.crear_ingrediente, name='crear_ingrediente'),
    path('./inventario/ingredientes/editar/<int:pk>/', views.editar_ingrediente, name='editar_ingrediente'),
    path('./inventario/ingredientes/eliminar/<int:pk>/', views.eliminar_ingrediente, name='eliminar_ingrediente'),
    path('./inventario/ingredientes/detalle/<int:pk>/', views.detalle_ingrediente, name='detalle_ingrediente'),
    path('./invenatrio/ingredientes/estado/<int:pk>/', views.estado_ingrediente, name="estado_ingrediente"),
#rutas para listar, crear, editar y eliminar categorias
    path('categorias/', views.listar_categorias, name='listar_categorias'),
    path('categorias/crear/', views.crear_categoria, name='crear_categoria'),
    path('categorias/editar/<int:pk>/', views.editar_categoria, name='editar_categoria'),
    path('categorias/eliminar/<int:pk>/', views.eliminar_categoria, name='eliminar_categoria'),
    path('categorias/detalle/<int:pk>/', views.detalle_categoria, name='detalle_categoria'),
    path('categorias/estado/<int:pk>/', views.estado_categoria, name='estado_categoria'),

]