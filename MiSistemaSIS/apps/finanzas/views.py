from django.shortcuts import render
from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator
from .models import metodo_pago, categoria_gasto, caja, gasto, Venta
from django.contrib.auth import authenticate, login
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required,user_passes_test
from django.contrib import messages
import re
from django.db.models import Q, Sum
from empleados.decorators import permiso_requerido
from decimal import Decimal, InvalidOperation
from django.db import transaction
from django.utils import timezone
from .models import caja
from empleados.models import Empleado
from ventas.models import Comanda, Mesa, Pago
from django.utils.dateparse import parse_date
from datetime import datetime, time, timedelta
from django.utils import timezone
from auditoria.models import LogAuditoria
from core.mensajes import error_campo
from django.urls import reverse
@login_required
def finanzas_home(request):
    return render(request, 'finanzas_home.html')

# FUNCIONES PARA CATEGORÍAS DE GASTOS
@login_required
@permiso_requerido('caja', 'leer')
def listar_cat_gasto(request):
    cat_gasto = categoria_gasto.objects.all().order_by('nombre_categoria_gasto')

    buscar = request.GET.get('buscar','').strip()
    estados = request.GET.getlist('estado')
    
    if buscar:
      cat_gasto = cat_gasto.filter(nombre_categoria_gasto__icontains=buscar)

    if estados:
      q_estado = Q()
      if 'activo' in estados:
          q_estado |= Q(estado_categoria_gasto=True)
      if 'inactivo' in estados:
          q_estado |= Q(estado_categoria_gasto=False)
      if q_estado:
          cat_gasto = cat_gasto.filter(q_estado)

      # Por paginacion
    por_pagina = request.GET.get('por_pagina', 10)
    try:
        por_pagina = int(por_pagina)
        if por_pagina not in [10, 25, 50, 100]:
            por_pagina = 10
    except (ValueError, TypeError):
        por_pagina = 10
    
    paginator = Paginator(cat_gasto, por_pagina)
    page_number = request.GET.get('page')
    cat_gasto = paginator.get_page(page_number)
    
    return render(request, 'CATEGORIA_GASTOS/listar_cat_gasto.html', {
        'categorias': cat_gasto, 'por_pagina': por_pagina, 'buscar': buscar, 'estados_seleccionados': estados, })



@login_required
@permiso_requerido('caja', 'escribir')
def crear_cat_gasto(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        descripcion = request.POST.get('descripcion', '').strip()
        if not nombre:
            error_campo(
                    request, "nombre", 'El nombre de la categoría es obligatorio.'
            )
            return render(
                request,
                'CATEGORIA_GASTOS/crear_cat_gasto.html'
            )
        nombre = nombre.title()
        if categoria_gasto.objects.filter(
            nombre_categoria_gasto__iexact=nombre
        ).exists():
            error_campo(
                    request, "nombre", 'Ya existe una categoría con ese nombre.'
            )
            return render(
                request,
                'CATEGORIA_GASTOS/crear_cat_gasto.html'
            )
        # Crear la categoría y obtener el objeto creado.
        categoria = categoria_gasto.objects.create(
            nombre_categoria_gasto=nombre,
            descripcion_categoria_gasto=descripcion
        )
        # Registrar la creación en la auditoría.
        LogAuditoria.objects.create(
            tabla="Categoria gastos",
            accion="CREAR",
            registro_id=categoria.pk,
            valores_anteriores="",
            valores_actuales=(
                f"Nombre: {categoria.nombre_categoria_gasto}, "
                f"Descripción: {categoria.descripcion_categoria_gasto}, "
                f"Estado: {categoria.estado_categoria_gasto}"
            ),
            empleado=request.user.empleado,
        )
        messages.success(
            request,
            f'Categoría "{nombre}" creada correctamente.'
        )
        return redirect('finanzas:listar_cat_gasto')
    return render(
        request,
        'CATEGORIA_GASTOS/crear_cat_gasto.html'
    )


@login_required
@permiso_requerido('caja', 'modificar')
def editar_cat_gasto(request, pk):
    categoria = get_object_or_404(categoria_gasto, pk=pk)

    # Impedir la modificación si ya fue utilizada.
    if categoria.gastos.exists():
        messages.error(
            request,
            'No se puede modificar esta categoría porque ya tiene gastos asociados.'
        )
        return redirect('finanzas:listar_cat_gasto')

    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        descripcion = request.POST.get('descripcion', '').strip()

        if not nombre:
            error_campo(
                    request, "nombre", 'El nombre es obligatorio.')

        elif categoria_gasto.objects.filter(
            nombre_categoria_gasto__iexact=nombre
        ).exclude(pk=categoria.pk).exists():
            error_campo(
                    request, "nombre", 'Ya existe una categoría con ese nombre.'
            )

        else:
            nombre = nombre.title()

            # Capturar los valores anteriores antes de modificar.
            valores_anteriores = (
                f"Nombre: {categoria.nombre_categoria_gasto}, "
                f"Descripción: {categoria.descripcion_categoria_gasto}, "
                f"Estado: {categoria.estado_categoria_gasto}"
            )

            # Preparar los valores nuevos.
            valores_actuales = (
                f"Nombre: {nombre}, "
                f"Descripción: {descripcion}, "
                f"Estado: {categoria.estado_categoria_gasto}"
            )

            # Guardar y auditar dentro de la misma transacción.
            with transaction.atomic():
                hubo_cambios = (
                    categoria.nombre_categoria_gasto != nombre
                    or categoria.descripcion_categoria_gasto != descripcion
                )

                categoria.nombre_categoria_gasto = nombre
                categoria.descripcion_categoria_gasto = descripcion
                categoria.save()

                # Registrar únicamente si hubo cambios reales.
                if hubo_cambios:
                    LogAuditoria.objects.create(
                        tabla="Categoria gastos",
                        accion="MODIFICAR",
                        registro_id=categoria.pk,
                        valores_anteriores=valores_anteriores,
                        valores_actuales=valores_actuales,
                        empleado=request.user.empleado,
                    )

            messages.success(
                request,
                'Categoría actualizada correctamente.'
            )
            return redirect('finanzas:listar_cat_gasto')

    return render(
        request,
        'CATEGORIA_GASTOS/editar_cat_gasto.html',
        {'categoria': categoria}
    )



@login_required
@permiso_requerido('caja', 'eliminar')
def eliminar_cat_gasto(request, pk):
    categoria = get_object_or_404(categoria_gasto, pk=pk)

    # Impedir la eliminación si existen gastos asociados.
    if categoria.gastos.exists():
        messages.error(
            request,
            f'No se puede eliminar la categoría '
            f'"{categoria.nombre_categoria_gasto}" '
            'porque está asociada a uno o más gastos.'
        )
        return redirect('finanzas:listar_cat_gasto')

    if request.method == 'POST':
        nombre = categoria.nombre_categoria_gasto

        # Capturar los datos antes de eliminar el registro.
        valores_anteriores = (
            f"Nombre: {categoria.nombre_categoria_gasto}, "
            f"Descripción: {categoria.descripcion_categoria_gasto}, "
            f"Estado: {categoria.estado_categoria_gasto}"
        )

        with transaction.atomic():
            # Registrar la auditoría ANTES de eliminar la categoría.
            LogAuditoria.objects.create(
                tabla="Categoria gastos",
                accion="ANULAR",
                registro_id=categoria.pk,
                valores_anteriores=valores_anteriores,
                valores_actuales=None,
                empleado=request.user.empleado,
            )

            categoria.delete()

        messages.success(
            request,
            f'Categoría "{nombre}" eliminada correctamente.'
        )
        return redirect('finanzas:listar_cat_gasto')

    return render(
        request,
        'CATEGORIA_GASTOS/eliminar_cat_gasto.html',
        {'categoria': categoria}
    )

@login_required
@permiso_requerido('caja', 'leer')
def detalle_cat_gasto(request, pk):
    categoria = get_object_or_404(categoria_gasto, pk=pk)
    gastos = categoria.gastos.all().order_by('-fecha_hora_gasto')
    return render(
        request,
        'CATEGORIA_GASTOS/detalle_cat_gasto.html',
        {
            'categoria': categoria,
            'gastos': gastos,
        }
    )

@login_required
@permiso_requerido('caja', 'modificar')
def estado_categoria(request, pk):
    if request.method != 'POST':
        messages.error(
            request,
            'La operación debe realizarse mediante un formulario.'
        )
        return redirect('finanzas:listar_cat_gasto')

    categoria = get_object_or_404(categoria_gasto, pk=pk)

    estado_anterior = categoria.estado_categoria_gasto
    estado_actual = not estado_anterior

    valores_anteriores = (
        f"Nombre: {categoria.nombre_categoria_gasto}, "
        f"Descripción: {categoria.descripcion_categoria_gasto}, "
        f"Estado: {estado_anterior}"
    )

    valores_actuales = (
        f"Nombre: {categoria.nombre_categoria_gasto}, "
        f"Descripción: {categoria.descripcion_categoria_gasto}, "
        f"Estado: {estado_actual}"
    )

    # Desactivar = ANULAR; reactivar = MODIFICAR.
    accion = 'ANULAR' if estado_anterior else 'MODIFICAR'

    with transaction.atomic():
        categoria.estado_categoria_gasto = estado_actual
        categoria.save(update_fields=['estado_categoria_gasto'])

        LogAuditoria.objects.create(
            tabla="Categoria gastos",
            accion=accion,
            registro_id=categoria.pk,
            valores_anteriores=valores_anteriores,
            valores_actuales=valores_actuales,
            empleado=request.user.empleado,
        )

    if estado_actual:
        messages.success(
            request,
            f'Categoría "{categoria.nombre_categoria_gasto}" activada.'
        )
    else:
        messages.success(
            request,
            f'Categoría "{categoria.nombre_categoria_gasto}" desactivada.'
        )

    return redirect(
        request.META.get(
            'HTTP_REFERER',
            reverse('finanzas:listar_cat_gasto')
        )
    )

# FUNCIONES PARA METODOS DE PAGO
@login_required
@permiso_requerido('caja', 'leer')
def listar_met_pago(request):
    metodos = metodo_pago.objects.all().order_by(
        'nombre_metodo_pago'
    )

    # Búsqueda por nombre
    buscar = request.GET.get('buscar', '').strip()

    if buscar:
        metodos = metodos.filter(
            nombre_metodo_pago__icontains=buscar
        )

    # Filtro por estado
    estados = request.GET.getlist('estado')

    if estados:
        filtros_estado = Q()

        if 'activo' in estados:
            filtros_estado |= Q(estado_metodo_pago=True)

        if 'inactivo' in estados:
            filtros_estado |= Q(estado_metodo_pago=False)

        if filtros_estado:
            metodos = metodos.filter(filtros_estado)

    # Cantidad de registros por página
    opciones_paginacion = [5, 10, 25, 50]

    try:
        por_pagina = int(request.GET.get('por_pagina', 10))
    except (ValueError, TypeError):
        por_pagina = 10

    if por_pagina not in opciones_paginacion:
        por_pagina = 10

    paginator = Paginator(metodos, por_pagina)
    pagina = paginator.get_page(request.GET.get('page'))

    contexto = {
        'metodos_pago': pagina,
        'por_pagina': por_pagina,
        'buscar': buscar,
        'estados_seleccionados': estados,
    }
    
    return render(
        request,
        'METODO_PAGO/listar_met_pago.html',
        contexto
    )


@login_required
@permiso_requerido('caja', 'escribir')
def crear_met_pago(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        descripcion = request.POST.get('descripcion', '').strip()
        permite_cambio = request.POST.get('permite_cambio') == 'on'

        if not nombre:
            error_campo(
                    request, "nombre", 'El nombre del método de pago es obligatorio.'
            )
            return render(request, 'METODO_PAGO/crear_met_pago.html')

        # Evitar nombres duplicados.
        nombre = nombre.title()

        if metodo_pago.objects.filter(
            nombre_metodo_pago__iexact=nombre
        ).exists():
            error_campo(
                    request, "nombre", 'Ya existe un método de pago con ese nombre.'
            )
            return render(request, 'METODO_PAGO/crear_met_pago.html')

        with transaction.atomic():
            # Crear método de pago.
            metodo = metodo_pago.objects.create(
                nombre_metodo_pago=nombre,
                descripcion_metodo_pago=descripcion,
                permite_cambio=permite_cambio,
            )

            # Registrar auditoría.
            LogAuditoria.objects.create(
                tabla="Métodos de pago",
                accion="CREAR",
                registro_id=metodo.pk,
                valores_anteriores="",
                valores_actuales=(
                    f"Nombre: {metodo.nombre_metodo_pago}, "
                    f"Descripción: {metodo.descripcion_metodo_pago}, "
                    f"Permite vuelto: {'Sí' if metodo.permite_cambio else 'No'}, "
                    f"Estado: {metodo.estado_metodo_pago}"
                ),
                empleado=request.user.empleado,
            )

        messages.success(
            request,
            f'Método de pago "{metodo.nombre_metodo_pago}" creado correctamente.'
        )

        return redirect('finanzas:listar_met_pago')

    return render(request, 'METODO_PAGO/crear_met_pago.html')


@login_required
@permiso_requerido('caja', 'modificar')
def editar_met_pago(request, pk):
    metodo = get_object_or_404(metodo_pago, pk=pk)

    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        descripcion = request.POST.get('descripcion', '').strip()
        permite_cambio = request.POST.get('permite_cambio') == 'on'

        if not nombre:
            error_campo(
                    request, "nombre", 'El nombre del método de pago es obligatorio.'
            )

        else:
            nombre = nombre.title()

            if metodo_pago.objects.filter(
                nombre_metodo_pago__iexact=nombre
            ).exclude(pk=metodo.pk).exists():

                error_campo(
                    request, "nombre", 'Ya existe otro método de pago con ese nombre.'
                )

            else:
                # Detectar cambios reales.
                hubo_cambios = (
                    metodo.nombre_metodo_pago != nombre
                    or metodo.descripcion_metodo_pago != descripcion
                    or metodo.permite_cambio != permite_cambio
                )

                if hubo_cambios:
                    # Capturar valores anteriores.
                    valores_anteriores = (
                        f"Nombre: {metodo.nombre_metodo_pago}, "
                        f"Descripción: {metodo.descripcion_metodo_pago}, "
                        f"Permite vuelto: {'Sí' if metodo.permite_cambio else 'No'}, "
                        f"Estado: {metodo.estado_metodo_pago}"
                    )

                    # Preparar valores actuales.
                    valores_actuales = (
                        f"Nombre: {nombre}, "
                        f"Descripción: {descripcion}, "
                        f"Permite vuelto: {'Sí' if permite_cambio else 'No'}, "
                        f"Estado: {metodo.estado_metodo_pago}"
                    )

                    with transaction.atomic():
                        metodo.nombre_metodo_pago = nombre
                        metodo.descripcion_metodo_pago = descripcion
                        metodo.permite_cambio = permite_cambio
                        metodo.save()

                        # Registrar auditoría.
                        LogAuditoria.objects.create(
                            tabla="Métodos de pago",
                            accion="MODIFICAR",
                            registro_id=metodo.pk,
                            valores_anteriores=valores_anteriores,
                            valores_actuales=valores_actuales,
                            empleado=request.user.empleado,
                        )

                    messages.success(
                        request,
                        f'Método de pago "{metodo.nombre_metodo_pago}" actualizado correctamente.'
                    )
                else:
                    messages.info(
                        request,
                        'No se realizaron cambios en el método de pago.'
                    )

                return redirect('finanzas:listar_met_pago')

    return render(request, 'METODO_PAGO/editar_met_pago.html', {
        'metodo': metodo
    })

@login_required
@permiso_requerido('caja', 'eliminar')
def eliminar_met_pago(request, pk):
    metodo = get_object_or_404(metodo_pago, pk=pk)
    related_name='pagos'
    if request.method == 'POST':
        # Verificar si el método está asociado a alguna venta.
        if Venta.objects.filter(metodo_pago_venta=metodo).exists():
            messages.error(
                request,
                f'No se puede eliminar "{metodo.nombre_metodo_pago}" '
                'porque está asociado a una o más ventas.'
            )
            return redirect('finanzas:listar_met_pago')
        if metodo.pagos.exists():
            messages.error(
                request,
                f'No se puede eliminar "{metodo.nombre_metodo_pago}" '
                'porque está asociado a uno o más pagos.'
            )
            return redirect('finanzas:listar_met_pago')
        nombre = metodo.nombre_metodo_pago
        valores_anteriores = (
                    f"Nombre: {metodo.nombre_metodo_pago}, "
                    f"Descripción: {metodo.descripcion_metodo_pago}, "
                    f"Estado: {metodo.estado_metodo_pago}"
                )

                # Registrar auditoría antes de eliminar.
        LogAuditoria.objects.create(
            tabla="Métodos de pago",
            accion="ANULAR",
            registro_id=metodo.pk,
            valores_anteriores=valores_anteriores,
            valores_actuales="",
            empleado=request.user.empleado,
        )
    
        metodo.delete()

        messages.success(
            request,
            f'El método de pago "{nombre}" se eliminó correctamente.'
        )
        return redirect('finanzas:listar_met_pago')

    return render(
        request,
        'METODO_PAGO/eliminar_met_pago.html',
        {'metodo': metodo}
    )

@login_required
@permiso_requerido('caja', 'leer')
def detalle_met_pago(request, pk):
    metodo = get_object_or_404(metodo_pago, pk=pk)
    return render(request, 'METODO_PAGO/detalle_met_pago.html', {
        'metodo': metodo
    })


@login_required
@permiso_requerido('caja', 'modificar')
def estado_metodo_pago(request, pk):
    with transaction.atomic():
        metodo = get_object_or_404(
            metodo_pago.objects.select_for_update(),
            pk=pk
        )

        estado_anterior = metodo.estado_metodo_pago

        metodo.estado_metodo_pago = not metodo.estado_metodo_pago
        metodo.save()

        LogAuditoria.objects.create(
            tabla="Métodos de pago",
            accion="MODIFICAR",
            registro_id=metodo.pk,
            valores_anteriores=(
                f"Nombre: {metodo.nombre_metodo_pago}, "
                f"Estado: {estado_anterior}"
            ),
            valores_actuales=(
                f"Nombre: {metodo.nombre_metodo_pago}, "
                f"Estado: {metodo.estado_metodo_pago}"
            ),
            empleado=request.user.empleado,
        )

    if metodo.estado_metodo_pago:
        messages.success(
            request,
            f'Método de pago "{metodo.nombre_metodo_pago}" activado.'
        )
    else:
        messages.success(
            request,
            f'Método de pago "{metodo.nombre_metodo_pago}" desactivado.'
        )

    return redirect(
        request.META.get(
            'HTTP_REFERER',
            'finanzas:listar_met_pago'
        )
    )

@login_required
@permiso_requerido('caja', 'leer')
def listar_cajas(request):
    cajas = caja.objects.select_related(
        'empleado_apertura',
        'empleado_cierre',
        'empleado_arqueamiento'
    ).all().order_by('-fecha_apertura')

    # Búsqueda por empleado o número de caja
    buscar = request.GET.get('buscar', '').strip()
    if buscar:
        filtros = (
            Q(empleado_apertura__nombre_empleado__icontains=buscar) |
            Q(empleado_apertura__apellido_empleado__icontains=buscar)
        )

        if buscar.isdigit():
            filtros |= Q(id_caja=int(buscar))

        cajas = cajas.filter(filtros)

    # Filtro por estado
    estado = request.GET.get('estado', '').strip()
    if estado in ['abierto', 'cerrado']:
        cajas = cajas.filter(estado_caja=estado)

    # Rango de fechas
       # Rango de fechas
    fecha_desde_texto = request.GET.get('fecha_desde', '').strip()
    fecha_hasta_texto = request.GET.get('fecha_hasta', '').strip()

    fecha_desde = parse_date(fecha_desde_texto) if fecha_desde_texto else None
    fecha_hasta = parse_date(fecha_hasta_texto) if fecha_hasta_texto else None

    if fecha_desde_texto and fecha_desde is None:
        messages.error(request, 'La fecha desde no es válida.')

    if fecha_hasta_texto and fecha_hasta is None:
        messages.error(request, 'La fecha hasta no es válida.')

    if fecha_desde and fecha_hasta and fecha_desde > fecha_hasta:
        messages.error(
            request,
            'La fecha desde no puede ser posterior a la fecha hasta.'
        )
    else:
        if fecha_desde:
            inicio = datetime.combine(fecha_desde, time.min)

            if timezone.is_aware(timezone.now()):
                inicio = timezone.make_aware(
                    inicio,
                    timezone.get_current_timezone()
                )

            cajas = cajas.filter(fecha_apertura__gte=inicio)

        if fecha_hasta:
            fin_exclusivo = datetime.combine(
                fecha_hasta + timedelta(days=1),
                time.min
            )

            if timezone.is_aware(timezone.now()):
                fin_exclusivo = timezone.make_aware(
                    fin_exclusivo,
                    timezone.get_current_timezone()
                )

            cajas = cajas.filter(fecha_apertura__lt=fin_exclusivo)
    # Cantidad de registros por página
    por_pagina = request.GET.get('por_pagina', 10)

    try:
        por_pagina = int(por_pagina)
        if por_pagina not in [10, 25, 50, 100]:
            por_pagina = 10
    except (ValueError, TypeError):
        por_pagina = 10

    paginator = Paginator(cajas, por_pagina)
    cajas_paginadas = paginator.get_page(request.GET.get('page'))

    return render(request, 'CAJA/listar_cajas.html', {
        'cajas': cajas_paginadas,
        'buscar': buscar,
        'estado_seleccionado': estado,
        'fecha_desde': fecha_desde_texto,
        'fecha_hasta': fecha_hasta_texto,
        'por_pagina': por_pagina,
    })

@login_required
@permiso_requerido('caja', 'escribir')
def abrir_caja(request):
    if request.method == 'POST':
        try:
            empleado = request.user.empleado
        except Exception:
            messages.error(request, 'No tienes un empleado asociado.')
            return redirect('finanzas:listar_cajas')

        # Comprobar si ya existe una caja abierta.
        caja_abierta = caja.objects.filter(
            estado_caja='abierto'
        ).first()

        if caja_abierta:
            messages.error(
                request,
                f'No se puede abrir otra caja. '
                f'La caja N.º {caja_abierta.id_caja} '
                f'ya se encuentra abierta.'
            )
            return redirect('finanzas:listar_cajas')

        saldo_inicial_texto = request.POST.get(
            'saldo_inicial', ''
        ).strip()

        observaciones = request.POST.get(
            'observaciones_apertura', ''
        ).strip()

        if len(observaciones) > 1000:
            error_campo(
                    request, "observaciones_apertura", 'Las observaciones de apertura no pueden superar los 1000 caracteres.'
            )
            return render(request, 'CAJA/abrir_caja.html', {
                'saldo_inicial': saldo_inicial_texto,
                'observaciones_apertura': observaciones,
            })

        try:
            saldo_inicial = Decimal(saldo_inicial_texto)

            if not saldo_inicial.is_finite() or saldo_inicial < 0:
                raise ValueError

        except (InvalidOperation, ValueError):
            error_campo(
                    request, "saldo_inicial", 'El saldo inicial debe ser un número válido y no negativo.'
            )
            return render(request, 'CAJA/abrir_caja.html', {
                'saldo_inicial': saldo_inicial_texto,
                'observaciones_apertura': observaciones,
            })

        with transaction.atomic():
            nueva_caja = caja.objects.create(
                empleado_apertura=empleado,
                saldo_inicial=saldo_inicial,
                observaciones_apertura=observaciones,
                observaciones_caja=observaciones,
                estado_caja='abierto'
            )

            LogAuditoria.objects.create(
                tabla="Cajas",
                accion="CREAR",
                registro_id=nueva_caja.pk,
                valores_anteriores="",
                valores_actuales=(
                    f"Estado: {nueva_caja.estado_caja}, "
                    f"Saldo inicial: ${nueva_caja.saldo_inicial}, "
                    f"Observaciones: {nueva_caja.observaciones_apertura}, "
                    f"Empleado de apertura: {empleado}"
                ),
                empleado=empleado,
            )

        messages.success(request, 'La caja se abrió correctamente.')
        return redirect('finanzas:listar_cajas')

    return render(request, 'CAJA/abrir_caja.html')

@login_required
@permiso_requerido('caja', 'leer')
def detalle_caja(request, pk):
    caja_actual = get_object_or_404(
        caja.objects.select_related(
            'empleado_apertura',
            'empleado_cierre',
            'empleado_arqueamiento'
        ),
        pk=pk
    )

    gastos = caja_actual.gastos.select_related(
        'cat_gasto',
        'empleado_gasto'
    ).order_by('-fecha_hora_gasto')

    # Gastos
    total_egresos = caja_actual.calcular_total_egresos()

    # Ventas
    pagos = caja_actual.pagos.select_related(
        'comanda',
        'empleado',
        'metodo_pago'
    ).order_by('-fecha_hora')

    total_ventas = caja_actual.calcular_total_ventas()
    ventas_efectivo = caja_actual.calcular_total_ventas_efectivo()
    ventas_otros_medios = total_ventas - ventas_efectivo

    # Agrupar ventas dinámicamente por método de pago
    ventas_por_metodo = (
        caja_actual.pagos.values(
            'metodo_pago__id_metodo_pago',
            'metodo_pago__nombre_metodo_pago'
        )
        .annotate(total=Sum('monto'))
        .order_by('metodo_pago__nombre_metodo_pago')
    )

    saldo_esperado = caja_actual.calcular_saldo_esperado()

    return render(request, 'CAJA/detalle_caja.html', {
        'caja': caja_actual,
        'gastos': gastos,
        'total_egresos': total_egresos,
        'saldo_esperado': saldo_esperado,

        # Datos de ventas
        'pagos': pagos,
        'total_ventas': total_ventas,
        'ventas_efectivo': ventas_efectivo,
        'ventas_otros_medios': ventas_otros_medios,
        'ventas_por_metodo': ventas_por_metodo,
    })


@login_required
@permiso_requerido('caja', 'modificar')
def arqueo_caja(request, pk):
    caja_actual = get_object_or_404(caja, pk=pk)

    if caja_actual.estado_caja != 'abierto':
        messages.error(
            request,
            'No se puede realizar el arqueo de una caja cerrada.'
        )
        return redirect('finanzas:listar_cajas')

    try:
        empleado = request.user.empleado
    except Exception:
        messages.error(request, 'No tienes un empleado asociado.')
        return redirect('finanzas:listar_cajas')

    # Datos que necesita la plantilla.
    cargo = getattr(empleado, 'cargo', None)
    cargo_nombre = (
        getattr(cargo, 'nombre_cargo', 'Sin cargo asignado')
        if cargo else 'Sin cargo asignado'
    )

    contexto = {
        'caja': caja_actual,
        'saldo_esperado': caja_actual.calcular_saldo_esperado(),
        'empleado': empleado,
        'cargo_nombre': cargo_nombre,
        'fecha_actual': timezone.now(),
        'observaciones_arqueo': caja_actual.observaciones_arqueo,
        'saldo_contado': caja_actual.saldo_contado,
    }

    if request.method == 'POST':
        saldo_texto = request.POST.get(
            'saldo_contado', ''
        ).strip()

        observaciones = request.POST.get(
            'observaciones_arqueo', ''
        ).strip()

        contexto['observaciones_arqueo'] = observaciones
        contexto['saldo_contado'] = saldo_texto

        if len(observaciones) > 1000:
            error_campo(
                    request, "observaciones_arqueo", 'Las observaciones de arqueo no pueden superar los 1000 caracteres.'
            )
            return render(
                request, 'CAJA/arqueo_caja.html', contexto
            )

        try:
            saldo_contado = Decimal(saldo_texto)

            if not saldo_contado.is_finite() or saldo_contado < 0:
                raise ValueError

        except (InvalidOperation, ValueError):
            error_campo(
                    request, "saldo_contado", 'El saldo contado debe ser un número válido y no negativo.'
            )
            return render(
                request, 'CAJA/arqueo_caja.html', contexto
            )

        try:
            with transaction.atomic():
                # Bloquear la caja durante el arqueo.
                caja_bloqueada = caja.objects.select_for_update().get(
                    pk=pk
                )

                if caja_bloqueada.estado_caja != 'abierto':
                    raise ValueError(
                        'No se puede realizar el arqueo de una caja cerrada.'
                    )

                # Guardar los valores anteriores.
                saldo_anterior = caja_bloqueada.saldo_contado
                observaciones_anteriores = (
                    caja_bloqueada.observaciones_arqueo
                )
                empleado_anterior = (
                    caja_bloqueada.empleado_arqueamiento
                )

                # Realizar el arqueo.
                caja_bloqueada.realizar_arqueo(
                    saldo_contado=saldo_contado,
                    empleado_arqueamiento=empleado,
                    observaciones_arqueo=observaciones
                )

                # Registrar auditoría.
                LogAuditoria.objects.create(
                    tabla="Cajas",
                    accion="MODIFICAR",
                    registro_id=caja_bloqueada.pk,
                    valores_anteriores=(
                        f"Saldo contado: {saldo_anterior}, "
                        f"Empleado de arqueo: {empleado_anterior}, "
                        f"Observaciones: {observaciones_anteriores}"
                    ),
                    valores_actuales=(
                        f"Saldo contado: ${caja_bloqueada.saldo_contado}, "
                        f"Empleado de arqueo: {empleado}, "
                        f"Observaciones: {caja_bloqueada.observaciones_arqueo}"
                    ),
                    empleado=empleado,
                )

            messages.success(
                request,
                'El arqueo se realizó correctamente.'
            )

        except ValueError as error:
            messages.error(request, str(error))
            return render(
                request, 'CAJA/arqueo_caja.html', contexto
            )

        return redirect('finanzas:detalle_caja', pk=pk)

    return render(request, 'CAJA/arqueo_caja.html', contexto)


def _resumen_caja(caja_actual):
    """Los números del resumen de saldos (detalle y cierre de caja)."""
    total_ventas = caja_actual.calcular_total_ventas()
    ventas_efectivo = caja_actual.calcular_total_ventas_efectivo()
    return {
        'total_egresos': caja_actual.calcular_total_egresos(),
        'total_ventas': total_ventas,
        'ventas_efectivo': ventas_efectivo,
        'ventas_otros_medios': total_ventas - ventas_efectivo,
        'saldo_esperado': caja_actual.calcular_saldo_esperado(),
    }


def _contexto_cierre(request, caja_actual, **extra):
    empleado = getattr(request.user, 'empleado', None)
    cargo = getattr(empleado, 'cargo', None)
    return {
        'caja': caja_actual,
        'empleado': empleado,
        'cargo_nombre': cargo.nombre_cargo if cargo else 'Sin cargo asignado',
        **_resumen_caja(caja_actual),
        **extra,
    }


@login_required
@permiso_requerido('caja', 'modificar')
def cerrar_caja(request, pk):

    caja_actual = get_object_or_404(caja, pk=pk)

    if caja_actual.estado_caja != 'abierto':
        messages.error(request, 'Esta caja ya está cerrada.')
        return redirect('finanzas:detalle_caja', pk=pk)

    if request.method == 'GET':
        return render(
            request,
            'CAJA/cerrar_caja.html',
            _contexto_cierre(request, caja_actual),
        )

    if request.method == 'POST':

        try:
            empleado = request.user.empleado
        except Exception:
            messages.error(
                request,
                'No tienes un empleado asociado.'
            )
            return redirect('finanzas:detalle_caja', pk=pk)

        observaciones = request.POST.get(
            'observaciones_cierre', ''
        ).strip()

        if len(observaciones) > 1000:
            error_campo(
                    request, "observaciones_cierre", 'Las observaciones de cierre no pueden superar los 1000 caracteres.'
            )
            return render(
                request,
                'CAJA/cerrar_caja.html',
                _contexto_cierre(
                    request, caja_actual, observaciones_cierre=observaciones
                ),
            )

        try:
            with transaction.atomic():
                caja_actual = caja.objects.select_for_update().get(
                    pk=pk
                )

                if caja_actual.estado_caja != 'abierto':
                    raise ValueError(
                        'Esta caja ya está cerrada.'
                    )

                # Guardar los valores anteriores.
                estado_anterior = caja_actual.estado_caja
                saldo_final_anterior = caja_actual.saldo_final
                empleado_cierre_anterior = caja_actual.empleado_cierre
                observaciones_anteriores = caja_actual.observaciones_cierre

                # Cerrar la caja.
                caja_actual.cerrar_caja(
                    empleado,
                    observaciones_cierre=observaciones
                )

                # Registrar auditoría.
                LogAuditoria.objects.create(
                    tabla="Cajas",
                    accion="MODIFICAR",
                    registro_id=caja_actual.pk,
                    valores_anteriores=(
                        f"Estado: {estado_anterior}, "
                        f"Saldo final: {saldo_final_anterior}, "
                        f"Empleado de cierre: {empleado_cierre_anterior}, "
                        f"Observaciones: {observaciones_anteriores}"
                    ),
                    valores_actuales=(
                        f"Estado: {caja_actual.estado_caja}, "
                        f"Saldo final: ${caja_actual.saldo_final}, "
                        f"Empleado de cierre: {empleado}, "
                        f"Observaciones: {caja_actual.observaciones_cierre}"
                    ),
                    empleado=empleado,
                )

            messages.success(
                request,
                'La caja se cerró correctamente.'
            )

            return redirect('finanzas:detalle_caja', pk=pk)

        except ValueError as error:
            messages.error(request, str(error))

            return render(
                request,
                'CAJA/cerrar_caja.html',
                _contexto_cierre(
                    request, caja_actual, observaciones_cierre=observaciones
                ),
            )


#FUNCIONES DE GASTOS
@login_required
@permiso_requerido('caja', 'leer')
def listar_gastos(request):
    gastos = gasto.objects.select_related(
        'caja_gasto',
        'cat_gasto',
        'empleado_gasto'
    ).all()

    # Buscar por descripción o categoría
    buscar = request.GET.get('buscar', '').strip()

    if buscar:
        gastos = gastos.filter(
            Q(descripcion_gasto__icontains=buscar)
            | Q(
                cat_gasto__nombre_categoria_gasto__icontains=buscar
            )
        )
# Rango de fechas
       # Rango de fechas
    fecha_desde_texto = request.GET.get('fecha_desde', '').strip()
    fecha_hasta_texto = request.GET.get('fecha_hasta', '').strip()

    fecha_desde = parse_date(fecha_desde_texto) if fecha_desde_texto else None
    fecha_hasta = parse_date(fecha_hasta_texto) if fecha_hasta_texto else None

    if fecha_desde_texto and fecha_desde is None:
        messages.error(request, 'La fecha desde no es válida.')

    if fecha_hasta_texto and fecha_hasta is None:
        messages.error(request, 'La fecha hasta no es válida.')

    if fecha_desde and fecha_hasta and fecha_desde > fecha_hasta:
        messages.error(
            request,
            'La fecha desde no puede ser posterior a la fecha hasta.'
        )
    else:
        if fecha_desde:
            inicio = datetime.combine(fecha_desde, time.min)

            if timezone.is_aware(timezone.now()):
                inicio = timezone.make_aware(
                    inicio,
                    timezone.get_current_timezone()
                )

            gastos = gastos.filter(fecha_hora_gasto__gte=inicio)

        if fecha_hasta:
            fin_exclusivo = datetime.combine(
                fecha_hasta + timedelta(days=1),
                time.min
            )

            if timezone.is_aware(timezone.now()):
                fin_exclusivo = timezone.make_aware(
                    fin_exclusivo,
                    timezone.get_current_timezone()
                )

            gastos = gastos.filter(fecha_hora_gasto__lt=fin_exclusivo)
    # Cantidad de registros por página
    por_pagina = request.GET.get('por_pagina', '10')

    try:
        por_pagina = int(por_pagina)
        if por_pagina not in [10, 25, 50, 100]:
            por_pagina = 10
    except (ValueError, TypeError):
        por_pagina = 10

    paginator = Paginator(
        gastos.order_by('-fecha_hora_gasto'),
        por_pagina
    )

    gastos_paginados = paginator.get_page(
        request.GET.get('page')
    )

    # Información de la caja abierta para mostrar en pantalla
    caja_abierta = caja.objects.filter(
        estado_caja='abierto'
    ).first()

    return render(
        request,
        'GASTOS/listar_gastos.html',
        {
            'gastos': gastos_paginados,
            'buscar': buscar,
            'por_pagina': por_pagina,
            'caja_abierta': caja_abierta,
            'fecha_desde': fecha_desde_texto,
            'fecha_hasta': fecha_hasta_texto,
        }
    )


@login_required
@permiso_requerido('caja', 'escribir')
def crear_gasto(request):
    # Obtener la única caja abierta.
    caja_actual = caja.objects.filter(
        estado_caja='abierto'
    ).first()

    # No permitir registrar gastos sin caja abierta.
    if not caja_actual:
        messages.error(
            request,
            'No hay una caja abierta. '
            'Debes abrir una caja antes de registrar gastos.'
        )
        return redirect('finanzas:listar_gastos')

    categorias = categoria_gasto.objects.filter(
        estado_categoria_gasto=True
    ).order_by('nombre_categoria_gasto')

    if request.method == 'POST':
        try:
            empleado = request.user.empleado
        except Exception:
            messages.error(
                request,
                'No tienes un empleado asociado.'
            )
            return redirect('finanzas:listar_gastos')

        descripcion = request.POST.get(
            'descripcion_gasto', ''
        ).strip()

        monto_texto = request.POST.get(
            'monto_gasto', ''
        ).strip()

        categoria_id = request.POST.get(
            'cat_gasto', ''
        ).strip()

        if not descripcion:
            error_campo(
                    request, "descripcion_gasto", 'La descripción es obligatoria.'
            )

        else:
            try:
                monto = Decimal(monto_texto)

                if not monto.is_finite() or monto <= 0:
                    raise ValueError

            except (InvalidOperation, ValueError):
                error_campo(
                    request, "monto_gasto", 'El monto debe ser un número válido mayor que cero.'
                )

            else:
                categoria = (
                    categoria_gasto.objects.filter(
                        pk=categoria_id,
                        estado_categoria_gasto=True
                    ).first()
                    if categoria_id.isdigit()
                    else None
                )

                if not categoria:
                    error_campo(
                    request, "cat_gasto", 'Seleccioná una categoría de gasto activa.'
                    )

                else:
                    with transaction.atomic():
                        caja_actual = caja.objects.select_for_update().filter(
                            estado_caja='abierto'
                        ).first()

                        if not caja_actual:
                            messages.error(
                                request,
                                'No hay una caja abierta para registrar el gasto.'
                            )

                        else:
                            # Validar saldo disponible.
                            saldo_disponible = (
                                caja_actual.calcular_saldo_esperado()
                            )

                            if monto > saldo_disponible:
                                error_campo(
                    request, "monto_gasto", f'El monto del gasto ${monto} supera '
                                    f'el saldo disponible de la caja '
                                    f'${saldo_disponible}.'
                                )
                                return render(
                                    request,
                                    'GASTOS/crear_gasto.html',
                                    {
                                        'categorias': categorias,
                                        'caja_abierta': caja_actual,
                                    }
                                )

                            else:
                                # Crear gasto.
                                nuevo_gasto = gasto.objects.create(
                                    descripcion_gasto=descripcion,
                                    monto_gasto=monto,
                                    caja_gasto=caja_actual,
                                    cat_gasto=categoria,
                                    empleado_gasto=empleado
                                )

                                # Registrar auditoría.
                                LogAuditoria.objects.create(
                                    tabla="Gastos",
                                    accion="CREAR",
                                    registro_id=nuevo_gasto.pk,
                                    valores_anteriores="",
                                    valores_actuales=(
                                        f"Descripción: {nuevo_gasto.descripcion_gasto}, "
                                        f"Monto: ${nuevo_gasto.monto_gasto}, "
                                        f"Categoría: {categoria.nombre_categoria_gasto}, "
                                        f"Caja: #{caja_actual.pk}, "
                                        f"Empleado: {empleado}"
                                    ),
                                    empleado=empleado,
                                )

                    if caja_actual:
                        messages.success(
                            request,
                            'El gasto se registró correctamente.'
                        )
                        return redirect('finanzas:listar_gastos')

        return render(
            request,
            'GASTOS/crear_gasto.html',
            {
                'categorias': categorias,
                'caja_abierta': caja_actual,
            }
        )

    return render(
        request,
        'GASTOS/crear_gasto.html',
        {
            'categorias': categorias,
            'caja_abierta': caja_actual,
        }
    )


@login_required
@permiso_requerido('caja', 'leer')
def detalle_gasto(request, pk):
    gasto_actual = get_object_or_404(
        gasto.objects.select_related(
            'caja_gasto',
            'cat_gasto',
            'empleado_gasto'
        ),
        pk=pk
    )

    return render(request, 'GASTOS/detalle_gasto.html', {
        'gasto': gasto_actual,
    })


@login_required
@permiso_requerido('caja', 'modificar')
def editar_gasto(request, pk):
    gasto_actual = get_object_or_404(
        gasto.objects.select_related(
            'caja_gasto',
            'cat_gasto'
        ),
        pk=pk
    )

    if gasto_actual.caja_gasto.estado_caja != 'abierto':
        messages.error(
            request,
            'No se pueden modificar gastos de una caja cerrada.'
        )
        return redirect('finanzas:detalle_gasto', pk=pk)

    cajas_abiertas = caja.objects.filter(estado_caja='abierto')

    categorias = categoria_gasto.objects.filter(
        Q(estado_categoria_gasto=True)
        | Q(pk=gasto_actual.cat_gasto_id)
    ).order_by('nombre_categoria_gasto')

    if request.method == 'POST':
        descripcion = request.POST.get(
            'descripcion_gasto', ''
        ).strip()

        monto_texto = request.POST.get(
            'monto_gasto', ''
        ).strip()

        caja_id = request.POST.get(
            'caja_gasto', ''
        ).strip()

        categoria_id = request.POST.get(
            'cat_gasto', ''
        ).strip()

        if not descripcion:
            error_campo(
                    request, "descripcion_gasto", 'La descripción es obligatoria.'
            )
            return render(request, 'GASTOS/editar_gasto.html', {
                'gasto': gasto_actual,
                'cajas': cajas_abiertas,
                'categorias': categorias,
            })

        try:
            monto = Decimal(monto_texto)

            if not monto.is_finite() or monto <= 0:
                raise ValueError

        except (InvalidOperation, ValueError):
            error_campo(
                    request, "monto_gasto", 'El monto debe ser un número válido mayor que cero.'
            )
            return render(request, 'GASTOS/editar_gasto.html', {
                'gasto': gasto_actual,
                'cajas': cajas_abiertas,
                'categorias': categorias,
            })

        caja_actual = caja.objects.filter(
            pk=caja_id,
            estado_caja='abierto'
        ).first() if caja_id.isdigit() else None

        categoria = categoria_gasto.objects.filter(
            pk=categoria_id
        ).first() if categoria_id.isdigit() else None

        if not caja_actual:
            error_campo(
                    request, "caja_gasto", 'Seleccioná una caja abierta válida.'
            )

        elif not categoria or (
            not categoria.estado_categoria_gasto
            and categoria.pk != gasto_actual.cat_gasto_id
        ):
            error_campo(
                    request, "cat_gasto", 'Seleccioná una categoría válida.'
            )

        else:
            # Validar saldo disponible de la caja.
            saldo_disponible = caja_actual.calcular_saldo_esperado()

            if gasto_actual.caja_gasto_id == caja_actual.pk:
                saldo_disponible += gasto_actual.monto_gasto

            if monto > saldo_disponible:
                error_campo(
                    request, "monto_gasto", f'El monto del gasto ${monto} supera el saldo '
                    f'disponible de la caja ${saldo_disponible}.'
                )
                return render(
                    request,
                    'GASTOS/editar_gasto.html',
                    {
                        'gasto': gasto_actual,
                        'cajas': cajas_abiertas,
                        'categorias': categorias,
                    }
                )

            else:
                # Detectar cambios reales.
                hubo_cambios = (
                    gasto_actual.descripcion_gasto != descripcion
                    or gasto_actual.monto_gasto != monto
                    or gasto_actual.caja_gasto_id != caja_actual.pk
                    or gasto_actual.cat_gasto_id != categoria.pk
                )

                if hubo_cambios:
                    # Capturar valores anteriores.
                    valores_anteriores = (
                        f"Descripción: {gasto_actual.descripcion_gasto}, "
                        f"Monto: ${gasto_actual.monto_gasto}, "
                        f"Categoría: {gasto_actual.cat_gasto.nombre_categoria_gasto}, "
                        f"Caja: #{gasto_actual.caja_gasto_id}"
                    )

                    # Preparar valores actuales.
                    valores_actuales = (
                        f"Descripción: {descripcion}, "
                        f"Monto: ${monto}, "
                        f"Categoría: {categoria.nombre_categoria_gasto}, "
                        f"Caja: #{caja_actual.pk}"
                    )

                    with transaction.atomic():
                        gasto_actual.descripcion_gasto = descripcion
                        gasto_actual.monto_gasto = monto
                        gasto_actual.caja_gasto = caja_actual
                        gasto_actual.cat_gasto = categoria
                        gasto_actual.save()

                        # Registrar auditoría.
                        LogAuditoria.objects.create(
                            tabla="Gastos",
                            accion="MODIFICAR",
                            registro_id=gasto_actual.pk,
                            valores_anteriores=valores_anteriores,
                            valores_actuales=valores_actuales,
                            empleado=request.user.empleado,
                        )

                    messages.success(
                        request,
                        'El gasto se actualizó correctamente.'
                    )

                else:
                    messages.info(
                        request,
                        'No se realizaron cambios en el gasto.'
                    )

                return redirect('finanzas:listar_gastos')

    return render(request, 'GASTOS/editar_gasto.html', {
        'gasto': gasto_actual,
        'cajas': cajas_abiertas,
        'categorias': categorias,
    })



@login_required
@permiso_requerido('caja', 'eliminar')
def eliminar_gasto(request, pk):
    gasto_actual = get_object_or_404(
        gasto.objects.select_related(
            'caja_gasto',
            'cat_gasto'
        ),
        pk=pk
    )

    if request.method == 'POST':
        with transaction.atomic():
            # Bloquear el gasto durante la operación.
            gasto_actual = get_object_or_404(
                gasto.objects.select_for_update().select_related(
                    'caja_gasto',
                    'cat_gasto'
                ),
                pk=pk
            )

            if gasto_actual.caja_gasto.estado_caja != 'abierto':
                messages.error(
                    request,
                    'No se pueden eliminar gastos de una caja cerrada.'
                )
                return redirect('finanzas:detalle_gasto', pk=pk)

            descripcion = gasto_actual.descripcion_gasto

            # Capturar los datos antes de eliminar.
            valores_anteriores = (
                f"Descripción: {gasto_actual.descripcion_gasto}, "
                f"Monto: ${gasto_actual.monto_gasto}, "
                f"Categoría: {gasto_actual.cat_gasto.nombre_categoria_gasto}, "
                f"Caja: #{gasto_actual.caja_gasto_id}, "
                f"Empleado: {gasto_actual.empleado_gasto}"
            )

            # Registrar auditoría antes de eliminar.
            LogAuditoria.objects.create(
                tabla="Gastos",
                accion="ANULAR",
                registro_id=gasto_actual.pk,
                valores_anteriores=valores_anteriores,
                valores_actuales="",
                empleado=request.user.empleado,
            )

            # Eliminar gasto.
            gasto_actual.delete()

        messages.success(
            request,
            f'El gasto "{descripcion}" se eliminó correctamente.'
        )
        return redirect('finanzas:listar_gastos')

    return render(request, 'GASTOS/eliminar_gasto.html', {
        'gasto': gasto_actual,
    })


#FUNCIONES PARA VENTAS
@login_required
@permiso_requerido('caja', 'leer')
def listar_ventas(request):
    pagos = Pago.objects.select_related(
        'comanda',
        'empleado',
        'caja',
        'metodo_pago'
    ).order_by('-fecha_hora')

    # Filtro de búsqueda
    buscar = request.GET.get('buscar', '').strip()
    # Información de la caja abierta para mostrar en pantalla
    caja_abierta = caja.objects.filter(
        estado_caja='abierto'
    ).first()
    if buscar:
        pagos = pagos.filter(
            Q(comanda__id_comanda__icontains=buscar) |
            Q(empleado__nombre_empleado__icontains=buscar) |
            Q(empleado__apellido_empleado__icontains=buscar) |
            Q(metodo_pago__nombre_metodo_pago__icontains=buscar)
        )
 # Rango de fechas
    fecha_desde_texto = request.GET.get('fecha_desde', '').strip()
    fecha_hasta_texto = request.GET.get('fecha_hasta', '').strip()

    fecha_desde = parse_date(fecha_desde_texto) if fecha_desde_texto else None
    fecha_hasta = parse_date(fecha_hasta_texto) if fecha_hasta_texto else None

    if fecha_desde_texto and fecha_desde is None:
        messages.error(request, 'La fecha desde no es válida.')

    if fecha_hasta_texto and fecha_hasta is None:
        messages.error(request, 'La fecha hasta no es válida.')

    if fecha_desde and fecha_hasta and fecha_desde > fecha_hasta:
        messages.error(
            request,
            'La fecha desde no puede ser posterior a la fecha hasta.'
        )
    else:
        if fecha_desde:
            inicio = datetime.combine(fecha_desde, time.min)

            if timezone.is_aware(timezone.now()):
                inicio = timezone.make_aware(
                    inicio,
                    timezone.get_current_timezone()
                )

            pagos = pagos.filter(fecha_hora__gte=inicio)

        if fecha_hasta:
            fin_exclusivo = datetime.combine(
                fecha_hasta + timedelta(days=1),
                time.min
            )

            if timezone.is_aware(timezone.now()):
                fin_exclusivo = timezone.make_aware(
                    fin_exclusivo,
                    timezone.get_current_timezone()
                )

            pagos = pagos.filter(fecha_hora__lt=fin_exclusivo)
    ventas_por_metodo = (
        pagos.values(
            'metodo_pago__id_metodo_pago',
            'metodo_pago__nombre_metodo_pago'
        )
        .annotate(total=Sum('monto'))
        .order_by('metodo_pago__nombre_metodo_pago')
    )
    return render(request, 'VENTAS/listar_ventas.html', {
        'pagos': pagos,
        'buscar': buscar,
        'caja_abierta': caja_abierta,
        'ventas_por_metodo': ventas_por_metodo,
        'fecha_desde': fecha_desde_texto,
        'fecha_hasta': fecha_hasta_texto,
    })