from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from .models import Empleado, Cargo, TipoPermiso, PermisoXCargo
from .forms import EmpleadoAltaForm, EmpleadoModificacionForm, RestablecerContrasenaForm, CargoForm, PermisoXCargoForm, AsignarPermisosCargoForm
from django.contrib.auth import authenticate, login
from empleados.decorators import permiso_requerido
from django.contrib.auth.models import User
# Create your views here.

@login_required
def empleados_home(request):
    return render(request, 'empleados_home.html')
#Empleado Listado
@login_required
@permiso_requerido('empleados', 'leer')
def empleado_listar (request):
    empleados = Empleado.objects.all().order_by('apellido_empleado')
    return render(request, 'empleado_listar.html', {'empleados': empleados, 'titulo': 'Listado de Empleados'})

@login_required
@permiso_requerido('empleados', 'escribir')
def empleado_alta(request):
    if request.method == 'POST':
        form  = EmpleadoAltaForm(request.POST)
        if form.is_valid():#verficar si el formulario es válido
            try:
                empleado = form.save()
                messages.success(request, f'Empleado {empleado.nombre_empleado} {empleado.apellido_empleado} creado exitosamente. Usuario: {empleado.user_auto}')
                return redirect('login')
            except Exception as e:
                messages.error(request, f'Error al crear el empleado: {(e)}')
        else:
            messages.error(request, 'Por favor corrija los errores en el formulario.')
    else:
        form = EmpleadoAltaForm()
    return render(request, 'empleado_alta.html', {'form': form, 'titulo': 'Alta de Empleado', 'boton': 'Crear Empleado'})

@login_required
@permiso_requerido('empleados', 'modificar')
def empleado_modificacion(request, pk):
    empleado = get_object_or_404(Empleado, pk=pk)
    
    if request.method == 'POST':
        empleado.nombre_empleado = request.POST.get('nombre_empleado', empleado.nombre_empleado)
        empleado.apellido_empleado = request.POST.get('apellido_empleado', empleado.apellido_empleado)
        empleado.dni = request.POST.get('dni', empleado.dni)
        empleado.telefono = request.POST.get('telefono', empleado.telefono)
        empleado.correo = request.POST.get('correo', empleado.correo)
        cargo_id = request.POST.get('cargo')
        if cargo_id:
            empleado.cargo = Cargo.objects.get(pk=cargo_id)
        else:
            empleado.cargo = None
        empleado.save()
        if empleado.user:
            empleado.user.email = empleado.correo
            empleado.user.first_name = empleado.nombre_empleado
            empleado.user.last_name = empleado.apellido_empleado
            empleado.user.save()
        
        messages.success(request, f'Empleado {empleado.user_auto} actualizado exitosamente.')
        return redirect('empleados:empleado_listar')
    cargos = Cargo.objects.all().order_by('nombre_cargo')
    
    return render(request, 'empleado_modificar.html', {
        'empleado': empleado,
        'cargos': cargos,
        'titulo': f'Modificar Empleado - {empleado.user_auto}'
    })

@login_required
@permiso_requerido('empleados', 'eliminar')
def empleado_baja(request,pk):
    empleado = get_object_or_404(Empleado, pk=pk)
    if empleado.user == request.user:
        messages.error(request, 'No puedes darte de baja a ti mismo')
        return redirect('empleados:empleado_listar')

    if request.method == 'POST':
        empleado.dar_baja()
        messages.success(request, f'Empleado {empleado.user_auto} dado de baja exitosamente.')
        return redirect('empleados:empleado_listar')
    
    return render( request, 'empleado_baja.html', {'empleado': empleado, 'titulo': f'Dar de baja Empleado - {empleado.user_auto}'})

@login_required
@permiso_requerido('empleados', 'modificar')
def empleado_reactivar(request, pk):
    empleado = get_object_or_404(Empleado, pk=pk)
    empleado.reactivar()
    messages.success(request, f'Empleado {empleado.user_auto} reactivado exitosamente.')
    return redirect('empleados:empleado_listar')


@login_required
@permiso_requerido('empleados', 'leer')
def empleado_detalle(request, pk):
    empleado = get_object_or_404(Empleado, pk=pk)
    return render(request, 'empleado_detalle.html', {'empleado': empleado, 'titulo': f'Detalle Empleado - {empleado.user_auto}'})

@login_required
@permiso_requerido('empleados', 'modificar')
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

def login_view(request):
    if request.method == 'POST':
        identificador = request.POST.get('username')  # Puede ser usuario, correo o nombre
        password = request.POST.get('password')
        # Intentar encontrar el username real
        username_real = None
        #Probar como username directo
        if User.objects.filter(username=identificador).exists():
            username_real = identificador
        else:
            #Probar como correo
            try:
                empleado = Empleado.objects.get(correo=identificador)
                if empleado.user:
                    username_real = empleado.user.username
            except Empleado.DoesNotExist:
                pass
            # Probar como nombre completo (Nombre Apellido o Apellido Nombre)
            if not username_real:
                try:
                    empleado = Empleado.objects.get(
                        nombre_empleado__iexact=identificador
                    )
                    if empleado.user:
                        username_real = empleado.user.username
                except Empleado.DoesNotExist:
                    pass
                
                # Probar "Apellido Nombre"
                if not username_real:
                    partes = identificador.split()
                    if len(partes) >= 2:
                        # Probar Apellido Nombre
                        try:
                            empleado = Empleado.objects.get(
                                apellido_empleado__iexact=partes[0],
                                nombre_empleado__iexact=partes[1]
                            )
                            if empleado.user:
                                username_real = empleado.user.username
                        except Empleado.DoesNotExist:
                            pass
        
        # Autenticar con el username real
        user = authenticate(request, username=username_real or identificador, password=password)
        print("\n" + "=" * 60)
        print(f"USUARIO: {user}")
        
        if user is not None:
            login(request, user)
            print(f"LOGIN OK: {user.username}")
            
            try:
                empleado = user.empleado
                print(f"EMPLEADO: {empleado}")
                print(f"DEBE CAMBIAR CONTRASEÑA: {empleado.debe_cambiar_contrasena}")
                
                if empleado.debe_cambiar_contrasena:
                    print(">>> REDIRIGIENDO A CAMBIO OBLIGATORIO")
                    messages.warning(request, 'Debes cambiar tu contraseña antes de continuar.')
                    return redirect('empleados:cambiar_clave_obligatorio')
                else:
                    print(">>> FLAG EN FALSE, REDIRIGIENDO A HOME")
            except Exception as e:
                print(f"ERROR: {e}")
            
            print(">>> REDIRIGIENDO A HOME (por defecto)")
            print("=" * 60 + "\n")
            
            return redirect('home')
        else:
            print("USUARIO NO AUTENTICADO")
            print("=" * 60 + "\n")
            messages.error(request, 'Usuario, correo o contraseña incorrectos')
    
    return render(request, 'login.html')
        #if user is not None:
    #         login(request, user)
    #         # Verificar si debe cambiar la contraseña
            
    #         try:
    #             empleado = user.empleado
    #             if empleado.debe_cambiar_contrasena:
    #                 messages.warning(request, 'Debes cambiar tu contraseña antes de continuar.')
    #                 return redirect('empleados:cambiar_clave_obligatorio')
    #         except Empleado.DoesNotExist:
    #             messages.info(request, 'Bienvenido al sistema')

    #         except Exception as e:
    #             messages.error(request, f'Error: {e}')
    #         return redirect('login')
    #     else:
    #         messages.error(request, 'Usuario, correo o contraseña incorrectos')
    # return render(request, 'login.html')

@login_required
def cambiar_clave_obligatorio(request):
    empleado = request.user.empleado
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
@permiso_requerido('cargos', 'leer')
def cargo_listar(request):
    cargos = Cargo.objects.all().order_by('nombre_cargo')
    return render(request, 'cargos/listar_cargos.html', {
        'cargos': cargos,
        'titulo': 'Listado de Cargos'
    })

@login_required
@permiso_requerido('cargos', 'escribir')
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
@permiso_requerido('cargos', 'modificar')
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
@permiso_requerido('cargos', 'eliminar')
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
@permiso_requerido('cargos', 'leer')
def permiso_listar(request):
    permisos = TipoPermiso.objects.all().order_by('modulo', 'accion')
    return render(request, 'permisos/listar_permiso.html', {
        'permisos': permisos,
        'titulo': 'Listado de Permisos'
    })

@login_required
@permiso_requerido('cargos', 'escribir')
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
@permiso_requerido('cargos', 'eliminar')
def permiso_eliminar(request, pk):
    permiso = get_object_or_404(TipoPermiso, pk=pk)
    if request.method == 'POST':
        descripcion = str(permiso)
        permiso.delete()
        messages.success(request, f'Permiso "{descripcion}" eliminado')
        return redirect('empleados:listar_permiso')
    return render(request, 'permisos/eliminar_permiso.html', {'permiso': permiso})

# VISTAS PARA ASIGNAR PERMISOS A CARGOS

@login_required
@permiso_requerido('cargos', 'modificar')
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
        return redirect('empleados:ver_permisos_cargo', pk=cargo.pk)
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
@permiso_requerido('cargos', 'leer')
def ver_permisos_cargo(request, pk):
    cargo = get_object_or_404(Cargo, pk=pk)
    permisos = PermisoXCargo.objects.filter(cargo=cargo).select_related('tipo_permiso')
    
    return render(request, 'permisos/ver_permisos_cargo.html', {
        'cargo': cargo,
        'permisos': permisos,
        'titulo': f'Permisos de {cargo.nombre_cargo}'
    })