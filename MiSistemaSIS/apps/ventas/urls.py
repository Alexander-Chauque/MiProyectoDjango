from django.urls import path
from . import views

app_name = 'ventas'

urlpatterns = [
    path('', views.mesa_listar, name='listar_mesa'),
    path('crear/', views.mesa_crear, name='crear_mesa'),
    path('editar/<int:pk>/', views.mesa_editar, name='editar_mesa'),
    path('eliminar/<int:pk>/', views.mesa_eliminar, name='eliminar_mesa'),
    path('estado/<int:pk>/', views.mesa_estado, name='estado_mesa'),
    path('mesas/<int:pk>/comandas/', views.mesa_ver_comandas, name='mesa_ver_comandas'),

    
    path('comandas/', views.comanda_listar, name='comanda_listar'),
    path('comandas/crear/', views.comanda_crear, name='comanda_crear'),
    path('comandas/editar/<int:pk>/', views.comanda_editar, name='comanda_editar'),
    path('comandas/eliminar/<int:pk>/', views.comanda_eliminar, name='comanda_eliminar'),
    path('comandas/detalle/<int:pk>/', views.comanda_detalle, name='comanda_detalle'),
    path('comandas/estado/<int:pk>/', views.comanda_cambiar_estado, name='comanda_cambiar_estado'),
    path('comandas/anular/<int:pk>/', views.comanda_anular, name='comanda_anular'),
    path('comandas/consultar/', views.comanda_consultar, name='comanda_consultar'),
    path('comandas/comprobante/<int:pk>/', views.comanda_comprobante, name='comanda_comprobante'),
    path('comanda/<int:pk>/ticket/', views.comanda_ticket, name='comanda_ticket'),
]