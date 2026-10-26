from django.shortcuts import render
from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator
from .models import metodo_pago, categoria_gasto, caja, gasto
from django.contrib.auth import authenticate, login
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required,user_passes_test
from django.contrib import messages
import re
from django.db.models import Q
from empleados.decorators import permiso_requerido
from decimal import Decimal, InvalidOperation
from django.db import transaction
from django.utils import timezone
from django.db.models import Q
from .models import caja
from empleados.models import Empleado
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
    
    return render(request, 'finanzas/listar_cat_gasto.html', {
        'categorias': cat_gasto, 'por_pagina': por_pagina, 'buscar': buscar, 'estados_seleccionados': estados, })


@login_required
@permiso_requerido('caja', 'escribir')
def crear_cat_gasto(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        descripcion = request.POST.get('descripcion', '').strip()

        if not nombre:
            messages.error(request, 'El nombre de la categoría es obligatorio.')
            return render(request, 'finanzas/crear_cat_gasto.html')

        nombre = nombre.title()

        if categoria_gasto.objects.filter(
            nombre_categoria_gasto__iexact=nombre
        ).exists():
            messages.error(request, 'Ya existe una categoría con ese nombre.')
            return render(request, 'finanzas/crear_cat_gasto.html')

        categoria_gasto.objects.create(
            nombre_categoria_gasto=nombre,
            descripcion_categoria_gasto=descripcion
        )

        messages.success(request, f'Categoría "{nombre}" creada correctamente.')
        return redirect('finanzas:listar_cat_gasto')

    return render(request, 'finanzas/crear_cat_gasto.html')
@login_required
@permiso_requerido('caja', 'modificar')
def editar_cat_gasto(request, pk):
    categoria = get_object_or_404(categoria_gasto, pk=pk)

    # Impedir la modificación si ya fue utilizada
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
            messages.error(request, 'El nombre es obligatorio.')
        elif categoria_gasto.objects.filter(
            nombre_categoria_gasto__iexact=nombre
        ).exclude(pk=categoria.pk).exists():
            messages.error(request, 'Ya existe una categoría con ese nombre.')
        else:
            categoria.nombre_categoria_gasto = nombre.title()
            categoria.descripcion_categoria_gasto = descripcion
            categoria.save()

            messages.success(request, 'Categoría actualizada correctamente.')
            return redirect('finanzas:listar_cat_gasto')

    return render(request, 'finanzas/editar_cat_gasto.html', {
        'categoria': categoria
    })

@login_required
@permiso_requerido('caja', 'eliminar')
def eliminar_cat_gasto(request, pk):
    categoria = get_object_or_404(categoria_gasto, pk=pk)
    # Comprobar si la categoría está siendo utilizada
    if categoria.gastos.exists():
        messages.error(
            request,
            f'No se puede eliminar la categoría "{categoria.nombre_categoria_gasto}" '
            'porque está asociada a uno o más gastos.'
        )
        return redirect('finanzas:listar_cat_gasto')
    if request.method == 'POST':
        nombre = categoria.nombre_categoria_gasto
        categoria.delete()
        messages.success(
            request,
            f'Categoría "{nombre}" eliminada correctamente.'
        )
        return redirect('finanzas:listar_cat_gasto')
    return render(request, 'finanzas/eliminar_cat_gasto.html', {
        'categoria': categoria
    })

@login_required
@permiso_requerido('caja', 'leer')
def detalle_cat_gasto(request, pk):
    categoria = get_object_or_404(categoria_gasto, pk=pk)
    gastos = categoria.gasto_set.all().order_by('-fecha_hora_gasto')
    return render(request, 'finanzas/detalle_cat_gasto.html', {
        'categoria': categoria,
        'gastos': gastos
    })

@login_required
@permiso_requerido('caja', 'modificar')
def estado_categoria(request, pk):
    categoria = get_object_or_404(categoria_gasto, pk=pk)
    categoria.estado_categoria_gasto = not categoria.estado_categoria_gasto
    categoria.save()
    
    if categoria.estado_categoria_gasto:
        messages.success(request, f'Categoría "{categoria.nombre_categoria_gasto}" activada')
    else:
        messages.success(request, f'Categoría "{categoria.nombre_categoria_gasto}" desactivada')
    
    return redirect(request.META.get('HTTP_REFERER','finanzas:listar_cat_gasto'))

# FUNCIONES PARA METODOS DE PAGO
@login_required
@permiso_requerido('caja', 'leer')
def listar_met_pago(request):
    met_pago = metodo_pago.objects.all().order_by('nombre_metodo_pago')

    buscar = request.GET.get('buscar','').strip()
    estados = request.GET.getlist('estado')
    
    if buscar:
      met_pago = met_pago.filter(nombre_metodo_pago__icontains=buscar)

    if estados:
      q_estado = Q()
      if 'activo' in estados:
          q_estado |= Q(estado_metodo_pago=True)
      if 'inactivo' in estados:
          q_estado |= Q(estado_metodo_pago=False)
      if q_estado:
          met_pago = met_pago.filter(q_estado)

      # Por paginacion
    por_pagina = request.GET.get('por_pagina', 10)
    try:
        por_pagina = int(por_pagina)
        if por_pagina not in [10, 25, 50, 100]:
            por_pagina = 10
    except (ValueError, TypeError):
        por_pagina = 10
    
    paginator = Paginator(met_pago, por_pagina)
    page_number = request.GET.get('page')
    met_pago = paginator.get_page(page_number)
    
    return render(request, 'finanzas/listar_met_pago.html', {
        'metodos_pago': met_pago, 'por_pagina': por_pagina, 'buscar': buscar, 'estados_seleccionados': estados, })


@login_required
@permiso_requerido('caja', 'escribir')
def crear_met_pago(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        descripcion = request.POST.get('descripcion', '').strip()
        if not nombre:
            messages.error(request, 'El nombre del método de pago es obligatorio.')
            return render(request, 'finanzas/crear_met_pago.html')
        # Evitar nombres duplicados, sin distinguir mayúsculas y minúsculas
        if metodo_pago.objects.filter(
            nombre_metodo_pago__iexact=nombre
        ).exists():
            messages.error(request, 'Ya existe un método de pago con ese nombre.')
            return render(request, 'finanzas/crear_met_pago.html')
        metodo = metodo_pago(
            nombre_metodo_pago=nombre,
            descripcion_metodo_pago=descripcion
        )
        metodo.save()
        messages.success(
            request,
            f'Método de pago "{metodo.nombre_metodo_pago}" creado correctamente.'
        )
        return redirect('finanzas:listar_met_pago')
    return render(request, 'finanzas/crear_met_pago.html')

@login_required
@permiso_requerido('caja', 'modificar')
def editar_met_pago(request, pk):
    metodo = get_object_or_404(metodo_pago, pk=pk)
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        descripcion = request.POST.get('descripcion', '').strip()
        if not nombre:
            messages.error(request, 'El nombre del método de pago es obligatorio.')
        elif metodo_pago.objects.filter(
            nombre_metodo_pago__iexact=nombre
        ).exclude(pk=metodo.pk).exists():
            messages.error(request, 'Ya existe otro método de pago con ese nombre.')
        else:
            metodo.nombre_metodo_pago = nombre
            metodo.descripcion_metodo_pago = descripcion
            metodo.save()
            messages.success(
                request,
                f'Método de pago "{metodo.nombre_metodo_pago}" actualizado correctamente.'
            )
            return redirect('finanzas:listar_met_pago')
    return render(request, 'finanzas/editar_met_pago.html', {
        'metodo': metodo
    })

@login_required
@permiso_requerido('caja', 'eliminar')
def eliminar_met_pago(request, pk):
    metodo = get_object_or_404(metodo_pago, pk=pk)

    if metodo.ventas.exists():
        messages.error(
            request,
            f'No se puede eliminar el método de pago "{metodo.nombre_metodo_pago}" '
            'porque está asociado a una o más ventas.'
        )
        return redirect('finanzas:listar_met_pago')

    if request.method == 'POST':
        nombre = metodo.nombre_metodo_pago
        metodo.delete()
        messages.success(
            request,
            f'Método de pago "{nombre}" eliminado correctamente.'
        )
        return redirect('finanzas:listar_met_pago')

    return render(request, 'finanzas/eliminar_met_pago.html', {
        'metodo': metodo
    })

@login_required
@permiso_requerido('caja', 'leer')
def detalle_met_pago(request, pk):
    metodo = get_object_or_404(metodo_pago, pk=pk)
    return render(request, 'finanzas/detalle_met_pago.html', {
        'metodo': metodo
    })

@login_required
@permiso_requerido('caja', 'modificar')
def estado_metodo_pago(request, pk):
    metodo = get_object_or_404(metodo_pago, pk=pk)
    metodo.estado_metodo_pago = not metodo.estado_metodo_pago
    metodo.save()
    
    if metodo.estado_metodo_pago:
        messages.success(request, f'Método de pago "{metodo.nombre_metodo_pago}" activado')
    else:
        messages.success(request, f'Método de pago "{metodo.nombre_metodo_pago}" desactivado')
    
    return redirect(request.META.get('HTTP_REFERER','finanzas:listar_met_pago'))

# FUNCIONES PARA CAJA
@login_required
@permiso_requerido('caja', 'leer')
def listar_cajas(request):
    cajas = caja.objects.select_related('empleado_apertura', 'empleado_cierre', 'empleado_arqueamiento').all().order_by('-fecha_apertura')
    buscar = request.GET.get('buscar', '').strip()
    estado = request.GET.get('estado', '').strip()
    if buscar:
        filtros = Q(empleado_apertura__nombre_empleado__icontains=buscar)
        filtros |= Q(empleado_apertura__apellido_empleado__icontains=buscar)
        if buscar.isdigit():
            filtros |= Q(id_caja=int(buscar))

        cajas = cajas.filter(filtros)

    if estado in ['abierto', 'cerrado']:
        cajas = cajas.filter(estado_caja=estado)

    por_pagina = request.GET.get('por_pagina', 10)

    try:
        por_pagina = int(por_pagina)
        if por_pagina not in [10, 25, 50, 100]:
            por_pagina = 10
    except (ValueError, TypeError):
        por_pagina = 10

    paginator = Paginator(cajas, por_pagina)
    cajas = paginator.get_page(request.GET.get('page'))

    return render(request, 'CAJA/listar_cajas.html', {
        'cajas': cajas,
        'buscar': buscar,
        'estado_seleccionado': estado,
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
        # Comprobar si ya existe una caja abierta
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
            'observaciones_caja', ''
        ).strip()

        try:
            saldo_inicial = Decimal(saldo_inicial_texto)

            if not saldo_inicial.is_finite() or saldo_inicial < 0:
                raise ValueError

        except (InvalidOperation, ValueError):
            messages.error(
                request,
                'El saldo inicial debe ser un número válido y no negativo.'
            )
            return render(request, 'CAJA/abrir_caja.html')

        caja.objects.create(
            empleado_apertura=empleado,
            saldo_inicial=saldo_inicial,
            observaciones_caja=observaciones,
            estado_caja='abierto'
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

    total_egresos = caja_actual.calcular_total_egresos()
    saldo_esperado = caja_actual.calcular_saldo_esperado()

    return render(request, 'CAJA/detalle_caja.html', {
        'caja': caja_actual,
        'gastos': gastos,
        'total_egresos': total_egresos,
        'saldo_esperado': saldo_esperado,
    })

@login_required
@permiso_requerido('caja', 'modificar')

@login_required
@permiso_requerido('caja', 'modificar')
def arqueo_caja(request, pk):
    caja_actual = get_object_or_404(caja, pk=pk)
    if caja_actual.estado_caja != 'abierto':
        messages.error(request,'No se puede realizar el arqueo de una caja cerrada.')
        return redirect('finanzas:listar_cajas')
    if request.method == 'POST':
        try:
            empleado = request.user.empleado
        except Exception:
            messages.error(request, 'No tienes un empleado asociado.')
            return redirect('finanzas:listar_cajas')
        saldo_texto = request.POST.get('saldo_contado', '').strip()
        observaciones = request.POST.get(
            'observaciones_caja', ''
        ).strip()
        try:
            saldo_contado = Decimal(saldo_texto)
            if not saldo_contado.is_finite() or saldo_contado < 0:
                raise ValueError
        except (InvalidOperation, ValueError):
            messages.error(
                request,
                'El saldo contado debe ser un número válido y no negativo.'
            )
            return render(request, 'CAJA/arqueo_caja.html', {
                'caja': caja_actual,
            })
        try:
            with transaction.atomic():
                caja_actual.realizar_arqueo(
                    saldo_contado=saldo_contado,
                    empleado_arqueamiento=empleado,
                    observaciones_arqueo=observaciones
                )
            messages.success(request, 'El arqueo se realizó correctamente.')
        except ValueError as error:
            messages.error(request, str(error))
        return redirect('finanzas:detalle_caja', pk=pk)
    return render(request, 'CAJA/arqueo_caja.html', {
        'caja': caja_actual,
        'saldo_esperado': caja_actual.calcular_saldo_esperado(),
    })

def cerrar_caja(request, pk):
    caja_actual = get_object_or_404(caja, pk=pk)
    if request.method != 'POST':
        return redirect('finanzas:detalle_caja', pk=pk)
    try:
        empleado = request.user.empleado
    except Exception:
        messages.error(request, 'No tienes un empleado asociado.')
        return redirect('finanzas:detalle_caja', pk=pk)
    try:
        with transaction.atomic():
            caja_actual.cerrar_caja(empleado)
        messages.success(request, 'La caja se cerró correctamente.')
    except ValueError as error:
        messages.error(request, str(error))
    return redirect('finanzas:detalle_caja', pk=pk)

#FUNCIONES DE GASTOS
@login_required
@permiso_requerido('caja', 'leer')
def listar_gastos(request):
    gastos = gasto.objects.select_related(
        'caja_gasto',
        'cat_gasto',
        'empleado_gasto'
    ).all()
    buscar = request.GET.get('buscar', '').strip()
    caja_id = request.GET.get('caja', '').strip()
    if buscar:
        gastos = gastos.filter(
            Q(descripcion_gasto__icontains=buscar)
            | Q(cat_gasto__nombre_categoria_gasto__icontains=buscar)
        )
    if caja_id.isdigit():   
        gastos = gastos.filter(caja_gasto_id=int(caja_id))

    por_pagina = request.GET.get('por_pagina', 10)
    try:
        por_pagina = int(por_pagina)
        if por_pagina not in [10, 25, 50, 100]:
            por_pagina = 10
    except (ValueError, TypeError):
        por_pagina = 10
    paginator = Paginator(gastos.order_by('-fecha_hora_gasto'), por_pagina)
    gastos_paginados = paginator.get_page(request.GET.get('page'))
    return render(request, 'finanzas/listar_gastos.html', {
        'gastos': gastos_paginados,
        'buscar': buscar,
        'caja_seleccionada': caja_id,
        'cajas': caja.objects.all(),
        'por_pagina': por_pagina,
    })

@login_required
@permiso_requerido('caja', 'escribir')
def crear_gasto(request):
    cajas_abiertas = caja.objects.filter(
        estado_caja='abierto'
    )
    categorias = categoria_gasto.objects.filter(
        estado_categoria_gasto=True
    ).order_by('nombre_categoria_gasto')
    if request.method == 'POST':
        try:
            empleado = request.user.empleado
        except Exception:
            messages.error(request, 'No tienes un empleado asociado.')
            return redirect('finanzas:listar_gastos')
        descripcion = request.POST.get(
            'descripcion_gasto', ''
        ).strip()
        monto_texto = request.POST.get('monto_gasto', '').strip()
        caja_id = request.POST.get('caja_gasto', '').strip()
        categoria_id = request.POST.get('cat_gasto', '').strip()
        if not descripcion:
            messages.error(request, 'La descripción es obligatoria.')
        else:
            try:
                monto = Decimal(monto_texto)
                if not monto.is_finite() or monto <= 0:
                    raise ValueError
            except (InvalidOperation, ValueError):
                messages.error(
                    request,
                    'El monto debe ser un número válido mayor que cero.'
                )
            else:
                caja_actual = caja.objects.filter(
                    pk=caja_id,
                    estado_caja='abierto'
                ).first() if caja_id.isdigit() else None
                categoria = categoria_gasto.objects.filter(
                    pk=categoria_id,
                    estado_categoria_gasto=True
                ).first() if categoria_id.isdigit() else None
                if not caja_actual:
                    messages.error(
                        request,
                        'Seleccioná una caja abierta válida.'
                    )
                elif not categoria:
                    messages.error(
                        request,
                        'Seleccioná una categoría de gasto activa.'
                    )
                else:
                    with transaction.atomic():
                        gasto.objects.create(
                            descripcion_gasto=descripcion,
                            monto_gasto=monto,
                            caja_gasto=caja_actual,
                            cat_gasto=categoria,
                            empleado_gasto=empleado
                        )
                    messages.success(
                        request,
                        'El gasto se registró correctamente.'
                    )
                    return redirect('finanzas:listar_gastos')
        return render(request, 'finanzas/crear_gasto.html', {
            'cajas': cajas_abiertas,
            'categorias': categorias,
        })
    return render(request, 'finanzas/crear_gasto.html', {
        'cajas': cajas_abiertas,
        'categorias': categorias,
    })

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

    return render(request, 'finanzas/detalle_gasto.html', {
        'gasto': gasto_actual,
    })

@login_required
@permiso_requerido('caja', 'modificar')
def editar_gasto(request, pk):
    gasto_actual = get_object_or_404(
        gasto.objects.select_related('caja_gasto'),
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
        monto_texto = request.POST.get('monto_gasto', '').strip()
        caja_id = request.POST.get('caja_gasto', '').strip()
        categoria_id = request.POST.get('cat_gasto', '').strip()
        if not descripcion:
            messages.error(request, 'La descripción es obligatoria.')
            return render(request, 'finanzas/editar_gasto.html', {
                'gasto': gasto_actual,
                'cajas': cajas_abiertas,
                'categorias': categorias,
            })
        try:
            monto = Decimal(monto_texto)
            if not monto.is_finite() or monto <= 0:
                raise ValueError
        except (InvalidOperation, ValueError):
            messages.error(
                request,
                'El monto debe ser un número válido mayor que cero.'
            )
            return render(request, 'finanzas/editar_gasto.html', {
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
            messages.error(request, 'Seleccioná una caja abierta válida.')
        elif not categoria or (
            not categoria.estado_categoria_gasto
            and categoria.pk != gasto_actual.cat_gasto_id
        ):
            messages.error(request, 'Seleccioná una categoría válida.')
        else:
            with transaction.atomic():
                gasto_actual.descripcion_gasto = descripcion
                gasto_actual.monto_gasto = monto
                gasto_actual.caja_gasto = caja_actual
                gasto_actual.cat_gasto = categoria
                gasto_actual.save()
            messages.success(request, 'El gasto se actualizó correctamente.')
            return redirect('finanzas:listar_gastos')
    return render(request, 'finanzas/editar_gasto.html', {
        'gasto': gasto_actual,
        'cajas': cajas_abiertas,
        'categorias': categorias,
    })

@login_required
@permiso_requerido('caja', 'eliminar')
def eliminar_gasto(request, pk):
    gasto_actual = get_object_or_404(
        gasto.objects.select_related('caja_gasto'),
        pk=pk
    )
    if request.method == 'POST':
        if gasto_actual.caja_gasto.estado_caja != 'abierto':
            messages.error(
                request,
                'No se pueden eliminar gastos de una caja cerrada.'
            )
            return redirect('finanzas:detalle_gasto', pk=pk)
        descripcion = gasto_actual.descripcion_gasto
        with transaction.atomic():
            gasto_actual.delete()
        messages.success(
            request,
            f'El gasto "{descripcion}" se eliminó correctamente.'
        )
        return redirect('finanzas:listar_gastos')
    return render(request, 'finanzas/eliminar_gasto.html', {
        'gasto': gasto_actual,
    })

