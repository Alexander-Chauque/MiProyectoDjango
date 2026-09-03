from django.shortcuts import render, get_object_or_404, redirect
from .models import Plato, CategoriaPlato, Ingrediente, DetallePlato
from django.db import models
from django.contrib.auth import authenticate, login
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages

@login_required
def home(request):
    total_platos = Plato.objects.count()
    total_ingredientes = Ingrediente.objects.count()
    total_categorias = CategoriaPlato.objects.count()
    
    activos_platos = Plato.objects.filter(estado=True).count()
    
    context = {
        'total_platos': total_platos,
        'total_ingredientes': total_ingredientes,
        'total_categorias': total_categorias,
        'activos_platos': activos_platos,
    }
    return render(request, 'home.html', context)

#login
def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('inventario:listar_platos')
        else:
            return render(request, 'login.html', {'error': 'Usuario o contraseña incorrectos'})
    else:
        return render(request, 'login.html')

#Funciones para listar, crear, editar y eliminar platos
@login_required
def listar_platos(request):
    platos = Plato.objects.all().order_by('nombre_plato')
    categorias = CategoriaPlato.objects.all().order_by('nombre_categoria_plato')
    return render(request, 'platos/listar.html', {'platos': platos, 'categorias': categorias})


@login_required
def crear_plato(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        if nombre:
            nombre = nombre.title()
        precio = request.POST.get('precio')
        categoria_id = request.POST.get('categoria')
        ingredientes_ids = request.POST.getlist('ingredientes')

        # Validar precio
        try:
            if float(precio) <= 0:
                messages.error(request, 'Precio inválido: el precio debe ser mayor a 0')
                return render(request, 'inventario/platos/crear.html', {
                    'ingredientes': Ingrediente.objects.all().order_by('nombre_ingrediente'),
                    'categorias': CategoriaPlato.objects.all().order_by('nombre_categoria_plato')
                })
        except ValueError:
            messages.error(request, 'Precio inválido: ingrese un número válido')
            return render(request, 'inventario/platos/crear.html', {
                'ingredientes': Ingrediente.objects.all().order_by('nombre_ingrediente'),
                'categorias': CategoriaPlato.objects.all().order_by('nombre_categoria_plato')
            })

        # Validar nombre
        if not re.match(r'^[a-zA-ZáéíóúÁÉÍÓÚñÑ\s/-]+$', nombre):
            messages.error(request, 'Nombre inválido: solo se permiten letras, espacios, / y -')
            return render(request, 'inventario/platos/crear.html', {
                'ingredientes': Ingrediente.objects.all().order_by('nombre_ingrediente'),
                'categorias': CategoriaPlato.objects.all().order_by('nombre_categoria_plato')
            })

        # Validar que no exista
        if Plato.objects.filter(nombre_plato=nombre).exists():
            messages.error(request, f'Plato "{nombre}" ya existe')
            return render(request, 'inventario/platos/crear.html', {
                'ingredientes': Ingrediente.objects.all().order_by('nombre_ingrediente'),
                'categorias': CategoriaPlato.objects.all().order_by('nombre_categoria_plato')
            })

        # Validar que tenga al menos un ingrediente
        if not ingredientes_ids:
            messages.error(request, 'Debe seleccionar al menos un ingrediente')
            return render(request, 'inventario/platos/crear.html', {
                'ingredientes': Ingrediente.objects.all().order_by('nombre_ingrediente'),
                'categorias': CategoriaPlato.objects.all().order_by('nombre_categoria_plato')
            })

        # Crear el plato
        categoria = CategoriaPlato.objects.get(id=categoria_id)
        plato = Plato.objects.create(
            nombre_plato=nombre,
            precio_plato=precio,
            categoria=categoria
        )

        # Agregar ingredientes
        for ingrediente_id in ingredientes_ids:
            DetallePlato.objects.create(
                plato=plato,
                ingrediente=Ingrediente.objects.get(id=ingrediente_id),
                cantidad=1
            )

        messages.success(request, f'Plato "{nombre}" creado exitosamente')
        return redirect('inventario:listar_platos')
    
    else:
        ingredientes = Ingrediente.objects.all().order_by('nombre_ingrediente')
        categorias = CategoriaPlato.objects.all().order_by('nombre_categoria_plato')
        return render(request, 'platos/crear.html', {
            'ingredientes': ingredientes,
            'categorias': categorias
        })


@login_required
def editar_plato(request, pk):
    plato = get_object_or_404(Plato, pk=pk)
    
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        if nombre:
            nombre = nombre.title()
        
        precio = request.POST.get('precio')
        categoria_id = request.POST.get('categoria')
        ingredientes_ids = request.POST.getlist('ingredientes')

        # Validar precio
        try:
            if float(precio) <= 0:
                messages.error(request, 'Precio inválido: el precio debe ser mayor a 0')
                return render(request, 'inventario/platos/editar.html', {
                    'plato': plato,
                    'categorias': CategoriaPlato.objects.all().order_by('nombre_categoria_plato'),
                    'ingredientes': Ingrediente.objects.all().order_by('nombre_ingrediente')
                })
        except ValueError:
            messages.error(request, 'Precio inválido: ingrese un número válido')
            return render(request, 'inventario/platos/editar.html', {
                'plato': plato,
                'categorias': CategoriaPlato.objects.all().order_by('nombre_categoria_plato'),
                'ingredientes': Ingrediente.objects.all().order_by('nombre_ingrediente')
            })

        # Validar que tenga al menos un ingrediente
        if not ingredientes_ids:
            messages.error(request, 'Debe seleccionar al menos un ingrediente')
            return render(request, 'inventario/platos/editar.html', {
                'plato': plato,
                'categorias': CategoriaPlato.objects.all().order_by('nombre_categoria_plato'),
                'ingredientes': Ingrediente.objects.all().order_by('nombre_ingrediente')
            })

        # Validar que no exista otro plato con el mismo nombre
        if Plato.objects.filter(nombre_plato=nombre).exclude(pk=pk).exists():
            messages.error(request, f'Plato "{nombre}" ya existe')
            return render(request, 'inventario/platos/editar.html', {
                'plato': plato,
                'categorias': CategoriaPlato.objects.all().order_by('nombre_categoria_plato'),
                'ingredientes': Ingrediente.objects.all().order_by('nombre_ingrediente')
            })

        # Actualizar plato
        plato.nombre_plato = nombre
        plato.precio_plato = precio
        plato.categoria = CategoriaPlato.objects.get(id=categoria_id)
        plato.save()

        # Eliminar ingredientes anteriores y agregar los nuevos
        plato.detalleplato_set.all().delete()
        
        for ingrediente_id in ingredientes_ids:
            DetallePlato.objects.create(
                plato=plato,
                ingrediente=Ingrediente.objects.get(id=ingrediente_id),
                cantidad=1
            )

        messages.success(request, f'Plato "{nombre}" editado exitosamente')
        return redirect('inventario:listar_platos')
    
    else:
        categorias = CategoriaPlato.objects.all().order_by('nombre_categoria_plato')
        ingredientes = Ingrediente.objects.all().order_by('nombre_ingrediente')
        return render(request, 'platos/editar.html', {
            'plato': plato,
            'categorias': categorias,
            'ingredientes': ingredientes
        })


@login_required
def eliminar_plato(request, pk):
    plato = get_object_or_404(Plato, pk=pk)
    
    if request.method == 'POST':
        nombre = plato.nombre_plato
        plato.delete()
        messages.success(request, f'Plato "{nombre}" eliminado exitosamente')
        return redirect('inventario:listar_platos')
    
    return render(request, 'platos/eliminar.html', {'plato': plato})


@login_required
def detalle_plato(request, pk):
    plato = get_object_or_404(Plato, pk=pk)
    detalles = plato.detalleplato_set.all().select_related('ingrediente')
    return render(request, 'platos/detalle.html', {
        'plato': plato,
        'detalles': detalles
    })


@login_required
def estado_plato(request, pk):
    plato = get_object_or_404(Plato, pk=pk)
    plato.estado_plato = not plato.estado_plato
    plato.save()
    
    if plato.estado_plato:
        messages.success(request, f'Plato "{plato.nombre_plato}" activado')
    else:
        messages.success(request, f'Plato "{plato.nombre_plato}" desactivado')
    
    return redirect('inventario:listar_platos')

# FUNCIONES PARA INGREDIENTES

@login_required
def listar_ingredientes(request):
    ingredientes = Ingrediente.objects.all().order_by('nombre_ingrediente')
    return render(request, 'ingredientes/listar_ingrediente.html', {'ingredientes': ingredientes})


@login_required
def crear_ingrediente(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        if nombre:
            nombre = nombre.lower()
        unidad_medida = request.POST.get('unidad_medida')
        if unidad_medida:
            unidad_medida = unidad_medida.title()
        costo_unitario = request.POST.get('costo_unitario', 0)
        
        Ingrediente.objects.create(
            nombre_ingrediente=nombre,
            unidad_medida=unidad_medida,
            costo_unitario=costo_unitario
        )
        messages.success(request, f'Ingrediente "{nombre}" creado exitosamente')
        return redirect('inventario:listar_ingredientes')
    else:
        return render(request, 'ingredientes/crear_ingrediente.html')


@login_required
def editar_ingrediente(request, pk):
    ingrediente = get_object_or_404(Ingrediente, pk=pk)
    
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        if nombre:
            nombre = nombre.title()
        ingrediente.nombre_ingrediente = nombre
        
        unidad_medida = request.POST.get('unidad_medida')
        if unidad_medida:
            unidad_medida = unidad_medida.lower()
        ingrediente.unidad_medida = unidad_medida
        
        ingrediente.costo_unitario = request.POST.get('costo_unitario', ingrediente.costo_unitario)
        ingrediente.save()
        
        messages.success(request, f'Ingrediente "{ingrediente.nombre_ingrediente}" actualizado')
        return redirect('inventario:listar_ingredientes')
    else:
        return render(request, 'ingredientes/editar_ingrediente.html', {
            'ingrediente': ingrediente
        })


@login_required
def eliminar_ingrediente(request, pk):
    ingrediente = get_object_or_404(Ingrediente, pk=pk)
    
    if request.method == 'POST':
        nombre = ingrediente.nombre_ingrediente
        ingrediente.delete()
        messages.success(request, f'Ingrediente "{nombre}" eliminado')
        return redirect('inventario:listar_ingredientes')
    else:
        return render(request, 'ingredientes/eliminar_ingrediente.html', {
            'ingrediente': ingrediente
        })


@login_required
def detalle_ingrediente(request, pk):
    ingrediente = get_object_or_404(Ingrediente, pk=pk)
    return render(request, 'ingredientes/detalle_ingrediente.html', {
        'ingrediente': ingrediente
    })


@login_required
def estado_ingrediente(request, pk):
    ingrediente = get_object_or_404(Ingrediente, pk=pk)
    ingrediente.estado_ingrediente = not ingrediente.estado_ingrediente
    ingrediente.save()
    
    if ingrediente.estado_ingrediente:
        messages.success(request, f'Ingrediente "{ingrediente.nombre_ingrediente}" activado')
    else:
        messages.success(request, f'Ingrediente "{ingrediente.nombre_ingrediente}" desactivado')
    
    return redirect('inventario:listar_ingredientes')

# FUNCIONES PARA CATEGORÍAS

@login_required
def listar_categorias(request):
    categorias = CategoriaPlato.objects.all().order_by('nombre_categoria_plato')
    return render(request, 'categorias/listar_categoria.html', {'categorias': categorias})


@login_required
def crear_categoria(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        if nombre:
            nombre = nombre.title()
        descripcion = request.POST.get('descripcion', '')
        
        CategoriaPlato.objects.create(
            nombre_categoria_plato=nombre,
            descripcion_categoria_plato=descripcion
        )
        messages.success(request, f'Categoría "{nombre}" creada')
        return redirect('inventario:listar_categorias')
    else:
        return render(request, 'categorias/crear_categoria.html')


@login_required
def editar_categoria(request, pk):
    categoria = get_object_or_404(CategoriaPlato, pk=pk)
    
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        if nombre:
            nombre = nombre.title()
        categoria.nombre_categoria_plato = nombre
        categoria.descripcion_categoria_plato = request.POST.get('descripcion', '')
        categoria.save()
        
        messages.success(request, f'Categoría "{categoria.nombre_categoria_plato}" actualizada')
        return redirect('inventario:listar_categorias')
    else:
        return render(request, 'categorias/editar_categoria.html', {
            'categoria': categoria
        })


@login_required
def eliminar_categoria(request, pk):
    categoria = get_object_or_404(CategoriaPlato, pk=pk)
    
    if request.method == 'POST':
        nombre = categoria.nombre_categoria_plato
        categoria.delete()
        messages.success(request, f'Categoría "{nombre}" eliminada')
        return redirect('inventario:listar_categorias')
    else:
        return render(request, 'categorias/eliminar_categoria.html', {
            'categoria': categoria
        })


@login_required
def detalle_categoria(request, pk):
    categoria = get_object_or_404(CategoriaPlato, pk=pk)
    platos = categoria.plato_set.all().order_by('nombre_plato')
    return render(request, 'categorias/detalle_categoria.html', {
        'categoria': categoria,
        'platos': platos
    })


@login_required
def estado_categoria(request, pk):
    categoria = get_object_or_404(CategoriaPlato, pk=pk)
    categoria.estado_categoria_plato = not categoria.estado_categoria_plato
    categoria.save()
    
    if categoria.estado_categoria_plato:
        messages.success(request, f'Categoría "{categoria.nombre_categoria_plato}" activada')
    else:
        messages.success(request, f'Categoría "{categoria.nombre_categoria_plato}" desactivada')
    
    return redirect(request.META.get('HTTP_REFERER,','inventario:listar_categorias'))