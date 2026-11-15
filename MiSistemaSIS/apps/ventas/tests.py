from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from empleados.models import Cargo, Empleado
from inventario.models import Bebida, CategoriaPlato, Plato, TipoBebida

from .models import Comanda, DetalleComanda, Mesa


class TicketsDeComandaTests(TestCase):
    def setUp(self):
        usuario = User.objects.create_user("ana.prueba", password="Clave-Prueba-123")
        cargo = Cargo.objects.create(nombre_cargo="Administrador Prueba", nivel_acceso=99)
        self.empleado = Empleado.objects.create(
            nombre_empleado="Ana", apellido_empleado="Prueba", dni="99000001",
            correo="ana@prueba.com", user=usuario, cargo=cargo,
        )
        self.client.force_login(usuario)
        self.mesa = Mesa.objects.create(numero_mesa=6)
        self.locro = self.plato("Locro", "Entradas")
        self.vacio = self.plato("Vacío de Ternera", "Parrilla")
        tipo = TipoBebida.objects.create(nombre_tipo_bebida="Gaseosa")
        self.gaseosa = Bebida.objects.create(nombre_bebida="Gaseosa 500 ml", id_tipo_bebida=tipo, precio_bebida=100)

    def plato(self, nombre, categoria):
        categoria, _ = CategoriaPlato.objects.get_or_create(nombre_categoria_plato=categoria)
        return Plato.objects.create(nombre_plato=nombre, precio_plato=100, categoria=categoria)

    def comanda(self, **datos):
        return Comanda.objects.create(mesa=self.mesa, empleado=self.empleado, **datos)

    def ver(self, comanda):
        respuesta = self.client.get(reverse("ventas:comanda_ticket", args=[comanda.pk]))
        self.assertEqual(respuesta.status_code, 200)
        return respuesta

    def test_reparte_cada_producto_en_su_ticket(self):
        comanda = self.comanda(observaciones_comanda="Sin cebolla")
        DetalleComanda.objects.create(comanda=comanda, plato=self.locro, cant_plato=2)
        DetalleComanda.objects.create(comanda=comanda, plato=self.vacio, cant_plato=1)
        DetalleComanda.objects.create(comanda=comanda, bebida=self.gaseosa, cant_bebida=3)

        respuesta = self.ver(comanda)

        tickets = {t["clave"]: t["productos"] for t in respuesta.context["tickets"]}
        self.assertEqual(tickets, {
            "cocina": [{"nombre": "Locro", "cantidad": 2, "nota": ""}],
            "bar": [{"nombre": self.gaseosa.nombre_bebida, "cantidad": 3, "nota": ""}],
            "parrilla": [{"nombre": "Vacío de Ternera", "cantidad": 1, "nota": ""}],
        })
        self.assertContains(respuesta, "Sin cebolla", count=3)
        self.assertContains(respuesta, "Ana Prueba", count=3)
        self.assertContains(respuesta, f"{comanda.pk:06d}", count=3)
        self.assertContains(respuesta, '<dd class="ticket-mesa">06</dd>', count=3)
        self.assertContains(respuesta, "Imprimir los 3 tickets")
        self.assertNotContains(respuesta, "no preparar")

    def test_un_detalle_con_plato_y_bebida_va_a_los_dos_tickets(self):
        comanda = self.comanda()
        DetalleComanda.objects.create(comanda=comanda, plato=self.vacio, cant_plato=1, bebida=self.gaseosa, cant_bebida=2)

        claves = [t["clave"] for t in self.ver(comanda).context["tickets"]]

        self.assertEqual(claves, ["bar", "parrilla"])

    def test_solo_aparecen_los_tickets_con_productos(self):
        comanda = self.comanda()
        DetalleComanda.objects.create(comanda=comanda, bebida=self.gaseosa, cant_bebida=1)

        respuesta = self.ver(comanda)

        self.assertEqual([t["clave"] for t in respuesta.context["tickets"]], ["bar"])
        self.assertNotContains(respuesta, "Imprimir los")

    def test_comanda_sin_productos_lo_avisa(self):
        self.assertContains(self.ver(self.comanda()), "no tiene productos")

    def test_comanda_anulada_avisa_que_no_se_prepare(self):
        for estado in ("anulado", "cancelado"):
            comanda = self.comanda(estado_comanda=estado)
            DetalleComanda.objects.create(comanda=comanda, plato=self.locro, cant_plato=1)
            self.assertContains(self.ver(comanda), "Comanda anulada: no preparar")

    def test_los_textos_cargados_se_escapan(self):
        comanda = self.comanda(observaciones_comanda="<script>alert(1)</script>")
        DetalleComanda.objects.create(comanda=comanda, plato=self.locro, cant_plato=1)

        self.assertNotContains(self.ver(comanda), "<script>alert(1)")


class TomarPedidoTests(TestCase):
    """Nueva comanda: la mesa se elige en el plano y el mozo con un botón."""

    def setUp(self):
        admin = Cargo.objects.create(nombre_cargo="Administrador Prueba", nivel_acceso=99)
        self.usuario = User.objects.create_user("ana.prueba", password="Clave-Prueba-123")
        self.cajera = Empleado.objects.create(
            nombre_empleado="Ana", apellido_empleado="Prueba", dni="99000001",
            correo="ana@prueba.com", user=self.usuario, cargo=admin,
        )
        otro = User.objects.create_user("teo.prueba", password="Clave-Prueba-123")
        self.mozo = Empleado.objects.create(
            nombre_empleado="Teo", apellido_empleado="Mozo", dni="99000002",
            correo="teo@prueba.com", user=otro, cargo=admin,
        )
        self.client.force_login(self.usuario)
        self.mesa = Mesa.objects.create(numero_mesa=1, ubicacion="salon")
        categoria = CategoriaPlato.objects.create(nombre_categoria_plato="Entradas")
        self.locro = Plato.objects.create(nombre_plato="Locro", precio_plato=100, categoria=categoria)

    def datos(self, **extra):
        return {
            "mesa": self.mesa.pk,
            "observaciones_comanda": "",
            "detalles-TOTAL_FORMS": "1",
            "detalles-INITIAL_FORMS": "0",
            "detalles-MIN_NUM_FORMS": "0",
            "detalles-MAX_NUM_FORMS": "1000",
            "detalles-0-plato": self.locro.pk,
            "detalles-0-cant_plato": "2",
            "detalles-0-bebida": "",
            "detalles-0-cant_bebida": "1",
            **extra,
        }

    def test_la_pantalla_muestra_el_plano_y_los_mozos(self):
        respuesta = self.client.get(reverse("ventas:comanda_crear"), {"mesa": self.mesa.pk})
        self.assertContains(respuesta, 'data-mesa-numero="1"')
        self.assertContains(respuesta, "plano-mesa--elegida")
        self.assertContains(respuesta, 'name="mozo"', count=2)
        self.assertContains(respuesta, f'value="{self.cajera.pk}" checked')

    def test_guarda_la_comanda_con_el_mozo_elegido(self):
        self.client.post(reverse("ventas:comanda_crear"), self.datos(mozo=self.mozo.pk))
        comanda = Comanda.objects.get()
        self.assertEqual(comanda.empleado, self.mozo)
        self.mesa.refresh_from_db()
        self.assertFalse(self.mesa.estado_mesa)

    def test_sin_mozo_usa_el_usuario_actual(self):
        self.client.post(reverse("ventas:comanda_crear"), self.datos())
        self.assertEqual(Comanda.objects.get().empleado, self.cajera)

    def test_un_mozo_que_no_puede_tomar_pedidos_no_se_acepta(self):
        sin_permiso = Cargo.objects.create(nombre_cargo="Cocinero", nivel_acceso=1)
        cocinero = Empleado.objects.create(
            nombre_empleado="Rosa", apellido_empleado="Cocina", dni="99000003",
            correo="rosa@prueba.com", cargo=sin_permiso,
        )
        self.client.post(reverse("ventas:comanda_crear"), self.datos(mozo=cocinero.pk))
        self.assertEqual(Comanda.objects.get().empleado, self.cajera)

    def test_los_productos_mas_pedidos_aparecen_primero(self):
        categoria = self.locro.categoria
        empanada = Plato.objects.create(nombre_plato="Empanada", precio_plato=50, categoria=categoria)
        vieja = Comanda.objects.create(mesa=self.mesa, empleado=self.cajera)
        DetalleComanda.objects.create(comanda=vieja, plato=empanada, cant_plato=12)
        anulada = Comanda.objects.create(mesa=self.mesa, empleado=self.cajera, estado_comanda="anulado")
        DetalleComanda.objects.create(comanda=anulada, plato=self.locro, cant_plato=50)

        respuesta = self.client.get(reverse("ventas:comanda_crear"))

        platos = respuesta.context["platos"]
        # La anulada no cuenta: la empanada (12) va antes que el locro (0)
        self.assertEqual([p.nombre_plato for p in platos], ["Empanada", "Locro"])
        self.assertTrue(platos[0].destacado)
        self.assertFalse(platos[1].destacado)
        self.assertContains(respuesta, "Más pedido", count=1)

    def test_mesa_ocupada_a_mano_sin_pedido_recibe_la_comanda(self):
        # Clientes sentados: la mesa se marcó ocupada desde el listado, todavía sin comanda
        Mesa.objects.filter(pk=self.mesa.pk).update(estado_mesa=False)
        respuesta = self.client.get(reverse("ventas:comanda_crear"))
        self.assertContains(respuesta, "plano-mesa--sin-pedido")
        self.client.post(reverse("ventas:comanda_crear"), self.datos())
        self.assertEqual(Comanda.objects.filter(mesa=self.mesa).count(), 1)

    def test_si_la_mesa_ya_tiene_comanda_no_se_pierde_el_pedido(self):
        Comanda.objects.create(mesa=self.mesa, empleado=self.cajera)
        Mesa.objects.filter(pk=self.mesa.pk).update(estado_mesa=False)

        respuesta = self.client.post(reverse("ventas:comanda_crear"), self.datos())

        self.assertEqual(Comanda.objects.count(), 1)
        self.assertEqual(
            respuesta.context["carrito_inicial"],
            [{"tipo": "plato", "id": str(self.locro.pk), "cantidad": 2, "nota": ""}],
        )
        self.assertContains(respuesta, 'id="carrito-inicial"')

    def test_mesa_con_pedido_abre_agregar_productos(self):
        comanda = Comanda.objects.create(mesa=self.mesa, empleado=self.cajera)
        Mesa.objects.filter(pk=self.mesa.pk).update(estado_mesa=False)
        respuesta = self.client.get(reverse("ventas:comanda_crear"))
        self.assertContains(respuesta, f'{reverse("ventas:comanda_crear")}?comanda={comanda.pk}')
        self.assertContains(respuesta, "Agregar productos")

    def test_al_crear_abre_el_ticket_para_imprimir(self):
        respuesta = self.client.post(reverse("ventas:comanda_crear"), self.datos())
        comanda = Comanda.objects.get()
        ticket = f'{reverse("ventas:comanda_ticket", args=[comanda.pk])}?imprimir=1'
        self.assertRedirects(respuesta, ticket, fetch_redirect_response=False)
        pagina = self.client.get(ticket)
        self.assertContains(pagina, "window.print()")
        self.assertContains(pagina, f'{reverse("ventas:comanda_listar")}?resaltar={comanda.pk}')

    def test_el_listado_resalta_la_comanda_recien_guardada(self):
        comanda = Comanda.objects.create(mesa=self.mesa, empleado=self.cajera)
        respuesta = self.client.get(reverse("ventas:comanda_listar"), {"resaltar": comanda.pk})
        self.assertContains(respuesta, 'id="comanda-resaltada"')

    def _mesa_con_pedido(self):
        comanda = Comanda.objects.create(mesa=self.mesa, empleado=self.cajera, total_comanda=200)
        Mesa.objects.filter(pk=self.mesa.pk).update(estado_mesa=False)
        return comanda

    def test_sin_caja_abierta_el_panel_avisa_en_lugar_de_cobrar(self):
        comanda = self._mesa_con_pedido()
        respuesta = self.client.get(reverse("ventas:comanda_crear"))
        self.assertContains(respuesta, f'data-comanda="{comanda.pk}"')
        self.assertContains(respuesta, 'data-saldo="200.00"')
        self.assertContains(respuesta, "Para cobrar hay que abrir la caja.")
        self.assertNotContains(respuesta, 'id="modal-pago"')

    def test_cobrar_desde_el_plano_libera_la_mesa_y_vuelve_al_plano(self):
        from finanzas.models import caja, metodo_pago

        caja.objects.create(empleado_apertura=self.cajera)
        efectivo = metodo_pago.objects.create(nombre_metodo_pago="Efectivo", permite_cambio=True)
        comanda = self._mesa_con_pedido()

        plano = self.client.get(reverse("ventas:comanda_crear"))
        self.assertContains(plano, 'id="modal-pago"')
        self.assertContains(plano, "data-panel-cobrar")

        respuesta = self.client.post(reverse("ventas:comanda_cobrar"), {
            "comanda_id": comanda.pk,
            "tipo_pago": "total",
            "metodo_pago": efectivo.pk,
            "monto_recibido": "500",
            "next": reverse("ventas:comanda_crear"),
        })

        self.assertRedirects(respuesta, reverse("ventas:comanda_crear"), fetch_redirect_response=False)
        comanda.refresh_from_db()
        self.mesa.refresh_from_db()
        self.assertEqual(comanda.estado_comanda, "pagado")
        self.assertTrue(self.mesa.estado_mesa)

    def test_agregar_a_una_mesa_usa_la_misma_pantalla(self):
        comanda = self._mesa_con_pedido()
        DetalleComanda.objects.create(comanda=comanda, plato=self.locro, cant_plato=1)

        pantalla = self.client.get(reverse("ventas:comanda_crear"), {"comanda": comanda.pk})
        self.assertContains(pantalla, "Agregar a la mesa 1")
        self.assertContains(pantalla, "Ya pedido")
        self.assertContains(pantalla, f'name="comanda_id" value="{comanda.pk}"')
        self.assertNotContains(pantalla, 'name="mozo"')

        datos = self.datos(comanda_id=comanda.pk)
        respuesta = self.client.post(reverse("ventas:comanda_crear"), datos)

        nuevo = comanda.detalles.order_by("-pk").first()
        ticket = f'{reverse("ventas:comanda_ticket", args=[comanda.pk])}?imprimir=1&detalles={nuevo.pk}'
        self.assertRedirects(respuesta, ticket, fetch_redirect_response=False)
        # El ticket lleva solo lo agregado, marcado para la cocina
        pagina = self.client.get(ticket)
        self.assertEqual(pagina.context["tickets"][0]["productos"], [{"nombre": "Locro", "cantidad": 2, "nota": ""}])
        self.assertContains(pagina, "AGREGADO")
        self.assertEqual(Comanda.objects.count(), 1)
        comanda.refresh_from_db()
        # Lo que ya tenía (1 locro) sigue igual y se suma lo nuevo (2 locros): total 3 x 100
        self.assertEqual(comanda.detalles.count(), 2)
        self.assertEqual(comanda.total_comanda, 300)
        self.mesa.refresh_from_db()
        self.assertFalse(self.mesa.estado_mesa)

    def test_no_se_agrega_a_una_comanda_cerrada(self):
        comanda = Comanda.objects.create(mesa=self.mesa, empleado=self.cajera, estado_comanda="pagado")
        respuesta = self.client.post(reverse("ventas:comanda_crear"), self.datos(comanda_id=comanda.pk))
        self.assertRedirects(respuesta, reverse("ventas:comanda_crear"), fetch_redirect_response=False)
        self.assertEqual(comanda.detalles.count(), 0)

    def test_el_plano_marca_las_mesas_demoradas_y_las_del_mozo(self):
        from datetime import timedelta
        from django.utils import timezone

        comanda = self._mesa_con_pedido()
        Comanda.objects.filter(pk=comanda.pk).update(fecha_hora=timezone.now() - timedelta(minutes=45))

        respuesta = self.client.get(reverse("ventas:comanda_crear"))

        self.assertContains(respuesta, "plano-mesa--demorada")
        self.assertContains(respuesta, "45&#x27;</span>")
        # La comanda es del usuario actual: aparece en "Tus mesas"
        self.assertContains(respuesta, 'data-abre-mesa="1"')

    def test_la_nota_de_un_producto_llega_al_ticket(self):
        datos = self.datos()
        datos["detalles-0-observacion"] = "sin sal"
        self.client.post(reverse("ventas:comanda_crear"), datos)

        comanda = Comanda.objects.get()
        self.assertEqual(comanda.detalles.get().observacion, "sin sal")
        ticket = self.client.get(reverse("ventas:comanda_ticket", args=[comanda.pk]))
        self.assertContains(ticket, "sin sal")

    def test_cada_estacion_ve_lo_suyo_y_lo_marca_listo(self):
        tipo = TipoBebida.objects.create(nombre_tipo_bebida="Gaseosa")
        gaseosa = Bebida.objects.create(nombre_bebida="Cola", id_tipo_bebida=tipo, precio_bebida=50)
        comanda = self._mesa_con_pedido()
        DetalleComanda.objects.create(comanda=comanda, plato=self.locro, cant_plato=2, observacion="sin sal")
        DetalleComanda.objects.create(comanda=comanda, bebida=gaseosa, cant_bebida=1)

        cocina = self.client.get(reverse("ventas:estacion", args=["cocina"]))
        self.assertContains(cocina, "Locro")
        self.assertContains(cocina, "sin sal")
        self.assertNotContains(cocina, "Cola")
        self.assertContains(self.client.get(reverse("ventas:estacion", args=["bar"])), "Cola")
        self.assertEqual(self.client.get(reverse("ventas:estacion", args=["sotano"])).status_code, 404)

        self.client.post(reverse("ventas:estacion_listo", args=["cocina", comanda.pk]))
        comanda.refresh_from_db()
        self.assertEqual(comanda.estado_comanda, "en_preparacion")
        self.assertNotContains(self.client.get(reverse("ventas:estacion", args=["cocina"])), "Locro")
        # Falta el bar: la mesa todavía no está lista
        self.assertNotContains(self.client.get(reverse("ventas:comanda_crear")), "plano-mesa--lista")

        self.client.post(reverse("ventas:estacion_listo", args=["bar", comanda.pk]))
        plano = self.client.get(reverse("ventas:comanda_crear"))
        self.assertContains(plano, "plano-mesa--lista")
        self.assertContains(plano, 'data-listo="1"')
