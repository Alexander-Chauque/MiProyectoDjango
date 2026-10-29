from django.shortcuts import render

# Create your views here.
from datetime import datetime, time
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import Mesa, Comanda, DetalleComanda
from django.forms import inlineformset_factory
from .forms import MesaForm, ComandaForm, DetalleComandaForm
from inventario.models import Plato, Bebida
from auditoria.models import LogAuditoria
from empleados.decorators import permiso_requerido
from django.db import transaction
from reportlab.pdfgen import canvas
from django.http import HttpResponse
from django.utils import timezone
from django.db.models import Q
from django.core.paginator import Paginator
from django.utils.http import url_has_allowed_host_and_scheme
import traceback

@login_required
@permiso_requerido("mesas", "leer")
def mesa_listar(request):
    mesas = Mesa.objects.all().order_by("numero_mesa")

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
        },
    )


@login_required
@permiso_requerido("mesas", "escribir")
def mesa_crear(request):
    if request.method == "POST":
        form = MesaForm(request.POST)
        if form.is_valid():
            mesa=form.save()

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
              empleado=request.user.empleado
            )
          messages.success(request, "Mesa actualizada")
          return redirect("ventas:listar_mesa")
    else:
        form = MesaForm(instance=mesa)
    return render(
        request,
        "mesas/editar_mesa.html",
        {"form": form, 'mesa':mesa, "titulo": "Editar Mesa", "boton": "Actualizar"},
    )


@login_required
@permiso_requerido("mesas", "eliminar")
def mesa_eliminar(request, pk):
    mesa = get_object_or_404(Mesa, pk=pk)

    # verificar si la mesa tiene comandas activas
    comandas_activas = Comanda.objects.filter(
        mesa=mesa, estado_comanda__in=["pendiente", "en_preparacion", "entregado"]
    )
    if comandas_activas.exists():
        messages.error(
            request,
            f"No se puede eliminar la mesa {mesa.numero_mesa} porque tiene comandas activas.",
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
    # 1. Capturamos el motivo que viene del modal
    motivo = request.POST.get("motivo_cambio", "Cambio de estado desde el listado")

    # 2. Si la mesa está OCUPADA (False), verificar que no tenga comandas activas
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

    # 3. Si llegó acá, se puede cambiar el estado
    estado_anterior = mesa.estado_mesa
    mesa.estado_mesa = not mesa.estado_mesa
    mesa.save()

    # 4. Registrar en el Log de Auditoría
    LogAuditoria.objects.create(
        tabla="Mesa",
        accion="MODIFICAR",
        registro_id=mesa.id_mesa,
        valores_anteriores=f"Estado: {'Disponible' if estado_anterior else 'Ocupada'}",
        valores_actuales=f"Estado: {'Disponible' if mesa.estado_mesa else 'Ocupada'}. Motivo: {motivo}",
        empleado=request.user.empleado,
    )

    # 5. Mensaje de éxito
    estado = "disponible" if mesa.estado_mesa else "ocupada"
    messages.success(request, f"Mesa {mesa.numero_mesa} ahora está {estado}")
    return redirect("ventas:listar_mesa")

@login_required
def mesa_ver_comandas(request, pk):
    mesa = get_object_or_404(Mesa, pk=pk)
    # Traemos todas las comandas de esa mesa, ordenadas por la más reciente
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
        .order_by("id_comanda")
    )
    mesas = Mesa.objects.all().order_by("numero_mesa")

    buscar = request.GET.get("buscar", "").strip()
    estados = request.GET.getlist("estado")
    mesas_ids = request.GET.getlist("mesa")
    fecha_desde = request.GET.get("fecha_desde", "")
    fecha_hasta = request.GET.get("fecha_hasta", "")
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
            "comandas": comandas,
            "mesas": mesas,
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

    if request.method == "POST":
        form = ComandaForm(request.POST)
        formset = DetalleFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            # Validar que haya al menos un detalle
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
                    {
                        "form": form,
                        "formset": formset,
                        "platos": Plato.objects.filter(estado_plato=True),
                        "bebidas": Bebida.objects.filter(disponible_bebida=True),
                    },
                )
            try:
                # TRANSACCIÓN: si algo falla, se revierte TODO
                with transaction.atomic():
                    # Crear la comanda (sin guardar aún)
                    comanda = form.save(commit=False)
                    # Asignar el empleado logueado
                    try:
                        comanda.empleado = request.user.empleado
                    except:
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
                return redirect("ventas:comanda_listar")
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
        form = ComandaForm()
        formset = DetalleFormSet()

    return render(
        request,
        "comandas/comanda_crear.html",
        {
            "form": form,
            "formset": formset,
            "platos": Plato.objects.filter(estado_plato=True),
            "bebidas": Bebida.objects.filter(disponible_bebida=True),
        },
    )


@login_required
@permiso_requerido("comandas", "modificar")
def comanda_editar(request, pk):
    comanda = get_object_or_404(Comanda, id_comanda=pk)
    mesa_anterior = comanda.mesa
    DetalleFormSet = inlineformset_factory(
        Comanda,
        DetalleComanda,
        form=DetalleComandaForm,
        extra=1,
        can_delete=True,
        fields=["plato", "cant_plato", "bebida", "cant_bebida"],
    )

    if request.method == "POST":
        form = ComandaForm(request.POST, instance=comanda)
        formset = DetalleFormSet(request.POST, instance=comanda)
        if form.is_valid() and formset.is_valid():
            comanda_guardada = form.save(commit=False)
            comanda_guardada.mesa = form.cleaned_data["mesa"]
            comanda_guardada.save()
            formset.instance = comanda_guardada
            formset.save()
            comanda_guardada.calcular_total()

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
            messages.success(request, f"Comanda #{comanda.id_comanda} actualizada")
            return redirect("ventas:comanda_listar")
    else:
        form = ComandaForm(instance=comanda)
        formset = DetalleFormSet(instance=comanda)
    return render(
        request,
        "comandas/comanda_editar.html",
        {
            "form": form,
            "formset": formset,
            "comanda": comanda,
            "platos": Plato.objects.filter(estado_plato=True),
            "bebidas": Bebida.objects.filter(disponible_bebida=True),
        },
    )


# ELIMINAR COMANDA
@login_required
@permiso_requerido("comandas", "eliminar")
def comanda_eliminar(request, pk):
    comanda = get_object_or_404(Comanda, id_comanda=pk)
    if request.method == "POST":
        # Liberar la mesa
        comanda.mesa.estado_mesa = True
        comanda.mesa.save()

        comanda.delete()
        messages.success(request, "Comanda eliminada")
        return redirect("ventas:comanda_listar")
    return render(request, "comandas/comanda_eliminar.html", {"comanda": comanda})


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
    nuevo_estado = request.GET.get("estado") or request.POST.get("estado")

    if nuevo_estado:
        # Si el estado es 'anulado', anular
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
                    LogAuditoria.objects.create(
                        tabla="Comanda",
                        accion="ANULAR",
                        registro_id=comanda.id_comanda,
                        valores_anteriores=f"Estado: {estado_anterior}",
                        valores_actuales=f"Estado: anulado. Motivo: {motivo}. Fecha anulación: {timezone.now().strftime('%d/%m/%Y %H:%M')}",
                        empleado=request.user.empleado
                        # El campo fecha_hora se llena solo con auto_now_add=True
                    )
                messages.success(
                    request, f"Comanda #{comanda.id_comanda} anulada exitosamente"
                )
            except Exception as e:
                messages.error(request, f"Error al anular: {e}")
        else:
            try:
                with transaction.atomic():
                    comanda.estado_comanda = nuevo_estado
                    comanda.save()
                    # Cambiar el estado de la mesa según el nuevo estado de la comanda
                    if nuevo_estado in ["pagado", "anulado"]:
                        comanda.mesa.estado_mesa = True
                    elif nuevo_estado in ["pendiente", "en_preparacion", "entregado"]:
                        comanda.mesa.estado_mesa = False
                    comanda.mesa.save()

                messages.success(
                    request,
                    f"Comanda #{comanda.id_comanda} ahora está {comanda.get_estado_comanda_display()}",
                )
            except Exception as e:
                messages.error(request, f"Error al cambiar el estado: {e}")
    next_url = request.GET.get("next")
    if next_url and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}
    ):
        return redirect(next_url)

    return redirect("ventas:comanda_listar")


@login_required
@permiso_requerido("comandas", "eliminar")  # Solo Admin
def comanda_eliminar(request, pk):
    comanda = get_object_or_404(Comanda, id_comanda=pk)

    if request.method == "POST":
        try:
            with transaction.atomic():
                comanda.delete()
            messages.success(request, f"Comanda #{comanda.id_comanda} eliminada")
            return redirect("ventas:comanda_listar")
        except Exception as e:
            messages.error(request, f"Error al eliminar la comanda: {e}")

    return render(request, "comandas/comanda_eliminar.html", {"comanda": comanda})


@login_required
@permiso_requerido("comandas", "modificar")
def comanda_anular(request, pk):
    comanda = get_object_or_404(Comanda, id_comanda=pk)

    if request.method == "POST":
        motivo = request.POST.get("motivo")

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

    fecha_desde = request.GET.get("fecha_desde")
    fecha_hasta = request.GET.get("fecha_hasta")
    estado = request.GET.get("estado")
    mesa_id = request.GET.get("mesa")

    # Obtener la zona horaria actual('America/Argentina/Salta')
    tz_actual = timezone.get_current_timezone()

    if fecha_desde:
        try:
            # Creamos un objeto datetime a las 00:00:00 del día elegido
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

    return render(
        request,
        "comandas/comanda_comprobante.html",
        {
            "comanda": comanda,
            "detalles": detalles,
        },
    )


@login_required
@permiso_requerido("comandas", "leer")
def comanda_ticket(request, pk):
    comanda = get_object_or_404(Comanda, id_comanda=pk)
    detalles = comanda.detalles.all().select_related("plato", "bebida")

    if comanda.estado_comanda == "pendiente":
        comanda.estado_comanda = "en_preparacion"
        comanda.save()
        messages.success(request, f"Comanda #{comanda.id_comanda} enviada a cocina")

    return render(
        request,
        "comandas/comanda_ticket.html",
        {
            "comanda": comanda,
            "detalles": detalles,
        },
    )
