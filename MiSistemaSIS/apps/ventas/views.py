from django.shortcuts import render

# Create your views here.
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import Mesa
from .forms import MesaForm

@login_required
def mesa_listar(request):
    mesas = Mesa.objects.all().order_by('numero_mesa')
    return render(request, 'mesas/listar_mesas.html', {
        'mesas': mesas,
        'titulo': 'Listado de Mesas'
    })

@login_required
def mesa_crear(request):
    if request.method == 'POST':
        form = MesaForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Mesa creada exitosamente')
            return redirect('ventas:listar_mesa')
    else:
        form = MesaForm()
    return render(request, 'mesas/crear_mesa.html', {
        'form': form,
        'titulo': 'Crear Mesa',
        'boton': 'Guardar'
    })

@login_required
def mesa_editar(request, pk):
    mesa = get_object_or_404(Mesa, pk=pk)
    if request.method == 'POST':
        form = MesaForm(request.POST, instance=mesa)
        if form.is_valid():
            form.save()
            messages.success(request, 'Mesa actualizada')
            return redirect('ventas:listar_mesa')
    else:
        form = MesaForm(instance=mesa)
    return render(request, 'mesas/editar_mesa.html', {
        'form': form,
        'titulo': 'Editar Mesa',
        'boton': 'Actualizar'
    })

@login_required
def mesa_eliminar(request, pk):
    mesa = get_object_or_404(Mesa, pk=pk)
    if request.method == 'POST':
        numero = mesa.numero_mesa
        mesa.delete()
        messages.success(request, f'Mesa {numero} eliminada')
        return redirect('ventas:listar_mesa')
    return render(request, 'mesas/eliminar_mesa.html', {'mesa': mesa})

@login_required
def mesa_estado(request, pk):
    mesa = get_object_or_404(Mesa, pk=pk)
    mesa.estado_mesa = not mesa.estado_mesa
    mesa.save()
    
    estado = "activada" if mesa.estado_mesa else "desactivada"
    messages.success(request, f'Mesa {mesa.numero_mesa} {estado}')
    return redirect('ventas:listar_mesa')