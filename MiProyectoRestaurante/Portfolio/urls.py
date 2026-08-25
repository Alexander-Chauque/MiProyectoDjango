from django.urls import path
from Portfolio import views

urlpatterns = [
    path('', views.ProjectIndex, name='project_index'),
    path('<int:pk>/', views.ProjectDetail, name='project_detail'),
]