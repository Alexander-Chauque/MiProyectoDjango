from django.urls import path
from MiPrimerApp import views

urlpatterns = [
    path('', views.MiPrimerFuncion, name='mi_primer_funcion'),
]