from datetime import datetime, timedelta, timezone as utc_tz
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from core.fechas import limitar_a_hoy, limitar_rango
from empleados.models import Asistencia, Cargo, Empleado, TipoAsistencia

NOCHE_EN_SALTA = datetime(2026, 11, 6, 1, 0, tzinfo=utc_tz.utc)


class LimitarAHoyTests(SimpleTestCase):
    def test_fecha_pasada_o_de_hoy_no_cambia(self):
        hoy = timezone.localdate()
        self.assertEqual(limitar_a_hoy("2020-01-15"), "2020-01-15")
        self.assertEqual(limitar_a_hoy(hoy.isoformat()), hoy.isoformat())

    def test_fecha_futura_pasa_a_hoy(self):
        hoy = timezone.localdate()
        self.assertEqual(limitar_a_hoy((hoy + timedelta(days=1)).isoformat()), hoy.isoformat())
        self.assertEqual(limitar_a_hoy("2999-12-31"), hoy.isoformat())

    def test_valor_invalido_se_ignora(self):
        for valor in ("abc", "2026-13-40", "06/11/2026"):
            self.assertEqual(limitar_a_hoy(valor), "")

    def test_vacio_no_cambia(self):
        self.assertEqual(limitar_a_hoy(""), "")
        self.assertIsNone(limitar_a_hoy(None))

    def test_usa_la_fecha_de_salta_y_no_la_utc(self):
        with patch("django.utils.timezone.now", return_value=NOCHE_EN_SALTA):
            self.assertEqual(limitar_a_hoy("2026-11-06"), "2026-11-05")


class LimitarRangoTests(SimpleTestCase):
    def test_rango_correcto_no_cambia(self):
        self.assertEqual(limitar_rango("2020-01-01", "2020-02-01"), ("2020-01-01", "2020-02-01"))
        self.assertEqual(limitar_rango("2020-01-01", "2020-01-01"), ("2020-01-01", "2020-01-01"))

    def test_rango_invertido_se_intercambia(self):
        self.assertEqual(limitar_rango("2020-02-01", "2020-01-01"), ("2020-01-01", "2020-02-01"))

    def test_fecha_futura_se_limita_antes_de_comparar(self):
        hoy = timezone.localdate().isoformat()
        self.assertEqual(limitar_rango("2999-01-01", "2020-01-01"), ("2020-01-01", hoy))
        self.assertEqual(limitar_rango("2999-01-01", "2999-12-31"), (hoy, hoy))

    def test_una_sola_fecha_o_ninguna(self):
        self.assertEqual(limitar_rango("2020-01-01", ""), ("2020-01-01", ""))
        self.assertEqual(limitar_rango("", "2020-01-01"), ("", "2020-01-01"))
        self.assertEqual(limitar_rango(None, None), (None, None))
        self.assertEqual(limitar_rango("abc", "2020-01-01"), ("", "2020-01-01"))


class FiltrosDeFechaEnPantallasTests(TestCase):
    PANTALLAS = (
        "auditoria:log_auditoria_listar",
        "ventas:comanda_listar",
        "ventas:comanda_consultar",
        "reportes:ventas",
        "empleados:listar_asistencias",
    )

    def setUp(self):
        self.user = User.objects.create_user("admin.prueba", password="Clave-Prueba-123")
        cargo = Cargo.objects.create(nombre_cargo="Admin Prueba", nivel_acceso=5)
        self.empleado = Empleado.objects.create(
            nombre_empleado="Ana", apellido_empleado="Prueba", dni="99000001",
            correo="ana@prueba.com", user=self.user, cargo=cargo,
        )
        self.tipo = TipoAsistencia.objects.create(nombre_tipo_asis="completo")
        self.client.force_login(self.user)

    def test_ninguna_pantalla_ofrece_fechas_futuras(self):
        maximo = f'max="{timezone.localdate().isoformat()}"'
        for nombre in self.PANTALLAS:
            with self.subTest(nombre):
                html = self.client.get(reverse(nombre)).content.decode()
                self.assertEqual(html.count('type="date"'), html.count(maximo), "cada campo debe tener límite")
                self.assertGreaterEqual(html.count(maximo), 2, "desde y hasta")

    def test_una_fecha_futura_en_la_direccion_se_limita_a_hoy(self):
        hoy = timezone.localdate().isoformat()
        for nombre in self.PANTALLAS:
            with self.subTest(nombre):
                html = self.client.get(
                    reverse(nombre), {"fecha_desde": "2999-01-01", "fecha_hasta": "2999-12-31"}
                ).content.decode()
                self.assertNotIn('value="2999', html)
                self.assertIn(f'value="{hoy}"', html)

    def test_una_fecha_invalida_no_rompe_ninguna_pantalla(self):
        for nombre in self.PANTALLAS:
            with self.subTest(nombre):
                respuesta = self.client.get(reverse(nombre), {"fecha_desde": "abc", "fecha_hasta": "2026-99-99"})
                self.assertEqual(respuesta.status_code, 200)

    def test_rango_invertido_en_la_direccion_se_corrige(self):
        for nombre in self.PANTALLAS:
            with self.subTest(nombre):
                html = self.client.get(
                    reverse(nombre), {"fecha_desde": "2020-02-01", "fecha_hasta": "2020-01-01"}
                ).content.decode()
                self.assertLess(html.index('value="2020-01-01"'), html.index('value="2020-02-01"'))

    def test_todas_las_pantallas_cargan_el_control_del_navegador(self):
        for nombre in self.PANTALLAS:
            with self.subTest(nombre):
                self.assertIn("js/filtros_fecha.js", self.client.get(reverse(nombre)).content.decode())

    def test_exportar_auditoria_limita_la_fecha(self):
        respuesta = self.client.get(reverse("auditoria:exportar_csv"), {"fecha_hasta": "abc"})
        self.assertEqual(respuesta.status_code, 200)

    def test_asistencia_se_registra_con_la_fecha_de_salta(self):
        with patch("django.utils.timezone.now", return_value=NOCHE_EN_SALTA):
            self.client.post(
                reverse("empleados:listar_asistencias"),
                {"empleado": self.empleado.pk, "tipo_asistencia": self.tipo.pk},
            )
        self.assertEqual(Asistencia.objects.get().fecha_asistencia.isoformat(), "2026-11-05")
