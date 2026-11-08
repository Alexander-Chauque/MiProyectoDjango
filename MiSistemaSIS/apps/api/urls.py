"""Direcciones de la API. Todas empiezan con /api/ (ver MiSistemaSIS/urls.py)."""
from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from . import (
    views,
    vistas_asistencias,
    vistas_cargos,
    vistas_catalogos,
    vistas_cuenta,
    vistas_empleados,
    vistas_finanzas,
    vistas_login,
    vistas_reportes,
)

app_name = "api"

urlpatterns = [
    # Login de la web en React
    path("token/", vistas_login.LoginView.as_view(), name="token"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("token/cambiar-clave/", vistas_cuenta.CambioObligatorioView.as_view(), name="cambio_obligatorio"),
    # Cuenta de quien inició sesión
    path("perfil/", vistas_cuenta.PerfilView.as_view(), name="perfil"),
    path("perfil/contrasena/", vistas_cuenta.CambiarContrasenaView.as_view(), name="perfil_contrasena"),
    path("yo/", views.YoView.as_view(), name="yo"),
    path("resumen/", views.ResumenView.as_view(), name="resumen"),
    # Ingredientes
    path("ingredientes/", views.IngredienteListaView.as_view(), name="ingredientes"),
    path("ingredientes/<int:pk>/", views.IngredienteDetalleView.as_view(), name="ingrediente"),
    path("ingredientes/<int:pk>/estado/", views.IngredienteEstadoView.as_view(), name="ingrediente_estado"),
    # Platos
    path("categorias/", views.CategoriasView.as_view(), name="categorias"),
    # Categorías de platos: alta, edición y estado (módulo "categorias")
    path("categorias-plato/", vistas_catalogos.CategoriaPlatoListaView.as_view(), name="categorias_plato"),
    path("categorias-plato/<int:pk>/", vistas_catalogos.CategoriaPlatoDetalleView.as_view(), name="categoria_plato"),
    path("categorias-plato/<int:pk>/estado/", vistas_catalogos.CategoriaPlatoEstadoView.as_view(), name="categoria_plato_estado"),
    path("platos/", views.PlatoListaView.as_view(), name="platos"),
    path("platos/ingredientes/", views.IngredientesParaPlatoView.as_view(), name="platos_ingredientes"),
    path("platos/<int:pk>/", views.PlatoDetalleView.as_view(), name="plato"),
    path("platos/<int:pk>/estado/", views.PlatoEstadoView.as_view(), name="plato_estado"),
    # Bebidas
    path("tipos-bebida/", vistas_catalogos.TipoBebidaListaView.as_view(), name="tipos_bebida"),
    path("tipos-bebida/<int:pk>/", vistas_catalogos.TipoBebidaDetalleView.as_view(), name="tipo_bebida"),
    path("tipos-bebida/<int:pk>/estado/", vistas_catalogos.TipoBebidaEstadoView.as_view(), name="tipo_bebida_estado"),
    path("bebidas/", views.BebidaListaView.as_view(), name="bebidas"),
    path("bebidas/<int:pk>/", views.BebidaDetalleView.as_view(), name="bebida"),
    path("bebidas/<int:pk>/estado/", views.BebidaEstadoView.as_view(), name="bebida_estado"),
    # Mesas
    path("mesas/", views.MesaListaView.as_view(), name="mesas"),
    path("mesas/<int:pk>/", views.MesaDetalleView.as_view(), name="mesa"),
    path("mesas/<int:pk>/estado/", views.MesaEstadoView.as_view(), name="mesa_estado"),
    # Comandas
    path("comandas/", views.ComandaListaView.as_view(), name="comandas"),
    path("comandas/productos/", views.ComandaProductosView.as_view(), name="comanda_productos"),
    path("comandas/consulta/", views.ComandaConsultaView.as_view(), name="comandas_consulta"),
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
    # Asistencias y turnos (módulo "empleados")
    path("asistencias/", vistas_asistencias.AsistenciaListaView.as_view(), name="asistencias"),
    path("asistencias/<int:pk>/", vistas_asistencias.AsistenciaDetalleView.as_view(), name="asistencia"),
    path("tipos-asistencia/", vistas_asistencias.TipoAsistenciaListaView.as_view(), name="tipos_asistencia"),
    path("tipos-asistencia/<int:pk>/", vistas_asistencias.TipoAsistenciaDetalleView.as_view(), name="tipo_asistencia"),
    # Finanzas (módulo "caja", salvo ventas)
    path("categorias-gasto/", vistas_finanzas.CategoriaGastoListaView.as_view(), name="categorias_gasto"),
    path("categorias-gasto/<int:pk>/", vistas_finanzas.CategoriaGastoDetalleView.as_view(), name="categoria_gasto"),
    path("categorias-gasto/<int:pk>/estado/", vistas_finanzas.CategoriaGastoEstadoView.as_view(), name="categoria_gasto_estado"),
    path("metodos-pago/", vistas_finanzas.MetodoPagoListaView.as_view(), name="metodos_pago"),
    path("metodos-pago/<int:pk>/", vistas_finanzas.MetodoPagoDetalleView.as_view(), name="metodo_pago"),
    path("metodos-pago/<int:pk>/estado/", vistas_finanzas.MetodoPagoEstadoView.as_view(), name="metodo_pago_estado"),
    path("cajas/", vistas_finanzas.CajaListaView.as_view(), name="cajas"),
    path("cajas/<int:pk>/", vistas_finanzas.CajaDetalleView.as_view(), name="caja"),
    path("cajas/<int:pk>/arqueo/", vistas_finanzas.CajaArqueoView.as_view(), name="caja_arqueo"),
    path("cajas/<int:pk>/cierre/", vistas_finanzas.CajaCierreView.as_view(), name="caja_cierre"),
    path("gastos/", vistas_finanzas.GastoListaView.as_view(), name="gastos"),
    path("gastos/<int:pk>/", vistas_finanzas.GastoDetalleView.as_view(), name="gasto"),
    path("ventas/", vistas_finanzas.VentaListaView.as_view(), name="ventas"),
    # Reportes y auditoría
    path("reportes/", vistas_reportes.ReporteView.as_view(), name="reportes"),
    path("auditoria/", vistas_reportes.AuditoriaView.as_view(), name="auditoria"),
]
