from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from .models import Empleado, Cargo, TipoPermiso, PermisoXCargo
from .forms import EmpleadoAltaForm, EmpleadoModificacionForm, RestablecerContrasenaForm, CargoForm, PermisoXCargoForm, AsignarPermisosCargoForm
from django.contrib.auth import authenticate, login

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
        if form.is_valid():#verficar si el formulario es válido
            try:
                empleado = form.save()
                messages.success(request, f'Empleado {empleado.nombre_empleado} {empleado.apellido_empleado} creado exitosamente.')
                return redirect('login')
            except Exception as e:
                messages.error(request, f'Error al crear el empleado: {(e)}')
        else:
            messages.error(request, 'Por favor corrija los errores en el formulario.')
    else:
        form = EmpleadoAltaForm()
    return render(request, 'empleado_alta.html', {'form': form, 'titulo': 'Alta de Empleado', 'boton': 'Crear Empleado'})


@login_required
def empleado_modificacion(request, pk):
    empleado = get_object_or_404(Empleado, pk=pk)
    if request.method == 'POST':
        form = EmpleadoModificacionForm(request.POST, instance=empleado)
        if form.is_valid():
            form.save() 

            messages.success(request, f'Correo actualizado para {empleado.user_auto}')
            return redirect('empleados:empleado_listar')
        else:
            messages.error(request, 'Por favor corrija los errores')
    else:
        form = EmpleadoModificacionForm(instance=empleado)
        
    return render(request, 'empleado_modificar.html', {
        'form': form, 
        'empleado': empleado, 
        'titulo': f'Modificar Empleado - {empleado.user_auto}'
    })



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
            nueva_contrasena = form.cleaned_data.get('nueva_contrasena')

            empleado.cambiar_contrasena(nueva_contrasena)
            messages.success(request, f'Contraseña restablecida para {empleado.user_auto}')
            return redirect('login')
        else:
            messages.error(request, 'Por favor corrija los errores en el formulario.')
    else:
        form = RestablecerContrasenaForm()
    return render(request, 'restablecer_contrasena.html', {'form': form, 'empleado': empleado, 'titulo': f'Restablecer Contraseña - {empleado.user_auto}'})

@login_required
def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            
            try:
                empleado = user.empleado
                if empleado.debe_cambiar_contrasena:
                    messages.warning(request, 'Debes cambiar tu contraseña antes de continuar.')
                    return redirect('empleados:cambiar_clave_obligatorio')
            except:
                pass
            
            return redirect('inventario:listar_platos')
        else:
            messages.error(request, 'Usuario o contraseña incorrectos')
    
    return render(request, 'login.html')

@login_required
def cambiar_clave_obligatorio(request):
    empleado = request.user.empleado
    
    # Si no debe cambiar clave, redirigir
    if not empleado.debe_cambiar_contrasena:
        return redirect('empleados:empleado_listar')
    
    if request.method == 'POST':
        nueva = request.POST.get('nueva_contrasena')
        confirmar = request.POST.get('confirmar_contrasena')
        
        if nueva and confirmar and nueva == confirmar:
            if len(nueva) >= 8:
                request.user.set_password(nueva)
                request.user.save()
                
                empleado.debe_cambiar_contrasena = False
                empleado.save()
                
                update_session_auth_hash(request, request.user)
                
                messages.success(request, 'Contraseña actualizada exitosamente')
                return redirect('login')
            else:
                messages.error(request, ' La contraseña debe tener al menos 8 caracteres')
        else:
            messages.error(request, 'Las contraseñas no coinciden')
    
    return render(request, 'cambiar_clave_obligatorio.html')


# VISTAS PARA CARGOS

@login_required
def cargo_listar(request):
    cargos = Cargo.objects.all().order_by('nombre_cargo')
    return render(request, 'cargos/listar_cargos.html', {
        'cargos': cargos,
        'titulo': 'Listado de Cargos'
    })

@login_required
def cargo_crear(request):
    if request.method == 'POST':
        form = CargoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Cargo creado exitosamente')
            return redirect('empleados:listar_cargo')
    else:
        form = CargoForm()
    return render(request, 'cargos/crear_cargo.html', {
        'form': form,
        'titulo': 'Crear Cargo',
        'boton': 'Guardar'
    })

@login_required
def cargo_editar(request, pk):
    cargo = get_object_or_404(Cargo, pk=pk)
    if request.method == 'POST':
        form = CargoForm(request.POST, instance=cargo)
        if form.is_valid():
            form.save()
            messages.success(request, 'Cargo actualizado')
            return redirect('empleados:listar_cargo')
    else:
        form = CargoForm(instance=cargo)
    return render(request, 'cargos/crear_cargo.html', {
        'form': form,
        'titulo': 'Editar Cargo',
        'boton': 'Actualizar'
    })

@login_required
def cargo_eliminar(request, pk):
    cargo = get_object_or_404(Cargo, pk=pk)
    if request.method == 'POST':
        nombre = cargo.nombre_cargo
        cargo.delete()
        messages.success(request, f'Cargo "{nombre}" eliminado')
        return redirect('empleados:listar_cargo')
    return render(request, 'cargos/eliminar_cargo.html', {'cargo': cargo})


# VISTAS PARA PERMISOS

@login_required
def permiso_listar(request):
    permisos = TipoPermiso.objects.all().order_by('modulo', 'accion')
    return render(request, 'permisos/listar_permiso.html', {
        'permisos': permisos,
        'titulo': 'Listado de Permisos'
    })

@login_required
def permiso_crear(request):
    if request.method == 'POST':
        modulo = request.POST.get('modulo')
        accion = request.POST.get('accion')
        descripcion = request.POST.get('descripcion', '')
        
        if TipoPermiso.objects.filter(modulo=modulo, accion=accion).exists():
            messages.error(request, 'Este permiso ya existe')
        else:
            TipoPermiso.objects.create(
                modulo=modulo,
                accion=accion,
                descripcion=descripcion
            )
            messages.success(request, 'Permiso creado exitosamente')
            return redirect('empleados:listar_permiso')
    
    return render(request, 'permisos/crear_permiso.html', {'titulo': 'Crear Permiso'})

@login_required
def permiso_eliminar(request, pk):
    permiso = get_object_or_404(TipoPermiso, pk=pk)
    if request.method == 'POST':
        descripcion = str(permiso)
        permiso.delete()
        messages.success(request, f'Permiso "{descripcion}" eliminado')
        return redirect('empleados:listar_permiso')
    return render(request, 'permiso/eliminar_permiso.html', {'permiso': permiso})

# VISTAS PARA ASIGNAR PERMISOS A CARGOS

@login_required
def asignar_permisos(request):
    if request.method == 'POST':
        cargo_id = request.POST.get('cargo')
        permisos_ids = request.POST.getlist('permisos')
        
        cargo = get_object_or_404(Cargo, pk=cargo_id)
        
        # Eliminar permisos anteriores
        PermisoXCargo.objects.filter(cargo=cargo).delete()
        
        # Asignar nuevos permisos
        for permiso_id in permisos_ids:
            tipo_permiso = get_object_or_404(TipoPermiso, pk=permiso_id)
            PermisoXCargo.objects.create(
                cargo=cargo,
                tipo_permiso=tipo_permiso
            )
        
        messages.success(request, f'Permisos asignados a "{cargo.nombre_cargo}"')
        return redirect('empleados:asignar_permisos')
    
    cargos = Cargo.objects.all().order_by('nombre_cargo')
    permisos = TipoPermiso.objects.all().order_by('modulo', 'accion')
    
    # Obtener permisos ya asignados
    permisos_asignados_por_cargo = {}
    for cargo in cargos:
        permisos_asignados_por_cargo[cargo.pk] = list(
            PermisoXCargo.objects.filter(cargo=cargo).values_list('tipo_permiso_id', flat=True)
        )
    
    return render(request, 'permisos/asignar_permisos.html', {
        'cargos': cargos,
        'permisos': permisos,
        'permisos_asignados': permisos_asignados_por_cargo,
        'titulo': 'Asignar Permisos a Cargos'
    })

@login_required
def ver_permisos_cargo(request, pk):

    cargo = get_object_or_404(Cargo, pk=pk)
    permisos = PermisoXCargo.objects.filter(cargo=cargo).select_related('tipo_permiso')
    
    return render(request, 'permisos/ver_permisos_cargo.html', {
        'cargo': cargo,
        'permisos': permisos,
        'titulo': f'Permisos de {cargo.nombre_cargo}'
    })