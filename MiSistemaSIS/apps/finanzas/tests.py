from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from empleados.models import Cargo, Empleado

from .models import caja, categoria_gasto, gasto, metodo_pago


class NavegacionFinanzasTests(TestCase):
    """Que cada pantalla de Finanzas diga dónde estás y no ofrezca caminos sin salida."""

    def setUp(self):
        admin = Cargo.objects.create(nombre_cargo="Administrador Prueba", nivel_acceso=99)
        usuario = User.objects.create_user("caja.prueba", password="Clave-Prueba-123")
        self.empleado = Empleado.objects.create(
            nombre_empleado="Cami", apellido_empleado="Caja", dni="99000010",
            correo="cami@prueba.com", user=usuario, cargo=admin,
        )
        self.client.force_login(usuario)

    def test_las_migas_no_llevan_a_una_pantalla_finanzas_que_no_existe(self):
        for nombre in ("listar_cajas", "listar_ventas", "listar_gastos", "listar_cat_gasto", "listar_met_pago"):
            respuesta = self.client.get(reverse(f"finanzas:{nombre}"))
            self.assertContains(respuesta, '<span class="breadcrumb-item">Finanzas</span>', msg_prefix=nombre)
            self.assertNotContains(respuesta, f'href="{reverse("finanzas:finanzas_home")}"', msg_prefix=nombre)

    def test_limpiar_filtros_de_ventas_se_queda_en_ventas(self):
        respuesta = self.client.get(reverse("finanzas:listar_ventas"))
        self.assertContains(respuesta, f'href="{reverse("finanzas:listar_ventas")}"\n')

    def test_sin_caja_abierta_se_ofrece_abrirla(self):
        respuesta = self.client.get(reverse("finanzas:listar_cajas"))
        self.assertContains(respuesta, reverse("finanzas:abrir_caja"))
        self.assertContains(respuesta, "Sin caja abierta")

    def test_con_caja_abierta_se_va_directo_a_ella(self):
        abierta = caja.objects.create(empleado_apertura=self.empleado, saldo_inicial=Decimal("1000"))
        respuesta = self.client.get(reverse("finanzas:listar_cajas"))
        self.assertContains(respuesta, "Ver caja abierta")
        self.assertContains(respuesta, reverse("finanzas:detalle_caja", args=[abierta.pk]))
        self.assertNotContains(respuesta, f'href="{reverse("finanzas:abrir_caja")}"')

    def test_una_categoria_con_gastos_no_ofrece_modificar_ni_eliminar(self):
        usada = categoria_gasto.objects.create(nombre_categoria_gasto="Limpieza")
        libre = categoria_gasto.objects.create(nombre_categoria_gasto="Varios")
        caja_actual = caja.objects.create(empleado_apertura=self.empleado, saldo_inicial=Decimal("1000"))
        gasto.objects.create(caja_gasto=caja_actual, cat_gasto=usada, monto_gasto=Decimal("50"),
                             empleado_gasto=self.empleado)

        respuesta = self.client.get(reverse("finanzas:listar_cat_gasto"))
        self.assertNotContains(respuesta, reverse("finanzas:editar_cat_gasto", args=[usada.pk]))
        self.assertNotContains(respuesta, reverse("finanzas:eliminar_cat_gasto", args=[usada.pk]))
        self.assertContains(respuesta, reverse("finanzas:editar_cat_gasto", args=[libre.pk]))
        self.assertContains(respuesta, "btn-icon--bloqueado", count=2)

        detalle = self.client.get(reverse("finanzas:detalle_cat_gasto", args=[usada.pk]))
        self.assertNotContains(detalle, "Editar categoría")

    def test_un_metodo_sin_uso_se_puede_eliminar(self):
        metodo = metodo_pago.objects.create(nombre_metodo_pago="Transferencia")
        respuesta = self.client.get(reverse("finanzas:listar_met_pago"))
        self.assertContains(respuesta, reverse("finanzas:eliminar_met_pago", args=[metodo.pk]))
