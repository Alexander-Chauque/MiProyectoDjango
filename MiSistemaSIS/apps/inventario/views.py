from decimal import Decimal, InvalidOperation
from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from .models import Plato, CategoriaPlato, Ingrediente, DetallePlato, TipoBebida, Bebida
from .forms import TipoBebidaForm, BebidaForm
from . import servicios
from .servicios import cambiar_estado_ingrediente
from django.contrib.auth import authenticate, login
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
import re
from django.db.models import Q
from empleados.decorators import permiso_requerido
from django.utils import timezone
from auditoria.models import LogAuditoria


@login_required
def inventario_home(request):
    return render(request, "inventario_home.html")

# Funciones para listar, crear, editar y eliminar platos
@login_required
@permiso_requerido("platos", "leer")
def listar_platos(request):
    platos = Plato.objects.all().order_by("nombre_plato")
    categorias = CategoriaPlato.objects.all().order_by("nombre_categoria_plato")
    por_pagina = request.GET.get("por_pagina", 10)

    # Filtro
    buscar = request.GET.get("buscar", "").strip()
    categoria_id = request.GET.getlist("categoria", "")
    estado = request.GET.getlist("estado", "")

    # BUsqueda nombre
    if buscar:
        platos = platos.filter(nombre_plato__icontains=buscar)

    # Filtro por categorias
    categoria_id_int = []
    for c in categoria_id:
        if c.isdigit():
            categoria_id_int.append(int(c))

    # Filtro por estado
    if estado:
        q_estado = Q()
        if "disponible" in estado:
            q_estado |= Q(estado_plato=True)
        if "no_disponible" in estado:
            q_estado |= Q(estado_plato=False)
        if q_estado:
            platos = platos.filter(q_estado)

    if categoria_id_int:
        platos = platos.filter(categoria_id__in=categoria_id_int)
    # Paginacion
    try:
        por_pagina = int(por_pagina)
        if por_pagina not in [10, 25, 50, 100]:
            por_pagina = 10
    except (ValueError, TypeError):
        por_pagina = 10

    paginator = Paginator(platos, por_pagina)
    page_number = request.GET.get("page")
    platos = paginator.get_page(page_number)
    return render(
        request,
        "platos/listar.html",
        {
            "platos": platos,
            "categorias": categorias,
            "por_pagina": por_pagina,
            "buscar": buscar,
            "categorias_seleccionadas": [str(c) for c in categoria_id_int],
            "estados_seleccionados": estado,
        },
    )


def _formulario_plato(request, plato=None):
    actuales = set()
    if plato:
        actuales = set(plato.detalleplato_set.values_list("ingrediente_id", flat=True))

    if request.method == "POST":
        seleccionados = {
            int(i) for i in request.POST.getlist("ingredientes") if i.isdigit()
        }
        datos = {
            campo: request.POST.get(campo, "")
            for campo in ("nombre", "precio", "categoria", "descripcion")
        }
    else:
        seleccionados = actuales
        datos = {}
        if plato:
            datos = {
                "nombre": plato.nombre_plato,
                "precio": f"{plato.precio_plato:.2f}",
                "categoria": str(plato.categoria_id),
                "descripcion": plato.descripcion_plato,
            }

    return {
        "plato": plato,
        "datos": datos,
        "categorias": CategoriaPlato.objects.all().order_by("nombre_categoria_plato"),
        "ingredientes": Ingrediente.objects.filter(
            Q(estado_ingrediente=True) | Q(pk__in=actuales)
        ).order_by("nombre_ingrediente"),
        "ingredientes_seleccionados": seleccionados,
    }


def _validar_plato(request, plato=None):
    """Devuelve los datos limpios del formulario o lanza ValueError con el motivo."""
    nombre = request.POST.get("nombre", "").strip().title()
    if not nombre or len(nombre) > 100 or not re.match(r"^[a-zA-Z0-9áéíóúÁÉÍÓÚñÑüÜ\s/-]+$", nombre):
        raise ValueError(
            "Nombre inválido: solo se permiten letras, números, espacios, / y -"
        )
    existentes = Plato.objects.filter(nombre_plato__iexact=nombre)
    if plato:
        existentes = existentes.exclude(pk=plato.pk)
    if existentes.exists():
        raise ValueError(f'Plato "{nombre}" ya existe')

    try:
        precio = Decimal(request.POST.get("precio", ""))
    except InvalidOperation:
        raise ValueError("Precio inválido: ingrese un número válido")
    if not precio.is_finite() or precio <= 0 or precio >= 10**8:
        raise ValueError("Precio inválido: debe ser mayor a 0 y menor a 100.000.000")
    if precio != precio.quantize(Decimal("0.01")):
        raise ValueError("Precio inválido: se permiten hasta 2 decimales")

    categoria_id = request.POST.get("categoria", "")
    categoria = None
    if categoria_id.isdigit():
        categoria = CategoriaPlato.objects.filter(pk=categoria_id).first()
    if not categoria:
        raise ValueError("Debe seleccionar una categoría válida")

    ids = request.POST.getlist("ingredientes")
    if not ids:
        raise ValueError("Debe seleccionar al menos un ingrediente")
    if not all(i.isdigit() for i in ids):
        raise ValueError("Hay ingredientes inválidos")
    actuales = plato.detalleplato_set.values("ingrediente_id") if plato else []
    ingredientes = list(
        Ingrediente.objects.filter(pk__in=ids).filter(
            Q(estado_ingrediente=True) | Q(pk__in=actuales)
        )
    )
    if len(ingredientes) != len(set(ids)):
        raise ValueError("Hay ingredientes que no existen o no están disponibles")

    return {
        "nombre": nombre,
        "precio": precio,
        "categoria": categoria,
        "ingredientes": ingredientes,
        "descripcion": request.POST.get("descripcion", ""),
    }


@login_required
@permiso_requerido("platos", "escribir")
def crear_plato(request):
    if request.method == "POST":
        try:
            datos = _validar_plato(request)
            with transaction.atomic():
                plato = Plato.objects.create(
                    nombre_plato=datos["nombre"],
                    precio_plato=datos["precio"],
                    descripcion_plato=datos["descripcion"],
                    categoria=datos["categoria"],
                )
                for ingrediente in datos["ingredientes"]:
                    DetallePlato.objects.create(
                        plato=plato, ingrediente=ingrediente, cantidad=1
                    )
                LogAuditoria.objects.create(
                    tabla="Plato",
                    accion="CREAR",
                    registro_id=plato.id_plato,
                    valores_anteriores="",
                    valores_actuales=f"Plato creado: {plato.nombre_plato}. Precio: ${plato.precio_plato}",
                    empleado=request.user.empleado,
                )
        except ValueError as e:
            messages.error(request, str(e))
        except IntegrityError:
            messages.error(request, "Ya existe un plato con ese nombre")
        else:
            messages.success(request, f'Plato "{plato.nombre_plato}" creado exitosamente')
            return redirect("inventario:listar_platos")

    return render(request, "platos/crear.html", _formulario_plato(request))


@login_required
@permiso_requerido("platos", "modificar")
def editar_plato(request, pk):
    plato = get_object_or_404(Plato, pk=pk)

    if request.method == "POST":
        try:
            datos = _validar_plato(request, plato)
            valores_viejos = f"Nombre: {plato.nombre_plato}, Precio: {plato.precio_plato}, Categoría: {plato.categoria.nombre_categoria_plato}"
            with transaction.atomic():
                plato.nombre_plato = datos["nombre"]
                plato.precio_plato = datos["precio"]
                plato.categoria = datos["categoria"]
                plato.descripcion_plato = datos["descripcion"]
                plato.save()

                # Reemplazar los ingredientes, conservando la cantidad de los que siguen
                cantidades = dict(
                    plato.detalleplato_set.values_list("ingrediente_id", "cantidad")
                )
                plato.detalleplato_set.all().delete()
                for ingrediente in datos["ingredientes"]:
                    DetallePlato.objects.create(
                        plato=plato,
                        ingrediente=ingrediente,
                        cantidad=cantidades.get(ingrediente.pk, 1),
                    )

                LogAuditoria.objects.create(
                    tabla="Plato",
                    accion="MODIFICAR",
                    registro_id=plato.id_plato,
                    valores_anteriores=valores_viejos,
                    valores_actuales=f"Nombre: {plato.nombre_plato}, Precio: {plato.precio_plato}, Categoría: {plato.categoria.nombre_categoria_plato}",
                    empleado=request.user.empleado,
                )
        except ValueError as e:
            messages.error(request, str(e))
        except IntegrityError:
            plato.refresh_from_db()
            messages.error(request, "Ya existe un plato con ese nombre")
        else:
            messages.success(request, f'Plato "{plato.nombre_plato}" editado exitosamente')
            return redirect("inventario:listar_platos")

    return render(request, "platos/editar.html", _formulario_plato(request, plato))


@login_required
@permiso_requerido("platos", "eliminar")
def eliminar_plato(request, pk):
    plato = get_object_or_404(Plato, pk=pk)
    # Solo se elimina si está no disponible hace 2 meses
    try:
        servicios.validar_eliminar_plato(plato)
    except ValueError as error:
        messages.error(request, str(error))
        return redirect("inventario:listar_platos")

    if request.method == "POST":
        nombre = plato.nombre_plato
        servicios.eliminar_plato(plato)
        messages.success(request, f'Plato "{nombre}" eliminado exitosamente')
        return redirect("inventario:listar_platos")

    return render(request, "platos/eliminar.html", {"plato": plato})


@login_required
@permiso_requerido("platos", "leer")
def detalle_plato(request, pk):
    plato = get_object_or_404(Plato, pk=pk)
    detalles = plato.detalleplato_set.all().select_related("ingrediente")
    return render(
        request, "platos/detalle.html", {"plato": plato, "detalles": detalles}
    )


@login_required
@permiso_requerido("platos", "modificar")
def estado_plato(request, pk):
    plato = get_object_or_404(Plato, pk=pk)
    if request.method == "POST":
        motivo = request.POST.get("motivo_cambio", "Cambio de estado")
        estado_anterior = plato.estado_plato
        plato.estado_plato = not plato.estado_plato
        plato.save()

        LogAuditoria.objects.create(
            tabla="Plato",
            accion="MODIFICAR",
            registro_id=plato.id_plato,
            valores_anteriores=f"Estado: {'Disponible' if estado_anterior else 'No disponible'}",
            valores_actuales=f"Estado: {'Disponible' if plato.estado_plato else 'No disponible'}. Motivo: {motivo}",
            empleado=request.user.empleado,
        )
        messages.success(request, f'Plato "{plato.nombre_plato}" actualizado')
    return redirect("inventario:listar_platos")


# FUNCIONES PARA INGREDIENTES
@login_required
@permiso_requerido("ingredientes", "leer")
def listar_ingredientes(request):
    ingredientes = Ingrediente.objects.all().order_by("nombre_ingrediente")
    por_pagina = request.GET.get("por_pagina", 10)

    # Filtro
    buscar = request.GET.get("buscar", "").strip()
    unidades = request.GET.getlist("unidad", "")
    estados = request.GET.getlist("estado", "")
    referer = request.META.get("HTTP_REFERER", "")

    # BUsqueda nombre
    if buscar:
        ingredientes = ingredientes.filter(nombre_ingrediente__icontains=buscar)

    # Filtro por categorias
    if unidades:
        ingredientes = ingredientes.filter(unidad_medida__in=unidades)

    # Filtro por estado
    if estados:
        q_estado = Q()
        if "disponible" in estados:
            q_estado |= Q(estado_ingrediente=True)
        if "no_disponible" in estados:
            q_estado |= Q(estado_ingrediente=False)
        if q_estado:
            ingredientes = ingredientes.filter(q_estado)

    # Paginacion
    try:
        por_pagina = int(por_pagina)
        if por_pagina not in [10, 25, 50, 100]:
            por_pagina = 10
    except (ValueError, TypeError):
        por_pagina = 10

    paginator = Paginator(ingredientes, por_pagina)
    page_number = request.GET.get("page")
    ingredientes = paginator.get_page(page_number)

    return render(
        request,
        "ingredientes/listar_ingrediente.html",
        {
            "ingredientes": ingredientes,
            "por_pagina": por_pagina,
            "buscar": buscar,
            "unidades_seleccionadas": unidades,
            "estados_seleccionados": estados,
            "viene_de_platos": "/platos/" in referer,
        },
    )


@login_required
@permiso_requerido("ingredientes", "escribir")
def crear_ingrediente(request):
    if request.method == "POST":
        nombre = request.POST.get("nombre")
        if nombre:
            nombre = nombre.lower()
        unidad_medida = request.POST.get("unidad_medida")
        if unidad_medida:
            unidad_medida = unidad_medida.lower()
        costo_unitario = request.POST.get("costo_unitario", 0)

        ingrediente = Ingrediente.objects.create(
            nombre_ingrediente=nombre,
            unidad_medida=unidad_medida,
            costo_unitario=costo_unitario,
        )

        LogAuditoria.objects.create(
            tabla="Ingrediente",
            accion="CREAR",
            registro_id=ingrediente.id_ingrediente,
            valores_anteriores="",
            valores_actuales=f"Ingrediente creado: {ingrediente.nombre_ingrediente}. Unidad: {ingrediente.unidad_medida}",
            empleado=request.user.empleado,
        )
        messages.success(request, f'Ingrediente "{nombre}" creado exitosamente')
        return redirect("inventario:listar_ingredientes")
    else:
        return render(request, "ingredientes/crear_ingrediente.html")


@login_required
@permiso_requerido("ingredientes", "modificar")
def editar_ingrediente(request, pk):
    ingrediente = get_object_or_404(Ingrediente, pk=pk)
    if request.method == "POST":
        valores_viejos = f"Nombre: {ingrediente.nombre_ingrediente}, Unidad: {ingrediente.unidad_medida}, Costo: {ingrediente.costo_unitario}"
        nombre = request.POST.get("nombre")
        if nombre:
            nombre = nombre.title()
        ingrediente.nombre_ingrediente = nombre

        unidad_medida = request.POST.get("unidad_medida")
        if unidad_medida:
            unidad_medida = unidad_medida.lower()
        ingrediente.unidad_medida = unidad_medida

        ingrediente.costo_unitario = request.POST.get(
            "costo_unitario", ingrediente.costo_unitario
        )
        ingrediente.save()

        valores_nuevos = f"Nombre: {ingrediente.nombre_ingrediente}, Unidad: {ingrediente.unidad_medida}, Costo: {ingrediente.costo_unitario}"
        LogAuditoria.objects.create(
            tabla="Ingrediente",
            accion="MODIFICAR",
            registro_id=ingrediente.id_ingrediente,
            valores_anteriores=valores_viejos,
            valores_actuales=valores_nuevos,
            empleado=request.user.empleado,
        )

        messages.success(
            request, f'Ingrediente "{ingrediente.nombre_ingrediente}" actualizado'
        )
        return redirect("inventario:listar_ingredientes")
    else:
        return render(
            request,
            "ingredientes/editar_ingrediente.html",
            {"ingrediente": ingrediente},
        )


@login_required
@permiso_requerido("ingredientes", "eliminar")
def eliminar_ingrediente(request, pk):
    ingrediente = get_object_or_404(Ingrediente, pk=pk)
    try:
        servicios.validar_eliminar_ingrediente(ingrediente)
    except ValueError as error:
        messages.error(request, str(error))
        return redirect("inventario:listar_ingredientes")

    if request.method == "POST":
        nombre = ingrediente.nombre_ingrediente
        servicios.eliminar_ingrediente(ingrediente)
        messages.success(request, f'Ingrediente "{nombre}" eliminado')
        return redirect("inventario:listar_ingredientes")
    else:
        return render(
            request,
            "ingredientes/eliminar_ingrediente.html",
            {"ingrediente": ingrediente},
        )


@login_required
@permiso_requerido("ingredientes", "leer")
def detalle_ingrediente(request, pk):
    ingrediente = get_object_or_404(Ingrediente, pk=pk)
    return render(
        request, "ingredientes/detalle_ingrediente.html", {"ingrediente": ingrediente}
    )


@login_required
@permiso_requerido("ingredientes", "modificar")
def estado_ingrediente(request, pk):
    ingrediente = get_object_or_404(Ingrediente, pk=pk)

    if request.method == "POST":
        motivo = request.POST.get("motivo_cambio", "Cambio desde el listado")
        cambiar_estado_ingrediente(ingrediente, request.user.empleado, motivo)

        estado_texto = (
            "disponible" if ingrediente.estado_ingrediente else "no disponible"
        )
        messages.success(
            request,
            f"Ingrediente {ingrediente.nombre_ingrediente} ahora está {estado_texto}",
        )
        return redirect("inventario:listar_ingredientes")

    return redirect("inventario:listar_ingredientes")


# FUNCIONES PARA CATEGORÍAS
@login_required
@permiso_requerido("categorias", "leer")
def listar_categorias(request):
    categorias = CategoriaPlato.objects.all().order_by("nombre_categoria_plato")

    buscar = request.GET.get("buscar", "").strip()
    estados = request.GET.getlist("estado")

    if buscar:
        categorias = categorias.filter(nombre_categoria_plato__icontains=buscar)

    if estados:
        q_estado = Q()
        if "activo" in estados:
            q_estado |= Q(estado_categoria_plato=True)
        if "inactivo" in estados:
            q_estado |= Q(estado_categoria_plato=False)
        if q_estado:
            categorias = categorias.filter(q_estado)

        # Por paginacion
    por_pagina = request.GET.get("por_pagina", 10)
    try:
        por_pagina = int(por_pagina)
        if por_pagina not in [10, 25, 50, 100]:
            por_pagina = 10
    except (ValueError, TypeError):
        por_pagina = 10

    paginator = Paginator(categorias, por_pagina)
    page_number = request.GET.get("page")
    categorias = paginator.get_page(page_number)

    return render(
        request,
        "categorias/listar_categoria.html",
        {
            "categorias": categorias,
            "por_pagina": por_pagina,
            "buscar": buscar,
            "estados_seleccionados": estados,
        },
    )


@login_required
@permiso_requerido("categorias", "escribir")
def crear_categoria(request):
    if request.method == "POST":
        nombre = request.POST.get("nombre")
        if nombre:
            nombre = nombre.title()
        descripcion = request.POST.get("descripcion", "")

        CategoriaPlato.objects.create(
            nombre_categoria_plato=nombre, descripcion_categoria_plato=descripcion
        )
        messages.success(request, f'Categoría "{nombre}" creada')
        return redirect("inventario:listar_categorias")
    else:
        return render(request, "categorias/crear_categoria.html")


@login_required
@permiso_requerido("categorias", "modificar")
def editar_categoria(request, pk):
    categoria = get_object_or_404(CategoriaPlato, pk=pk)

    if request.method == "POST":
        nombre = request.POST.get("nombre")
        if nombre:
            nombre = nombre.title()
        categoria.nombre_categoria_plato = nombre
        categoria.descripcion_categoria_plato = request.POST.get("descripcion", "")
        categoria.save()

        messages.success(
            request, f'Categoría "{categoria.nombre_categoria_plato}" actualizada'
        )
        return redirect("inventario:listar_categorias")
    else:
        return render(
            request, "categorias/editar_categoria.html", {"categoria": categoria}
        )


@login_required
@permiso_requerido("categorias", "eliminar")
def eliminar_categoria(request, pk):
    categoria = get_object_or_404(CategoriaPlato, pk=pk)

    if request.method == "POST":
        nombre = categoria.nombre_categoria_plato
        categoria.delete()
        messages.success(request, f'Categoría "{nombre}" eliminada')
        return redirect("inventario:listar_categorias")
    else:
        return render(
            request, "categorias/eliminar_categoria.html", {"categoria": categoria}
        )


@login_required
@permiso_requerido("categorias", "leer")
def detalle_categoria(request, pk):
    categoria = get_object_or_404(CategoriaPlato, pk=pk)
    platos = categoria.plato_set.all().order_by("nombre_plato")
    return render(
        request,
        "categorias/detalle_categoria.html",
        {"categoria": categoria, "platos": platos},
    )


@login_required
@permiso_requerido("categorias", "modificar")
def estado_categoria(request, pk):
    categoria = get_object_or_404(CategoriaPlato, pk=pk)
    if request.method != "POST":
        return redirect("inventario:listar_categorias")
    categoria.estado_categoria_plato = not categoria.estado_categoria_plato
    categoria.save()

    if categoria.estado_categoria_plato:
        messages.success(
            request, f'Categoría "{categoria.nombre_categoria_plato}" activada'
        )
    else:
        messages.success(
            request, f'Categoría "{categoria.nombre_categoria_plato}" desactivada'
        )

    return redirect("inventario:listar_categorias")


# funcion de Tipo de Bebidas
@login_required
@permiso_requerido("bebidas", "leer")
def listar_tipo_bebida(request):
    tipos = TipoBebida.objects.all().order_by("nombre_tipo_bebida")

    buscar = request.GET.get("buscar", "").strip()
    estados = request.GET.getlist("estado")

    if buscar:
        tipos = tipos.filter(nombre_tipo_bebida__icontains=buscar)

    if estados:
        q_estado = Q()
        if "activo" in estados:
            q_estado |= Q(estado_tipo_bebida=True)
        if "inactivo" in estados:
            q_estado |= Q(estado_tipo_bebida=False)
        if q_estado:
            tipos = tipos.filter(q_estado)

    por_pagina = request.GET.get("por_pagina", 10)
    try:
        por_pagina = int(por_pagina)
        if por_pagina not in [10, 25, 50, 100]:
            por_pagina = 10
    except (ValueError, TypeError):
        por_pagina = 10

    paginator = Paginator(tipos, por_pagina)
    page_number = request.GET.get("page")
    tipo = paginator.get_page(page_number)

    return render(
        request,
        "bebidas/listar_tipo_bebida.html",
        {
            "tipos": tipo,
            "por_pagina": por_pagina,
            "buscar": buscar,
            "estados_seleccionados": estados,
        },
    )


@login_required
@permiso_requerido("bebidas", "escribir")
def crear_tipo_bebida(request):
    if request.method == "POST":
        form = TipoBebidaForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, " Tipo de bebida creado con exito")
            return redirect("inventario:listar_tipo_bebida")
    else:
        form = TipoBebidaForm()
    return render(request, "bebidas/crear_tipo_bebida.html", {"form": form})


@login_required
@permiso_requerido("bebidas", "modificar")
def editar_tipo_bebida(request, pk):
    tipo = get_object_or_404(TipoBebida, pk=pk)
    if request.method == "POST":
        form = TipoBebidaForm(request.POST, instance=tipo)
        if form.is_valid():
            form.save()
            messages.success(request, " Tipo de bebida actualizado")
            return redirect("inventario:listar_tipo_bebida")
    else:
        form = TipoBebidaForm(instance=tipo)
    return render(request, "bebidas/editar_tipo_bebida.html", {"form": form})


@login_required
@permiso_requerido("bebidas", "eliminar")
def eliminar_tipo_bebida(request, pk):
    tipo = get_object_or_404(TipoBebida, pk=pk)
    if request.method == "POST":
        nombre = tipo.nombre_tipo_bebida
        tipo.delete()
        messages.success(request, f'Tipo "{nombre} eliminado')
        return redirect("inventario:listar_tipo_bebida")
    return render(request, "bebidas/eliminar_tipo_bebida.html")


@login_required
@permiso_requerido("bebidas", "modificar")
def estado_tipo_bebida(request, pk):
    tipo = get_object_or_404(TipoBebida, pk=pk)
    if request.method == "POST":
        motivo = request.POST.get("motivo_cambio", "Cambio de estado")
        estado_anterior = tipo.estado_tipo_bebida
        tipo.estado_tipo_bebida = not tipo.estado_tipo_bebida
        tipo.save()
        LogAuditoria.objects.create(
            tabla="Tipo de Bebida",
            accion="MODIFICAR",
            registro_id=tipo.id_tipo_bebida,
            valores_anteriores=f"Estado: {'Activo' if estado_anterior else 'Inactivo'}",
            valores_actuales=f"Estado: {'Activo' if tipo.estado_tipo_bebida else 'Inactivo'}. Motivo: {motivo}",
            empleado=request.user.empleado,
        )
        estado_texto = "activo" if tipo.estado_tipo_bebida else "inactivo"
        messages.success(
            request, f"Tipo {tipo.nombre_tipo_bebida} actulizado a {estado_texto} "
        )
    return redirect("inventario:listar_tipo_bebida")


# Funcion de Bebida
@login_required
@permiso_requerido("bebidas", "leer")
def bebida_listar(request):
    bebidas = Bebida.objects.all().order_by("nombre_bebida")
    tipos = TipoBebida.objects.all().order_by("nombre_tipo_bebida")

    # Filtros
    buscar = request.GET.get("buscar", "").strip()
    tipos_ids = request.GET.getlist("tipo")
    estados = request.GET.getlist("estado")

    if buscar:
        bebidas = bebidas.filter(nombre_bebida__icontains=buscar)

    tipos_ids_int = []
    for t in tipos_ids:
        if t.isdigit():
            tipos_ids_int.append(int(t))
    if tipos_ids_int:
        bebidas = bebidas.filter(id_tipo_bebida__in=tipos_ids_int)

    # Estado
    if estados:
        q_estado = Q()
        if "disponible" in estados:
            q_estado |= Q(disponible_bebida=True)
        if "no_disponible" in estados:
            q_estado |= Q(disponible_bebida=False)
        if q_estado:
            bebidas = bebidas.filter(q_estado)

    # Paginación
    por_pagina = request.GET.get("por_pagina", 10)
    try:
        por_pagina = int(por_pagina)
        if por_pagina not in [10, 25, 50, 100]:
            por_pagina = 10
    except (ValueError, TypeError):
        por_pagina = 10

    paginator = Paginator(bebidas, por_pagina)
    page_number = request.GET.get("page")
    bebidas = paginator.get_page(page_number)

    return render(
        request,
        "bebidas/listar_bebida.html",
        {
            "bebidas": bebidas,
            "tipos": tipos,
            "por_pagina": por_pagina,
            "buscar": buscar,
            "tipos_seleccionados": [str(t) for t in tipos_ids_int],
            "estados_seleccionados": estados,
        },
    )


@login_required
@permiso_requerido("bebidas", "escribir")
def bebida_crear(request):
    if request.method == "POST":
        form = BebidaForm(request.POST, request.FILES)
        if form.is_valid():
            bebida = form.save()

            LogAuditoria.objects.create(
                tabla="Bebida",
                accion="CREAR",
                registro_id=bebida.id_bebida,
                valores_anteriores="",
                valores_actuales=f"Bebida creada: {bebida.nombre_bebida}. Precio: ${bebida.precio_bebida}",
                empleado=request.user.empleado,
            )
            messages.success(request, "Bebida creada exitosamente")
            return redirect("inventario:listar_bebida")
    else:
        form = BebidaForm()
    return render(
        request,
        "bebidas/crear_bebida.html",
        {"form": form, "titulo": "Crear Bebida", "boton": "Guardar"},
    )


@login_required
@permiso_requerido("bebidas", "modificar")
def bebida_editar(request, pk):
    bebida = get_object_or_404(Bebida, pk=pk)
    if request.method == "POST":
        form = BebidaForm(request.POST, request.FILES, instance=bebida)
        if form.is_valid():
            valores_viejos = (
                f"Nombre: {bebida.nombre_bebida}, Precio: {bebida.precio_bebida}"
            )
            form.save()

            valores_nuevos = (
                f"Nombre: {bebida.nombre_bebida}, Precio: {bebida.precio_bebida}"
            )
            LogAuditoria.objects.create(
                tabla="Bebida",
                accion="MODIFICAR",
                registro_id=bebida.id_bebida,
                valores_anteriores=valores_viejos,
                valores_actuales=valores_nuevos,
                empleado=request.user.empleado,
            )
            messages.success(request, "Bebida actualizada")
            return redirect("inventario:listar_bebida")
    else:
        form = BebidaForm(instance=bebida)
    return render(
        request,
        "bebidas/editar_bebida.html",
        {
            "bebida": bebida,
            "form": form,
            "titulo": "Editar Bebida",
            "boton": "Actualizar",
        },
    )


@login_required
@permiso_requerido("bebidas", "eliminar")
def bebida_eliminar(request, pk):
    bebida = get_object_or_404(Bebida, pk=pk)
    try:
        servicios.validar_eliminar_bebida(bebida)
    except ValueError as error:
        messages.error(request, str(error))
        return redirect("inventario:listar_bebida")
    if request.method == "POST":
        nombre = bebida.nombre_bebida
        servicios.eliminar_bebida(bebida)
        messages.success(request, f'Bebida "{nombre}" eliminada')
        return redirect("inventario:listar_bebida")
    return render(request, "bebidas/eliminar_bebida.html", {"bebida": bebida})


@login_required
@permiso_requerido("bebidas", "leer")
def bebida_detalle(request, pk):
    bebida = get_object_or_404(Bebida, pk=pk)
    return render(request, "bebidas/detalle_bebida.html", {"bebida": bebida})


@login_required
@permiso_requerido("bebidas", "modificar")
def bebida_estado(request, pk):
    bebida = get_object_or_404(Bebida, pk=pk)
    if request.method == "POST":
        motivo = request.POST.get("motivo_cambio", "Cambio de estado")
        estado_anterior = bebida.disponible_bebida
        bebida.disponible_bebida = not bebida.disponible_bebida
        bebida.save()

        LogAuditoria.objects.create(
            tabla="Bebida",
            accion="MODIFICAR",
            registro_id=bebida.id_bebida,
            valores_anteriores=f"Estado: {'Disponible' if estado_anterior else 'No disponible'}",
            valores_actuales=f"Estado: {'Disponible' if bebida.disponible_bebida else 'No disponible'}. Motivo: {motivo}",
            empleado=request.user.empleado,
        )
        if bebida.disponible_bebida:
            messages.success(request, f'Bebida "{bebida.nombre_bebida}" disponible')
        else:
            messages.success(request, f'Bebida "{bebida.nombre_bebida}" no disponible')
    return redirect("inventario:listar_bebida")
