from django.urls import path
from . import views

app_name = 'reportes'
urlpatterns = [
  path('', views.reportes_home, name='reportes_home'),
  path('exportar-csv/', views.exportar_reporte_csv, name='exportar_csv'),
]
