"""Pruebas de los módulos de la API que usa la web en React.

Igual que tests.py, se ejecutan con ajustes que usan SQLite y omiten las migraciones.
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from auditoria.models import LogAuditoria
from empleados.models import Asistencia, Cargo, Empleado, PermisoXCargo, TipoAsistencia, TipoPermiso
from finanzas.models import Venta, caja, categoria_gasto, gasto, metodo_pago
from inventario.models import Bebida, CategoriaPlato, DetallePlato, Ingrediente, Plato, TipoBebida
from ventas.models import Comanda, DetalleComanda, Mesa, Pago

CONTRASENA = "Clave-de-prueba-123"


class BaseApi(TestCase):
    def setUp(self):
        cache.clear()
        self.admin = self._empleado("ana", nivel=99)
        self.cliente = self._cliente(self.admin)

    def _empleado(self, nombre, nivel=1, permisos=()):
        user = User.objects.create_user(f"{nombre}.prueba", password=CONTRASENA)
        cargo = Cargo.objects.create(nombre_cargo=f"Cargo {nombre}", nivel_acceso=nivel)
        for modulo, accion in permisos:
            tipo, _ = TipoPermiso.objects.get_or_create(modulo=modulo, accion=accion)
            PermisoXCargo.objects.create(cargo=cargo, tipo_permiso=tipo)
        return Empleado.objects.create(
            nombre_empleado=nombre, apellido_empleado="Prueba", dni=str(90000000 + User.objects.count()),
            correo=f"{nombre}@prueba.com", user=user, cargo=cargo,
        )

    def _cliente(self, empleado):
        cliente = APIClient()
        cliente.force_authenticate(empleado.user)
        return cliente


class CatalogosTests(BaseApi):
    def test_categoria_plato_alta_repetida_y_estado(self):
        r = self.cliente.post("/api/categorias-plato/", {"nombre_categoria_plato": "postres"}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["nombre_categoria_plato"], "Postres")
        r = self.cliente.post("/api/categorias-plato/", {"nombre_categoria_plato": "POSTRES"}, format="json")
        self.assertEqual(r.status_code, 400)
        pk = CategoriaPlato.objects.get().pk
        r = self.cliente.post(f"/api/categorias-plato/{pk}/estado/")
        self.assertFalse(r.data["estado_categoria_plato"])
        self.assertTrue(LogAuditoria.objects.filter(tabla="Categoria plato").exists())

    def test_no_elimina_categoria_con_platos(self):
        categoria = CategoriaPlato.objects.create(nombre_categoria_plato="Entradas")
        Plato.objects.create(nombre_plato="Locro", precio_plato=10, categoria=categoria)
        self.assertEqual(self.cliente.delete(f"/api/categorias-plato/{categoria.pk}/").status_code, 400)
        self.assertTrue(Plato.objects.exists())

    def test_tipo_bebida_lista_conserva_campos_de_la_app(self):
        TipoBebida.objects.create(nombre_tipo_bebida="Gaseosa")
        fila = self.cliente.get("/api/tipos-bebida/").data[0]
        for campo in ("id_tipo_bebida", "nombre_tipo_bebida", "estado_tipo_bebida"):
            self.assertIn(campo, fila)

    def test_sin_permiso_no_crea(self):
        mozo = self._cliente(self._empleado("mozo", permisos=[("categorias", "leer")]))
        self.assertEqual(mozo.get("/api/categorias-plato/").status_code, 200)
        r = mozo.post("/api/categorias-plato/", {"nombre_categoria_plato": "X"}, format="json")
        self.assertEqual(r.status_code, 403)


class MesasYComandasTests(BaseApi):
    def setUp(self):
        super().setUp()
        categoria = CategoriaPlato.objects.create(nombre_categoria_plato="Parrilla")
        self.plato = Plato.objects.create(nombre_plato="Vacio", precio_plato=100, categoria=categoria)

    def test_alta_mesa_numero_repetido_y_edicion(self):
        r = self.cliente.post("/api/mesas/", {"numero_mesa": 3, "ubicacion": "salon"}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertTrue(r.data["estado_mesa"])
        r = self.cliente.post("/api/mesas/", {"numero_mesa": 3, "ubicacion": "patio"}, format="json")
        self.assertEqual(r.status_code, 400)
        pk = Mesa.objects.get().pk
        r = self.cliente.patch(f"/api/mesas/{pk}/", {"ubicacion": "patio", "estado_mesa": False}, format="json")
        self.assertEqual(r.data["ubicacion"], "patio")
        self.assertTrue(r.data["estado_mesa"], "El estado no se cambia por PATCH")

    def test_no_elimina_mesa_con_comandas(self):
        mesa = Mesa.objects.create(numero_mesa=1, ubicacion="salon")
        Comanda.objects.create(mesa=mesa, empleado=self.admin)
        self.assertEqual(self.cliente.delete(f"/api/mesas/{mesa.pk}/").status_code, 400)

    def _comanda(self):
        mesa = Mesa.objects.create(numero_mesa=Mesa.objects.count() + 1, ubicacion="salon")
        r = self.cliente.post(
            "/api/comandas/", {"mesa": mesa.pk, "items": [{"tipo": "plato", "id": self.plato.pk, "cantidad": 2}]},
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.data)
        return r.data

    def test_detalle_trae_categoria_y_eliminar_libera_mesa(self):
        comanda = self._comanda()
        self.assertEqual(comanda["items"][0]["categoria"], "Parrilla")
        self.assertEqual(self.cliente.delete(f"/api/comandas/{comanda['id_comanda']}/").status_code, 204)
        self.assertTrue(Mesa.objects.get(pk=comanda["mesa"]).estado_mesa)

    def _desactivado_hace(self, producto, dias):
        """Marca el producto como no disponible hace `dias` días (en MySQL lo haría el trigger)."""
        campo = {"Plato": "estado_plato", "Bebida": "disponible_bebida", "Ingrediente": "estado_ingrediente"}[type(producto).__name__]
        type(producto).objects.filter(pk=producto.pk).update(
            **{campo: False, "fecha_desactivacion": timezone.now() - timedelta(days=dias)}
        )

    def test_no_elimina_un_plato_disponible(self):
        r = self.cliente.delete(f"/api/platos/{self.plato.pk}/")
        self.assertEqual(r.status_code, 400)
        self.assertIn("primero marcalo como no disponible", r.data["detail"])
        self.assertTrue(Plato.objects.filter(pk=self.plato.pk).exists())

    def test_no_elimina_antes_de_los_dos_meses_y_avisa_la_fecha(self):
        self._desactivado_hace(self.plato, 30)
        r = self.cliente.delete(f"/api/platos/{self.plato.pk}/")
        self.assertEqual(r.status_code, 400)
        self.assertIn("Se podrá eliminar a partir del", r.data["detail"])
        # La web usa esta fecha para avisar sin tener que preguntarle al servidor
        self.assertIsNotNone(self.cliente.get(f"/api/platos/{self.plato.pk}/").data["eliminable_desde"])

    def test_elimina_a_los_dos_meses_y_la_comanda_conserva_el_plato(self):
        comanda = self._comanda()
        self._desactivado_hace(self.plato, 61)
        self.assertEqual(self.cliente.delete(f"/api/platos/{self.plato.pk}/").status_code, 204)
        self.assertFalse(Plato.objects.filter(pk=self.plato.pk).exists())
        self.assertTrue(LogAuditoria.objects.filter(tabla="Plato", accion="ELIMINAR").exists())
        # La comanda vieja sigue mostrando qué se vendió y a qué precio
        item = self.cliente.get(f"/api/comandas/{comanda['id_comanda']}/").data["items"][0]
        self.assertEqual((item["nombre"], item["precio"], item["categoria"], item["id"]), ("Vacio", "100.00", "Parrilla", None))
        self.assertEqual(Comanda.objects.get(pk=comanda["id_comanda"]).detalles.get().subtotal, 200)

    def test_elimina_bebida_a_los_dos_meses(self):
        tipo = TipoBebida.objects.create(nombre_tipo_bebida="Gaseosa")
        bebida = Bebida.objects.create(nombre_bebida="Cola", precio_bebida=10, id_tipo_bebida=tipo)
        self.assertEqual(self.cliente.delete(f"/api/bebidas/{bebida.pk}/").status_code, 400)
        self._desactivado_hace(bebida, 60)
        self.assertEqual(self.cliente.delete(f"/api/bebidas/{bebida.pk}/").status_code, 204)

    def test_ingrediente_viejo_no_se_borra_si_un_plato_disponible_lo_usa(self):
        usado = Ingrediente.objects.create(nombre_ingrediente="Sal", unidad_medida="kg")
        DetallePlato.objects.create(plato=self.plato, ingrediente=usado)
        self._desactivado_hace(usado, 90)
        r = self.cliente.delete(f"/api/ingredientes/{usado.pk}/")
        self.assertEqual(r.status_code, 400)
        self.assertIn("plato(s) disponible(s)", r.data["detail"])
        # Con el plato desactivado sí se elimina, y se quita de su receta
        Plato.objects.filter(pk=self.plato.pk).update(estado_plato=False)
        self.assertEqual(self.cliente.delete(f"/api/ingredientes/{usado.pk}/").status_code, 204)
        self.assertFalse(DetallePlato.objects.filter(plato=self.plato).exists())

    def test_la_fecha_de_desactivacion_se_anota_y_se_borra_al_reactivar(self):
        self.cliente.post(f"/api/platos/{self.plato.pk}/estado/")
        self.plato.refresh_from_db()
        self.assertIsNotNone(self.plato.fecha_desactivacion)
        self.cliente.post(f"/api/platos/{self.plato.pk}/estado/")
        self.plato.refresh_from_db()
        self.assertIsNone(self.plato.fecha_desactivacion)

    def test_eliminar_pide_permiso_de_eliminar(self):
        mozo = self._cliente(self._empleado("mozo", permisos=[("platos", "leer"), ("platos", "modificar")]))
        self.assertEqual(mozo.delete(f"/api/platos/{self.plato.pk}/").status_code, 403)

    def test_consulta_filtra_por_varias_mesas(self):
        primera, segunda, tercera = self._comanda(), self._comanda(), self._comanda()
        r = self.cliente.get("/api/comandas/consulta/", {"mesa": f"{primera['mesa']},{segunda['mesa']}"})
        ids = {c["id_comanda"] for c in r.data["resultados"]}
        self.assertEqual(ids, {primera["id_comanda"], segunda["id_comanda"]})
        self.assertNotIn(tercera["id_comanda"], ids)

    def test_no_elimina_comanda_con_pagos(self):
        comanda = self._comanda()
        Pago.objects.create(comanda_id=comanda["id_comanda"], monto=10, metodo_pago="efectivo")
        self.assertEqual(self.cliente.delete(f"/api/comandas/{comanda['id_comanda']}/").status_code, 400)

    def test_consulta_paginada_con_filtros(self):
        self._comanda()
        segunda = self._comanda()
        r = self.cliente.get("/api/comandas/consulta/", {"mesa": segunda["mesa"], "estado": "pendiente"})
        self.assertEqual(r.data["total"], 1)
        self.assertEqual(r.data["resultados"][0]["id_comanda"], segunda["id_comanda"])
        r = self.cliente.get("/api/comandas/consulta/", {"estado": "pagado"})
        self.assertEqual(r.data["total"], 0)


class FinanzasTests(BaseApi):
    def test_flujo_de_caja_con_gasto_arqueo_y_cierre(self):
        r = self.cliente.post("/api/cajas/", {"saldo_inicial": "1000"}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        id_caja = r.data["id_caja"]
        self.assertEqual(self.cliente.post("/api/cajas/", {"saldo_inicial": "5"}, format="json").status_code, 400)

        categoria = categoria_gasto.objects.create(nombre_categoria_gasto="Limpieza")
        r = self.cliente.post(
            "/api/gastos/", {"descripcion_gasto": "Lavandina", "monto_gasto": "150,50", "cat_gasto": categoria.pk},
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(Decimal(r.data["monto_gasto"]), Decimal("150.50"))

        detalle = self.cliente.get(f"/api/cajas/{id_caja}/").data
        self.assertEqual(Decimal(detalle["saldo_esperado_actual"]), Decimal("849.50"))

        r = self.cliente.post(f"/api/cajas/{id_caja}/arqueo/", {"saldo_contado": "840"}, format="json")
        self.assertEqual(Decimal(r.data["diferencia_caja"]), Decimal("-9.50"))

        r = self.cliente.post(f"/api/cajas/{id_caja}/cierre/", {}, format="json")
        self.assertEqual(r.data["estado_caja"], "cerrado")
        # Con la caja cerrada, el gasto ya no se puede tocar
        id_gasto = gasto.objects.get().pk
        self.assertEqual(self.cliente.delete(f"/api/gastos/{id_gasto}/").status_code, 400)
        # La categoría ya tiene gastos: no se edita ni elimina
        self.assertEqual(self.cliente.delete(f"/api/categorias-gasto/{categoria.pk}/").status_code, 400)

    def test_gasto_sin_caja_abierta_y_montos_invalidos(self):
        categoria = categoria_gasto.objects.create(nombre_categoria_gasto="Varios")
        datos = {"descripcion_gasto": "X", "monto_gasto": "10", "cat_gasto": categoria.pk}
        self.assertEqual(self.cliente.post("/api/gastos/", datos, format="json").status_code, 400)
        self.cliente.post("/api/cajas/", {"saldo_inicial": "0"}, format="json")
        for monto in ("0", "-5", "abc", "1.234", "NaN"):
            r = self.cliente.post("/api/gastos/", {**datos, "monto_gasto": monto}, format="json")
            self.assertEqual(r.status_code, 400, monto)

    def test_venta_cobra_comanda_entregada(self):
        self.cliente.post("/api/cajas/", {"saldo_inicial": "0"}, format="json")
        metodo = metodo_pago.objects.create(nombre_metodo_pago="Efectivo")
        mesa = Mesa.objects.create(numero_mesa=1, ubicacion="salon", estado_mesa=False)
        comanda = Comanda.objects.create(mesa=mesa, empleado=self.admin, estado_comanda="entregado", total_comanda=500)

        pendientes = self.cliente.get("/api/ventas/").data["comandas_pendientes"]
        self.assertEqual([c["id_comanda"] for c in pendientes], [comanda.pk])

        datos = {"comanda": comanda.pk, "metodo_pago": metodo.pk, "monto_recibido": "400"}
        self.assertEqual(self.cliente.post("/api/ventas/", datos, format="json").status_code, 400)
        r = self.cliente.post("/api/ventas/", {**datos, "monto_recibido": "600"}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(Decimal(r.data["vuelto"]), Decimal("100"))
        comanda.refresh_from_db()
        self.assertEqual(comanda.estado_comanda, "pagado")
        self.assertTrue(Mesa.objects.get(pk=mesa.pk).estado_mesa)
        self.assertEqual(self.cliente.post("/api/ventas/", {**datos, "monto_recibido": "600"}, format="json").status_code, 400)
        self.assertEqual(Venta.objects.count(), 1)

    def test_ventas_piden_su_propio_permiso(self):
        cajero = self._cliente(self._empleado("cajero", permisos=[("caja", "leer")]))
        self.assertEqual(cajero.get("/api/cajas/").status_code, 200)
        self.assertEqual(cajero.get("/api/ventas/").status_code, 403)


class ReportesYAuditoriaTests(BaseApi):
    def test_reporte_resume_las_comandas_pagadas(self):
        categoria = CategoriaPlato.objects.create(nombre_categoria_plato="Entradas")
        plato = Plato.objects.create(nombre_plato="Locro", precio_plato=100, categoria=categoria)
        mesa = Mesa.objects.create(numero_mesa=1, ubicacion="salon")
        for estado in ("pagado", "pagado", "pendiente"):
            comanda = Comanda.objects.create(mesa=mesa, empleado=self.admin, estado_comanda=estado, total_comanda=200)
            DetalleComanda.objects.create(comanda=comanda, plato=plato, cant_plato=2, cant_bebida=0)
        r = self.cliente.get("/api/reportes/")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["cantidad_comandas"], 2)
        self.assertEqual(Decimal(r.data["ventas_totales"]), Decimal("400"))
        self.assertEqual(r.data["top_platos"], [{"nombre": "Locro", "cantidad": 4}])
        self.assertEqual(len(r.data["comandas"]), 2)

    def test_auditoria_filtra_y_exporta(self):
        LogAuditoria.objects.create(tabla="Mesa", accion="CREAR", registro_id=1, valores_actuales="mesa uno")
        LogAuditoria.objects.create(tabla="Plato", accion="MODIFICAR", registro_id=2, valores_actuales="locro")
        r = self.cliente.get("/api/auditoria/", {"tabla": "Mesa"})
        self.assertEqual(r.data["total"], 1)
        self.assertIn("Plato", r.data["tablas"])
        r = self.cliente.get("/api/auditoria/", {"detalle": "locro", "exportar": "1"})
        self.assertEqual(len(r.data["resultados"]), 1)

    def test_auditoria_requiere_permiso(self):
        mozo = self._cliente(self._empleado("mozo"))
        self.assertEqual(mozo.get("/api/auditoria/").status_code, 403)
        self.assertEqual(mozo.get("/api/reportes/").status_code, 403)


class CuentaYAsistenciasTests(BaseApi):
    def test_perfil_edita_solo_correo_y_telefono(self):
        r = self.cliente.patch("/api/perfil/", {"correo": "nuevo@prueba.com", "telefono": "387 1234567", "dni": "1"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.correo, "nuevo@prueba.com")
        self.assertNotEqual(self.admin.dni, "1")
        r = self.cliente.patch("/api/perfil/", {"telefono": "letras"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_cambiar_contrasena_exige_la_actual_y_una_segura(self):
        r = self.cliente.post("/api/perfil/contrasena/", {"actual": "mal", "nueva": "Nueva-Clave-789", "confirmar": "Nueva-Clave-789"}, format="json")
        self.assertEqual(r.status_code, 400)
        r = self.cliente.post("/api/perfil/contrasena/", {"actual": CONTRASENA, "nueva": "simpleclave", "confirmar": "simpleclave"}, format="json")
        self.assertEqual(r.status_code, 400)
        r = self.cliente.post("/api/perfil/contrasena/", {"actual": CONTRASENA, "nueva": "Nueva-Clave-789", "confirmar": "Nueva-Clave-789"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.admin.user.refresh_from_db()
        self.assertTrue(self.admin.user.check_password("Nueva-Clave-789"))

    def test_cambio_obligatorio_y_luego_login(self):
        Empleado.objects.filter(pk=self.admin.pk).update(debe_cambiar_contrasena=True)
        anonimo = APIClient()
        datos = {"username": "ana@prueba.com", "password": CONTRASENA, "nueva": "Nueva-Clave-789", "confirmar": "Nueva-Clave-789"}
        self.assertEqual(anonimo.post("/api/token/cambiar-clave/", {**datos, "password": "mal"}, format="json").status_code, 400)
        r = anonimo.post("/api/token/cambiar-clave/", datos, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        r = anonimo.post("/api/token/", {"username": "ana.prueba", "password": "Nueva-Clave-789"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)

    def test_asistencia_una_por_dia_y_turnos(self):
        r = self.cliente.post("/api/tipos-asistencia/", {"nombre_tipo_asis": "completo"}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        tipo = r.data["id_tipo_asistencia"]
        self.assertEqual(self.cliente.post("/api/tipos-asistencia/", {"nombre_tipo_asis": "completo"}, format="json").status_code, 400)
        datos = {"empleado": self.admin.pk, "tipo": tipo}
        self.assertEqual(self.cliente.post("/api/asistencias/", datos, format="json").status_code, 201)
        self.assertEqual(self.cliente.post("/api/asistencias/", datos, format="json").status_code, 400)
        self.assertEqual(self.cliente.delete(f"/api/tipos-asistencia/{tipo}/").status_code, 400)
        r = self.cliente.get("/api/asistencias/")
        self.assertEqual(r.data["total"], 1)
        self.assertEqual(self.cliente.delete(f"/api/asistencias/{Asistencia.objects.get().pk}/").status_code, 204)
        self.assertTrue(TipoAsistencia.objects.exists())
