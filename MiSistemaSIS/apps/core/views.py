from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib import messages
def home(request):
    # Si el usuario está logueado → mostrar el home con tarjetas
    if request.user.is_authenticated:
        return render(request, 'home.html')
    # Si NO está logueado → mostrar la página de bienvenida
    else:
        return render(request, 'bienvenida.html')

@login_required
def home(request):
    return render(request, 'home.html')

@login_required
def home(request):
    return render(request, 'home.html')


def password_reset_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        # Buscar usuarios con ese correo
        users = User.objects.filter(email=email)
        
        if users.exists():
            user = users.first()
            # Generar el token y uid
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            
            # Construir el enlace
            reset_url = request.build_absolute_uri(f'/password-reset-confirm/{uid}/{token}/')
            
            # Pasar el enlace a la plantilla (SIMULACIÓN)
            return render(request, 'registration/password_reset_done.html', {
                'reset_url': reset_url,
                'email': email,
            })
        else:
            messages.error(request, 'No existe una cuenta con ese correo.')
    
    return render(request, 'registration/password_reset_form.html')