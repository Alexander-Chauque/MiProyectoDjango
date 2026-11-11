from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.utils import timezone
from django.views.decorators.http import require_POST
from empleados.models import Empleado
from .models import Notificacion

# Create your views here.
def mis_notificaciones(request):
  """Las notificaciones dirigidas al cargo del usuario. Sin empleado, no hay notificaciones."""
  try:
    cargo = request.user.empleado.cargo
  except Empleado.DoesNotExist:
    return Notificacion.objects.none()  # Usuario sin empleado, no hay notificaciones
  return Notificacion.objects.filter(destino_perfil=cargo).order_by('-fecha')

@login_required
def bandeja_notificaciones(request):
  """Muestra la bandeja de notificaciones del usuario."""
  notificaciones = mis_notificaciones(request)
  if request.GET.get("estado") =="sin_leer":
    notificaciones = notificaciones.filter(leida=False)
  
  paginator = Paginator(notificaciones, 10) # Mostrar 10 notificaciones por página
  
  page_number = request.GET.get('page')
  page_obj = paginator.get_page(page_number)
  
  return render(request, 'notificaciones/bandeja.html', {'notificaciones': page_obj, 'estado': request.GET.get("estado", ""),})

@login_required
@require_POST
def marcar_como_leida(request, id_notificacion):
  """Marca una notificación como leída."""
  notificacion = get_object_or_404(mis_notificaciones(request), id_notificacion=id_notificacion)
  if notificacion.leida:
    messages.info(request, "La notificación ya estaba marcada como leída.")
  else:
    notificacion.leida = True
    notificacion.fecha_lectura = timezone.now()
    notificacion.save(update_fields=['leida', 'fecha_lectura'])
    messages.success(request, "Notificación marcada como leída.")
  return redirect('notificaciones:bandeja')

@login_required
@require_POST 
def marcar_todas_como_leidas(request):
  """Marca todas las notificaciones como leídas."""
  notificaciones = mis_notificaciones(request).filter(leida=False)
  if notificaciones.exists():
    cantidad = notificaciones.update(leida=True, fecha_lectura=timezone.now())
    messages.success(request, f"{cantidad} notificaciones marcadas como leídas.")
  else:
    messages.info(request, "No hay notificaciones sin leer.")
  return redirect('notificaciones:bandeja')