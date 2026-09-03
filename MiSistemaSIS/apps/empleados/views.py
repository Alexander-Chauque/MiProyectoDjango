from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from .models import Empleado, Cargo
from .forms import EmpleadoAltaForm, EmpleadoModificacionForm, RestablecerContrasenaForm

# Create your views here.

#Empleado Listado
@login_required
def empleado_listar (request):
    empleados = Empleado.objects.all().order_by('apellido_empleado')
    return render(request, 'empleado_listar.html', {'empleados': empleados, 'titulo': 'Listado de Empleados'})

@login_required
def empleado_alta(request):
    if request.method == 'POST':
        form  = EmpleadoAltaForm(request.POST)
        if form.is_valid():
            try:
                empleado = form.save()
                messages.success(request, f'Empleado {empleado.nombre_empleado} {empleado.apellido_empleado} creado exitosamente.')
                return redirect('empleados:empleado_listar')
            except Exception as e:
                messages.error(request, f'Error al crear el empleado: {str(e)}')
        else:
            messages.error(request, 'Por favor corrija los errores en el formulario.')
    else:
        form = EmpleadoAltaForm()
    return render(request, 'empleado_alta.html', {'form': form, 'titulo': 'Alta de Empleado', 'boton': 'Crear Empleado'})


@login_required
def empleado_modificacion(request, pk):
    empleado = get_object_or_404(Empleado, pk=pk)
    if request.method == 'POST':
        form = EmpleadoModificacionForm(request.POST, instance = empleado)
        if form.is_valid():
            form.save()
            messages.success(request, f'Correo actualizado para {empleado.user_auto}')
            return redirect('empleados:empleado_listar')
        else:
            messages.error(request, 'Por favor corrija los errores')
    else:
        form = EmpleadoModificacionForm(instance=empleado)
    return render(request, 'empleado_modificar.html', {'form': form, 'empleado': empleado, 'titulo': f'Modificar Empleado - {empleado.user_auto}'})


@login_required
def empleado_baja(request,pk):
    empleado = get_object_or_404(Empleado, pk=pk)

    if request.method == 'POST':
        empleado.dar_baja()
        messages.success(request, f'Empleado {empleado.user_auto} dado de baja exitosamente.')
        return redirect('empleados:empleado_listar')
    
    return render( request, 'empleado_baja.html', {'empleado': empleado, 'titulo': f'Dar de baja Empleado - {empleado.user_auto}'})


@login_required
def empleado_reactivar(request, pk):
    empleado = get_object_or_404(Empleado, pk=pk)
    empleado.reactivar()
    messages.success(request, f'Empleado {empleado.user_auto} reactivado exitosamente.')
    return redirect('empleados:empleado_listar')


@login_required
def empleado_detalle(request, pk):
    empleado = get_object_or_404(Empleado, pk=pk)
    return render(request, 'empleado_detalle.html', {'empleado': empleado, 'titulo': f'Detalle Empleado - {empleado.user_auto}'})

@login_required
def empleado_restablecer_contrasena(request, pk):
    empleado = get_object_or_404(Empleado, pk=pk)
    if request.method == 'POST':
        form = RestablecerContrasenaForm(request.POST)
        if form.is_valid():
            nueva_contrasena = form.cleaned_data['nueva_contrasena']
            empleado.cambiar_contrasena(nueva_contrasena)
            messages.success(request, f'Contraseña restablecida para {empleado.user_auto}')
            return redirect('empleados:empleado_listar')
        else:
            messages.error(request, 'Por favor corrija los errores en el formulario.')
    else:
        form = RestablecerContrasenaForm()
        return render(request, 'restablecer_contrasena.html', {'form': form, 'empleado': empleado, 'titulo': f'Restablecer Contraseña - {empleado.user_auto}'})