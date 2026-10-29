from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator
from .models import Plato, CategoriaPlato, Ingrediente, DetallePlato, TipoBebida, Bebida
from .forms import TipoBebidaForm, BebidaForm
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
        platos = platos.filter(id_categoria_plato__in=categoria_id_int)
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


@login_required
@permiso_requerido("platos", "escribir")
def crear_plato(request):
    if request.method == "POST":
        nombre = request.POST.get("nombre")
        if nombre:
            nombre = nombre.title()
        precio = request.POST.get("precio")
        categoria_id = request.POST.get("categoria")
        ingredientes_ids = request.POST.getlist("ingredientes")
        descripcion = request.POST.get("descripcion", "")
        # Validar precio
        try:
            if float(precio) <= 0:
                messages.error(request, "Precio inválido: el precio debe ser mayor a 0")
                return render(
                    request,
                    "./platos/crear.html",
                    {
                        "ingredientes": Ingrediente.objects.all().order_by(
                            "nombre_ingrediente"
                        ),
                        "categorias": CategoriaPlato.objects.all().order_by(
                            "nombre_categoria_plato"
                        ),
                    },
                )
        except ValueError:
            messages.error(request, "Precio inválido: ingrese un número válido")
            return render(
                request,
                "inventario/platos/crear.html",
                {
                    "ingredientes": Ingrediente.objects.all().order_by(
                        "nombre_ingrediente"
                    ),
                    "categorias": CategoriaPlato.objects.all().order_by(
                        "nombre_categoria_plato"
                    ),
                },
            )
        # Validar nombre
        if not re.match(r"^[a-zA-ZáéíóúÁÉÍÓÚñÑ\s/-]+$", nombre):
            messages.error(
                request, "Nombre inválido: solo se permiten letras, espacios, / y -"
            )
            return render(
                request,
                "inventario/platos/crear.html",
                {
                    "ingredientes": Ingrediente.objects.all().order_by(
                        "nombre_ingrediente"
                    ),
                    "categorias": CategoriaPlato.objects.all().order_by(
                        "nombre_categoria_plato"
                    ),
                },
            )
        # Validar que no exista
        if Plato.objects.filter(nombre_plato=nombre).exists():
            messages.error(request, f'Plato "{nombre}" ya existe')
            return render(
                request,
                "inventario/platos/crear.html",
                {
                    "ingredientes": Ingrediente.objects.all().order_by(
                        "nombre_ingrediente"
                    ),
                    "categorias": CategoriaPlato.objects.all().order_by(
                        "nombre_categoria_plato"
                    ),
                },
            )
        # Validar que tenga al menos un ingrediente
        if not ingredientes_ids:
            messages.error(request, "Debe seleccionar al menos un ingrediente")
            return render(
                request,
                "./platos/crear.html",
                {
                    "ingredientes": Ingrediente.objects.all().order_by(
                        "nombre_ingrediente"
                    ),
                    "categorias": CategoriaPlato.objects.all().order_by(
                        "nombre_categoria_plato"
                    ),
                },
            )
        # Crear el plato
        categoria = CategoriaPlato.objects.get(id_categoria_plato=categoria_id)
        plato = Plato.objects.create(
            nombre_plato=nombre,
            precio_plato=precio,
            descripcion_plato=descripcion,
            categoria=categoria,
        )
        # Agregar ingredientes
        for ingrediente_id in ingredientes_ids:
            DetallePlato.objects.create(
                plato=plato,
                ingrediente=Ingrediente.objects.get(id_ingrediente=ingrediente_id),
                cantidad=1,
            )

        LogAuditoria.objects.create(
            tabla="Plato",
            accion="CREAR",
            registro_id=plato.id_plato,
            valores_anteriores="",
            valores_actuales=f"Plato creado: {plato.nombre_plato}. Precio: ${plato.precio_plato}",
            empleado=request.user.empleado,
        )
        messages.success(request, f'Plato "{nombre}" creado exitosamente')
        return redirect("inventario:listar_platos")

    else:
        ingredientes = Ingrediente.objects.all().order_by("nombre_ingrediente")
        categorias = CategoriaPlato.objects.all().order_by("nombre_categoria_plato")
        return render(
            request,
            "platos/crear.html",
            {"ingredientes": ingredientes, "categorias": categorias},
        )


@login_required
@permiso_requerido("platos", "modificar")
def editar_plato(request, pk):
    plato = get_object_or_404(Plato, pk=pk)

    if request.method == "POST":
        nombre = request.POST.get("nombre")
        if nombre:
            nombre = nombre.title()

        precio = request.POST.get("precio")
        categoria_id = request.POST.get("categoria")
        ingredientes_ids = request.POST.getlist("ingredientes")
        # Validar precio
        try:
            if float(precio) <= 0:
                messages.error(request, "Precio inválido: el precio debe ser mayor a 0")
                return render(
                    request,
                    "inventario/platos/editar.html",
                    {
                        "plato": plato,
                        "categorias": CategoriaPlato.objects.all().order_by(
                            "nombre_categoria_plato"
                        ),
                        "ingredientes": Ingrediente.objects.all().order_by(
                            "nombre_ingrediente"
                        ),
                    },
                )
        except ValueError:
            messages.error(request, "Precio inválido: ingrese un número válido")
            return render(
                request,
                "inventario/platos/editar.html",
                {
                    "plato": plato,
                    "categorias": CategoriaPlato.objects.all().order_by(
                        "nombre_categoria_plato"
                    ),
                    "ingredientes": Ingrediente.objects.all().order_by(
                        "nombre_ingrediente"
                    ),
                },
            )
        # Validar que tenga al menos un ingrediente
        if not ingredientes_ids:
            messages.error(request, "Debe seleccionar al menos un ingrediente")
            return render(
                request,
                "inventario/platos/editar.html",
                {
                    "plato": plato,
                    "categorias": CategoriaPlato.objects.all().order_by(
                        "nombre_categoria_plato"
                    ),
                    "ingredientes": Ingrediente.objects.all().order_by(
                        "nombre_ingrediente"
                    ),
                },
            )
        # Validar que no exista otro plato con el mismo nombre
        if Plato.objects.filter(nombre_plato=nombre).exclude(pk=pk).exists():
            messages.error(request, f'Plato "{nombre}" ya existe')
            return render(
                request,
                "inventario/platos/editar.html",
                {
                    "plato": plato,
                    "categorias": CategoriaPlato.objects.all().order_by(
                        "nombre_categoria_plato"
                    ),
                    "ingredientes": Ingrediente.objects.all().order_by(
                        "nombre_ingrediente"
                    ),
                },
            )
        # Actualizar plato
        valores_viejos = f"Nombre: {plato.nombre_plato}, Precio: {plato.precio_plato}, Categoría: {plato.categoria.nombre_categoria_plato}"
        plato.nombre_plato = nombre
        plato.precio_plato = precio
        plato.categoria = CategoriaPlato.objects.get(id_categoria_plato=categoria_id)
        plato.save()
        # Eliminar ingredientes anteriores y agregar los nuevos
        plato.detalleplato_set.all().delete()
        for ingrediente_id in ingredientes_ids:
            DetallePlato.objects.create(
                plato=plato,
                ingrediente=Ingrediente.objects.get(id_ingrediente=ingrediente_id),
                cantidad=1,
            )
        valores_nuevos = f"Nombre: {plato.nombre_plato}, Precio: {plato.precio_plato}, Categoría: {plato.categoria.nombre_categoria_plato}"
        LogAuditoria.objects.create(
            tabla="Plato",
            accion="MODIFICAR",
            registro_id=plato.id_plato,
            valores_anteriores=valores_viejos,
            valores_actuales=valores_nuevos,
            empleado=request.user.empleado,
        )
        messages.success(request, f'Plato "{nombre}" editado exitosamente')
        return redirect("inventario:listar_platos")
    else:
        categorias = CategoriaPlato.objects.all().order_by("nombre_categoria_plato")
        ingredientes = Ingrediente.objects.all().order_by("nombre_ingrediente")
        return render(
            request,
            "platos/editar.html",
            {"plato": plato, "categorias": categorias, "ingredientes": ingredientes},
        )


@login_required
@permiso_requerido("platos", "eliminar")
def eliminar_plato(request, pk):
    plato = get_object_or_404(Plato, pk=pk)

    if request.method == "POST":
        nombre = plato.nombre_plato
        plato.delete()
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
            unidad_medida = unidad_medida.title()
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

    if request.method == "POST":
        nombre = ingrediente.nombre_ingrediente
        ingrediente.delete()
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

        estado_anterior = ingrediente.estado_ingrediente
        ingrediente.estado_ingrediente = not ingrediente.estado_ingrediente
        ingrediente.save()

        if not ingrediente.estado_ingrediente:
            platos_afectados = Plato.objects.filter(
                detalleplato__ingrediente=ingrediente, estado_plato=True
            )
            for plato in platos_afectados:
                plato.estado_plato = False
                plato.save()

                LogAuditoria.objects.create(
                    tabla="Plato",
                    accion="MODIFICAR",
                    registro_id=plato.id_plato,
                    valores_anteriores="Estado: Disponible",
                    valores_actuales=f"Estado: No disponible. Motivo: Ingrediente '{ingrediente.nombre_ingrediente}' fuera de stock.",
                    empleado=request.user.empleado,
                )
        else:
            platos_afectados = Plato.objects.filter(
                detalleplato__ingrediente=ingrediente, estado_plato=False
            )
            for plato in platos_afectados:
                plato.estado_plato = True
                plato.save()

                LogAuditoria.objects.create(
                    tabla="Plato",
                    accion="MODIFICAR",
                    registro_id=plato.id_plato,
                    valores_anteriores="Estado: No disponible",
                    valores_actuales=f"Estado: Disponible. Motivo: Ingrediente '{ingrediente.nombre_ingrediente}' vuelve a estar en stock.",
                    empleado=request.user.empleado,
                )

        # LOG DEL INGREDIENTE
        LogAuditoria.objects.create(
            tabla="Ingrediente",
            accion="MODIFICAR",
            registro_id=ingrediente.id_ingrediente,
            valores_anteriores=f"Estado: {'Disponible' if estado_anterior else 'No disponible'}",
            valores_actuales=f"Estado: {'Disponible' if ingrediente.estado_ingrediente else 'No disponible'}. Motivo: {motivo}",
            empleado=request.user.empleado,
        )

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

    return redirect(request.META.get("HTTP_REFERER,", "inventario:listar_categorias"))


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
    if request.method == "POST":
        nombre = bebida.nombre_bebida
        bebida.delete()
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
