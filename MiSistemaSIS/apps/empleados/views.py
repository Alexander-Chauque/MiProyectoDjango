from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.utils import timezone
from core.fechas import limitar_rango
from .models import (
    Empleado,
    Cargo,
    TipoPermiso,
    PermisoXCargo,
    Asistencia,
    TipoAsistencia,
)
from .forms import (
    EmpleadoAltaForm,
    CambiarContrasenaForm,
    EmpleadoModificacionForm,
    MiPerfilForm,
    RestablecerContrasenaForm,
    CargoForm,
    PermisoXCargoForm,
    AsignarPermisosCargoForm,
    PermisoForm,
    AsistenciaForm,
)
from django.contrib.auth import authenticate, login
from empleados.decorators import NIVEL_ADMINISTRADOR, nivel_de, permiso_requerido, puede_gestionar, tiene_permiso
from empleados.servicios import asignar_permisos_a_cargo, es_administrador
from django.contrib.auth.models import User
from django.db import transaction
from datetime import datetime
from django.db.models import Q
from django.core.paginator import Paginator
from auditoria.models import LogAuditoria


# Create your views here.

_SIN_NIVEL_EMPLEADO = "No podés gestionar a un empleado con un nivel de acceso igual o superior al tuyo."
_SIN_NIVEL_CARGO = "No podés gestionar un cargo con un nivel de acceso igual o superior al tuyo."


def _nivel_empleado(empleado):
    return empleado.cargo.nivel_acceso if empleado.cargo else 0


@login_required
def empleados_home(request):
    return render(request, "empleados_home.html")


# Empleado Listado
@login_required
@permiso_requerido("empleados", "leer")
def empleado_listar(request):
    empleados = Empleado.objects.all().order_by("apellido_empleado")
    cargos = Cargo.objects.all().order_by("nombre_cargo")

    buscar = request.GET.get("buscar", "").strip()
    cargos_ids = request.GET.getlist("cargo")
    estados = request.GET.getlist("estado")

    if buscar:
        empleados = empleados.filter(
            Q(nombre_empleado__icontains=buscar)
            | Q(apellido_empleado__icontains=buscar)
            | Q(user_auto__icontains=buscar)
            | Q(dni__icontains=buscar)
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
        if "activo" in estados:
            q_estado |= Q(estado=True)
        if "inactivo" in estados:
            q_estado |= Q(estado=False)
        if q_estado:
            empleados = empleados.filter(q_estado)

    por_pagina = request.GET.get("por_pagina", 10)
    try:
        por_pagina = int(por_pagina)
        if por_pagina not in [10, 25, 50, 100]:
            por_pagina = 10
    except (ValueError, TypeError):
        por_pagina = 10

    paginator = Paginator(empleados, por_pagina)
    page_number = request.GET.get("page")
    empleados = paginator.get_page(page_number)

    return render(
        request,
        "empleados/empleado_listar.html",
        {
            "empleados": empleados,
            "cargos": cargos,
            "por_pagina": por_pagina,
            "buscar": buscar,
            "cargos_seleccionados": [str(c) for c in cargos_ids_int],
            "estados_seleccionados": estados,
        },
    )


@login_required
@permiso_requerido("empleados", "escribir")
def empleado_alta(request):
    if request.method == "POST":
        form = EmpleadoAltaForm(request.POST)
        if form.is_valid():
            cargo = form.cleaned_data.get("cargo")
            if cargo and not puede_gestionar(request.user, cargo.nivel_acceso):
                messages.error(request, _SIN_NIVEL_CARGO)
                return render(request, "empleados/empleado_alta.html", {"form": form})
            try:
                empleado = form.save()

                LogAuditoria.objects.create(
                    tabla="Empleado",
                    accion="CREAR",
                    registro_id=empleado.id_empleado,
                    valores_anteriores="",
                    valores_actuales=f"Empleado creado: {empleado.nombre_empleado} {empleado.apellido_empleado}. Usuario: {empleado.user_auto}",
                    empleado=request.user.empleado,
                )

                messages.success(
                    request,
                    f"Empleado {empleado.nombre_empleado} {empleado.apellido_empleado} creado exitosamente. Usuario: {empleado.user_auto}",
                )
                return redirect("login")
            except Exception as e:
                messages.error(request, f"Error al crear el empleado: {(e)}")
        else:
            messages.error(request, "Por favor corrija los errores en el formulario.")
    else:
        form = EmpleadoAltaForm()
    return render(
        request, "empleados/empleado_alta.html", {"form": form}
    )


@login_required
@permiso_requerido("empleados", "modificar")
def empleado_modificacion(request, pk):
    empleado = get_object_or_404(Empleado, pk=pk)
    if not puede_gestionar(request.user, _nivel_empleado(empleado)):
        messages.error(request, _SIN_NIVEL_EMPLEADO)
        return redirect("empleados:empleado_listar")

    if request.method == "POST":
        form = EmpleadoModificacionForm(request.POST, instance=empleado)

        if form.is_valid():
            cargo = form.cleaned_data.get("cargo")
            if cargo and not puede_gestionar(request.user, cargo.nivel_acceso):
                messages.error(request, _SIN_NIVEL_CARGO)
                return redirect("empleados:empleado_modificacion", pk=pk)
            valores_viejos = f"Nombre: {empleado.nombre_empleado}, Apellido: {empleado.apellido_empleado}, Correo: {empleado.correo}"
            empleado_guardado = form.save(commit=True)
            if empleado_guardado.user:
                user = empleado_guardado.user
                user.first_name = empleado_guardado.nombre_empleado
                user.last_name = empleado_guardado.apellido_empleado
                user.email = empleado_guardado.correo
                user.save() 
            valores_nuevos = f"Nombre: {empleado_guardado.nombre_empleado}, Apellido: {empleado_guardado.apellido_empleado}, Correo: {empleado_guardado.correo}"

            LogAuditoria.objects.create(
                tabla="Empleado",
                accion="MODIFICAR",
                registro_id=empleado_guardado.id_empleado,
                valores_anteriores=valores_viejos,
                valores_actuales=valores_nuevos,
                empleado=request.user.empleado,
            )

            messages.success(
                request,
                f'Empleado "{empleado_guardado.nombre_empleado}" actualizado correctamente',
            )
            return redirect("empleados:empleado_listar")
    else:
        form = EmpleadoModificacionForm(instance=empleado)

    return render(
        request,
        "empleados/empleado_modificar.html",
        {"form": form, "empleado": empleado},
    )


@login_required
@permiso_requerido("empleados", "eliminar")
def empleado_baja(request, pk):
    empleado = get_object_or_404(Empleado, pk=pk)
    if empleado.user == request.user:
        messages.error(request, "No puedes darte de baja a ti mismo")
        return redirect("empleados:empleado_listar")
    if not puede_gestionar(request.user, _nivel_empleado(empleado)):
        messages.error(request, _SIN_NIVEL_EMPLEADO)
        return redirect("empleados:empleado_listar")

    if request.method == "POST":
        motivo = request.POST.get("motivo_cambio", "Baja desde el listado")
        empleado.dar_baja()

        LogAuditoria.objects.create(
            tabla="Empleado",
            accion="MODIFICAR",
            registro_id=empleado.id_empleado,
            valores_anteriores="Estado: Activo",
            valores_actuales=f"Estado: Dado de baja. Motivo: {motivo}",
            empleado=request.user.empleado,
        )
        messages.success(
            request, f"Empleado {empleado.user_auto} dado de baja exitosamente."
        )
        return redirect("empleados:empleado_listar")

    return render(
        request,
        "empleados/empleado_baja.html",
        {
            "empleado": empleado,
            "titulo": f"Dar de baja Empleado - {empleado.user_auto}",
        },
    )


@login_required
@permiso_requerido("empleados", "modificar")
def empleado_reactivar(request, pk):
    empleado = get_object_or_404(Empleado, pk=pk)
    if not puede_gestionar(request.user, _nivel_empleado(empleado)):
        messages.error(request, _SIN_NIVEL_EMPLEADO)
        return redirect("empleados:empleado_listar")

    if request.method == "POST":
        motivo = request.POST.get("motivo_cambio", "Reactivación desde el listado")
        empleado.reactivar()
        LogAuditoria.objects.create(
            tabla="Empleado",
            accion="MODIFICAR",
            registro_id=empleado.id_empleado,
            valores_anteriores="Estado: Inactivo",
            valores_actuales=f"Estado: Reactivado. Motivo: {motivo}",
            empleado=request.user.empleado,
        )

        messages.success(
            request, f"Empleado {empleado.user_auto} reactivado exitosamente."
        )
        return redirect("empleados:empleado_listar")

    return redirect("empleados:empleado_listar")


@login_required
@permiso_requerido("empleados", "leer")
def empleado_detalle(request, pk):
    empleado = get_object_or_404(Empleado, pk=pk)
    return render(
        request,
        "empleados/empleado_detalle.html",
        {"empleado": empleado, "titulo": f"Detalle Empleado - {empleado.user_auto}"},
    )


@login_required
@permiso_requerido("empleados", "modificar")
def empleado_restablecer_contrasena(request, pk):
    empleado = get_object_or_404(Empleado, pk=pk)
    if not puede_gestionar(request.user, _nivel_empleado(empleado)):
        messages.error(request, _SIN_NIVEL_EMPLEADO)
        return redirect("empleados:empleado_listar")
    if request.method == "POST":
        form = RestablecerContrasenaForm(request.POST)
        if form.is_valid():
            nueva_contrasena = form.cleaned_data.get("nueva_contrasena")

            empleado.cambiar_contrasena(nueva_contrasena)
            LogAuditoria.objects.create(
                tabla="Empleado",
                accion="MODIFICAR",
                registro_id=empleado.id_empleado,
                valores_anteriores="",
                valores_actuales=f"Contraseña restablecida para {empleado.user_auto}",
                empleado=request.user.empleado,
            )
            messages.success(
                request, f"Contraseña restablecida para {empleado.user_auto}"
            )
            return redirect("empleados:empleado_listar")
        else:
            messages.error(request, "Por favor corrija los errores en el formulario.")
    else:
        form = RestablecerContrasenaForm()
    return render(
        request,
        "restablecer_contrasena.html",
        {
            "form": form,
            "empleado": empleado,
            "titulo": f"Restablecer Contraseña - {empleado.user_auto}",
        },
    )


def login_view(request):
    if request.method == "POST":
        identificador = request.POST.get(
            "username"
        )  # Puede ser usuario, correo o nombre
        password = request.POST.get("password")

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
                            apellido_empleado__iexact=partes[1],
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
                                nombre_empleado__iexact=partes[1],
                            )
                            if empleado.user:
                                username_real = empleado.user.username
                        except Empleado.DoesNotExist:
                            pass

        # Autenticar al usuario
        if username_real:
            user = authenticate(request, username=username_real, password=password)
            if user is not None:
                login(request, user)
                # Verificar si debe cambiar la contraseña
                try:
                    empleado = user.empleado
                    if empleado.debe_cambiar_contrasena:
                        messages.warning(
                            request, "Debes cambiar tu contraseña antes de continuar."
                        )
                        return redirect("empleados:cambiar_clave_obligatorio")
                except Empleado.DoesNotExist:
                    pass
                return redirect("home")
        messages.error(request, "Usuario, correo o contraseña incorrectos")
    return render(request, "login.html")


@login_required
def cambiar_clave_obligatorio(request):
    empleado = request.user.empleado
    if not empleado.debe_cambiar_contrasena:
        return redirect("empleados:empleado_listar")
    if request.method == "POST":
        nueva = request.POST.get("nueva_contrasena")
        confirmar = request.POST.get("confirmar_contrasena")
        if nueva and confirmar and nueva == confirmar:
            if len(nueva) >= 8:
                request.user.set_password(nueva)
                request.user.save()
                empleado.debe_cambiar_contrasena = False
                empleado.save()
                update_session_auth_hash(request, request.user)
                messages.success(request, "Contraseña actualizada exitosamente")
                return redirect("login")
            else:
                messages.error(
                    request, " La contraseña debe tener al menos 8 caracteres"
                )
        else:
            messages.error(request, "Las contraseñas no coinciden")
    return render(request, "cambiar_clave_obligatorio.html")


# CUENTA DEL USUARIO
_MODULOS_PERMISOS = [
    ("platos", "Platos", "restaurant"),
    ("bebidas", "Bebidas", "local_bar"),
    ("ingredientes", "Ingredientes", "grocery"),
    ("categorias", "Categorías", "category"),
    ("empleados", "Empleados", "groups"),
    ("cargos", "Cargos", "badge"),
    ("mesas", "Mesas", "table_restaurant"),
    ("comandas", "Comandas", "receipt_long"),
    ("reportes", "Reportes", "bar_chart"),
    ("auditoria", "Auditoría", "history"),
]
_ACCIONES_PERMISOS = [
    ("leer", "Ver"),
    ("escribir", "Crear"),
    ("modificar", "Editar"),
    ("eliminar", "Eliminar"),
]


def _empleado_de(user):
    try:
        return user.empleado
    except Empleado.DoesNotExist:
        return None


@login_required
def mi_perfil(request):
    empleado = _empleado_de(request.user)
    form = None

    if empleado and request.method == "POST":
        valores_viejos = f"Correo: {empleado.correo}, Teléfono: {empleado.telefono or ''}"
        form = MiPerfilForm(request.POST, instance=empleado)
        if form.is_valid():
            with transaction.atomic():
                empleado = form.save()
                request.user.email = empleado.correo
                request.user.save(update_fields=["email"])
                LogAuditoria.objects.create(
                    tabla="Empleado",
                    accion="MODIFICAR",
                    registro_id=empleado.id_empleado,
                    valores_anteriores=valores_viejos,
                    valores_actuales=f"Correo: {empleado.correo}, Teléfono: {empleado.telefono or ''}",
                    empleado=empleado,
                )
            messages.success(request, "Tus datos se actualizaron correctamente.")
            return redirect("empleados:mi_perfil")
        # Los valores rechazados no deben verse como si estuvieran guardados
        empleado.refresh_from_db()
    elif empleado and request.GET.get("editar"):
        form = MiPerfilForm(instance=empleado)

    return render(
        request, "cuenta/mi_perfil.html", {"empleado": empleado, "form": form}
    )


@login_required
def cambiar_contrasena(request):
    if request.method == "POST":
        form = CambiarContrasenaForm(request.user, request.POST)
        if form.is_valid():
            with transaction.atomic():
                form.save()
                empleado = _empleado_de(request.user)
                if empleado:
                    if empleado.debe_cambiar_contrasena:
                        empleado.debe_cambiar_contrasena = False
                        empleado.save()
                    LogAuditoria.objects.create(
                        tabla="Empleado",
                        accion="MODIFICAR",
                        registro_id=empleado.id_empleado,
                        valores_anteriores="",
                        valores_actuales="Cambió su propia contraseña",
                        empleado=empleado,
                    )
            update_session_auth_hash(request, form.user)
            messages.success(request, "Tu contraseña se actualizó correctamente.")
            return redirect("empleados:mi_perfil")
    else:
        form = CambiarContrasenaForm(request.user)
    return render(request, "cuenta/cambiar_contrasena.html", {"form": form})


@login_required
def mis_permisos(request):
    nivel = nivel_de(request.user)
    es_admin = nivel >= NIVEL_ADMINISTRADOR
    asignados = set(
        PermisoXCargo.objects.filter(cargo__empleado__user=request.user).values_list(
            "tipo_permiso__modulo", "tipo_permiso__accion"
        )
    )
    modulos = []
    for clave, nombre, icono in _MODULOS_PERMISOS:
        acciones = [
            {"nombre": etiqueta, "permitida": es_admin or (clave, accion) in asignados}
            for accion, etiqueta in _ACCIONES_PERMISOS
        ]
        modulos.append(
            {
                "nombre": nombre,
                "icono": icono,
                "acciones": acciones,
                "con_acceso": any(a["permitida"] for a in acciones),
            }
        )
    empleado = _empleado_de(request.user)
    return render(
        request,
        "cuenta/mis_permisos.html",
        {
            "modulos": modulos,
            "es_admin": es_admin,
            "nivel": nivel,
            "cargo": empleado.cargo if empleado else None,
        },
    )


# VISTAS PARA CARGOS
@login_required
@permiso_requerido("cargos", "leer")
def cargo_listar(request):
    cargos = Cargo.objects.all().order_by("nombre_cargo")
    referer = request.META.get("HTTP_REFERER", "")

    buscar = request.GET.get("buscar", "").strip()
    if buscar:
        cargos = cargos.filter(nombre_cargo__icontains=buscar)

    por_pagina = request.GET.get("por_pagina", 10)
    try:
        por_pagina = int(por_pagina)
        if por_pagina not in [10, 25, 50, 100]:
            por_pagina = 10
    except (ValueError, TypeError):
        por_pagina = 10

    paginator = Paginator(cargos, por_pagina)
    page_number = request.GET.get("page")
    cargos = paginator.get_page(page_number)
    return render(
        request,
        "cargos/listar_cargos.html",
        {
            "cargos": cargos,
            "por_pagina": por_pagina,
            "buscar": buscar,
            "viene_de_empleados": "/empleados/listar/" in referer,
        },
    )


@login_required
@permiso_requerido("cargos", "escribir")
def cargo_crear(request):
    if request.method == "POST":
        form = CargoForm(request.POST)
        if form.is_valid():
            if not puede_gestionar(request.user, int(form.cleaned_data["nivel_acceso"])):
                messages.error(request, _SIN_NIVEL_CARGO)
                return render(request, "cargos/crear_cargo.html", {"form": form})
            cargo = form.save()

            LogAuditoria.objects.create(
                tabla="Cargo",
                accion="CREAR",
                registro_id=cargo.id_cargo,
                valores_anteriores="",
                valores_actuales=f"Cargo creado: {cargo.nombre_cargo}",
                empleado=request.user.empleado,
            )

            messages.success(request, "Cargo creado exitosamente")
            return redirect("empleados:listar_cargo")
    else:
        form = CargoForm()
    return render(
        request,
        "cargos/crear_cargo.html",
        {
            "form": form,
        },
    )


@login_required
@permiso_requerido("cargos", "modificar")
def cargo_editar(request, pk):
    cargo = get_object_or_404(Cargo, pk=pk)
    if not puede_gestionar(request.user, cargo.nivel_acceso):
        messages.error(request, _SIN_NIVEL_CARGO)
        return redirect("empleados:listar_cargo")
    if request.method == "POST":
        form = CargoForm(request.POST, instance=cargo)
        if form.is_valid():
            if not puede_gestionar(request.user, int(form.cleaned_data["nivel_acceso"])):
                messages.error(request, _SIN_NIVEL_CARGO)
                return redirect("empleados:editar_cargo", pk=pk)
            valores_viejos = f"Nombre: {cargo.nombre_cargo}"
            form.save()
            valores_nuevos = f"Nombre: {cargo.nombre_cargo}"

            LogAuditoria.objects.create(
                tabla="Cargo",
                accion="MODIFICAR",
                registro_id=cargo.id_cargo,
                valores_anteriores=valores_viejos,
                valores_actuales=valores_nuevos,
                empleado=request.user.empleado,
            )
            messages.success(request, "Cargo actualizado exitosamente")
            return redirect("empleados:listar_cargo")
    else:
        form = CargoForm(instance=cargo)
    return render(
        request,
        "cargos/editar_cargo.html",
        {
            "form": form,
            "cargo": cargo,
        },
    )


@login_required
@permiso_requerido("cargos", "eliminar")
def cargo_eliminar(request, pk):
    cargo = get_object_or_404(Cargo, pk=pk)
    if not puede_gestionar(request.user, cargo.nivel_acceso):
        messages.error(request, _SIN_NIVEL_CARGO)
        return redirect("empleados:listar_cargo")
    if cargo.empleado_set.exists():
        messages.error(
            request,
            f'No se puede eliminar el cargo "{cargo.nombre_cargo}" porque tiene empleados asignados.',
        )
        return redirect("empleados:listar_cargo")
    if request.method == "POST":
        nombre = cargo.nombre_cargo
        cargo.delete()
        messages.success(request, f'Cargo "{nombre}" eliminado')
        return redirect("empleados:listar_cargo")
    return render(request, "cargos/eliminar_cargo.html", {"cargo": cargo})


# VISTAS PARA PERMISOS
@login_required
@permiso_requerido("cargos", "leer")
def permiso_listar(request):
    permisos = TipoPermiso.objects.all().order_by("modulo", "accion")
    buscar = request.GET.get("buscar", "").strip()
    modulos = request.GET.getlist("modulo")
    acciones = request.GET.getlist("accion")
    referer = request.META.get("HTTP_REFERER", "")

    if buscar:
        permisos = permisos.filter(
            Q(modulo__icontains=buscar) | Q(accion__icontains=buscar)
        )

    if modulos:
        permisos = permisos.filter(modulo__in=modulos)

    if acciones:
        permisos = permisos.filter(accion__in=acciones)

    modulos_disponibles = TipoPermiso.objects.values_list(
        "modulo", flat=True
    ).distinct()
    acciones_disponibles = TipoPermiso.objects.values_list(
        "accion", flat=True
    ).distinct()

    por_pagina = request.GET.get("por_pagina", 10)
    try:
        por_pagina = int(por_pagina)
        if por_pagina not in [10, 25, 50, 100]:
            por_pagina = 10
    except (ValueError, TypeError):
        por_pagina = 10

    paginator = Paginator(permisos, por_pagina)
    page_number = request.GET.get("page")
    permisos = paginator.get_page(page_number)
    return render(
        request,
        "permisos/listar_permiso.html",
        {
            "permisos": permisos,
            "por_pagina": por_pagina,
            "buscar": buscar,
            "modulos_seleccionados": modulos,
            "acciones_seleccionadas": acciones,
            "modulos": modulos_disponibles,
            "acciones": acciones_disponibles,
            "viene_de_empleados": "/empleados/listar/" in referer,
        },
    )


@login_required
@permiso_requerido("cargos", "escribir")
def permiso_crear(request):
    if request.method == "POST":
        form = PermisoForm(request.POST)
        if form.is_valid():
            permiso = form.save()

            LogAuditoria.objects.create(
                tabla="Permiso",
                accion="CREAR",
                registro_id=permiso.id_tipo_permiso,
                valores_anteriores="",
                valores_actuales=f"Permiso creado: Módulo {permiso.modulo} - Acción {permiso.accion}",
                empleado=request.user.empleado,
            )
            messages.success(request, "Permiso creado exitosamente")
            return redirect("empleados:listar_permiso")
        else:
            messages.error(request, "Error al crear el permiso. Revisá los datos.")
    else:
        form = PermisoForm()

    return render(
        request,
        "permisos/crear_permiso.html",
        {"form": form, "titulo": "Crear Permiso"},
    )


@login_required
@permiso_requerido("cargos", "eliminar")
def permiso_eliminar(request, pk):
    permiso = get_object_or_404(TipoPermiso, pk=pk)
    # Borrar un permiso se lo quita a todos los cargos, incluso a los de nivel superior
    if not es_administrador(request.user):
        messages.error(request, "Solo un administrador puede eliminar permisos.")
        return redirect("empleados:listar_permiso")
    if request.method == "POST":
        descripcion = str(permiso)
        permiso.delete()
        messages.success(request, f'Permiso "{descripcion}" eliminado')
        return redirect("empleados:listar_permiso")
    return render(request, "permisos/eliminar_permiso.html", {"permiso": permiso})


# VISTAS PARA ASIGNAR PERMISOS A CARGOS


@login_required
@permiso_requerido("cargos", "modificar")
def asignar_permisos(request):
    if request.method == "POST":
        cargo_id = request.POST.get("cargo")
        permisos_ids = request.POST.getlist("permisos")
        cargo = get_object_or_404(Cargo, pk=cargo_id)
        if not puede_gestionar(request.user, cargo.nivel_acceso):
            messages.error(request, _SIN_NIVEL_CARGO)
            return redirect("empleados:asignar_permisos")
        # La misma regla que usa la app: nadie reparte permisos que no tiene
        try:
            permisos_viejos_str, permisos_nuevos_str = asignar_permisos_a_cargo(
                request.user, cargo, permisos_ids
            )
        except (ValueError, PermissionError) as error:
            messages.error(request, str(error))
            return redirect("empleados:asignar_permisos")

        LogAuditoria.objects.create(
            tabla="Cargo",
            accion="MODIFICAR",
            registro_id=cargo.id_cargo,
            valores_anteriores=f"Permisos: {permisos_viejos_str}",
            valores_actuales=f"Permisos: {permisos_nuevos_str}",
            empleado=request.user.empleado,
        )
        messages.success(request, f'Permisos asignados a "{cargo.nombre_cargo}"')
        return redirect("empleados:ver_permisos_cargo", pk=cargo.pk)
    cargos = Cargo.objects.all().order_by("nombre_cargo")
    permisos = TipoPermiso.objects.all().order_by("modulo", "accion")

    # Obtener permisos ya asignados
    permisos_asignados_por_cargo = {}
    for cargo in cargos:
        permisos_asignados_por_cargo[cargo.pk] = list(
            PermisoXCargo.objects.filter(cargo=cargo).values_list(
                "tipo_permiso_id", flat=True
            )
        )
    return render(
        request,
        "permisos/asignar_permisos.html",
        {
            "cargos": cargos,
            "permisos": permisos,
            "permisos_asignados": permisos_asignados_por_cargo,
            "titulo": "Asignar Permisos a Cargos",
        },
    )


@login_required
@permiso_requerido("cargos", "leer")
def ver_permisos_cargo(request, pk):
    cargo = get_object_or_404(Cargo, pk=pk)
    permisos = TipoPermiso.objects.filter(permisoxcargo__cargo=cargo).order_by(
        "modulo", "accion"
    )

    return render(
        request,
        "permisos/ver_permisos_cargo.html",
        {"cargo": cargo, "permisos": permisos},
    )


@login_required
@permiso_requerido("empleados", "leer")
def listar_asistencias(request):
    if request.method == "POST":
        if not tiene_permiso(request.user, "empleados", "escribir"):
            messages.error(request, "No tenés permiso para registrar asistencias.")
            return redirect("empleados:listar_asistencias")

        empleado_id = request.POST.get("empleado", "")
        tipo_id = request.POST.get("tipo_asistencia", "")
        # La fecha de Salta: la de timezone.now() ya es mañana después de las 21:00
        hoy = timezone.localdate()

        if not (
            empleado_id.isdigit()
            and tipo_id.isdigit()
            and Empleado.objects.filter(pk=empleado_id, estado=True).exists()
            and TipoAsistencia.objects.filter(pk=tipo_id).exists()
        ):
            messages.error(request, "Debe seleccionar un empleado y un turno.")
            return redirect("empleados:listar_asistencias")

        # Validar que no se duplique
        if Asistencia.objects.filter(
            id_empleado_id=empleado_id, fecha_asistencia=hoy
        ).exists():
            messages.error(
                request, "Este empleado ya tiene una asistencia registrada hoy."
            )
        else:
            asistencia = Asistencia.objects.create(
                id_empleado_id=empleado_id,
                id_tipo_asistencia_id=tipo_id,
                fecha_asistencia=hoy,
            )

            # Auditoría
            LogAuditoria.objects.create(
                tabla="Asistencia",
                accion="CREAR",
                registro_id=asistencia.id_asistencia,
                valores_anteriores="",
                valores_actuales=f"Asistencia registrada: {asistencia.id_empleado.nombre_empleado}. Fecha: {hoy}. Turno: {asistencia.id_tipo_asistencia.nombre_tipo_asis}",
                empleado=request.user.empleado,
            )
            messages.success(request, "Asistencia registrada correctamente.")

        return redirect("empleados:listar_asistencias")

    asistencias = (
        Asistencia.objects.all()
        .select_related("id_empleado", "id_tipo_asistencia")
        .order_by("-fecha_asistencia")
    )

    # Filtros
    buscar = request.GET.get("buscar", "").strip()
    fecha_desde, fecha_hasta = limitar_rango(
        request.GET.get("fecha_desde", ""), request.GET.get("fecha_hasta", "")
    )
    tipo_asistencia = request.GET.get("tipo_asistencia", "")

    if buscar:
        asistencias = asistencias.filter(
            Q(id_empleado__nombre_empleado__icontains=buscar)
            | Q(id_empleado__apellido_empleado__icontains=buscar)
        )
    if fecha_desde:
        asistencias = asistencias.filter(fecha_asistencia__gte=fecha_desde)
    if fecha_hasta:
        asistencias = asistencias.filter(fecha_asistencia__lte=fecha_hasta)
    if tipo_asistencia:
        asistencias = asistencias.filter(id_tipo_asistencia_id=tipo_asistencia)

    # Paginación
    por_pagina = request.GET.get("por_pagina", 10)
    try:
        por_pagina = int(por_pagina)
        if por_pagina not in [10, 25, 50, 100]:
            por_pagina = 10
    except (ValueError, TypeError):
        por_pagina = 10

    paginator = Paginator(asistencias, por_pagina)
    page_number = request.GET.get("page")
    asistencias_paginadas = paginator.get_page(page_number)

    # Datos para el modal
    empleados_activos = Empleado.objects.filter(estado=True).order_by("nombre_empleado")
    tipos = TipoAsistencia.objects.all().order_by("nombre_tipo_asis")
    hoy = timezone.localdate().strftime("%d/%m/%Y")
    hoy_iso = timezone.localdate().strftime("%Y-%m-%d")

    return render(
        request,
        "asistencias/listar_asistencia.html",
        {
            "asistencias": asistencias_paginadas,
            "empleados_activos": empleados_activos,
            "tipos": tipos,
            "hoy": hoy,
            'hoy_iso' : hoy_iso,
            "buscar": buscar,
            "fecha_desde": fecha_desde,
            "fecha_hasta": fecha_hasta,
            "tipo_seleccionado": tipo_asistencia,
            "por_pagina": por_pagina,
        },
    )


@login_required
@permiso_requerido("empleados", "modificar")
def editar_asistencia(request, pk):
    asistencia = get_object_or_404(Asistencia, pk=pk)

    if request.method == "POST":
        tipo_id_nuevo = request.POST.get("tipo_asistencia")
        valores_viejos = f"Empleado: {asistencia.id_empleado.nombre_empleado}, Fecha: {asistencia.fecha_asistencia}, Turno: {asistencia.id_tipo_asistencia.nombre_tipo_asis}"

        asistencia.id_tipo_asistencia_id = tipo_id_nuevo
        asistencia.save()

        valores_nuevos = f"Empleado: {asistencia.id_empleado.nombre_empleado}, Fecha: {asistencia.fecha_asistencia}, Turno: {asistencia.id_tipo_asistencia.nombre_tipo_asis}"

        LogAuditoria.objects.create(
            tabla="Asistencia",
            accion="MODIFICAR",
            registro_id=asistencia.id_asistencia,
            valores_anteriores=valores_viejos,
            valores_actuales=valores_nuevos,
            empleado=request.user.empleado,
        )

        messages.success(request, "Asistencia actualizada correctamente.")
        return redirect("empleados:listar_asistencias")

    return redirect("empleados:listar_asistencias")


@login_required
@permiso_requerido("empleados", "eliminar")
def anular_asistencia(request, pk):
    asistencia = get_object_or_404(Asistencia, pk=pk)

    if request.method == "POST":
        LogAuditoria.objects.create(
            tabla="Asistencia",
            accion="ANULAR",
            registro_id=asistencia.id_asistencia,
            valores_anteriores=f"Asistencia anulada: {asistencia.id_empleado.nombre_empleado}. Fecha: {asistencia.fecha_asistencia}. Turno: {asistencia.id_tipo_asistencia.nombre_tipo_asis}",
            valores_actuales="",
            empleado=request.user.empleado,
        )

        asistencia.delete()
        messages.success(request, "Asistencia anulada correctamente.")
    return redirect("empleados:listar_asistencias")

@login_required
@permiso_requerido("empleados", "leer")
def listar_tipos_asistencia(request):
    tipos = TipoAsistencia.objects.all().order_by("nombre_tipo_asis")
    buscar = request.GET.get("buscar", "").strip()
    if buscar:
        tipos = tipos.filter(nombre_tipo_asis__icontains=buscar)

    por_pagina = request.GET.get("por_pagina", 10)
    try:
        por_pagina = int(por_pagina)
        if por_pagina not in [10, 25, 50, 100]:
            por_pagina = 10
    except (ValueError, TypeError):
        por_pagina = 10

    paginator = Paginator(tipos, por_pagina)
    page_number = request.GET.get("page")
    tipos_paginados = paginator.get_page(page_number)

    return render(
        request,
        "tipos_asistencia/listar.html",
        {"tipos": tipos_paginados, "buscar": buscar, "por_pagina": por_pagina},
    )


@login_required
@permiso_requerido("empleados", "escribir")
def crear_tipo_asistencia(request):
    if request.method == "POST":
        nombre = request.POST.get("nombre_tipo_asis", "").strip().title()
        descripcion = request.POST.get("desc_tipo_asis", "").strip()

        if TipoAsistencia.objects.filter(nombre_tipo_asis=nombre).exists():
            messages.error(request, f'El turno "{nombre}" ya existe.')
        else:
            tipo = TipoAsistencia.objects.create(
                nombre_tipo_asis=nombre,
                desc_tipo_asistencia=descripcion,
            )

            LogAuditoria.objects.create(
                tabla="TipoAsistencia",
                accion="CREAR",
                registro_id=tipo.id_tipo_asistencia,
                valores_anteriores="",
                valores_actuales=f"Tipo de turno creado: {tipo.nombre_tipo_asis}. Descripción: {descripcion}",
                empleado=request.user.empleado,
            )
            messages.success(request, f'Turno "{nombre}" creado exitosamente.')
            return redirect("empleados:listar_tipos_asistencia")

    return render(request, "tipos_asistencia/crear.html")


@login_required
@permiso_requerido("empleados", "modificar")
def editar_tipo_asistencia(request, pk):
    tipo = get_object_or_404(TipoAsistencia, pk=pk)

    if request.method == "POST":
        nombre = request.POST.get("nombre_tipo_asis", "").strip().title()
        descripcion = request.POST.get("desc_tipo_asis", "").strip()

        if (
            TipoAsistencia.objects.filter(nombre_tipo_asis=nombre)
            .exclude(pk=pk)
            .exists()
        ):
            messages.error(request, f'El turno "{nombre}" ya existe.')
        else:
            valores_viejos = f"Nombre: {tipo.nombre_tipo_asis}, Descripción: {tipo.desc_tipo_asistencia}"

            tipo.nombre_tipo_asis = nombre
            tipo.desc_tipo_asistencia = descripcion
            tipo.save()

            valores_nuevos = f"Nombre: {tipo.nombre_tipo_asis}, Descripción: {tipo.desc_tipo_asistencia}"

            LogAuditoria.objects.create(
                tabla="TipoAsistencia",
                accion="MODIFICAR",
                registro_id=tipo.id_tipo_asistencia,
                valores_anteriores=valores_viejos,
                valores_actuales=valores_nuevos,
                empleado=request.user.empleado,
            )
            messages.success(request, f'Turno "{nombre}" actualizado exitosamente.')
            return redirect("empleados:listar_tipos_asistencia")

    return render(request, "tipos_asistencia/editar.html", {"tipo": tipo})


@login_required
@permiso_requerido("empleados", "eliminar")
def eliminar_tipo_asistencia(request, pk):
    tipo = get_object_or_404(TipoAsistencia, pk=pk)

    if request.method == "POST":
        motivo = request.POST.get("motivo_cambio", "Sin motivo especificado")

        if tipo.asistencia_set.exists():
            messages.error(
                request,
                f'No se puede eliminar el turno "{tipo.nombre_tipo_asis}" porque tiene asistencias registradas.',
            )
            return redirect("empleados:listar_tipos_asistencia")

        LogAuditoria.objects.create(
            tabla="TipoAsistencia",
            accion="ANULAR",
            registro_id=tipo.id_tipo_asistencia,
            valores_anteriores=f"Turno eliminado: {tipo.nombre_tipo_asis}",
            valores_actuales=f"Motivo de eliminación: {motivo}",
            empleado=request.user.empleado,  # <-- CORREGIDO: faltaba esto
        )

        nombre = tipo.nombre_tipo_asis
        tipo.delete()
        messages.success(request, f'Turno "{nombre}" eliminado exitosamente.')
        return redirect("empleados:listar_tipos_asistencia")

    return redirect("empleados:listar_tipos_asistencia")
