"""Direcciones de la API. Todas empiezan con /api/ (ver MiSistemaSIS/urls.py)."""
from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from . import views, vistas_cargos, vistas_empleados, vistas_login

app_name = "api"

urlpatterns = [
    # Login de la web en React
    path("token/", vistas_login.LoginView.as_view(), name="token"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("yo/", views.YoView.as_view(), name="yo"),
    path("resumen/", views.ResumenView.as_view(), name="resumen"),
    # Ingredientes
    path("ingredientes/", views.IngredienteListaView.as_view(), name="ingredientes"),
    path("ingredientes/<int:pk>/", views.IngredienteDetalleView.as_view(), name="ingrediente"),
    path("ingredientes/<int:pk>/estado/", views.IngredienteEstadoView.as_view(), name="ingrediente_estado"),
    # Platos
    path("categorias/", views.CategoriasView.as_view(), name="categorias"),
    path("platos/", views.PlatoListaView.as_view(), name="platos"),
    path("platos/ingredientes/", views.IngredientesParaPlatoView.as_view(), name="platos_ingredientes"),
    path("platos/<int:pk>/", views.PlatoDetalleView.as_view(), name="plato"),
    path("platos/<int:pk>/estado/", views.PlatoEstadoView.as_view(), name="plato_estado"),
    # Bebidas
    path("tipos-bebida/", views.TiposBebidaView.as_view(), name="tipos_bebida"),
    path("bebidas/", views.BebidaListaView.as_view(), name="bebidas"),
    path("bebidas/<int:pk>/", views.BebidaDetalleView.as_view(), name="bebida"),
    path("bebidas/<int:pk>/estado/", views.BebidaEstadoView.as_view(), name="bebida_estado"),
    # Mesas
    path("mesas/", views.MesaListaView.as_view(), name="mesas"),
    path("mesas/<int:pk>/estado/", views.MesaEstadoView.as_view(), name="mesa_estado"),
    # Comandas
    path("comandas/", views.ComandaListaView.as_view(), name="comandas"),
    path("comandas/productos/", views.ComandaProductosView.as_view(), name="comanda_productos"),
    path("comandas/<int:pk>/", views.ComandaDetalleView.as_view(), name="comanda"),
    path("comandas/<int:pk>/estado/", views.ComandaEstadoView.as_view(), name="comanda_estado"),
    path("comandas/<int:pk>/pago/", views.ComandaPagoView.as_view(), name="comanda_pago"),
    # Empleados
    path("empleados/", vistas_empleados.EmpleadoListaView.as_view(), name="empleados"),
    path("empleados/cargos/", vistas_empleados.CargosParaEmpleadoView.as_view(), name="empleados_cargos"),
    path("empleados/<int:pk>/", vistas_empleados.EmpleadoDetalleView.as_view(), name="empleado"),
    path("empleados/<int:pk>/estado/", vistas_empleados.EmpleadoEstadoView.as_view(), name="empleado_estado"),
    path("empleados/<int:pk>/contrasena/", vistas_empleados.EmpleadoContrasenaView.as_view(), name="empleado_contrasena"),
    # Cargos y permisos
    path("cargos/", vistas_cargos.CargoListaView.as_view(), name="cargos"),
    path("cargos/<int:pk>/", vistas_cargos.CargoDetalleView.as_view(), name="cargo"),
    path("cargos/<int:pk>/permisos/", vistas_cargos.CargoPermisosView.as_view(), name="cargo_permisos"),
    path("permisos/", vistas_cargos.PermisoListaView.as_view(), name="permisos"),
    path("permisos/<int:pk>/", vistas_cargos.PermisoDetalleView.as_view(), name="permiso"),
]
