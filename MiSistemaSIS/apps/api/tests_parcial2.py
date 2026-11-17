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


class PestanasConsolidadosWebTests(BaseApi):
    """En la web de Django, los consolidados son pestañas de Reportes según el perfil."""

    def test_pestanas_segun_el_perfil(self):
        from django.test import Client
        from django.urls import reverse

        web = Client()
        web.force_login(self.admin.user)
        html = web.get(reverse("reportes:ventas")).content.decode()
        for clave in ("rentabilidad", "cajas", "personal"):
            self.assertIn(reverse("reportes:consolidado", args=[clave]), html)

        mozo = self._empleado("ceci", nivel=1, permisos=[("reportes", "leer")])
        web.force_login(mozo.user)
        html = web.get(reverse("reportes:ventas")).content.decode()
        self.assertIn(reverse("reportes:consolidado", args=["personal"]), html)
        self.assertNotIn(reverse("reportes:consolidado", args=["rentabilidad"]), html)

    def test_tarjeta_con_el_titulo_de_las_demas_pestanas(self):
        from django.test import Client
        from django.urls import reverse

        web = Client()
        web.force_login(self.admin.user)
        html = web.get(reverse("reportes:consolidado", args=["personal"])).content.decode()
        self.assertIn('<div class="titulo-top"><span class="material-symbols-outlined icono-naranja">badge</span>', html)


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
        # Varios tipos separados por coma, como los manda la web en React
        r = self.cliente.get("/api/notificaciones/", {"tipo": "VENTA_INUSUAL,CAJA_ABIERTA"})
        self.assertEqual(r.data["total"], 2)
        r = self.cliente.get("/api/notificaciones/", {"buscar": "13 horas"})
        self.assertEqual(r.data["total"], 1)

    def test_revisar_alertas_ahora_solo_admin(self):
        from datetime import timedelta
        from unittest.mock import patch

        from django.utils import timezone
        from ventas.models import Comanda, Mesa

        mesa = Mesa.objects.create(numero_mesa=70, ubicacion="salon")
        comanda = Comanda.objects.create(mesa=mesa, empleado=self.admin)
        Comanda.objects.filter(pk=comanda.pk).update(fecha_hora=timezone.now() - timedelta(minutes=90))
        Cargo = type(self.admin.cargo)
        Cargo.objects.get_or_create(nombre_cargo="Mozo", defaults={"nivel_acceso": 1})

        sin_permiso = self._cliente(self._empleado("dani", nivel=1, permisos=[("comandas", "leer")]))
        self.assertEqual(sin_permiso.post("/api/notificaciones/evaluar/").status_code, 403)

        with patch("notificaciones.reglas.enviar_por_correo", return_value=1) as correo:
            r = self.cliente.post("/api/notificaciones/evaluar/")
            self.assertEqual(r.status_code, 200, r.data)
            self.assertEqual(r.data["comandas_demoradas"], 1)
            self.assertEqual(correo.call_count, 1)
            # Una segunda revisión no repite la alerta ni el correo
            self.assertEqual(self.cliente.post("/api/notificaciones/evaluar/").data["comandas_demoradas"], 0)
            self.assertEqual(correo.call_count, 1)

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


class EstacionesTests(BaseApi):
    """Pantalla por estación: cada una ve lo suyo, lo marca listo y la comanda queda lista para llevar."""

    def setUp(self):
        super().setUp()
        from inventario.models import Bebida, CategoriaPlato, Plato, TipoBebida
        from ventas.models import Mesa

        self.plato = Plato.objects.create(nombre_plato="Locro", precio_plato=100, categoria=CategoriaPlato.objects.create(nombre_categoria_plato="Guisos"))
        self.bebida = Bebida.objects.create(nombre_bebida="Agua", precio_bebida=50, id_tipo_bebida=TipoBebida.objects.create(nombre_tipo_bebida="Sin alcohol"))
        mesa = Mesa.objects.create(numero_mesa=80, ubicacion="salon")
        items = [
            {"tipo": "plato", "id": self.plato.pk, "cantidad": 2, "observacion": "sin sal"},
            {"tipo": "bebida", "id": self.bebida.pk, "cantidad": 1},
        ]
        self.comanda = self.cliente.post("/api/comandas/", {"mesa": mesa.pk, "items": items}, format="json").data

    def test_cada_estacion_ve_lo_suyo_y_lo_marca_listo(self):
        cocina = self.cliente.get("/api/estaciones/cocina/").data
        self.assertEqual([p["id_comanda"] for p in cocina["pedidos"]], [self.comanda["id_comanda"]])
        self.assertEqual(cocina["pedidos"][0]["productos"], [{"nombre": "Locro", "cantidad": 2, "nota": "sin sal"}])
        bar = self.cliente.get("/api/estaciones/bar/").data
        self.assertEqual(bar["pedidos"][0]["productos"][0]["nombre"], "Agua")

        r = self.cliente.post(f"/api/estaciones/cocina/{self.comanda['id_comanda']}/listo/")
        self.assertEqual(r.data["listos"], 1)
        self.assertEqual(self.cliente.get("/api/estaciones/cocina/").data["pedidos"], [])
        detalle = self.cliente.get(f"/api/comandas/{self.comanda['id_comanda']}/").data
        self.assertEqual(detalle["estado_comanda"], "en_preparacion")
        self.assertFalse(detalle["listo_para_llevar"])

        self.cliente.post(f"/api/estaciones/bar/{self.comanda['id_comanda']}/listo/")
        self.assertTrue(self.cliente.get(f"/api/comandas/{self.comanda['id_comanda']}/").data["listo_para_llevar"])

    def test_editar_conserva_lo_ya_preparado(self):
        self.cliente.post(f"/api/estaciones/cocina/{self.comanda['id_comanda']}/listo/")
        items = [
            {"tipo": "plato", "id": self.plato.pk, "cantidad": 2, "observacion": "sin sal"},
            {"tipo": "bebida", "id": self.bebida.pk, "cantidad": 2},
        ]
        self.cliente.patch(f"/api/comandas/{self.comanda['id_comanda']}/", {"items": items}, format="json")
        self.assertEqual(self.cliente.get("/api/estaciones/cocina/").data["pedidos"], [])
        self.assertEqual(len(self.cliente.get("/api/estaciones/bar/").data["pedidos"]), 1)

    def test_estacion_inexistente_y_permiso(self):
        self.assertEqual(self.cliente.get("/api/estaciones/nada/").status_code, 404)
        solo_ver = self._cliente(self._empleado("eli", nivel=1, permisos=[("comandas", "leer")]))
        self.assertEqual(solo_ver.get("/api/estaciones/cocina/").status_code, 200)
        self.assertEqual(solo_ver.post(f"/api/estaciones/cocina/{self.comanda['id_comanda']}/listo/").status_code, 403)
