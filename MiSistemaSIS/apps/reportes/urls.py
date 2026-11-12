from django.urls import path
from . import views

app_name = "reportes"

urlpatterns = [
    path("", views.reporte_ventas, name="ventas"),
    path("top/", views.reporte_top, name="top"),
    path("categorias/", views.reporte_categorias, name="categorias"),
    path("mozos/", views.reporte_mozos, name="mozos"),
    path("metodos/", views.reporte_metodos, name="metodos"),
    path("pdf/ventas/", views.exportar_pdf_ventas, name="pdf_ventas"),
    path("pdf/top/", views.exportar_pdf_ventas, name="pdf_top"),
    path("pdf/categorias/", views.exportar_pdf_ventas, name="pdf_categorias"),
    path("pdf/mozos/", views.exportar_pdf_ventas, name="pdf_mozos"),
]
