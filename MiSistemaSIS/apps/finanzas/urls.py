from django.urls import path
from . import views
app_name = 'finanzas'
urlpatterns = [ 
    path('', views.finanzas_home, name='finanzas_home'),
    #RUTAS PARA CATEGORIAS DE GASTOS
    path('CATEGORIA_GASTOS/listar_cat_gasto/', views.listar_cat_gasto, name='listar_cat_gasto'),
    path('CATEGORIA_GASTOS/crear_cat_gasto/', views.crear_cat_gasto, name='crear_cat_gasto'),
    path('CATEGORIA_GASTOS/<int:pk>/editar_cat_gasto/', views.editar_cat_gasto, name='editar_cat_gasto'),
    path('CATEGORIA_GASTOS/<int:pk>/eliminar_cat_gasto/', views.eliminar_cat_gasto, name='eliminar_cat_gasto'),
    path('CATEGORIA_GASTOS/<int:pk>/detalle_cat_gasto/', views.detalle_cat_gasto, name='detalle_cat_gasto'),
    path('CATEGORIA_GASTOS/<int:pk>/estado_categoria/', views.estado_categoria, name='estado_categoria'),
    #RUTAS PARA METODOS DE PAGO
    path('METODOS_PAGO/listar_met_pago/', views.listar_met_pago, name='listar_met_pago'),
    path('METODOS_PAGO/crear_met_pago/', views.crear_met_pago, name='crear_met_pago'),
    path('METODOS_PAGO/<int:pk>/editar_met_pago/', views.editar_met_pago, name='editar_met_pago'),
    path('METODOS_PAGO/<int:pk>/eliminar_met_pago/', views.eliminar_met_pago, name='eliminar_met_pago'),
    path('METODOS_PAGO/<int:pk>/detalle_met_pago/', views.detalle_met_pago, name='detalle_met_pago'),
    path('METODOS_PAGO/<int:pk>/estado_metodo_pago/', views.estado_metodo_pago, name='estado_metodo_pago'),
    #RUTAS PARA CAJA
    path('CAJA/listar_cajas/', views.listar_cajas, name='listar_cajas'),
    path('CAJA/abrir/', views.abrir_caja, name='abrir_caja'),
    path('CAJA/<int:pk>/detalle_caja/', views.detalle_caja, name='detalle_caja'),
    path('CAJA/<int:pk>/arqueo_caja/', views.arqueo_caja, name='arqueo_caja'),
    path('CAJA/<int:pk>/cerrar_caja/', views.cerrar_caja, name='cerrar_caja'),
    #RUTAS PARA GASTOS
    path('GASTOS/', views.listar_gastos, name='listar_gastos'),
    path('GASTOS/crear/', views.crear_gasto, name='crear_gasto'),
    path('GASTOS/<int:pk>/', views.detalle_gasto, name='detalle_gasto'),
    path('GASTOS/<int:pk>/editar/', views.editar_gasto, name='editar_gasto'),
    path('GASTOS/<int:pk>/eliminar/', views.eliminar_gasto, name='eliminar_gasto'),
    #RUTAS PARA VENTAS
    path('VENTAS/listar_ventas/', views.venta_listar, name='venta_listar'),
    path('VENTAS/crear_venta/', views.venta_crear, name='venta_crear'),
]
