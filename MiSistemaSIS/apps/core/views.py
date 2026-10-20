from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Sum
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib import messages
from inventario.models import Plato, Bebida
from ventas.models import Mesa, Comanda


def home(request):
    # Si NO está logueado  (bienvenida)
    if not request.user.is_authenticated:
        return render(request, 'bienvenida.html')
    
    # Si está logueado(home con estadísticas)
    hoy = timezone.now().date()
    
    total_productos = (
        Plato.objects.filter(estado_plato=True).count() +
        Bebida.objects.filter(disponible_bebida=True).count()
    )
    
    mesas_ocupadas = Mesa.objects.filter(estado_mesa=False).count()
    mesas_totales = Mesa.objects.count()
    porcentaje_mesas = int((mesas_ocupadas / mesas_totales) * 100) if mesas_totales > 0 else 0
    
    comandas_pendientes = Comanda.objects.filter(
        estado_comanda__in=['pendiente', 'en_preparacion']
    ).count()
    
    comandas_en_preparacion = Comanda.objects.filter(
        estado_comanda='en_preparacion'
    ).count()
    
    ventas_hoy = Comanda.objects.filter(
        estado_comanda='pagado',
        fecha_hora__date=hoy
    ).aggregate(total=Sum('total_comanda'))['total'] or 0
    
    contexto = {
        'total_productos': total_productos,
        'mesas_ocupadas': mesas_ocupadas,
        'mesas_totales': mesas_totales,
        'porcentaje_mesas': porcentaje_mesas,
        'comandas_pendientes': comandas_pendientes,
        'comandas_en_preparacion': comandas_en_preparacion,
        'ventas_hoy': ventas_hoy,
    }
    
    return render(request, 'home.html', contexto)


def password_reset_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        users = User.objects.filter(email=email)
        
        if users.exists():
            user = users.first()
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            
            reset_url = request.build_absolute_uri(f'/password-reset-confirm/{uid}/{token}/')
            
            return render(request, 'registration/password_reset_done.html', {
                'reset_url': reset_url,
                'email': email,
            })
        else:
            messages.error(request, 'No existe una cuenta con ese correo.')
    
    return render(request, 'registration/password_reset_form.html')