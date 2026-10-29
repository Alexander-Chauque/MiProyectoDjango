from django.urls import path
from . import views

app_name = "auditoria"

urlpatterns = [
    path("", views.log_auditoria_listar, name="log_auditoria_listar"),
    path("exportar/", views.exportar_auditoria_csv, name="exportar_csv"),
]
