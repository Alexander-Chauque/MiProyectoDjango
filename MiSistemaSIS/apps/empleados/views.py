from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from .models import Empleado, Cargo, TipoPermiso, PermisoXCargo, Asistencia, TipoAsistencia
from .forms import EmpleadoAltaForm, EmpleadoModificacionForm, RestablecerContrasenaForm, CargoForm, PermisoXCargoForm, AsignarPermisosCargoForm, PermisoForm, AsistenciaForm
from django.contrib.auth import authenticate, login
from empleados.decorators import permiso_requerido
from django.contrib.auth.models import User
from datetime import date
from django.db.models import Q
from django.core.paginator import Paginator
# Create your views here.

@login_required
def empleados_home(request):
    return render(request, 'empleados_home.html')
#Empleado Listado
@login_required
@permiso_requerido('empleados', 'leer')
def empleado_listar (request):
  empleados = Empleado.objects.all().order_by('apellido_empleado')
  cargos = Cargo.objects.all().order_by('nombre_cargo')

  buscar = request.GET.get('buscar', '').strip()
  cargos_ids = request.GET.getlist('cargo')
  estados = request.GET.getlist('estado')

  if buscar:
    empleados = empleados.filter( Q(nombre_empleado__icontains=buscar) | Q(apellido_empleado__icontains=buscar) | Q(user_auto__icontains=buscar) | Q(dni__icontains=buscar)
    )

    # Filtro por cargo
  cargos_ids_int = []
  for c in cargos_ids:
    if c.isdigit():
      cargos_ids_int.append(int(c))
  if cargos_ids_int:
    empleados = empleados.filter(cargo_id__in=cargos_ids_int)
  
  # Filtro por estado
  if estados:
    q_estado = Q()
    if 'activo' in estados:
      q_estado |= Q(estado=True)
    if 'inactivo' in estados:
      q_estado |= Q(estado=False)
    if q_estado:
      empleados= empleados.filter(q_estado)

  por_pagina = request.GET.get('por_pagina', 10)
  try:
    por_pagina = int(por_pagina)
    if por_pagina not in [10, 25, 50, 100]:
      por_pagina = 10
  except (ValueError, TypeError):
    por_pagina = 10
  
  paginator = Paginator(empleados, por_pagina)
  page_number = request.GET.get('page')
  empleados = paginator.get_page(page_number)

  return render(request, 'empleados/empleado_listar.html', {'empleados': empleados,'cargos': cargos, 'por_pagina': por_pagina, 'buscar': buscar, 'cargos_seleccionados': [str (c) for c in cargos_ids_int], 'estados_seleccionados': estados})

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
    return render(request, 'empleados/empleado_alta.html', {'form': form, 'titulo': 'Alta de Empleado', 'boton': 'Crear Empleado'})

@login_required
@permiso_requerido('empleados', 'modificar')
def empleado_modificacion(request, pk):
    empleado = get_object_or_404(Empleado, pk=pk)
    if request.method == 'POST':
        if request.method == 'POST':
          form = EmpleadoModificacionForm(request.POST, instance=empleado)
        if form.is_valid():
            form.save()
            messages.success(request, f'Empleado "{empleado.nombre_empleado}" actualizado correctamente')
            return redirect('empleados:listar_empleados')
    else:
        form = EmpleadoModificacionForm(instance=empleado)
        
    return render(request, 'empleados/empleado_modificar.html', {
        'form': form,
        'empleado': empleado
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
    
    return render( request, 'empleados/empleado_baja.html', {'empleado': empleado, 'titulo': f'Dar de baja Empleado - {empleado.user_auto}'})

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
    return render(request, 'empleados/empleado_detalle.html', {'empleado': empleado, 'titulo': f'Detalle Empleado - {empleado.user_auto}'})

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
        
        username_real = None
        if User.objects.filter(username=identificador).exists():
            username_real = identificador
        else:
            try:
                empleado = Empleado.objects.get(correo__iexact=identificador)
                if empleado.user:
                    username_real = empleado.user.username
            except Empleado.DoesNotExist:
                pass
            if not username_real:
                partes = identificador.split()
                if len(partes) >= 2:
                    # Probar Nombre Apellido
                    try:
                        empleado = Empleado.objects.get(
                            nombre_empleado__iexact=partes[0],
                            apellido_empleado__iexact=partes[1]
                        )
                        if empleado.user:
                            username_real = empleado.user.username
                    except Empleado.DoesNotExist:
                        pass
                    # Probar Apellido Nombre
                    if not username_real:
                        try:
                            empleado = Empleado.objects.get(
                                apellido_empleado__iexact=partes[0],
                                nombre_empleado__iexact=partes[1]
                            )
                            if empleado.user:
                                username_real = empleado.user.username
                        except Empleado.DoesNotExist:
                            pass

        #Autenticar al usuario
        if username_real:
            user = authenticate(request, username=username_real, password=password)
            if user is not None:
                login(request, user)
                # Verificar si debe cambiar la contraseña
                try:
                    empleado = user.empleado
                    if empleado.debe_cambiar_contrasena:
                        messages.warning(request, 'Debes cambiar tu contraseña antes de continuar.')
                        return redirect('empleados:cambiar_clave_obligatorio')
                except Empleado.DoesNotExist:
                    pass 
                return redirect('home')
        messages.error(request, 'Usuario, correo o contraseña incorrectos')
    return render(request, 'login.html')

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
  referer = request.META.get('HTTP_REFERER', '')

  buscar = request.GET.get('buscar', '').strip()
  if buscar:
    cargos= cargos.filter(nombre_cargo__icontains=buscar)
  
  por_pagina = request.GET.get('por_pagina', 10)
  try:
    por_pagina = int(por_pagina)
    if por_pagina not in [10, 25, 50, 100]:
      por_pagina = 10
  except (ValueError, TypeError):
    por_pagina = 10
  
  paginator = Paginator(cargos, por_pagina)
  page_number = request.GET.get('page')
  cargos = paginator.get_page(page_number)
  return render(request, 'cargos/listar_cargos.html', {'cargos': cargos, 'por_pagina': por_pagina, 'buscar': buscar, 'viene_de_empleados': '/empleados/listar/' in referer, })

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
        form = CargoForm(request.POST, instance=cargo) # Le pasamos la instancia
        if form.is_valid():
            form.save()
            messages.success(request, 'Cargo actualizado exitosamente')
            return redirect('empleados:listar_cargos')
    else:
        form = CargoForm(instance=cargo) # Cargamos los datos actuales
        
    return render(request, 'cargos/editar_cargo.html', {
        'form': form,
        'cargo': cargo,
        'titulo': 'Editar Cargo'
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
    buscar = request.GET.get('buscar', '').strip()
    modulos = request.GET.getlist('modulo')
    acciones = request.GET.getlist('accion')
    referer = request.META.get('HTTP_REFERER', '')
    
    
    if buscar:
      permisos = permisos.filter(Q(modulo__icontains=buscar) | Q(accion__icontains=buscar))

    if modulos:
      permisos= permisos.filter(modulo__in=modulos)
    
    if acciones:
      permisos = permisos.filter(accion__in=acciones)

    modulos_disponibles = TipoPermiso.objects.values_list('modulo', flat=True).distinct()
    acciones_disponibles = TipoPermiso.objects.values_list('accion', flat=True).distinct()

    por_pagina = request.GET.get('por_pagina', 10)
    try:
      por_pagina = int(por_pagina)
      if por_pagina not in [10, 25, 50, 100]:
          por_pagina = 10
    except (ValueError, TypeError):
      por_pagina = 10
    
    paginator = Paginator(permisos, por_pagina)
    page_number = request.GET.get('page')
    permisos = paginator.get_page(page_number)
    return render(request, 'permisos/listar_permiso.html', {'permisos': permisos, 'por_pagina': por_pagina, 'buscar': buscar, 'modulos_seleccionados': modulos, 'acciones_seleccionadas': acciones, 'modulos': modulos_disponibles, 'acciones': acciones_disponibles, 'viene_de_empleados': '/empleados/listar/' in referer})

@login_required
@permiso_requerido('cargos', 'escribir')
def permiso_crear(request):
    if request.method == 'POST':
        form = PermisoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Permiso creado exitosamente')
            return redirect('empleados:listar_permiso')
        else:
            messages.error(request, 'Error al crear el permiso. Revisá los datos.')
    else:
        form = PermisoForm()
    
    return render(request, 'permisos/crear_permiso.html', {
        'form': form,
        'titulo': 'Crear Permiso'
    })


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
def ver_permisos_cargo(request, pk):
    cargo = get_object_or_404(Cargo, pk=pk)
    permisos = TipoPermiso.objects.filter(
        permisoxcargo__cargo=cargo
    ).order_by('modulo', 'accion')
    
    return render(request, 'permisos/ver_permisos_cargo.html', {'cargo': cargo,'permisos': permisos})

@login_required
def asistencia_listar(request):
    asistencias_list = Asistencia.objects.all().select_related('id_empleado__cargo', 'id_tipo_asistencia').order_by('-fecha_asistencia')
    buscar = request.GET.get('buscar', '').strip()
    fecha_filtro = request.GET.get('fecha', '')
    tipo_filtro = request.GET.get('tipo', '')
    
    if buscar:
        asistencias_list = asistencias_list.filter(
            Q(id_empleado__nombre_empleado__icontains=buscar) | 
            Q(id_empleado__apellido_empleado__icontains=buscar) |
            Q(id_empleado__dni__icontains=buscar)
        )
    if fecha_filtro:
        asistencias_list = asistencias_list.filter(fecha_asistencia=fecha_filtro)
    if tipo_filtro:
        asistencias_list = asistencias_list.filter(id_tipo_asistencia=tipo_filtro)
    paginator = Paginator(asistencias_list, 10)
    page_number = request.GET.get('page')
    asistencias = paginator.get_page(page_number)
    hoy = date.today()
    asistencias_hoy = Asistencia.objects.filter(fecha_asistencia=hoy)
    presentes = asistencias_hoy.filter(id_tipo_asistencia__nombre_tipo_asis__iexact='Presente').count()
    ausentes = asistencias_hoy.filter(id_tipo_asistencia__nombre_tipo_asis__iexact='Ausente').count()
    tardanzas = asistencias_hoy.filter(id_tipo_asistencia__nombre_tipo_asis__iexact='Tardanza').count()
    
    total_empleados = Empleado.objects.filter(estado=True).count()
    tipos_asistencia = TipoAsistencia.objects.all()

    return render(request, 'asistencias/listar_asistencia.html', {
        'asistencias': asistencias,
        'buscar': buscar,
        'fecha_filtro': fecha_filtro,
        'tipo_filtro': tipo_filtro,
        'presentes': presentes,
        'ausentes': ausentes,
        'tardanzas': tardanzas,
        'total_empleados': total_empleados,
        'hoy': hoy,
        'tipos_asistencia': tipos_asistencia,
    })

@login_required
def asistencia_crear(request):
    if request.method == 'POST':
        form = AsistenciaForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Asistencia registrada correctamente.')
            return redirect('empleados:asistencia_listar')
    else:
        form = AsistenciaForm(initial={'fecha_asistencia': date.today()})
    
    return render(request, 'asistencias/crear_asistencia.html', {'form': form})

@login_required
def asistencia_editar(request, pk):
    asistencia = get_object_or_404(Asistencia, pk=pk)
    
    if request.method == 'POST':
        form = AsistenciaForm(request.POST, instance=asistencia)
        if form.is_valid():
            form.save()
            messages.success(request, 'Asistencia actualizada correctamente.')
            return redirect('empleados:asistencia_listar')
    else:
        form = AsistenciaForm(instance=asistencia)
        
    return render(request, 'asistencias/editar_asistencia.html', {'form': form, 'asistencia': asistencia})