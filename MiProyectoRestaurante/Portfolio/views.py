from django.shortcuts import render
from Portfolio.models import Proyecto

# Create your views here.
def ProjectIndex(request):
    proyectos = Proyecto.objects.all()

    context = {
        'proyectos': proyectos
    }
    return render(request, 'projects/index.html', context)

def ProjectDetail(request, pk):
    proyecto = Proyecto.objects.get(pk=pk)

    context = {
        'proyecto': proyecto
    }
    return render(request, 'projects/detail.html', context)
