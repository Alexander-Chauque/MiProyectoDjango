from django.shortcuts import render, get_object_or_404, redirect
from .models import Plato, Categoria, Ingrediente, DetallePlato
from django.db import models

#Funciones para listar, crear, editar y eliminar platos
def listar_platos(request):
    platos = Plato.objects.all()
    return render(request, 'listar.html', {'platos': platos})

def crear_plato(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        precio = request.POST.get('precio')
        categoria_id = request.POST.get('categoria')
        categoria = Categoria.objects.get(id=categoria_id)
        ingredientes = request.POST.getlist('ingredientes')
        plato = Plato.objects.create(nombre=nombre, precio=precio, categoria=categoria, ingredientes=ingredientes)
        for ingrediente_id in ingredientes:
            DetallePlato.objects.create(plato=plato, ingrediente=Ingrediente.objects.get(id=ingrediente_id), cantidad=1)
        # plato.ingredientes.set(ingredientes)  
        return redirect('listar_platos')
    else:
        ingredientes = Ingrediente.objects.all()
        categoria = Categoria.objects.all()
        return render(request, 'crear.html', {'ingredientes': ingredientes, 'categoria': categoria})

def editar_plato(request, pk):
    plato = get_object_or_404(Plato, pk=pk)
    if request.method == 'POST':
        plato.nombre = request.POST.get('nombre')
        plato.precio = request.POST.get('precio')
        categoria_id = request.POST.get('categoria')
        plato.categoria = Categoria.objects.get(id=categoria_id)
        ingredientes = request.POST.getlist('ingredientes')
        plato.detalleplato_set.all().delete()  # Elimina los detalles existentes
        for ingrediente_id in ingredientes:
            DetallePlato.objects.create(plato=plato, ingrediente=Ingrediente.objects.get(id=ingrediente_id), cantidad=1)
        plato.save()
        return redirect('listar_platos')
    return render(request, 'editar.html', {'plato': plato})

def eliminar_plato(request, pk):
    plato = get_object_or_404(Plato, pk=pk)
    if request.method == 'POST':
        plato.delete()
        return redirect('listar_platos')
    return render(request, 'eliminar.html', {'plato': plato})

def detalle_plato(request, pk):
    plato = get_object_or_404(Plato,pk=pk)
    return render(request, 'detalle.html', {'plato':plato})

#Funciones para listar, crear, editar y eliminar ingredientes

def listar_ingredientes(request):
    ingredientes = Ingrediente.objects.all()
    return render(request, 'ingredientes/listar_ingrediente.html', {'ingredientes': ingredientes})

def crear_ingrediente(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        unidad_medida = request.POST.get('unidad_medida')
        costo_unitario = request.POST.get('costo_unitario')
        Ingrediente.objects.create(nombre=nombre, unidad_medida=unidad_medida, costo_unitario=costo_unitario)
        return redirect('listar_ingredientes')
    else:
        return render(request, 'ingredientes/crear_ingrediente.html')

def editar_ingrediente(request, pk):
    ingrediente = get_object_or_404(Ingrediente, pk=pk)
    if request.method == 'POST':
        ingrediente.nombre = request.POST.get('nombre')
        ingrediente.unidad_medida = request.POST.get('unidad_medida')
        ingrediente.costo_unitario = request.POST.get('costo_unitario')
        ingrediente.save()
        return redirect('listar_ingredientes')
    else:
        return render(request, 'ingredientes/editar_ingrediente.html', {'ingrediente': ingrediente})

def eliminar_ingrediente(request, pk):
    ingrediente = get_object_or_404(Ingrediente, pk=pk)
    if request.method == 'POST':
        ingrediente.delete()
        return redirect('listar_ingredientes')
    else:
        return render(request, 'ingredientes/eliminar_ingrediente.html', {'ingrediente': ingrediente})

def detalle_ingrediente(request, pk):
    ingrediente = get_object_or_404(Ingrediente,pk=pk)
    return render(request, 'ingredientes/detalle_ingrediente.html', {'ingrediente':ingrediente})

#Funciones para listar, crear, editar y eliminar categorias
def listar_categorias(request):
    categorias = Categoria.objects.all()
    return render(request, 'categorias/listar_categoria.html', {'categorias': categorias})

def crear_categoria(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        descripcion = request.POST.get('descripcion')
        Categoria.objects.create(nombre=nombre, descripcion=descripcion)
        return redirect('listar_categorias')
    else:
        return render(request, 'categorias/crear_categoria.html')

def editar_categoria(request, pk):
    categoria = get_object_or_404(Categoria, pk=pk)
    if request.method == 'POST':
        categoria.nombre = request.POST.get('nombre')
        categoria.descripcion = request.POST.get('descripcion')
        categoria.save()
        return redirect('listar_categorias')
    else:
        return render(request, 'categorias/editar_categoria.html', {'categoria': categoria})

def eliminar_categoria(request, pk):
    categoria = get_object_or_404(Categoria, pk=pk)
    if request.method == 'POST':
        categoria.delete()
        return redirect('listar_categorias')
    else:
        return render(request, 'categorias/eliminar_categoria.html', {'categoria': categoria})

def detalle_categoria(request, pk):
    categoria = get_object_or_404(Categoria,pk=pk)
    return render(request, 'categorias/detalle_categoria.html', {'categoria':categoria})