from django.urls import path
from . import views
app_name = 'finanzas'
urlpatterns = [ 
    path('', views.finanzas_home, name='finanzas_home'),
    #RUTAS PARA CATEGORIAS DE GASTOS
    path('CATEGORIA_GASTOS/listar_cat_gasto/', views.listar_cat_gasto, name='listar_cat_gasto'),
    path('CATEGORIA_GASTOS/crear_cat_gasto/', views.crear_cat_gasto, name='crear_cat_gasto'),
    path('CATEGORIA_GASTOS/editar_cat_gasto/', views.editar_cat_gasto, name='editar_cat_gasto'),
    path('CATEGORIA_GASTOS/eliminar_cat_gasto/', views.eliminar_cat_gasto, name='eliminar_cat_gasto'),
    path('CATEGORIA_GASTOS/detalle_cat_gasto/', views.detalle_cat_gasto, name='detalle_cat_gasto'),
    #RUTAS PARA METODOS DE PAGO
    path('METODOS_PAGO/listar_met_pago/', views.listar_met_pago, name='listar_met_pago'),
    path('METODOS_PAGO/crear_met_pago/', views.crear_met_pago, name='crear_met_pago'),
    path('METODOS_PAGO/editar_met_pago/', views.editar_met_pago, name='editar_met_pago'),
    path('METODOS_PAGO/eliminar_met_pago/', views.eliminar_met_pago, name='eliminar_met_pago'),
    #RUTAS PARA CAJA
    path('cajas/', views.listar_cajas, name='listar_cajas'),
    path('cajas/abrir/', views.abrir_caja, name='abrir_caja'),
    path('cajas/<int:pk>/', views.detalle_caja, name='detalle_caja'),
    path('cajas/<int:pk>/arqueo/', views.arqueo_caja, name='arqueo_caja'),
    path('cajas/<int:pk>/cerrar/', views.cerrar_caja, name='cerrar_caja'),
    #RUTAS PARA GASTOS
    path('gastos/', views.listar_gastos, name='listar_gastos'),
    path('gastos/crear/', views.crear_gasto, name='crear_gasto'),
    path('gastos/<int:pk>/', views.detalle_gasto, name='detalle_gasto'),
    path('gastos/<int:pk>/editar/', views.editar_gasto, name='editar_gasto'),
    path('gastos/<int:pk>/eliminar/', views.eliminar_gasto, name='eliminar_gasto'),
    #RUTAS PARA VENTAS
    #path('VENTAS/listar_ventas/', views.listar_ventas, name='listar_ventas'),
]
