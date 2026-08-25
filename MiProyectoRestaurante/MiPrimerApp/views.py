from django.shortcuts import render

# Create your views here.
def MiPrimerFuncion(request):
    datos = {
        'nombre': 'Mi Primer App',}
    return render(request, 'mi_pagina_sis.html', datos)