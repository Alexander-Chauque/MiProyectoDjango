from django.shortcuts import render

# Create your views here.
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import Mesa, Comanda,DetalleComanda
from django.forms import inlineformset_factory
from .forms import MesaForm, ComandaForm, DetalleComandaForm
from inventario.models import Plato, Bebida
from empleados.decorators import permiso_requerido

@login_required
@permiso_requerido('mesas', 'leer')
def mesa_listar(request):
    mesas = Mesa.objects.all().order_by('numero_mesa')
    return render(request, 'mesas/listar_mesas.html', {
        'mesas': mesas,
        'titulo': 'Listado de Mesas'})

@login_required
@permiso_requerido('mesas', 'escribir')
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
        'boton': 'Guardar'})

@login_required
@permiso_requerido('mesas', 'modificar')
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
        'boton': 'Actualizar' })

@login_required
@permiso_requerido('mesas', 'eliminar')
def mesa_eliminar(request, pk):
    mesa = get_object_or_404(Mesa, pk=pk)
    if request.method == 'POST':
        numero = mesa.numero_mesa
        mesa.delete()
        messages.success(request, f'Mesa {numero} eliminada')
        return redirect('ventas:listar_mesa')
    return render(request, 'mesas/eliminar_mesa.html', {'mesa': mesa})

@login_required
@permiso_requerido('mesas', 'modificar')
def mesa_estado(request, pk):
    mesa = get_object_or_404(Mesa, pk=pk)
    mesa.estado_mesa = not mesa.estado_mesa
    mesa.save()
    
    estado = "activada" if mesa.estado_mesa else "desactivada"
    messages.success(request, f'Mesa {mesa.numero_mesa} {estado}')
    return redirect('ventas:listar_mesa')

#COMANDAS
# LISTAR COMANDAS
@login_required
@permiso_requerido('comandas', 'leer')
def comanda_listar(request):
    comandas = Comanda.objects.all().select_related('mesa', 'empleado')
    return render(request, 'comandas/comanda_listar.html', {
        'comandas': comandas,})

# CREAR COMANDA
@login_required
@permiso_requerido('comandas', 'escribir')
def comanda_crear(request):
    DetalleFormSet = inlineformset_factory(
        Comanda, DetalleComanda,
        form=DetalleComandaForm,
        extra=3, can_delete=True)
    if request.method == 'POST':
        form = ComandaForm(request.POST)
        formset = DetalleFormSet(request.POST)
        # ===== DEBUG =====
        print("=" * 60)
        print("FORM VÁLIDO:", form.is_valid())
        print("FORMSET VÁLIDO:", formset.is_valid())
        print("ERRORES FORM:", form.errors)
        print("ERRORES FORMSET:", formset.errors)
        print("NO ERRORES FORMSET:", formset.non_form_errors())
        print("POST DATA:", request.POST)
        print("=" * 60)
        # =================
        

        if form.is_valid() and formset.is_valid():
            comanda = form.save(commit=False)# <-- No guardar aún
            # Asignar automáticamente el empleado logueado
            try:
                comanda.empleado = request.user.empleado
            except:
                messages.error(request, 'No tienes un empleado asociado. Contacta al administrador.')
                return redirect('ventas:comanda_listar')
            comanda=form.save() # <-- Ahora sí guardar
            
            formset.instance = comanda
            formset.save()
            comanda.calcular_total()
            # Cambiar estado de la mesa
            comanda.mesa.estado_mesa = False
            comanda.mesa.save()
            messages.success(request, f'Comanda #{comanda.id_comanda} creada')
            return redirect('ventas:comanda_listar')
    else:
        form = ComandaForm()
        formset = DetalleFormSet()
    return render(request, 'comandas/comanda_crear.html', {  
        'form': form,
        'formset': formset,
        'platos': Plato.objects.filter(estado_plato=True),
        'bebidas': Bebida.objects.filter(disponible_bebida=True),})

@login_required
@permiso_requerido('comandas', 'modificar')
def comanda_editar(request, pk):
    comanda = get_object_or_404(Comanda, id_comanda=pk)
    mesa_anterior = comanda.mesa
    DetalleFormSet = inlineformset_factory(
    Comanda, DetalleComanda,
    form=DetalleComandaForm,
    extra=1, 
    can_delete=True,
    fields=['plato', 'cant_plato', 'bebida', 'cant_bebida'])
    
    if request.method == 'POST':
        form = ComandaForm(request.POST, instance=comanda)
        formset = DetalleFormSet(request.POST, instance=comanda)
        print("=" * 60)
        print("FORM VÁLIDO:", form.is_valid())
        print("FORMSET VÁLIDO:", formset.is_valid())
        print("ERRORES FORM:", form.errors)
        print("ERRORES FORMSET:", formset.errors)
        print("NO ERRORES FORMSET:", formset.non_form_errors())
        print("=" * 60)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            comanda.calcular_total()

            if mesa_anterior != comanda.mesa:
                mesa_anterior.estado_mesa = True   # Liberar la anterior
                mesa_anterior.save()
                comanda.mesa.estado_mesa = False   # Ocupar la nueva
                comanda.mesa.save()
            
            messages.success(request, f'Comanda #{comanda.id_comanda} actualizada')
            return redirect('ventas:comanda_listar')
    else:
        form = ComandaForm(instance=comanda)
        formset = DetalleFormSet(instance=comanda)
    return render(request, 'comandas/comanda_editar.html', {
        'form': form,
        'formset': formset,
        'comanda': comanda,
    })
# ELIMINAR COMANDA
@login_required
@permiso_requerido('comandas', 'eliminar')
def comanda_eliminar(request, pk):
    comanda = get_object_or_404(Comanda, id_comanda=pk)
    if request.method == 'POST':
        # Liberar la mesa
        comanda.mesa.estado_mesa = True
        comanda.mesa.save()
        
        comanda.delete()
        messages.success(request, 'Comanda eliminada')
        return redirect('ventas:comanda_listar')
    return render(request, 'comandas/comanda_eliminar.html', {'comanda': comanda})

# DETALLE COMANDA
@login_required
@permiso_requerido('comandas', 'leer')
def comanda_detalle(request, pk):
    comanda = get_object_or_404(Comanda, id_comanda=pk)
    detalles = comanda.detalles.all().select_related('plato', 'bebida')
    return render(request, 'comandas/comanda_detalle.html', {
        'comanda': comanda,
        'detalles': detalles
    })

# CAMBIAR ESTADO
@login_required
@permiso_requerido('comandas', 'modificar')
def comanda_cambiar_estado(request, pk):
    comanda = get_object_or_404(Comanda, id_comanda=pk)
    nuevo_estado = request.GET.get('estado') or request.POST.get('estado')
    if nuevo_estado:
        comanda.estado_comanda = nuevo_estado
        comanda.save()
        # Si la comanda se marca como "Pagada" o "Entregada", liberar la mesa
        if nuevo_estado in ['pagada', 'entregada']:
            comanda.mesa.estado_mesa = True
            comanda.mesa.save()
        messages.success(request, f'Comanda #{comanda.id_comanda} ahora está {comanda.get_estado_comanda_display()}')
    return redirect('ventas:comanda_listar')


