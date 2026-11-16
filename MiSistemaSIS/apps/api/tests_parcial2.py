"""Pruebas de la API del Parcial Nº 2 que usa la web en React.

M2: reportes consolidados (lista, datos, permisos y PDF).
M3: bandeja de notificaciones (filtros, contador y marcar como leídas).
"""
from notificaciones.models import Notificacion

from .tests_modulos import BaseApi


class ConsolidadosTests(BaseApi):
    def setUp(self):
        super().setUp()
        # Solo puede ver reportes: no ve el de cajas ni el de rentabilidad (sensible)
        self.mozo = self._empleado("beto", nivel=1, permisos=[("reportes", "leer")])
        self.cliente_mozo = self._cliente(self.mozo)

    def test_lista_segun_el_perfil(self):
        r = self.cliente.get("/api/reportes/consolidados/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual([x["clave"] for x in r.data], ["rentabilidad", "cajas", "personal"])
        self.assertTrue(next(x for x in r.data if x["clave"] == "rentabilidad")["restringido"])

        r = self.cliente_mozo.get("/api/reportes/consolidados/")
        self.assertEqual([x["clave"] for x in r.data], ["personal"])

    def test_datos_del_reporte_con_filtros(self):
        for clave in ("rentabilidad", "cajas", "personal"):
            with self.subTest(clave):
                r = self.cliente.get(
                    f"/api/reportes/consolidados/{clave}/",
                    {"fecha_desde": "2026-01-01", "fecha_hasta": "2026-01-31"},
                )
                self.assertEqual(r.status_code, 200, r.data)
                self.assertEqual(r.data["clave"], clave)
                self.assertEqual(r.data["filtros"]["fecha_desde"], "2026-01-01")
                # Cada fila y los totales tienen una celda por columna
                self.assertEqual(len(r.data["totales"]), len(r.data["columnas"]))
                for fila in r.data["filas"]:
                    self.assertEqual(len(fila), len(r.data["columnas"]))
                self.assertIn("opciones", r.data["filtro_extra"])

    def test_reporte_sensible_restringido_por_perfil(self):
        r = self.cliente_mozo.get("/api/reportes/consolidados/rentabilidad/")
        self.assertEqual(r.status_code, 403)
        self.assertIn("restringido", str(r.data["detail"]))
        r = self.cliente_mozo.get("/api/reportes/consolidados/rentabilidad/pdf/")
        self.assertEqual(r.status_code, 403)

    def test_reporte_inexistente(self):
        self.assertEqual(self.cliente.get("/api/reportes/consolidados/nada/").status_code, 404)

    def test_exporta_pdf(self):
        r = self.cliente.get("/api/reportes/consolidados/personal/pdf/", {"fecha_desde": "2026-01-01"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "application/pdf")
        self.assertTrue(r.content.startswith(b"%PDF"))


class NotificacionesTests(BaseApi):
    def setUp(self):
        super().setUp()
        cargo = self.admin.cargo
        self.nueva = Notificacion.objects.create(
            tipo="CAJA_ABIERTA", mensaje="La caja #1 lleva 13 horas abierta", destino_perfil=cargo, referencia="prueba:1"
        )
        Notificacion.objects.create(
            tipo="VENTA_INUSUAL", mensaje="Venta inusual", destino_perfil=cargo, leida=True, referencia="prueba:2"
        )
        # Dirigida a otro cargo: no la ve el administrador de la prueba
        self.otro = self._empleado("carla", nivel=1)
        self.ajena = Notificacion.objects.create(
            tipo="COMANDA_DEMORADA", mensaje="Comanda demorada", destino_perfil=self.otro.cargo, referencia="prueba:3"
        )

    def test_bandeja_solo_del_cargo_y_con_filtros(self):
        r = self.cliente.get("/api/notificaciones/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["total"], 2)
        self.assertEqual(r.data["sin_leer"], 1)
        self.assertEqual(len(r.data["tipos"]), 3)

        r = self.cliente.get("/api/notificaciones/", {"estado": "sin_leer"})
        self.assertEqual([n["id"] for n in r.data["resultados"]], [self.nueva.pk])
        r = self.cliente.get("/api/notificaciones/", {"tipo": "VENTA_INUSUAL"})
        self.assertEqual(r.data["total"], 1)
        r = self.cliente.get("/api/notificaciones/", {"buscar": "13 horas"})
        self.assertEqual(r.data["total"], 1)

    def test_contador_de_la_campana(self):
        r = self.cliente.get("/api/notificaciones/sin-leer/")
        self.assertEqual(r.data, {"sin_leer": 1})

    def test_marcar_leida(self):
        r = self.cliente.post(f"/api/notificaciones/{self.nueva.pk}/leida/")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["leida"])
        self.nueva.refresh_from_db()
        self.assertTrue(self.nueva.leida)
        self.assertIsNotNone(self.nueva.fecha_lectura)
        # La de otro cargo no se puede marcar
        self.assertEqual(self.cliente.post(f"/api/notificaciones/{self.ajena.pk}/leida/").status_code, 404)

    def test_marcar_todas(self):
        r = self.cliente.post("/api/notificaciones/marcar-todas/")
        self.assertEqual(r.data, {"cantidad": 1})
        self.ajena.refresh_from_db()
        self.assertFalse(self.ajena.leida)
        self.assertEqual(self.cliente.get("/api/notificaciones/sin-leer/").data, {"sin_leer": 0})

    def test_sin_sesion_no_responde(self):
        from rest_framework.test import APIClient

        self.assertEqual(APIClient().get("/api/notificaciones/sin-leer/").status_code, 401)
