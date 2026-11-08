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
            "cocina": [{"nombre": "Locro", "cantidad": 2}],
            "bar": [{"nombre": self.gaseosa.nombre_bebida, "cantidad": 3}],
            "parrilla": [{"nombre": "Vacío de Ternera", "cantidad": 1}],
        })
        self.assertContains(respuesta, "Sin cebolla", count=3)
        self.assertContains(respuesta, "Ana Prueba", count=3)
        self.assertContains(respuesta, f"{comanda.pk:06d}", count=3)
        self.assertContains(respuesta, "Mesa:</strong> 06", count=3)
        self.assertContains(respuesta, "Imprimir los 3 tickets")
        self.assertNotContains(respuesta, "NO PREPARAR")

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
            self.assertContains(self.ver(comanda), "NO PREPARAR")

    def test_los_textos_cargados_se_escapan(self):
        comanda = self.comanda(observaciones_comanda="<script>alert(1)</script>")
        DetalleComanda.objects.create(comanda=comanda, plato=self.locro, cant_plato=1)

        self.assertNotContains(self.ver(comanda), "<script>alert(1)")
