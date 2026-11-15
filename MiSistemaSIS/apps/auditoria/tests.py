from django.contrib.auth.models import User
from django.test import TestCase

from empleados.models import Cargo, Empleado

from .models import LogAuditoria


class ExportarAuditoriaPdfTests(TestCase):
    def setUp(self):
        cargo = Cargo.objects.create(nombre_cargo="Administrador", nivel_acceso=5)
        user = User.objects.create_user("admin.prueba", password="Clave#2026")
        self.empleado = Empleado.objects.create(
            nombre_empleado="Ana", apellido_empleado="Perez", dni="30111222",
            correo="ana@example.com", cargo=cargo, user=user,
        )
        self.client.force_login(user)
        LogAuditoria.objects.create(tabla="Plato", accion="CREAR", registro_id=1,
                                    valores_actuales="Empanada", empleado=self.empleado)
        LogAuditoria.objects.create(tabla="Plato", accion="MODIFICAR", registro_id=1,
                                    valores_anteriores="Empanada", valores_actuales="Empanada salteña",
                                    empleado=self.empleado)

    def test_descarga_el_pdf_con_el_formato_de_los_reportes(self):
        respuesta = self.client.get("/auditoria/exportar/", {"accion": "MODIFICAR", "fecha_desde": "2026-11-01"})
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta["Content-Type"], "application/pdf")
        self.assertIn('filename="Auditoria_', respuesta["Content-Disposition"])
        self.assertTrue(respuesta.content.startswith(b"%PDF"))

    def test_texto_de_filtros_y_periodo(self):
        from .views import _describir_filtros, _periodo
        filtros = {"tabla": "", "accion": "MODIFICAR", "usuario": "", "fecha_desde": "2026-11-01",
                   "fecha_hasta": "", "detalle": ""}
        texto = _describir_filtros(filtros, "")
        self.assertIn("Acción: Modificar", texto)
        self.assertIn("Desde: 01/11/2026", texto)
        self.assertEqual(_periodo(filtros), "desde el 01/11/2026")
