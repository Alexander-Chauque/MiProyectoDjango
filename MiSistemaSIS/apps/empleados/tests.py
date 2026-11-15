from io import StringIO

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from .forms import CargoForm, EmpleadoAltaForm
from .models import Cargo, Empleado

CLAVE = "Clave#2026"


def crear_empleado(nombre, apellido, dni, cargo, clave=CLAVE):
    user = User.objects.create_user(username=f"{apellido}{nombre[0]}".lower(), password=clave)
    return Empleado.objects.create(
        nombre_empleado=nombre, apellido_empleado=apellido, dni=dni,
        correo=f"{apellido}@example.com".lower(), cargo=cargo, user=user,
    )


class AccesoPorCargoTests(TestCase):
    """Solo los cargos con acceso (Mozo y Administrador) ingresan al sistema."""

    def setUp(self):
        cache.clear()  # el límite de intentos del login usa la caché
        self.admin = Cargo.objects.create(nombre_cargo="Administrador", nivel_acceso=5, acceso_sistema=True)
        self.mozo = Cargo.objects.create(nombre_cargo="Mozo", nivel_acceso=2, acceso_sistema=True)
        self.cocinero = Cargo.objects.create(nombre_cargo="Cocinero", nivel_acceso=1)
        self.empleado_mozo = crear_empleado("Ana", "Perez", "30111222", self.mozo)
        self.empleado_cocina = crear_empleado("Rosa", "Mamani", "30222333", self.cocinero)

    def ingresar(self, usuario, clave=CLAVE):
        return self.client.post(reverse("login"), {"username": usuario, "password": clave})

    def test_mozo_ingresa(self):
        respuesta = self.ingresar("pereza")
        self.assertRedirects(respuesta, reverse("home"), fetch_redirect_response=False)

    def test_cargo_sin_acceso_no_ingresa(self):
        respuesta = self.ingresar("mamanir")
        self.assertEqual(respuesta.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertContains(respuesta, "no tiene acceso al sistema")

    def test_clave_incorrecta_no_revela_el_cargo(self):
        respuesta = self.ingresar("mamanir", "otra-clave")
        self.assertNotContains(respuesta, "no tiene acceso al sistema")
        self.assertContains(respuesta, "incorrectos")

    def test_sesion_abierta_se_cierra_al_quitar_el_acceso(self):
        self.ingresar("pereza")
        self.empleado_mozo.cargo = self.cocinero
        self.empleado_mozo.save()
        respuesta = self.client.get(reverse("home"))
        self.assertRedirects(respuesta, reverse("login"), fetch_redirect_response=False)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_api_no_entrega_token_sin_acceso(self):
        respuesta = self.client.post("/api/token/", {"username": "mamanir", "password": CLAVE})
        self.assertEqual(respuesta.status_code, 401)
        self.assertEqual(respuesta.json().get("codigo"), "cargo_sin_acceso")
        self.assertEqual(self.client.post("/api/token/", {"username": "pereza", "password": CLAVE}).status_code, 200)

    def test_alta_sin_acceso_no_pide_contrasena(self):
        datos = {"nombre_empleado": "Hugo", "apellido_empleado": "Chocobar", "dni": "30666777",
                 "correo": "hugo@example.com", "cargo": self.cocinero.pk}
        form = EmpleadoAltaForm(datos)
        self.assertTrue(form.is_valid(), form.errors)
        empleado = form.save()
        self.assertFalse(empleado.user.has_usable_password())

    def test_alta_con_acceso_exige_contrasena(self):
        datos = {"nombre_empleado": "Luis", "apellido_empleado": "Rios", "dni": "30777888",
                 "correo": "luis@example.com", "cargo": self.mozo.pk}
        form = EmpleadoAltaForm(datos)
        self.assertFalse(form.is_valid())
        self.assertIn("contrasena", form.errors)

    def test_administrador_no_puede_perder_el_acceso(self):
        form = CargoForm({"nombre_cargo": "Administrador", "nivel_acceso": 5, "sueldo_cargo": "0"},
                         instance=self.admin)
        self.assertFalse(form.is_valid())
        self.assertIn("acceso_sistema", form.errors)

    def test_cargar_personal(self):
        call_command("cargar_personal", stdout=StringIO())
        call_command("cargar_personal", stdout=StringIO())
        con_acceso = set(Cargo.objects.filter(acceso_sistema=True).values_list("nombre_cargo", flat=True))
        self.assertEqual(con_acceso, {"Administrador", "Mozo"})
        self.assertEqual(Empleado.objects.filter(dni="40111222").count(), 1)
        bachero = Empleado.objects.get(dni="37888999")
        self.assertFalse(bachero.puede_ingresar)
        self.assertFalse(bachero.user.has_usable_password())


class MiPerfilTests(TestCase):
    """La pantalla Mi perfil: datos propios, el día de trabajo y la edición del contacto."""

    def setUp(self):
        cargo = Cargo.objects.create(nombre_cargo="Mozo Prueba", nivel_acceso=1, acceso_sistema=True)
        self.usuario = User.objects.create_user("lu.perfil", password="Clave-Prueba-123")
        self.empleado = Empleado.objects.create(
            nombre_empleado="Lucía", apellido_empleado="Perfil", dni="99000020",
            correo="lu@prueba.com", telefono="3871234567", user=self.usuario, cargo=cargo,
        )
        self.client.force_login(self.usuario)

    def test_muestra_quien_soy_y_mis_datos(self):
        respuesta = self.client.get(reverse("empleados:mi_perfil"))
        self.assertContains(respuesta, "Lucía Perfil")
        self.assertContains(respuesta, "Mozo Prueba")
        self.usuario.refresh_from_db()  # el usuario se sincroniza con el empleado al guardarlo
        self.assertContains(respuesta, f"@{self.usuario.username}")
        self.assertContains(respuesta, "99000020")
        self.assertContains(respuesta, reverse("empleados:cambiar_contrasena"))

    def test_muestra_lo_que_hice_hoy(self):
        from decimal import Decimal

        from ventas.models import Comanda, Mesa

        mesa = Mesa.objects.create(numero_mesa=1, ubicacion="salon")
        Comanda.objects.create(mesa=mesa, empleado=self.empleado, total_comanda=Decimal("100"))
        respuesta = self.client.get(reverse("empleados:mi_perfil"))
        self.assertEqual(respuesta.context["mi_dia"]["comandas"], 1)
        self.assertEqual(respuesta.context["mi_dia"]["abiertas"], 1)
        self.assertContains(respuesta, "Comanda tomada hoy")

    def test_editar_el_contacto_en_la_misma_tarjeta(self):
        pantalla = self.client.get(reverse("empleados:mi_perfil") + "?editar=1")
        self.assertContains(pantalla, 'name="correo"')
        self.client.post(reverse("empleados:mi_perfil"), {"correo": "lucia@prueba.com", "telefono": "3879999999"})
        self.empleado.refresh_from_db()
        self.assertEqual(self.empleado.correo, "lucia@prueba.com")
        self.assertEqual(self.empleado.telefono, "3879999999")
