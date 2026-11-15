from django.shortcuts import render

# Create your views here.
from datetime import datetime, time
from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import Mesa, Comanda, DetalleComanda
from .servicios import ESTADOS_ABIERTOS, registrar_pago
from django.forms import inlineformset_factory
from .forms import MesaForm, ComandaForm, DetalleComandaForm
from inventario.models import Plato, Bebida, CategoriaPlato, TipoBebida 
from auditoria.models import LogAuditoria
from core.mensajes import error_campo
from finanzas.models import caja, metodo_pago as MetodoPago
from empleados.decorators import permiso_requerido, tiene_permiso
from django.db import transaction
from reportlab.pdfgen import canvas
from django.http import HttpResponse
from django.utils import timezone
from core.fechas import limitar_rango
from django.db.models import Exists, OuterRef, Q
from django.core.paginator import Paginator
from django.utils.http import url_has_allowed_host_and_scheme
import traceback

_MENSAJE_COMANDA_BLOQUEADA = "La comanda #{} está cerrada o tiene pagos registrados: no se puede {}."


@login_required
@permiso_requerido("mesas", "leer")
def mesa_listar(request):
    mesas = Mesa.objects.annotate(
        comanda_abierta=Exists(
            Comanda.objects.filter(mesa=OuterRef("pk"), estado_comanda__in=ESTADOS_ABIERTOS)
        )
    ).order_by("numero_mesa")

    buscar = request.GET.get("buscar", "").strip()
    ubicaciones = request.GET.getlist("ubicacion")
    estados = request.GET.getlist("estado")

    if buscar:
        mesas = mesas.filter(numero_mesa__icontains=buscar)

    if ubicaciones:
        mesas = mesas.filter(ubicacion__in=ubicaciones)

    if estados:
        q_estado = Q()
        if "disponible" in estados:
            q_estado |= Q(estado_mesa=True)
        if "ocupada" in estados:
            q_estado |= Q(estado_mesa=False)
        if q_estado:
            mesas = mesas.filter(q_estado)

    por_pagina = request.GET.get("por_pagina", 10)
    try:
        por_pagina = int(por_pagina)
        if por_pagina not in [10, 25, 50, 100]:
            por_pagina = 10
    except (ValueError, TypeError):
        por_pagina = 10

    paginator = Paginator(mesas, por_pagina)
    page_number = request.GET.get("page")
    mesas = paginator.get_page(page_number)

    return render(
        request,
        "mesas/listar_mesas.html",
        {
            "mesas": mesas,
            "por_pagina": por_pagina,
            "buscar": buscar,
            "ubicaciones_seleccionadas": ubicaciones,
            "estados_seleccionados": estados,
            "puede_crear_comanda": tiene_permiso(request.user, "comandas", "escribir"),
        },
    )


@login_required
@permiso_requerido("mesas", "escribir")
def mesa_crear(request):
    if request.method == "POST":
        form = MesaForm(request.POST)
        if form.is_valid():
            mesa = form.save()

            LogAuditoria.objects.create(
                tabla="Mesa",
                accion="CREAR",
                registro_id=mesa.id_mesa,
                valores_anteriores="",
                valores_actuales=f"Mesa creada: N° {mesa.numero_mesa}. Ubicación: {mesa.ubicacion}",
                empleado=request.user.empleado,
            )

            messages.success(request, "Mesa creada exitosamente")
            return redirect("ventas:listar_mesa")
    else:
        form = MesaForm()
    return render(
        request,
        "mesas/crear_mesa.html",
        {"form": form, "titulo": "Crear Mesa", "boton": "Guardar"},
    )


@login_required
@permiso_requerido("mesas", "modificar")
def mesa_editar(request, pk):
    mesa = get_object_or_404(Mesa, pk=pk)
    if request.method == "POST":
        form = MesaForm(request.POST, instance=mesa)
        if form.is_valid():
            valores_viejos = f"N° {mesa.numero_mesa}, Ubicación: {mesa.ubicacion}"
            form.save()

            valores_nuevos = f"N° {mesa.numero_mesa}, Ubicación: {mesa.ubicacion}"
            LogAuditoria.objects.create(
                tabla="Mesa",
                accion="MODIFICAR",
                registro_id=mesa.id_mesa,
                valores_anteriores=valores_viejos,
                valores_actuales=valores_nuevos,
                empleado=request.user.empleado,
            )
            messages.success(request, "Mesa actualizada")
            return redirect("ventas:listar_mesa")
    else:
        form = MesaForm(instance=mesa)
    return render(
        request,
        "mesas/editar_mesa.html",
        {"form": form, "mesa": mesa, "titulo": "Editar Mesa", "boton": "Actualizar"},
    )


@login_required
@permiso_requerido("mesas", "eliminar")
def mesa_eliminar(request, pk):
    mesa = get_object_or_404(Mesa, pk=pk)
    if mesa.comandas.exists():
        messages.error(
            request,
            f"No se puede eliminar la mesa {mesa.numero_mesa} porque tiene comandas registradas.",
        )
        return redirect("ventas:listar_mesa")

    if request.method == "POST":
        numero = mesa.numero_mesa
        id_mesa = mesa.id_mesa

        LogAuditoria.objects.create(
            tabla="Mesa",
            accion="ELIMINAR",
            registro_id=id_mesa,
            valores_anteriores=f"Mesa N° {numero} eliminada",
            valores_actuales="",
            empleado=request.user.empleado,
        )

        mesa.delete()
        messages.success(request, f"Mesa {numero} eliminada")
        return redirect("ventas:listar_mesa")
    return render(request, "mesas/eliminar_mesa.html", {"mesa": mesa})


@login_required
@permiso_requerido("mesas", "modificar")
def mesa_estado(request, pk):
    mesa = get_object_or_404(Mesa, pk=pk)
    if request.method != "POST":
        return redirect("ventas:listar_mesa")
    motivo = request.POST.get("motivo_cambio", "Cambio de estado desde el listado")
    
    if mesa.estado_mesa == False:
        comandas_activas = mesa.comandas.filter(
            estado_comanda__in=["pendiente", "en_preparacion", "entregado"]
        )

        if comandas_activas.exists():
            comandas_ids = ",".join([f"#{c.id_comanda}" for c in comandas_activas])
            messages.error(
                request,
                f"No se puede liberar la Mesa {mesa.numero_mesa} porque tiene comandas activas: {comandas_ids}",
            )
            return redirect("ventas:listar_mesa")

    # Si llegó acá, se puede cambiar el estado
    estado_anterior = mesa.estado_mesa
    mesa.estado_mesa = not mesa.estado_mesa
    mesa.save()

    # Registrar en el Log de Auditoría
    LogAuditoria.objects.create(
        tabla="Mesa",
        accion="MODIFICAR",
        registro_id=mesa.id_mesa,
        valores_anteriores=f"Estado: {'Disponible' if estado_anterior else 'Ocupada'}",
        valores_actuales=f"Estado: {'Disponible' if mesa.estado_mesa else 'Ocupada'}. Motivo: {motivo}",
        empleado=request.user.empleado,
    )

    # Mensaje de éxito
    estado = "disponible" if mesa.estado_mesa else "ocupada"
    messages.success(request, f"Mesa {mesa.numero_mesa} ahora está {estado}")
    return redirect("ventas:listar_mesa")


@login_required
@permiso_requerido("mesas", "leer")
def mesa_ver_comandas(request, pk):
    mesa = get_object_or_404(Mesa, pk=pk)
    comandas = Comanda.objects.filter(mesa=mesa).order_by("-fecha_hora")

    return render(
        request, "mesas/mesa_comandas.html", {"mesa": mesa, "comandas": comandas}
    )


# COMANDAS
# LISTAR COMANDAS
@login_required
@permiso_requerido("comandas", "leer")
def comanda_listar(request):
    comandas = (
        Comanda.objects.all()
        .select_related(
            "mesa",
            "empleado",
        )
        .order_by("-fecha_hora")
    )
    mesas = Mesa.objects.all().order_by("numero_mesa")
    metodos_pago = MetodoPago.objects.filter(
        estado_metodo_pago=True
    ).order_by('nombre_metodo_pago')
    buscar = request.GET.get("buscar", "").strip()
    estados = request.GET.getlist("estado")
    mesas_ids = request.GET.getlist("mesa")
    fecha_desde, fecha_hasta = limitar_rango(
        request.GET.get("fecha_desde", ""), request.GET.get("fecha_hasta", "")
    )
    if buscar:
        comandas = comandas.filter(
            Q(id_comanda__icontains=buscar)
            | Q(empleado__nombre_empleado__icontains=buscar)
            | Q(empleado__apellido_empleado__icontains=buscar)
        )
    if estados:
        comandas = comandas.filter(estado_comanda__in=estados)
    mesas_ids_int = []
    for m in mesas_ids:
        if m.isdigit():
            mesas_ids_int.append(int(m))
    if mesas_ids_int:
        comandas = comandas.filter(mesa_id__in=mesas_ids_int)

    tz_actual = timezone.get_current_timezone()

    if fecha_desde:
        try:
            desde_dt = datetime.strptime(fecha_desde, "%Y-%m-%d")
            desde_con_tz = timezone.make_aware(
                datetime.combine(desde_dt.date(), time.min), tz_actual
            )
            comandas = comandas.filter(fecha_hora__gte=desde_con_tz)
        except ValueError:
            pass

    if fecha_hasta:
        try:
            hasta_dt = datetime.strptime(fecha_hasta, "%Y-%m-%d")
            hasta_con_tz = timezone.make_aware(
                datetime.combine(hasta_dt.date(), time.max), tz_actual
            )
            comandas = comandas.filter(fecha_hora__lte=hasta_con_tz)
        except ValueError:
            pass

    por_pagina = request.GET.get("por_pagina", 10)
    try:
        por_pagina = int(por_pagina)
        if por_pagina not in [10, 25, 50, 100]:
            por_pagina = 10
    except (ValueError, TypeError):
        por_pagina = 10

    paginator = Paginator(comandas, por_pagina)
    page_number = request.GET.get("page")
    comandas = paginator.get_page(page_number)

    return render(
        request,
        "comandas/comanda_listar.html",
        {
            "resaltar": request.GET.get("resaltar", ""),
            "comandas": comandas,
            "mesas": mesas,
            "metodos_pago": metodos_pago,
            "por_pagina": por_pagina,
            "buscar": buscar,
            "estados_seleccionados": estados,
            "mesas_seleccionadas": [str(m) for m in mesas_ids_int],
            "fecha_desde": fecha_desde,
            "fecha_hasta": fecha_hasta,
        },
    )


# CREAR COMANDA
from django.db import transaction
@login_required
@permiso_requerido("comandas", "escribir")
def comanda_crear(request):
    DetalleFormSet = inlineformset_factory(
        Comanda, DetalleComanda, form=DetalleComandaForm, extra=3, can_delete=True
    )

    try:
        mozo_actual = request.user.empleado
    except Exception:
        mozo_actual = None
    mozo_id = request.POST.get("mozo") or (mozo_actual.pk if mozo_actual else "")

    # Agregar productos a una mesa que ya tiene pedido: misma pantalla, sobre su comanda abierta
    id_existente = request.POST.get("comanda_id") or request.GET.get("comanda")
    if id_existente:
        return _agregar_a_comanda(request, id_existente, DetalleFormSet, mozo_id)

    if request.method == "POST":
        form = ComandaForm(request.POST)
        formset = DetalleFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            detalles_validos = 0
            for form_detalle in formset:
                if form_detalle.cleaned_data and not form_detalle.cleaned_data.get(
                    "DELETE", False
                ):
                    if form_detalle.cleaned_data.get(
                        "plato"
                    ) or form_detalle.cleaned_data.get("bebida"):
                        detalles_validos += 1

            if detalles_validos == 0:
                messages.error(
                    request, "Debe agregar al menos un plato o bebida a la comanda."
                )
                return render(
                    request,
                    "comandas/comanda_crear.html",
                    _contexto_crear_comanda(request, form, formset, mozo_id),
                )
            try:
                with transaction.atomic():
                    # Crear la comanda (sin guardar aún)
                    comanda = form.save(commit=False)
                    # El mozo elegido en la pantalla; si no vino o no es válido, el usuario actual
                    mozo = _mozos_disponibles().filter(pk=mozo_id).first() if str(mozo_id).isdigit() else None
                    comanda.empleado = mozo or mozo_actual
                    if comanda.empleado is None:
                        messages.error(request, "No tienes un empleado asociado.")
                        return redirect("ventas:comanda_listar")
                    # Guardar la comanda
                    comanda.save()
                    # Guardar los detalles
                    formset.instance = comanda
                    formset.save()
                    # Calcular el total
                    comanda.calcular_total()
                    # Cambiar el estado de la mesa
                    comanda.mesa.estado_mesa = False
                    comanda.mesa.save()

                    LogAuditoria.objects.create(
                        tabla="Comanda",
                        accion="CREAR",
                        registro_id=comanda.id_comanda,
                        valores_anteriores="",
                        valores_actuales=f"Comanda #{comanda.id_comanda} creada. Mesa: {comanda.mesa.numero_mesa}. Total: ${comanda.total_comanda}",
                        empleado=request.user.empleado,
                    )
                # Si llegó acá, TODO se guardó correctamente
                messages.success(
                    request, f"Comanda #{comanda.id_comanda} creada exitosamente"
                )
                return redirect(_ir_al_ticket(comanda))
            except Exception as e:
                # Si algo falló, la transacción se revirtió automáticamente
                messages.error(request, f"Error al crear la comanda: {e}")
                print("=" * 60)
                print("ERROR EN TRANSACCIÓN:")
                print(f"Tipo: {type(e).__name__}")
                print(f"Mensaje: {e}")
                import traceback

                traceback.print_exc()
                print("=" * 60)

    else:
        form = ComandaForm(initial={"mesa": request.GET.get("mesa")})
        formset = DetalleFormSet()

    return render(
        request,
        "comandas/comanda_crear.html",
        _contexto_crear_comanda(request, form, formset, mozo_id),
    )


@login_required
@permiso_requerido("comandas", "modificar")
def comanda_editar(request, pk):
    comanda = get_object_or_404(Comanda, id_comanda=pk)
    if not comanda.esta_abierta:
        messages.error(request, f"La comanda #{comanda.id_comanda} está cerrada: no se puede editar.")
        return redirect("ventas:comanda_listar")
    tiene_pagos = comanda.pagos.exists()
    mesa_anterior = comanda.mesa
    DetalleFormSet = inlineformset_factory(
        Comanda,
        DetalleComanda,
        form=DetalleComandaForm,
        extra=1,
        can_delete=True,
        fields=["plato", "cant_plato", "bebida", "cant_bebida", "observacion"],
    )

    if request.method == "POST":
        form = ComandaForm(request.POST, instance=comanda)
        formset = DetalleFormSet(request.POST, instance=comanda, form_kwargs={"comanda": comanda})
        if form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():
                    _validar_cambios_detalle(pk, formset, tiene_pagos)
                    comanda_guardada = form.save(commit=False)
                    comanda_guardada.mesa = form.cleaned_data["mesa"]
                    comanda_guardada.save()
                    # Lo que la estación ya marcó como listo se conserva si su cantidad no aumentó
                    ya_listos = {
                        (d.plato_id, d.bebida_id): (d.listo, d.cant_plato, d.cant_bebida)
                        for d in DetalleComanda.objects.filter(comanda_id=pk, listo__isnull=False)
                    }
                    formset.save()
                    comanda_guardada.detalles.all().delete()
                    formset.instance = comanda_guardada
                    formset.save()
                    for d in comanda_guardada.detalles.all():
                        previo = ya_listos.get((d.plato_id, d.bebida_id))
                        if previo and d.cant_plato <= previo[1] and d.cant_bebida <= previo[2]:
                            DetalleComanda.objects.filter(pk=d.pk).update(listo=previo[0])
                    comanda_guardada.calcular_total()
                    if comanda_guardada.total_comanda < comanda_guardada.total_pagado:
                        raise ValueError(
                            f"El nuevo total (${comanda_guardada.total_comanda}) no puede ser menor a lo ya cobrado (${comanda_guardada.total_pagado})."
                        )

                    if mesa_anterior != comanda_guardada.mesa:
                        mesa_anterior.estado_mesa = True  # Liberar la anterior
                        mesa_anterior.save()
                        comanda_guardada.mesa.estado_mesa = False  # Ocupar la nueva
                        comanda_guardada.mesa.save()

                    LogAuditoria.objects.create(
                        tabla="Comanda",
                        accion="MODIFICAR",
                        registro_id=comanda_guardada.id_comanda,
                        valores_anteriores=f"Comanda #{comanda_guardada.id_comanda}",
                        valores_actuales=f"Comanda #{comanda_guardada.id_comanda} actualizada. Mesa: {comanda_guardada.mesa.numero_mesa}. Total: ${comanda_guardada.total_comanda}",
                        empleado=request.user.empleado,
                    )
            except ValueError as e:
                messages.error(request, str(e))
                return redirect("ventas:comanda_editar", pk=pk)
            messages.success(request, f"Comanda #{pk} actualizada")
            return redirect(_ir_al_ticket(comanda, modificada=True))
    else:
        form = ComandaForm(instance=comanda)
        formset = DetalleFormSet(instance=comanda, form_kwargs={"comanda": comanda})
    return render(
        request,
        "comandas/comanda_editar.html",
        {
            "form": form,
            "formset": formset,
            "comanda": comanda,
            "tiene_pagos": tiene_pagos,
            "productos_no_disponibles": _productos_no_disponibles(comanda),
            **_productos_por_pedidos(),
            "categorias": CategoriaPlato.objects.filter(estado_categoria_plato=True),
            "tipos_bebida": TipoBebida.objects.filter(estado_tipo_bebida=True),
        },
    )


def _productos_no_disponibles(comanda):
    """Productos de la comanda que ya no se venden: no están en la grilla, pero siguen en el carrito."""
    productos = []
    for d in comanda.detalles.select_related("plato", "bebida"):
        if d.plato and not d.plato.estado_plato:
            productos.append(
                {"tipo": "plato", "id": d.plato_id, "nombre": d.plato.nombre_plato, "precio": d.plato.precio_plato}
            )
        if d.bebida and not d.bebida.disponible_bebida:
            productos.append(
                {"tipo": "bebida", "id": d.bebida_id, "nombre": d.bebida.nombre_bebida, "precio": d.bebida.precio_bebida}
            )
    return productos


def _sumar_cantidades(filas):
    """Agrupa (plato, cant_plato, bebida, cant_bebida) en {producto: cantidad total}."""
    cantidades = {}
    for plato, cant_plato, bebida, cant_bebida in filas:
        if plato:
            cantidades[plato] = cantidades.get(plato, 0) + (cant_plato or 0)
        if bebida:
            cantidades[bebida] = cantidades.get(bebida, 0) + (cant_bebida or 0)
    return cantidades


def _validar_cambios_detalle(id_comanda, formset, tiene_pagos):
    """Un producto no disponible no puede aumentar. Con pagos, tampoco se puede quitar ni reducir nada."""
    anteriores = _sumar_cantidades(
        (d.plato, d.cant_plato, d.bebida, d.cant_bebida)
        for d in DetalleComanda.objects.filter(comanda_id=id_comanda).select_related("plato", "bebida")
    )
    nuevas = _sumar_cantidades(
        (
            form.cleaned_data.get("plato"),
            form.cleaned_data.get("cant_plato"),
            form.cleaned_data.get("bebida"),
            form.cleaned_data.get("cant_bebida"),
        )
        for form in formset.forms
        if not form.cleaned_data.get("DELETE")
    )
    if tiene_pagos:
        for producto, cantidad in anteriores.items():
            if nuevas.get(producto, 0) < cantidad:
                raise ValueError(
                    "La comanda tiene pagos registrados: podés agregar productos, pero no quitar ni reducir los que ya tenía."
                )
    for producto, cantidad in nuevas.items():
        disponible = producto.estado_plato if isinstance(producto, Plato) else producto.disponible_bebida
        if not disponible and cantidad > anteriores.get(producto, 0):
            raise ValueError("Un producto no disponible no se puede agregar ni aumentar.")


# DETALLE COMANDA
@login_required
@permiso_requerido("comandas", "leer")
def comanda_detalle(request, pk):
    comanda = get_object_or_404(Comanda, id_comanda=pk)
    detalles = comanda.detalles.all().select_related("plato", "bebida")
    return render(
        request,
        "comandas/comanda_detalle.html",
        {"comanda": comanda, "detalles": detalles},
    )


# CAMBIAR ESTADO
@login_required
@permiso_requerido("comandas", "modificar")
def comanda_cambiar_estado(request, pk):
    comanda = get_object_or_404(Comanda, id_comanda=pk)
    if request.method != "POST":
        return redirect("ventas:comanda_listar")
    nuevo_estado = request.POST.get("estado") or request.GET.get("estado")

    if comanda.estado_comanda in ["pagado", "anulado"]:
        messages.error(
            request,
            f"La comanda #{comanda.id_comanda} ya está {comanda.get_estado_comanda_display()} y no se puede modificar.",
        )
        return redirect("ventas:comanda_listar")

    if nuevo_estado == "pagado":
        messages.error(request, "Para marcar una comanda como pagada, registrá el pago.")
        return redirect("ventas:comanda_listar")

    if nuevo_estado not in ["pendiente", "en_preparacion", "entregado", "anulado"]:
        messages.error(request, "Estado no válido.")
        return redirect("ventas:comanda_listar")

    if nuevo_estado == "anulado" and not comanda.puede_modificarse:
        messages.error(request, _MENSAJE_COMANDA_BLOQUEADA.format(comanda.id_comanda, "anular"))
        return redirect("ventas:comanda_listar")

    if nuevo_estado:
        if nuevo_estado == "anulado":
            motivo = request.POST.get("motivo_cambio", "Anulada desde el listado")

            try:
                with transaction.atomic():
                    estado_anterior = comanda.estado_comanda
                    comanda.estado_comanda = "anulado"
                    comanda.fecha_anulacion = timezone.now()
                    comanda.motivo_anulacion = motivo
                    comanda.usuario_anulacion = request.user.empleado
                    comanda.save()
                    # Revertir la mesa a "Disponible"
                    comanda.mesa.estado_mesa = True
                    comanda.mesa.save()

                    # LOG DE AUDITORÍA
                    LogAuditoria.objects.create(
                        tabla="Comanda",
                        accion="ANULAR",
                        registro_id=comanda.id_comanda,
                        valores_anteriores=f"Estado: {estado_anterior}",
                        valores_actuales=f"Estado: anulado. Motivo: {motivo}. Fecha anulación: {timezone.now().strftime('%d/%m/%Y %H:%M')}",
                        empleado=request.user.empleado,
                    )
                messages.success(
                    request, f"Comanda #{comanda.id_comanda} anulada exitosamente"
                )
            except Exception as e:
                messages.error(request, f"Error al anular: {e}")
        else:
            try:
                with transaction.atomic():
                    estado_anterior = comanda.estado_comanda
                    comanda.estado_comanda = nuevo_estado
                    comanda.save()
                    if nuevo_estado in ["pagado", "anulado"]:
                        comanda.mesa.estado_mesa = True
                    elif nuevo_estado in ["pendiente", "en_preparacion", "entregado"]:
                        comanda.mesa.estado_mesa = False
                    comanda.mesa.save()

                    # LOG DE AUDITORÍA
                    LogAuditoria.objects.create(
                        tabla="Comanda",
                        accion="MODIFICAR",
                        registro_id=comanda.id_comanda,
                        valores_anteriores=f"Estado: {estado_anterior}",
                        valores_actuales=f"Estado: {nuevo_estado}",
                        empleado=request.user.empleado,
                    )

                messages.success(
                    request,
                    f"Comanda #{comanda.id_comanda} ahora está {comanda.get_estado_comanda_display()}",
                )
            except Exception as e:
                messages.error(request, f"Error al cambiar el estado: {e}")
    next_url = request.POST.get("next")
    if next_url and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}
    ):
        return redirect(next_url)

    return redirect("ventas:comanda_listar")


@login_required
@permiso_requerido("comandas", "eliminar")  
def comanda_eliminar(request, pk):
    comanda = get_object_or_404(Comanda, id_comanda=pk)
    if not comanda.puede_modificarse:
        messages.error(request, _MENSAJE_COMANDA_BLOQUEADA.format(comanda.id_comanda, "eliminar"))
        return redirect("ventas:comanda_listar")

    if request.method == "POST":
        id_comanda = comanda.id_comanda
        try:
            with transaction.atomic():
                # Liberar la mesa
                comanda.mesa.estado_mesa = True
                comanda.mesa.save()
                comanda.delete()
            messages.success(request, f"Comanda #{id_comanda} eliminada")
            return redirect("ventas:comanda_listar")
        except Exception as e:
            messages.error(request, f"Error al eliminar la comanda: {e}")

    return render(request, "comandas/comanda_eliminar.html", {"comanda": comanda})


@login_required
@permiso_requerido("comandas", "modificar")
def comanda_anular(request, pk):
    comanda = get_object_or_404(Comanda, id_comanda=pk)

    if not comanda.puede_modificarse:
        messages.error(request, _MENSAJE_COMANDA_BLOQUEADA.format(comanda.id_comanda, "anular"))
        return redirect("ventas:comanda_listar")

    if request.method == "POST":
        motivo = (request.POST.get("motivo") or "").strip()
        if not motivo:
            error_campo(request, "motivo", "Escribí el motivo de la anulación.")
            return render(request, "comandas/comanda_anular.html", {"comanda": comanda})
        if len(motivo) > 250:
            error_campo(request, "motivo", "El motivo no puede superar los 250 caracteres.")
            return render(request, "comandas/comanda_anular.html", {"comanda": comanda})

        try:
            with transaction.atomic():
                comanda.estado_comanda = "anulado"
                comanda.fecha_anulacion = timezone.now()
                comanda.motivo_anulacion = motivo
                comanda.usuario_anulacion = request.user.empleado
                comanda.save()

                # Revertir mesa
                comanda.mesa.estado_mesa = True
                comanda.mesa.save()

            messages.success(request, f"Comanda #{comanda.id_comanda} anulada")
            return redirect("ventas:comanda_listar")
        except Exception as e:
            messages.error(request, f"Error: {e}")

    return render(request, "comandas/comanda_anular.html", {"comanda": comanda})


@login_required
@permiso_requerido("comandas", "leer")
def comanda_consultar(request):
    comandas = Comanda.objects.all().order_by("-fecha_hora")

    fecha_desde, fecha_hasta = limitar_rango(
        request.GET.get("fecha_desde"), request.GET.get("fecha_hasta")
    )
    estado = request.GET.get("estado")
    mesa_id = request.GET.get("mesa")

    # Obtener la zona horaria actual('America/Argentina/Salta')
    tz_actual = timezone.get_current_timezone()

    if fecha_desde:
        try:
            # Crear un objeto datetime a las 00:00:00 del día elegido
            desde_dt = datetime.strptime(fecha_desde, "%Y-%m-%d")
            desde_con_tz = timezone.make_aware(
                datetime.combine(desde_dt.date(), time.min), tz_actual
            )
            # Filtramos directamente sobre el campo DateTimeField sin usar __date
            comandas = comandas.filter(fecha_hora__gte=desde_con_tz)
        except ValueError:
            pass

    if fecha_hasta:
        try:
            # Creamos un objeto datetime a las 23:59:59.999999 del día elegido para incluir todo el día
            hasta_dt = datetime.strptime(fecha_hasta, "%Y-%m-%d")
            hasta_con_tz = timezone.make_aware(
                datetime.combine(hasta_dt.date(), time.max), tz_actual
            )
            comandas = comandas.filter(fecha_hora__lte=hasta_con_tz)
        except ValueError:
            pass

    if estado:
        comandas = comandas.filter(estado_comanda=estado)

    if mesa_id and mesa_id.isdigit():
        comandas = comandas.filter(mesa_id=int(mesa_id))

    mesas = Mesa.objects.all()

    return render(
        request,
        "comandas/comanda_consultar.html",
        {
            "comandas": comandas,
            "mesas": mesas,
            "filtros": {
                "fecha_desde": fecha_desde,
                "fecha_hasta": fecha_hasta,
                "estado": estado,
                "mesa": int(mesa_id) if (mesa_id and mesa_id.isdigit()) else "",
            },
        },
    )


@login_required
@permiso_requerido("comandas", "leer")
def comanda_comprobante(request, pk):
    comanda = get_object_or_404(Comanda, id_comanda=pk)
    detalles = comanda.detalles.all().select_related("plato", "bebida")
    pagos = comanda.pagos.select_related("metodo_pago").order_by("fecha_hora")

    return render(
        request,
        "comandas/comanda_comprobante.html",
        {
            "comanda": comanda,
            "detalles": detalles,
            "pagos": pagos,
            "subtotal_platos": sum(d.subtotal_plato for d in detalles),
            "subtotal_bebidas": sum(d.subtotal_bebida for d in detalles),
        },
    )


_ESTACIONES_TICKET = (
    {"clave": "cocina", "titulo": "PLATOS", "destino": "Cocina", "icono": "bandeja"},
    {"clave": "bar", "titulo": "BEBIDAS", "destino": "Bar", "icono": "vaso-blanco"},
    {"clave": "parrilla", "titulo": "PARRILLA", "destino": "Parrilla", "icono": "parrilla"},
)


def _tickets_de_comanda(detalles):
    """Bebidas al bar, platos de la categoría Parrilla a la parrilla, y el resto a la cocina.

    Solo devuelve los tickets que tienen algo para preparar.
    """
    productos = {estacion["clave"]: [] for estacion in _ESTACIONES_TICKET}
    for detalle in detalles:
        # Si el producto ya se eliminó del inventario, se usan los datos guardados en la línea
        if detalle.tiene_plato:
            categoria = (detalle.categoria_del_plato or "").strip().lower()
            estacion = "parrilla" if categoria == "parrilla" else "cocina"
            productos[estacion].append(
                {"nombre": detalle.nombre_del_plato, "cantidad": detalle.cant_plato, "nota": detalle.observacion}
            )
        # Un mismo detalle puede traer un plato y una bebida
        if detalle.tiene_bebida:
            productos["bar"].append(
                {"nombre": detalle.nombre_de_la_bebida, "cantidad": detalle.cant_bebida, "nota": detalle.observacion}
            )
    return [
        {**estacion, "productos": productos[estacion["clave"]]}
        for estacion in _ESTACIONES_TICKET
        if productos[estacion["clave"]]
    ]


@login_required
@permiso_requerido("comandas", "leer")
def comanda_ticket(request, pk):
    comanda = get_object_or_404(Comanda.objects.select_related("mesa", "empleado"), id_comanda=pk)
    detalles = comanda.detalles.all().select_related("plato__categoria", "bebida")
    # ?detalles=1,2: solo lo que se agregó a la comanda (lo demás ya está en la cocina)
    solo = [d for d in request.GET.get("detalles", "").split(",") if d.isdigit()]
    if solo:
        detalles = detalles.filter(pk__in=solo)

    return render(
        request,
        "comandas/comanda_ticket.html",
        {
            "comanda": comanda,
            "tickets": _tickets_de_comanda(detalles),
            "anulada": comanda.estado_comanda in ("anulado", "cancelado"),
            "agregado": bool(solo),
            "modificada": request.GET.get("modificada") == "1",
            # Recién guardada: se imprime sola y después se va al listado, con la comanda resaltada
            "imprimir_al_abrir": request.GET.get("imprimir") == "1",
            "url_listado": f"{reverse('ventas:comanda_listar')}?resaltar={comanda.pk}",
        },
    )

@login_required
@permiso_requerido("comandas", "modificar")
def comanda_cobrar(request):
    if request.method == "POST":
        try:
            with transaction.atomic():
                _registrar_pago(request)
        except ValueError as e:
            messages.error(request, str(e))
        except Exception as e:
            messages.error(request, f"Error al registrar el pago: {e}")

    next_url = request.POST.get("next")
    if next_url and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}
    ):
        return redirect(next_url)
    return redirect("ventas:comanda_listar")


def _registrar_pago(request):
    """Registra el pago y cierra la comanda si queda sin saldo."""
    metodo_pago_id = request.POST.get("metodo_pago")
    comanda, monto, saldo_restante, vuelto = registrar_pago(
        request.POST.get("comanda_id"),
        request.POST.get("tipo_pago"),
        metodo_pago_id,
        request.POST.get("monto_abonado", ""),
        request.user.empleado,
        request.POST.get("monto_recibido", "").strip(),
    )
    texto_vuelto = f" Vuelto a entregar: ${vuelto}." if vuelto else ""

    if saldo_restante == 0:
        messages.success(
            request,
            f"Comanda #{comanda.id_comanda} pagada en su totalidad.{texto_vuelto}"
        )
    else:
        messages.success(
            request,
            f"Pago de ${monto} registrado en la comanda "
            f"#{comanda.id_comanda}. Saldo pendiente: ${saldo_restante}.{texto_vuelto}"
        )

def texto_espera(minutos):
    """Espera corta para el plano: 25', 3h o 2d."""
    if minutos < 60:
        return f"{minutos}'"
    if minutos < 60 * 24:
        return f"{minutos // 60}h"
    return f"{minutos // (60 * 24)}d"


# PLANO DEL SALÓN Y MOZOS (para tomar el pedido)
def _plano_de_mesas(request, mesa_elegida_id=None):
    """El local con cada mesa en su lugar y su estado (ver ventas/plano_salon.py)."""
    from . import plano_salon as plano

    mesas = {mesa.numero_mesa: mesa for mesa in Mesa.objects.all()}
    # La comanda abierta más reciente de cada mesa (una sola consulta)
    from django.db.models import Count, Subquery, Sum
    from django.db.models.functions import Coalesce

    # Mismo límite que la alerta de "Comanda demorada" (configurable, 30 minutos por defecto)
    from notificaciones.reglas import leer_config

    limite_minutos = int(leer_config("minutos_comanda_demorada", 30))
    ahora = timezone.now()

    abiertas = {}
    for comanda in (
        Comanda.objects.filter(estado_comanda__in=ESTADOS_ABIERTOS)
        .select_related("empleado")
        .annotate(con_productos=Exists(DetalleComanda.objects.filter(comanda=OuterRef("pk"))))
        .annotate(sin_preparar=Coalesce(Subquery(
            DetalleComanda.objects.filter(comanda=OuterRef("pk"), listo__isnull=True)
            .order_by().values("comanda").annotate(n=Count("pk")).values("n")[:1]
        ), 0))
        .annotate(pagado=Coalesce(Sum("pagos__monto"), Decimal("0")))
        .order_by("fecha_hora")
    ):
        comanda.saldo = max(comanda.total_comanda - comanda.pagado, Decimal("0"))
        comanda.espera = max(int((ahora - comanda.fecha_hora).total_seconds() // 60), 0)
        comanda.espera_texto = texto_espera(comanda.espera)
        # Todo lo pedido está preparado y falta llevarlo a la mesa
        comanda.listo_para_llevar = (
            comanda.con_productos and comanda.sin_preparar == 0 and comanda.estado_comanda != "entregado"
        )
        # Solo se demora lo que todavía no se entregó
        comanda.demorada = not comanda.listo_para_llevar and (
            comanda.estado_comanda in ("pendiente", "en_preparacion")
            and comanda.espera >= limite_minutos
        )
        abiertas[comanda.mesa_id] = comanda
    puede_ver = tiene_permiso(request.user, "comandas", "leer")
    puede_agregar = tiene_permiso(request.user, "comandas", "modificar")

    lugares = []
    for dato in plano.MESAS:
        mesa = mesas.get(dato["numero"])
        lugar = {
            **dato,
            "pos": plano.a_porcentajes(dato["x"], dato["y"], plano.MESA_LADO, plano.MESA_LADO),
            "mesa": mesa,
            "comanda": None,
            "url": "",
            "elegida": bool(mesa and str(mesa.pk) == str(mesa_elegida_id)),
        }
        if mesa is None:
            lugar["estado"] = "sin-cargar"
        elif mesa.estado_mesa:
            lugar["estado"] = "libre"
        elif mesa.pk not in abiertas:
            # Marcada como ocupada a mano (clientes sentados), todavía sin comanda: se puede tomar el pedido
            lugar["estado"] = "sin-pedido"
        else:
            lugar["estado"] = "ocupada"
            lugar["comanda"] = abiertas.get(mesa.pk)
            if lugar["comanda"] and puede_agregar:
                lugar["url"] = reverse("ventas:comanda_editar", args=[lugar["comanda"].pk])
                lugar["accion"] = "agregar"
            elif lugar["comanda"] and puede_ver:
                lugar["url"] = reverse("ventas:comanda_detalle", args=[lugar["comanda"].pk])
            else:
                lugar["url"] = reverse("ventas:mesa_ver_comandas", args=[mesa.pk])
        lugares.append(lugar)

    def con_posicion(items):
        return [{**item, "pos": plano.a_porcentajes(item["x"], item["y"], item["ancho"], item["alto"])} for item in items]

    return {
        "lugares": lugares,
        "zonas": con_posicion(plano.ZONAS),
        "elementos": con_posicion(plano.ELEMENTOS),
        "pilares": [
            plano.a_porcentajes(x - plano.PILAR_DIAMETRO / 2, y - plano.PILAR_DIAMETRO / 2,
                                plano.PILAR_DIAMETRO, plano.PILAR_DIAMETRO)
            for x, y in plano.PILARES
        ],
        "libres": sum(1 for lugar in lugares if lugar["estado"] == "libre"),
        "sin_pedido": sum(1 for lugar in lugares if lugar["estado"] == "sin-pedido"),
        "ocupadas": sum(1 for lugar in lugares if lugar["estado"] == "ocupada"),
        "proporcion": f"{plano.LIENZO[2]} / {plano.LIENZO[3]}",
        "puede_agregar": puede_agregar,
        "puede_ver": puede_ver,
        "limite_minutos": limite_minutos,
        # Las mesas abiertas del mozo que está usando el sistema, de la más antigua a la más nueva
        "mis_mesas": sorted(
            (lugar for lugar in lugares
             if lugar["comanda"] and lugar["comanda"].empleado.user_id == request.user.pk),
            key=lambda lugar: lugar["comanda"].fecha_hora,
        ),
        "demoradas": sum(1 for lugar in lugares if lugar["comanda"] and lugar["comanda"].demorada),
    }


def _ir_al_ticket(comanda, detalles=None, modificada=False):
    """Después de guardar: el ticket se abre y se imprime solo; al terminar, va al listado.

    detalles: solo esas líneas (lo agregado a una comanda que ya existía), para que la
    cocina no vuelva a preparar lo que ya salió.
    """
    from urllib.parse import urlencode

    parametros = {"imprimir": 1}
    if detalles:
        parametros["detalles"] = ",".join(str(d.pk) for d in detalles)
    if modificada:
        parametros["modificada"] = 1
    return f"{reverse('ventas:comanda_ticket', args=[comanda.pk])}?{urlencode(parametros)}"


def _mozos_disponibles():
    """Empleados activos que pueden tomar pedidos: su cargo puede crear comandas, o es administrador."""
    from empleados.decorators import NIVEL_ADMINISTRADOR
    from empleados.models import Empleado, PermisoXCargo

    cargos = PermisoXCargo.objects.filter(
        tipo_permiso__modulo="comandas", tipo_permiso__accion="escribir"
    ).values("cargo")
    return (
        Empleado.objects.filter(estado=True, user__is_active=True)
        .filter(Q(cargo__in=cargos) | Q(cargo__nivel_acceso__gte=NIVEL_ADMINISTRADOR))
        .select_related("cargo")
        .order_by("nombre_empleado", "apellido_empleado")
    )


def _agregar_a_comanda(request, id_comanda, DetalleFormSet, mozo_id):
    """Suma productos nuevos a una comanda abierta, desde la pantalla de toma de pedido.

    Lo que la comanda ya tenía no se toca (sirve aunque tenga pagos): solo se agregan filas.
    """
    comanda = (
        Comanda.objects.select_related("mesa", "empleado").filter(pk=id_comanda).first()
        if str(id_comanda).isdigit() else None
    )
    if comanda is None or not comanda.esta_abierta:
        messages.error(request, "Esa comanda ya está cerrada: elegí la mesa de nuevo en el plano.")
        return redirect("ventas:comanda_crear")
    if not tiene_permiso(request.user, "comandas", "modificar"):
        messages.error(request, "Tu cargo no puede agregar productos a una comanda.")
        return redirect("ventas:comanda_crear")

    form = ComandaForm(initial={"mesa": comanda.mesa_id})
    if request.method == "POST":
        formset = DetalleFormSet(request.POST)
        if formset.is_valid():
            nuevos = [
                f.cleaned_data for f in formset
                if f.cleaned_data and not f.cleaned_data.get("DELETE")
                and (f.cleaned_data.get("plato") or f.cleaned_data.get("bebida"))
            ]
            if not nuevos:
                messages.error(request, "Sumá al menos un plato o una bebida para agregar a la comanda.")
            else:
                with transaction.atomic():
                    agregados = []
                    for datos in nuevos:
                        agregados.append(DetalleComanda.objects.create(
                            comanda=comanda,
                            plato=datos.get("plato"),
                            cant_plato=datos.get("cant_plato") or 0,
                            bebida=datos.get("bebida"),
                            cant_bebida=datos.get("cant_bebida") or 0,
                            observacion=(datos.get("observacion") or "").strip(),
                        ))
                    total_anterior = comanda.total_comanda
                    comanda.calcular_total()
                    LogAuditoria.objects.create(
                        tabla="Comanda",
                        accion="MODIFICAR",
                        registro_id=comanda.id_comanda,
                        valores_anteriores=f"Total: ${total_anterior}",
                        valores_actuales=(
                            f"Se agregaron {len(nuevos)} producto(s) a la comanda #{comanda.id_comanda}. "
                            f"Mesa: {comanda.mesa.numero_mesa}. Total: ${comanda.total_comanda}"
                        ),
                        empleado=request.user.empleado,
                    )
                messages.success(
                    request,
                    f"Se agregaron productos a la mesa {comanda.mesa.numero_mesa} (comanda #{comanda.id_comanda}).",
                )
                return redirect(_ir_al_ticket(comanda, detalles=agregados))
    else:
        formset = DetalleFormSet()

    contexto = _contexto_crear_comanda(request, form, formset, mozo_id)
    contexto["comanda_existente"] = comanda
    contexto["ya_pedido"] = list(comanda.detalles.select_related("plato", "bebida"))
    return render(request, "comandas/comanda_crear.html", contexto)


def _carrito_enviado(datos):
    """Los productos que venían en el formulario, para no perder el pedido si hay que corregir algo."""
    try:
        total = min(int(datos.get("detalles-TOTAL_FORMS", 0)), 200)
    except (TypeError, ValueError):
        return []
    items = []
    for i in range(total):
        for tipo, campo_cantidad in (("plato", "cant_plato"), ("bebida", "cant_bebida")):
            producto = datos.get(f"detalles-{i}-{tipo}", "")
            cantidad = datos.get(f"detalles-{i}-{campo_cantidad}", "")
            if str(producto).isdigit() and str(cantidad).isdigit() and int(cantidad) > 0:
                items.append({
                    "tipo": tipo, "id": producto, "cantidad": int(cantidad),
                    "nota": str(datos.get(f"detalles-{i}-observacion", ""))[:120],
                })
    return items


def _contexto_crear_comanda(request, form, formset, mozo_id):
    return {
        "carrito_inicial": _carrito_enviado(request.POST) if request.method == "POST" else [],
        "form": form,
        "formset": formset,
        "plano": _plano_de_mesas(request, form["mesa"].value()),
        "mozos": _mozos_disponibles(),
        "mozo_elegido": str(mozo_id or ""),
        # Cobrar desde el plano usa el mismo permiso que el cobro del listado
        "puede_cobrar": tiene_permiso(request.user, "comandas", "modificar"),
        "caja_abierta": caja.objects.filter(estado_caja="abierto").exists(),
        "metodos_pago": MetodoPago.objects.filter(estado_metodo_pago=True).order_by("nombre_metodo_pago"),
        **_productos_por_pedidos(),
        "categorias": CategoriaPlato.objects.filter(estado_categoria_plato=True),
        "tipos_bebida": TipoBebida.objects.filter(estado_tipo_bebida=True),
    }


# Para ordenar los productos al tomar el pedido: lo más pedido primero
DIAS_MAS_PEDIDOS = 30
MAS_PEDIDOS_DESTACADOS = 5


def _productos_por_pedidos():
    """Platos y bebidas disponibles, de lo más pedido en los últimos 30 días a lo menos pedido.

    Cuenta las unidades de comandas no anuladas (dos consultas en total). Los primeros
    con pedidos llevan la marca "destacado" para mostrar "Más pedido".
    """
    from datetime import timedelta

    from django.db.models import Sum
    from django.db.models.functions import Coalesce

    desde = timezone.now() - timedelta(days=DIAS_MAS_PEDIDOS)
    validas = Q(detallecomanda__comanda__fecha_hora__gte=desde) & ~Q(
        detallecomanda__comanda__estado_comanda__in=["anulado", "cancelado"]
    )
    platos = list(
        Plato.objects.filter(estado_plato=True)
        .select_related("categoria")
        .annotate(pedidos=Coalesce(Sum("detallecomanda__cant_plato", filter=validas), 0))
        .order_by("-pedidos", "nombre_plato")
    )
    bebidas = list(
        Bebida.objects.filter(disponible_bebida=True)
        .select_related("id_tipo_bebida")
        .annotate(pedidos=Coalesce(Sum("detallecomanda__cant_bebida", filter=validas), 0))
        .order_by("-pedidos", "nombre_bebida")
    )
    for lista in (platos, bebidas):
        for posicion, producto in enumerate(lista):
            producto.destacado = posicion < MAS_PEDIDOS_DESTACADOS and producto.pedidos > 0
    return {"platos": platos, "bebidas": bebidas}


# PANTALLA POR ESTACIÓN (Cocina, Bar, Parrilla)
def _estaciones_de(detalle):
    """A qué estaciones va una línea: la misma regla que reparte los tickets."""
    estaciones = []
    if detalle.tiene_plato:
        categoria = (detalle.categoria_del_plato or "").strip().lower()
        estaciones.append("parrilla" if categoria == "parrilla" else "cocina")
    if detalle.tiene_bebida:
        estaciones.append("bar")
    return estaciones


def _estacion_o_404(clave):
    from django.http import Http404

    estacion = next((e for e in _ESTACIONES_TICKET if e["clave"] == clave), None)
    if estacion is None:
        raise Http404("Estación inexistente")
    return estacion


@login_required
@permiso_requerido("comandas", "leer")
def estacion(request, clave):
    """Lo que tiene que preparar una estación: comandas abiertas con líneas sin terminar, la más vieja primero."""
    from django.db.models import Prefetch
    from notificaciones.reglas import leer_config

    actual = _estacion_o_404(clave)
    limite = int(leer_config("minutos_comanda_demorada", 30))
    ahora = timezone.now()
    pendientes = DetalleComanda.objects.filter(listo__isnull=True).select_related("plato__categoria", "bebida")
    comandas = (
        Comanda.objects.filter(estado_comanda__in=ESTADOS_ABIERTOS, detalles__listo__isnull=True)
        .distinct()
        .select_related("mesa", "empleado")
        .prefetch_related(Prefetch("detalles", queryset=pendientes, to_attr="sin_terminar"))
        .order_by("fecha_hora")
    )
    pedidos = []
    for comanda in comandas:
        lineas = [d for d in comanda.sin_terminar if clave in _estaciones_de(d)]
        if not lineas:
            continue
        espera = max(int((ahora - comanda.fecha_hora).total_seconds() // 60), 0)
        productos = []
        for d in lineas:
            if clave == "bar":
                productos.append({"nombre": d.nombre_de_la_bebida, "cantidad": d.cant_bebida, "nota": d.observacion})
            else:
                productos.append({"nombre": d.nombre_del_plato, "cantidad": d.cant_plato, "nota": d.observacion})
        pedidos.append({
            "comanda": comanda,
            "productos": productos,
            "espera": espera,
            "espera_texto": texto_espera(espera),
            "demorada": espera >= limite,
        })
    return render(request, "comandas/estacion.html", {
        "estacion": actual,
        "estaciones": _ESTACIONES_TICKET,
        "pedidos": pedidos,
        "limite_minutos": limite,
        "puede_marcar": tiene_permiso(request.user, "comandas", "modificar"),
    })


@login_required
@permiso_requerido("comandas", "modificar")
def estacion_listo(request, clave, pk):
    """La estación terminó su parte de una comanda: se marcan sus líneas como listas."""
    _estacion_o_404(clave)
    if request.method != "POST":
        return redirect("ventas:estacion", clave=clave)
    comanda = get_object_or_404(Comanda, pk=pk)
    lineas = [
        d for d in comanda.detalles.filter(listo__isnull=True).select_related("plato__categoria", "bebida")
        if clave in _estaciones_de(d)
    ]
    if lineas:
        ahora = timezone.now()
        with transaction.atomic():
            DetalleComanda.objects.filter(pk__in=[d.pk for d in lineas]).update(listo=ahora)
            if comanda.estado_comanda == "pendiente":
                comanda.estado_comanda = "en_preparacion"
                comanda.save(update_fields=["estado_comanda"])
            LogAuditoria.objects.create(
                tabla="Comanda",
                accion="MODIFICAR",
                registro_id=comanda.id_comanda,
                valores_anteriores="",
                valores_actuales=f"{clave.capitalize()}: listo ({len(lineas)} producto(s)). Mesa: {comanda.mesa.numero_mesa}",
                empleado=request.user.empleado,
            )
        messages.success(request, f"Mesa {comanda.mesa.numero_mesa}: listo en {clave}.")
    return redirect("ventas:estacion", clave=clave)
