"""Pruebas del login de la web en React.

Las migraciones actuales del proyecto fallan al crear la base de pruebas en MySQL,
así que estas pruebas se ejecutan con ajustes que usan SQLite y omiten las migraciones.
"""
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from empleados.models import Cargo, Empleado
from inventario.models import Ingrediente

CONTRASENA = "Clave-de-prueba-123"


class LoginWebTests(TestCase):
    def setUp(self):
        cache.clear()
        self.cliente = APIClient()
        self.user = User.objects.create_user("ana.prueba", password=CONTRASENA)
        cargo = Cargo.objects.create(nombre_cargo="Administrador Prueba", nivel_acceso=99)
        self.empleado = Empleado.objects.create(
            nombre_empleado="Ana",
            apellido_empleado="Prueba",
            dni="99000001",
            correo="ana@prueba.com",
            user=self.user,
            cargo=cargo,
        )

    def _login(self, identificador="ana.prueba", contrasena=CONTRASENA):
        return self.cliente.post(
            "/api/token/", {"username": identificador, "password": contrasena}, format="json"
        )

    def _con_token(self, token):
        cliente = APIClient()
        cliente.credentials(HTTP_AUTHORIZATION=f"JWT {token}")
        return cliente

    def test_entra_con_usuario_o_correo(self):
        for identificador in ("ana.prueba", "ANA@prueba.com", "  ana.prueba  "):
            with self.subTest(identificador):
                respuesta = self._login(identificador)
                self.assertEqual(respuesta.status_code, 200, respuesta.data)
                self.assertIn("access", respuesta.data)
                self.assertIn("refresh", respuesta.data)

    def test_rechaza_contrasena_incorrecta_con_mensaje_en_espanol(self):
        respuesta = self._login(contrasena="incorrecta")
        self.assertEqual(respuesta.status_code, 401)
        self.assertIn("incorrectos", str(respuesta.data["detail"]))

    def test_rechaza_correo_de_otra_persona_con_contrasena_incorrecta(self):
        self.assertEqual(self._login("nadie@prueba.com").status_code, 401)

    def test_rechaza_empleado_dado_de_baja(self):
        Empleado.objects.filter(pk=self.empleado.pk).update(estado=False)
        self.assertEqual(self._login().status_code, 401)

    def test_rechaza_usuario_sin_empleado(self):
        User.objects.create_user("sin.empleado", password=CONTRASENA)
        self.assertEqual(self._login("sin.empleado").status_code, 401)

    def test_exige_cambio_de_contrasena_pendiente(self):
        Empleado.objects.filter(pk=self.empleado.pk).update(debe_cambiar_contrasena=True)
        respuesta = self._login()
        self.assertEqual(respuesta.status_code, 401)
        self.assertIn("cambiar tu contraseña", str(respuesta.data["detail"]))

    def test_token_permite_usar_la_api(self):
        token = self._login().data["access"]
        cliente = self._con_token(token)
        yo = cliente.get("/api/yo/")
        self.assertEqual(yo.status_code, 200, yo.data)
        self.assertEqual(yo.data["usuario"], "ana.prueba")
        self.assertIn("ingredientes:leer", yo.data["permisos"])
        self.assertEqual(cliente.get("/api/resumen/").status_code, 200)

    def test_sin_token_responde_401(self):
        self.assertEqual(APIClient().get("/api/yo/").status_code, 401)

    def test_token_deja_de_servir_al_dar_de_baja(self):
        cliente = self._con_token(self._login().data["access"])
        Empleado.objects.filter(pk=self.empleado.pk).update(estado=False)
        self.assertEqual(cliente.get("/api/yo/").status_code, 401)

    def test_token_deja_de_servir_al_cambiar_contrasena(self):
        cliente = self._con_token(self._login().data["access"])
        self.user.set_password("Otra-clave-456789")
        self.user.save()
        self.assertEqual(cliente.get("/api/yo/").status_code, 401)

    def test_refresh_entrega_un_token_nuevo_que_funciona(self):
        refresh = self._login().data["refresh"]
        respuesta = self.cliente.post("/api/token/refresh/", {"refresh": refresh}, format="json")
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(self._con_token(respuesta.data["access"]).get("/api/yo/").status_code, 200)

    def test_refresh_no_sirve_para_entrar_tras_la_baja(self):
        refresh = self._login().data["refresh"]
        Empleado.objects.filter(pk=self.empleado.pk).update(estado=False)
        respuesta = self.cliente.post("/api/token/refresh/", {"refresh": refresh}, format="json")
        if respuesta.status_code == 200:
            cliente = self._con_token(respuesta.data["access"])
            self.assertEqual(cliente.get("/api/yo/").status_code, 401)

    def test_limita_los_intentos_de_login(self):
        codigos = [self._login(contrasena="mal").status_code for _ in range(11)]
        self.assertEqual(codigos[:10], [401] * 10)
        self.assertEqual(codigos[10], 429)

    def test_crea_y_edita_ingrediente_con_auditoria(self):
        cliente = self._con_token(self._login().data["access"])
        creado = cliente.post(
            "/api/ingredientes/",
            {"nombre_ingrediente": "ingrediente de prueba", "costo_unitario": "12.50", "unidad_medida": "kg"},
            format="json",
        )
        self.assertEqual(creado.status_code, 201, creado.data)
        id_nuevo = creado.data["id_ingrediente"]
        editado = cliente.patch(
            f"/api/ingredientes/{id_nuevo}/", {"costo_unitario": "20.00"}, format="json"
        )
        self.assertEqual(editado.status_code, 200, editado.data)
        estado = cliente.post(f"/api/ingredientes/{id_nuevo}/estado/", {"motivo": "Prueba"}, format="json")
        self.assertEqual(estado.status_code, 200, estado.data)
        self.assertFalse(Ingrediente.objects.get(pk=id_nuevo).estado_ingrediente)

    def test_navegador_de_la_web_puede_llamar_a_la_api(self):
        respuesta = self.cliente.options(
            "/api/token/",
            HTTP_ORIGIN="http://localhost:5173",
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS="authorization,content-type",
        )
        self.assertEqual(respuesta["Access-Control-Allow-Origin"], "http://localhost:5173")

    def test_app_movil_sigue_entrando_con_firebase(self):
        cliente = APIClient()
        cliente.credentials(HTTP_AUTHORIZATION="Bearer token-de-firebase")
        with patch("empleados.autenticacion.id_token.verify_firebase_token") as verificar, override_settings(
            FIREBASE_PROJECT_ID="proyecto"
        ):
            verificar.return_value = {
                "iss": "https://securetoken.google.com/proyecto",
                "email": "ana@prueba.com",
                "email_verified": True,
            }
            self.assertEqual(cliente.get("/api/yo/").status_code, 200)

    def test_token_de_la_web_no_pasa_por_firebase(self):
        token = self._login().data["access"]
        with patch("empleados.autenticacion.id_token.verify_firebase_token") as verificar:
            self.assertEqual(self._con_token(token).get("/api/yo/").status_code, 200)
            verificar.assert_not_called()
