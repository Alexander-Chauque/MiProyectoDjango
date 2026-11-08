"""Los serializers convierten los modelos a JSON y validan lo que envía la app."""
import re
from decimal import Decimal

from django.db import transaction
from django.db.models import Q
from rest_framework import serializers

from inventario.models import Bebida, DetallePlato, Ingrediente, Plato
from inventario.servicios import eliminable_desde
from ventas.models import Comanda, Mesa

TAMANIO_MAXIMO_IMAGEN = 5 * 1024 * 1024  # 5 MB
FORMATOS_DE_IMAGEN = ("JPEG", "PNG", "WEBP")


class IngredienteSerializer(serializers.ModelSerializer):
    # Texto para mostrar, por ejemplo "Kilogramo" para "kg". Solo lectura.
    unidad_nombre = serializers.CharField(source="get_unidad_medida_display", read_only=True)
    costo_unitario = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0")
    )
    # Al leer devuelve la dirección completa de la foto. Comprueba que sea una imagen real.
    imagen_ingrediente = serializers.ImageField(required=False, allow_null=True)
    # La app envía true cuando la persona toca "Quitar foto"
    quitar_imagen = serializers.BooleanField(write_only=True, required=False, default=False)
    fecha_desactivacion = serializers.DateTimeField(read_only=True)
    eliminable_desde = serializers.SerializerMethodField()

    def get_eliminable_desde(self, producto):
        desde = eliminable_desde(producto)
        return desde.isoformat() if desde else None

    class Meta:
        model = Ingrediente
        fields = [
            "id_ingrediente",
            "nombre_ingrediente",
            "unidad_medida",
            "unidad_nombre",
            "costo_unitario",
            "descripcion_ingrediente",
            "imagen_ingrediente",
            "quitar_imagen",
            "estado_ingrediente",
            "fecha_desactivacion",
            "eliminable_desde",
        ]
        # El estado cambia solo por /estado/, porque también afecta a los platos
        read_only_fields = ["id_ingrediente", "estado_ingrediente"]
        # Quita el validador automático: el duplicado se revisa abajo, con mensaje propio
        validators = []

    def validate_imagen_ingrediente(self, imagen):
        if imagen is None:
            return imagen
        if imagen.size > TAMANIO_MAXIMO_IMAGEN:
            raise serializers.ValidationError("La foto no puede superar los 5 MB.")
        # El formato real del archivo, no lo que dice su nombre
        if imagen.image.format not in FORMATOS_DE_IMAGEN:
            raise serializers.ValidationError("La foto debe ser JPG, PNG o WEBP.")
        return imagen

    def create(self, datos):
        datos.pop("quitar_imagen", None)
        return super().create(datos)

    def update(self, ingrediente, datos):
        quitar = datos.pop("quitar_imagen", False)
        foto_anterior = ingrediente.imagen_ingrediente
        nombre_anterior = foto_anterior.name if foto_anterior else None
        almacen = foto_anterior.storage

        if quitar and "imagen_ingrediente" not in datos:
            datos["imagen_ingrediente"] = None
        ingrediente = super().update(ingrediente, datos)

        # Borra el archivo viejo recién cuando el cambio quedó guardado en la base
        nombre_nuevo = ingrediente.imagen_ingrediente.name if ingrediente.imagen_ingrediente else None
        if nombre_anterior and nombre_anterior != nombre_nuevo:
            transaction.on_commit(lambda: almacen.delete(nombre_anterior))
        return ingrediente

    def validate(self, datos):
        """Rechaza otro ingrediente con el mismo nombre y unidad, sin importar mayúsculas."""
        nombre = datos.get("nombre_ingrediente", getattr(self.instance, "nombre_ingrediente", None))
        unidad = datos.get("unidad_medida", getattr(self.instance, "unidad_medida", None))
        repetidos = Ingrediente.objects.filter(
            nombre_ingrediente__iexact=nombre, unidad_medida=unidad
        )
        if self.instance:
            repetidos = repetidos.exclude(pk=self.instance.pk)
        if repetidos.exists():
            raise serializers.ValidationError(
                {"nombre_ingrediente": "Ya existe un ingrediente con ese nombre y unidad."}
            )
        return datos


class PlatoSerializer(serializers.ModelSerializer):
    categoria_nombre = serializers.CharField(source="categoria.nombre_categoria_plato", read_only=True)
    precio_plato = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0.01")
    )
    # Al guardar se envían los ids. Al leer se devuelven los datos de cada ingrediente.
    ingredientes_ids = serializers.ListField(
        child=serializers.IntegerField(), write_only=True, required=False
    )
    ingredientes = serializers.SerializerMethodField()
    fecha_desactivacion = serializers.DateTimeField(read_only=True)
    eliminable_desde = serializers.SerializerMethodField()

    def get_eliminable_desde(self, producto):
        desde = eliminable_desde(producto)
        return desde.isoformat() if desde else None

    class Meta:
        model = Plato
        fields = [
            "id_plato",
            "nombre_plato",
            "precio_plato",
            "categoria",
            "categoria_nombre",
            "descripcion_plato",
            "estado_plato",
            "ingredientes_ids",
            "ingredientes",
            "fecha_desactivacion",
            "eliminable_desde",
        ]
        read_only_fields = ["id_plato", "estado_plato"]
        # Quita el validador automático de nombre único: se revisa abajo, sin importar mayúsculas
        extra_kwargs = {"nombre_plato": {"validators": []}}

    def get_ingredientes(self, plato):
        return [
            {
                "id_ingrediente": detalle.ingrediente_id,
                "nombre_ingrediente": detalle.ingrediente.nombre_ingrediente,
                "estado_ingrediente": detalle.ingrediente.estado_ingrediente,
                "unidad_medida": detalle.ingrediente.unidad_medida,
            }
            for detalle in plato.detalleplato_set.select_related("ingrediente")
        ]

    def validate_nombre_plato(self, nombre):
        nombre = nombre.strip().title()
        if not re.fullmatch(r"[a-zA-Z0-9áéíóúÁÉÍÓÚñÑüÜ\s/-]+", nombre):
            raise serializers.ValidationError(
                "Nombre inválido: solo se permiten letras, números, espacios, / y -"
            )
        repetidos = Plato.objects.filter(nombre_plato__iexact=nombre)
        if self.instance:
            repetidos = repetidos.exclude(pk=self.instance.pk)
        if repetidos.exists():
            raise serializers.ValidationError(f'Plato "{nombre}" ya existe')
        return nombre

    def validate_ingredientes_ids(self, ids):
        if not ids:
            raise serializers.ValidationError("Debe seleccionar al menos un ingrediente")
        # Solo se aceptan activos, o inactivos que el plato ya usaba
        actuales = (
            self.instance.detalleplato_set.values("ingrediente_id") if self.instance else []
        )
        validos = Ingrediente.objects.filter(pk__in=ids).filter(
            Q(estado_ingrediente=True) | Q(pk__in=actuales)
        )
        if validos.count() != len(set(ids)):
            raise serializers.ValidationError(
                "Hay ingredientes que no existen o no están disponibles"
            )
        return list(set(ids))

    def validate(self, datos):
        if not self.instance and "ingredientes_ids" not in datos:
            raise serializers.ValidationError(
                {"ingredientes_ids": "Debe seleccionar al menos un ingrediente"}
            )
        return datos

    def _guardar_ingredientes(self, plato, ids):
        # Conserva la cantidad de los ingredientes que siguen en el plato
        cantidades = dict(plato.detalleplato_set.values_list("ingrediente_id", "cantidad"))
        plato.detalleplato_set.all().delete()
        for id_ingrediente in ids:
            DetallePlato.objects.create(
                plato=plato,
                ingrediente_id=id_ingrediente,
                cantidad=cantidades.get(id_ingrediente, 1),
            )

    @transaction.atomic
    def create(self, datos):
        ids = datos.pop("ingredientes_ids")
        plato = Plato.objects.create(**datos)
        self._guardar_ingredientes(plato, ids)
        return plato

    @transaction.atomic
    def update(self, plato, datos):
        ids = datos.pop("ingredientes_ids", None)
        plato = super().update(plato, datos)
        if ids is not None:
            self._guardar_ingredientes(plato, ids)
        return plato


class BebidaSerializer(serializers.ModelSerializer):
    tipo_nombre = serializers.CharField(source="id_tipo_bebida.nombre_tipo_bebida", read_only=True)
    precio_bebida = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0.01")
    )
    fecha_desactivacion = serializers.DateTimeField(read_only=True)
    eliminable_desde = serializers.SerializerMethodField()

    def get_eliminable_desde(self, producto):
        desde = eliminable_desde(producto)
        return desde.isoformat() if desde else None

    class Meta:
        model = Bebida
        fields = [
            "id_bebida",
            "nombre_bebida",
            "precio_bebida",
            "id_tipo_bebida",
            "tipo_nombre",
            "descripcion_bebida",
            "disponible_bebida",
            "fecha_desactivacion",
            "eliminable_desde",
        ]
        read_only_fields = ["id_bebida", "disponible_bebida"]
        extra_kwargs = {"nombre_bebida": {"validators": []}}

    def validate_nombre_bebida(self, nombre):
        nombre = nombre.strip().title()
        repetidas = Bebida.objects.filter(nombre_bebida__iexact=nombre)
        if self.instance:
            repetidas = repetidas.exclude(pk=self.instance.pk)
        if repetidas.exists():
            raise serializers.ValidationError("Esta bebida ya existe")
        return nombre


class MesaSerializer(serializers.ModelSerializer):
    ubicacion_nombre = serializers.CharField(source="get_ubicacion_display", read_only=True)
    # La comanda abierta de la mesa, para abrirla directamente desde la lista
    comanda_abierta = serializers.SerializerMethodField()

    class Meta:
        model = Mesa
        fields = ["id_mesa", "numero_mesa", "ubicacion", "ubicacion_nombre", "estado_mesa", "comanda_abierta"]
        # El estado cambia solo por /estado/, que revisa las comandas abiertas
        read_only_fields = ["id_mesa", "estado_mesa"]
        # El número repetido se revisa abajo, con un mensaje propio
        extra_kwargs = {"numero_mesa": {"validators": []}}

    def validate_numero_mesa(self, numero):
        if numero < 1:
            raise serializers.ValidationError("El número de mesa debe ser mayor a 0.")
        repetidas = Mesa.objects.filter(numero_mesa=numero)
        if self.instance:
            repetidas = repetidas.exclude(pk=self.instance.pk)
        if repetidas.exists():
            raise serializers.ValidationError("Este número de mesa ya existe.")
        return numero

    def get_comanda_abierta(self, mesa):
        comanda = (
            mesa.comandas.filter(estado_comanda__in=["pendiente", "en_preparacion", "entregado"])
            .order_by("-fecha_hora")
            .first()
        )
        return comanda.id_comanda if comanda else None


class ComandaSerializer(serializers.ModelSerializer):
    """Datos resumidos, para las listas."""

    mesa_numero = serializers.IntegerField(source="mesa.numero_mesa", read_only=True)
    mozo = serializers.CharField(source="empleado.get_full_name", read_only=True)
    estado_nombre = serializers.SerializerMethodField()
    total_pagado = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    saldo_pendiente = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    esta_abierta = serializers.BooleanField(read_only=True)
    puede_modificarse = serializers.BooleanField(read_only=True)

    class Meta:
        model = Comanda
        fields = [
            "id_comanda",
            "mesa",
            "mesa_numero",
            "mozo",
            "estado_comanda",
            "estado_nombre",
            "total_comanda",
            "total_pagado",
            "saldo_pendiente",
            "fecha_hora",
            "esta_abierta",
            "puede_modificarse",
        ]

    def get_estado_nombre(self, comanda):
        # "anulado" no está en la lista de estados del modelo
        return "Anulado" if comanda.estado_comanda == "anulado" else comanda.get_estado_comanda_display()


class ComandaDetalleSerializer(ComandaSerializer):
    """Datos completos de una comanda, con sus productos y pagos."""

    items = serializers.SerializerMethodField()
    pagos = serializers.SerializerMethodField()

    class Meta(ComandaSerializer.Meta):
        fields = ComandaSerializer.Meta.fields + [
            "observaciones_comanda",
            "motivo_anulacion",
            "items",
            "pagos",
        ]

    def get_items(self, comanda):
        items = []
        for detalle in comanda.detalles.select_related("plato__categoria", "bebida"):
            if detalle.tiene_plato:
                items.append(
                    {
                        "tipo": "plato",
                        # None si el plato ya se eliminó del inventario
                        "id": detalle.plato_id,
                        "nombre": detalle.nombre_del_plato,
                        "precio": str(detalle.precio_del_plato),
                        "cantidad": detalle.cant_plato,
                        "disponible": bool(detalle.plato and detalle.plato.estado_plato),
                        # Los tickets mandan la categoría Parrilla a la parrilla y el resto a la cocina
                        "categoria": detalle.categoria_del_plato,
                    }
                )
            if detalle.tiene_bebida:
                items.append(
                    {
                        "tipo": "bebida",
                        "id": detalle.bebida_id,
                        "nombre": detalle.nombre_de_la_bebida,
                        "precio": str(detalle.precio_de_la_bebida),
                        "cantidad": detalle.cant_bebida,
                        "disponible": bool(detalle.bebida and detalle.bebida.disponible_bebida),
                    }
                )
        return items

    def get_pagos(self, comanda):
        return [
            {
                "id_pago": pago.id_pago,
                "monto": str(pago.monto),
                "metodo": pago.get_metodo_pago_display(),
                "fecha_hora": pago.fecha_hora,
            }
            for pago in comanda.pagos.all()
        ]
