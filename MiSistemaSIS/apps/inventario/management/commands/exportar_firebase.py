"""Copia los catálogos de MySQL a Firestore. MySQL no se modifica.

Solo muestra lo que copiaría, sin conectarse a Firebase:
    python manage.py exportar_firebase

Copia los datos:
    python manage.py exportar_firebase --ejecutar --clave "C:\\ruta\\clave.json"

Copia lo que faltaba (comandas, cargos, permisos y empleados), sin tocar lo ya copiado:
    python manage.py exportar_firebase --restantes --ejecutar --clave "C:\\ruta\\clave.json"

Si Firestore ya tiene datos, el comando se detiene para no pisarlos.
Para reemplazarlos a propósito, agregar --sobrescribir.
"""
import json
from datetime import datetime

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from auditoria.models import LogAuditoria
from empleados.decorators import nivel_de, tiene_permiso
from empleados.models import Cargo, Empleado, TipoPermiso
from inventario.models import Bebida, CategoriaPlato, Ingrediente, Plato, TipoBebida
from ventas.models import Comanda, Mesa

# Estados en los que una comanda sigue abierta
ESTADOS_ABIERTOS = ["pendiente", "en_preparacion", "entregado"]

# Tienen datos personales o sueldos: no se muestran como ejemplo en la terminal
SIN_EJEMPLO = {"usuarios", "empleados", "comandas", "cargos", "sueldos", "auditoria"}

# Firestore acepta como máximo 500 escrituras por lote
TAMANIO_DE_LOTE = 500

# En Firestore los ids son textos, también los de los documentos nuevos.
# Por eso todos los ids y las referencias a otros documentos se guardan como texto.


def _categoria(categoria):
    return {
        "id_categoria_plato": str(categoria.pk),
        "nombre_categoria_plato": categoria.nombre_categoria_plato,
        "descripcion_categoria_plato": categoria.descripcion_categoria_plato,
        "estado_categoria_plato": categoria.estado_categoria_plato,
    }


def _ingrediente(ingrediente):
    return {
        "id_ingrediente": str(ingrediente.pk),
        "nombre_ingrediente": ingrediente.nombre_ingrediente,
        "unidad_medida": ingrediente.unidad_medida,
        "unidad_nombre": ingrediente.get_unidad_medida_display(),
        "costo_unitario": float(ingrediente.costo_unitario),
        "descripcion_ingrediente": ingrediente.descripcion_ingrediente,
        # Solo la ruta en Django: el archivo de la foto no se copia
        "imagen_ingrediente": ingrediente.imagen_ingrediente.name or None,
        "estado_ingrediente": ingrediente.estado_ingrediente,
    }


def _plato(plato):
    detalles = list(plato.detalleplato_set.all())
    return {
        "id_plato": str(plato.pk),
        "nombre_plato": plato.nombre_plato,
        "precio_plato": float(plato.precio_plato),
        "categoria": str(plato.categoria_id),
        "categoria_nombre": plato.categoria.nombre_categoria_plato,
        "descripcion_plato": plato.descripcion_plato,
        "estado_plato": plato.estado_plato,
        # Firestore no busca dentro de una lista de objetos: esta lista permite
        # encontrar los platos que usan un ingrediente
        "ingredientes_ids": [str(detalle.ingrediente_id) for detalle in detalles],
        # Firestore no tiene tablas intermedias: los ingredientes van dentro del plato
        "ingredientes": [
            {
                "id_ingrediente": str(detalle.ingrediente_id),
                "nombre_ingrediente": detalle.ingrediente.nombre_ingrediente,
                "estado_ingrediente": detalle.ingrediente.estado_ingrediente,
                "unidad_medida": detalle.ingrediente.unidad_medida,
                "cantidad": detalle.cantidad,
            }
            for detalle in detalles
        ],
    }


def _tipo_bebida(tipo):
    return {
        "id_tipo_bebida": str(tipo.pk),
        "nombre_tipo_bebida": tipo.nombre_tipo_bebida,
        "descripcion_tipo_bebida": tipo.descripcion_tipo_bebida,
        "estado_tipo_bebida": tipo.estado_tipo_bebida,
    }


def _bebida(bebida):
    return {
        "id_bebida": str(bebida.pk),
        "nombre_bebida": bebida.nombre_bebida,
        "precio_bebida": float(bebida.precio_bebida),
        "id_tipo_bebida": str(bebida.id_tipo_bebida_id),
        "tipo_nombre": bebida.id_tipo_bebida.nombre_tipo_bebida,
        "descripcion_bebida": bebida.descripcion_bebida,
        "disponible_bebida": bebida.disponible_bebida,
    }


def _mesa(mesa):
    return {
        "id_mesa": str(mesa.pk),
        "numero_mesa": mesa.numero_mesa,
        "ubicacion": mesa.ubicacion,
        "ubicacion_nombre": mesa.get_ubicacion_display(),
        # Las comandas no se copian: una mesa ocupada quedaría sin su comanda
        "estado_mesa": True,
    }


def _usuarios():
    """Los mismos datos y permisos que entrega /api/yo/, con el correo como id del documento.

    Es lo mismo que hace Django: el correo une la cuenta de Firebase con el empleado.
    """
    modulos = [clave for clave, _ in TipoPermiso._meta.get_field("modulo").choices]
    acciones = [clave for clave, _ in TipoPermiso._meta.get_field("accion").choices]
    empleados = Empleado.objects.filter(estado=True, user__is_active=True).exclude(correo="")
    return {
        empleado.correo.lower(): {
            "id_empleado": str(empleado.pk),
            "nombre": empleado.get_full_name(),
            "usuario": empleado.user.username,
            "correo": empleado.correo.lower(),
            "telefono": empleado.telefono,
            "id_cargo": _texto_o_nada(empleado.cargo_id),
            "cargo": empleado.cargo.nombre_cargo if empleado.cargo else None,
            "nivel": nivel_de(empleado.user),
            "activo": True,
            # Ya tienen su contraseña de Firebase: no se les pide cambiarla otra vez
            "debe_cambiar_contrasena": False,
            "permisos": [
                f"{modulo}:{accion}"
                for modulo in modulos
                for accion in acciones
                if tiene_permiso(empleado.user, modulo, accion)
            ],
        }
        for empleado in empleados.select_related("user", "cargo")
    }


def construir_colecciones():
    """Devuelve {colección: {id del documento: datos}} con catálogos y usuarios."""
    origenes = {
        "categorias": (CategoriaPlato.objects.all(), _categoria),
        "ingredientes": (Ingrediente.objects.all(), _ingrediente),
        "platos": (
            Plato.objects.select_related("categoria").prefetch_related(
                "detalleplato_set__ingrediente"
            ),
            _plato,
        ),
        "tipos_bebida": (TipoBebida.objects.all(), _tipo_bebida),
        "bebidas": (Bebida.objects.select_related("id_tipo_bebida"), _bebida),
        "mesas": (Mesa.objects.all(), _mesa),
    }
    colecciones = {
        nombre: {str(fila.pk): convertir(fila) for fila in filas}
        for nombre, (filas, convertir) in origenes.items()
    }
    colecciones["usuarios"] = _usuarios()
    return colecciones


def _fecha(valor):
    """Firestore necesita saber la zona horaria de cada fecha."""
    if valor is None:
        return None
    if isinstance(valor, datetime) and timezone.is_naive(valor):
        return timezone.make_aware(valor)
    return valor


def _texto_o_nada(valor):
    return None if valor is None else str(valor)


def _items_de_comanda(comanda):
    """Firestore no tiene tablas intermedias: los productos van dentro de la comanda."""
    items = []
    for detalle in comanda.detalles.all():
        if detalle.plato:
            items.append({
                "tipo": "plato",
                "id": str(detalle.plato_id),
                "nombre": detalle.plato.nombre_plato,
                "precio": float(detalle.plato.precio_plato),
                "cantidad": detalle.cant_plato,
            })
        if detalle.bebida:
            items.append({
                "tipo": "bebida",
                "id": str(detalle.bebida_id),
                "nombre": detalle.bebida.nombre_bebida,
                "precio": float(detalle.bebida.precio_bebida),
                "cantidad": detalle.cant_bebida,
            })
    return items


def _comanda(comanda):
    pagos = list(comanda.pagos.all())
    total_pagado = sum(float(pago.monto) for pago in pagos)
    total = float(comanda.total_comanda)
    # "anulado" no está en la lista de estados del modelo
    anulada = comanda.estado_comanda == "anulado"
    return {
        "id_comanda": str(comanda.pk),
        "mesa": str(comanda.mesa_id),
        "mesa_numero": comanda.mesa.numero_mesa,
        "empleado": str(comanda.empleado_id),
        "mozo": comanda.empleado.get_full_name(),
        "estado_comanda": comanda.estado_comanda,
        "estado_nombre": "Anulado" if anulada else comanda.get_estado_comanda_display(),
        "fecha_hora": _fecha(comanda.fecha_hora),
        "observaciones_comanda": comanda.observaciones_comanda,
        "total_comanda": total,
        "total_pagado": total_pagado,
        "saldo_pendiente": max(total - total_pagado, 0.0),
        "fecha_anulacion": _fecha(comanda.fecha_anulacion),
        "motivo_anulacion": comanda.motivo_anulacion,
        "usuario_anulacion": _texto_o_nada(comanda.usuario_anulacion_id),
        "items": _items_de_comanda(comanda),
        "pagos": [
            {
                "id_pago": str(pago.pk),
                "monto": float(pago.monto),
                "metodo": pago.metodo_pago,
                "metodo_nombre": pago.get_metodo_pago_display(),
                "fecha_hora": _fecha(pago.fecha_hora),
                "empleado": _texto_o_nada(pago.empleado_id),
            }
            for pago in pagos
        ],
    }


def _cargo(cargo):
    return {
        "id_cargo": str(cargo.pk),
        "nombre_cargo": cargo.nombre_cargo,
        "descripcion_cargo": cargo.descripcion_cargo,
        "nivel_acceso": cargo.nivel_acceso,
        "total_empleados": cargo.empleado_set.count(),
        # Los permisos del cargo van dentro del cargo, igual que los ingredientes en un plato
        "permisos_ids": [str(p.tipo_permiso_id) for p in cargo.permisoxcargo_set.all()],
        "permisos": [
            f"{p.tipo_permiso.modulo}:{p.tipo_permiso.accion}"
            for p in cargo.permisoxcargo_set.all()
        ],
    }


def _permiso(permiso):
    return {
        "id_tipo_permiso": str(permiso.pk),
        "modulo": permiso.modulo,
        "modulo_nombre": permiso.get_modulo_display(),
        "accion": permiso.accion,
        "accion_nombre": permiso.get_accion_display(),
        "descripcion": permiso.descripcio_permiso or "",
    }


def _empleado(empleado):
    """Nunca incluye la contraseña."""
    return {
        "id_empleado": str(empleado.pk),
        "nombre_empleado": empleado.nombre_empleado,
        "apellido_empleado": empleado.apellido_empleado,
        "dni": empleado.dni,
        "telefono": empleado.telefono,
        "correo": empleado.correo.lower(),
        "user_auto": empleado.user_auto,
        # Firestore no guarda fechas sin hora: se guardan como texto, por ejemplo "2026-11-06"
        "fecha_ingreso": empleado.fecha_ingreso.isoformat(),
        "fecha_baja": empleado.fecha_baja.isoformat() if empleado.fecha_baja else None,
        "estado": empleado.estado,
        "cargo": _texto_o_nada(empleado.cargo_id),
        "cargo_nombre": empleado.cargo.nombre_cargo if empleado.cargo else None,
        "nivel_cargo": empleado.cargo.nivel_acceso if empleado.cargo else 0,
    }


def _auditoria(registro):
    return {
        "id_log": str(registro.pk),
        "tabla": registro.tabla,
        "accion": registro.accion,
        "registro_id": str(registro.registro_id),
        "valores_anteriores": registro.valores_anteriores or "",
        "valores_actuales": registro.valores_actuales or "",
        "fecha_hora": _fecha(registro.fecha_hora),
        "empleado": _texto_o_nada(registro.empleado_id),
        "empleado_nombre": registro.empleado.get_full_name() if registro.empleado else "Sistema",
    }


def construir_auditoria():
    filas = LogAuditoria.objects.select_related("empleado")
    return {"auditoria": {str(fila.pk): _auditoria(fila) for fila in filas}}


def construir_restantes():
    """Lo que no se copió en la primera etapa."""
    origenes = {
        "comandas": (
            Comanda.objects.select_related("mesa", "empleado").prefetch_related(
                "pagos", "detalles__plato", "detalles__bebida"
            ),
            _comanda,
        ),
        "cargos": (Cargo.objects.prefetch_related("permisoxcargo_set__tipo_permiso"), _cargo),
        "permisos": (TipoPermiso.objects.all(), _permiso),
        "empleados": (Empleado.objects.select_related("cargo"), _empleado),
    }
    colecciones = {
        nombre: {str(fila.pk): convertir(fila) for fila in filas}
        for nombre, (filas, convertir) in origenes.items()
    }
    # Los sueldos van aparte: quien ve empleados puede elegir un cargo sin ver cuánto se paga
    colecciones["sueldos"] = {
        str(cargo.pk): {"sueldo_cargo": float(cargo.sueldo_cargo)} for cargo in Cargo.objects.all()
    }
    # La app sigue la numeración a partir de la última comanda
    ultimo = max((fila.pk for fila in Comanda.objects.only("pk")), default=0)
    colecciones["contadores"] = {"comandas": {"ultimo": ultimo}}
    return colecciones


def mesas_con_comanda_abierta():
    ids = Comanda.objects.filter(estado_comanda__in=ESTADOS_ABIERTOS).values_list("mesa_id", flat=True)
    return sorted({str(id_mesa) for id_mesa in ids})


def ocupar_mesas(db, ids):
    """Solo cambia el estado de esas mesas. Los demás datos de Firestore no se tocan."""
    lote = db.batch()
    for id_mesa in ids:
        lote.update(db.collection("mesas").document(id_mesa), {"estado_mesa": False})
    lote.commit()


def colecciones_con_datos(db, colecciones):
    """Devuelve los nombres de las colecciones que ya tienen documentos en Firestore."""
    return [
        nombre for nombre in colecciones
        if any(True for _ in db.collection(nombre).limit(1).stream())
    ]


def subir(db, colecciones):
    """Escribe los documentos por lotes. Usa el mismo id que MySQL."""
    documentos = [
        (db.collection(nombre).document(id_documento), datos)
        for nombre, filas in colecciones.items()
        for id_documento, datos in filas.items()
    ]
    for inicio in range(0, len(documentos), TAMANIO_DE_LOTE):
        lote = db.batch()
        for referencia, datos in documentos[inicio:inicio + TAMANIO_DE_LOTE]:
            lote.set(referencia, datos)
        lote.commit()
    return len(documentos)


def avisos(colecciones):
    """Datos que no quedan completos en Firestore y conviene revisar."""
    resultado = []
    con_foto = sum(1 for i in colecciones.get("ingredientes", {}).values() if i["imagen_ingrediente"])
    if con_foto:
        resultado.append(
            f"{con_foto} ingrediente(s) tienen foto: se copia la ruta, no el archivo."
        )
    return resultado


class Command(BaseCommand):
    help = "Copia catálogos, mesas y permisos de usuarios de MySQL a Firestore."

    def add_arguments(self, parser):
        parser.add_argument(
            "--ejecutar", action="store_true", help="Escribe en Firestore. Sin esto, solo muestra."
        )
        parser.add_argument("--clave", help="Ruta al JSON de la cuenta de servicio de Firebase.")
        parser.add_argument(
            "--sobrescribir",
            action="store_true",
            help="Reemplaza los documentos con el mismo id si la colección ya tiene datos.",
        )
        parser.add_argument(
            "--restantes",
            action="store_true",
            help="Copia solo comandas, cargos, permisos y empleados.",
        )
        parser.add_argument(
            "--auditoria",
            action="store_true",
            help="Copia solo el registro de auditoría.",
        )

    def handle(self, *args, **opciones):
        restantes = opciones["restantes"]
        if opciones["auditoria"]:
            colecciones = construir_auditoria()
        else:
            colecciones = construir_restantes() if restantes else construir_colecciones()
        self._mostrar_resumen(colecciones)
        mesas = mesas_con_comanda_abierta() if restantes else []
        if restantes:
            self.stdout.write(f"\nMesas que pasarán a ocupadas por tener una comanda abierta: {len(mesas)}")

        if not opciones["ejecutar"]:
            self.stdout.write(self.style.WARNING(
                "\nModo de prueba: no se escribió nada. Para copiar, usá --ejecutar --clave."
            ))
            return

        db = self._conectar(opciones["clave"])

        if not opciones["sobrescribir"]:
            ocupadas = colecciones_con_datos(db, colecciones)
            if ocupadas:
                raise CommandError(
                    f"Estas colecciones ya tienen datos: {', '.join(ocupadas)}. "
                    "No se escribió nada. Para reemplazarlos, usá --sobrescribir."
                )

        total = subir(db, colecciones)
        if mesas:
            ocupar_mesas(db, mesas)
        self.stdout.write(self.style.SUCCESS(f"\nListo: {total} documentos copiados a Firestore."))

    def _mostrar_resumen(self, colecciones):
        self.stdout.write("Documentos por colección:")
        for nombre, filas in colecciones.items():
            self.stdout.write(f"  {nombre}: {len(filas)}")
        for aviso in avisos(colecciones):
            self.stdout.write(self.style.WARNING(f"Aviso: {aviso}"))

        self.stdout.write("\nEjemplo de cada colección:")
        for nombre, filas in colecciones.items():
            if filas and nombre not in SIN_EJEMPLO:
                ejemplo = next(iter(filas.values()))
                self.stdout.write(f"{nombre}: {json.dumps(ejemplo, ensure_ascii=False)}")

    def _conectar(self, ruta_clave):
        if not ruta_clave:
            raise CommandError("Falta --clave con la ruta al JSON de la cuenta de servicio.")

        # Se importa acá para que el modo de prueba funcione sin firebase-admin
        import firebase_admin
        from firebase_admin import credentials, firestore

        try:
            credencial = credentials.Certificate(ruta_clave)
        except (OSError, ValueError) as error:
            raise CommandError(f"No se pudo leer la clave: {error}")

        # Evita copiar los datos a un proyecto que no es el de la app
        esperado = settings.FIREBASE_PROJECT_ID
        if esperado and credencial.project_id != esperado:
            raise CommandError(
                f"La clave es del proyecto '{credencial.project_id}', "
                f"pero FIREBASE_PROJECT_ID es '{esperado}'."
            )

        firebase_admin.initialize_app(credencial)
        return firestore.client()
