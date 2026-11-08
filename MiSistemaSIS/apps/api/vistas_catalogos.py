"""Categorías de platos y tipos de bebida en la API.

A diferencia de la web de Django, no se elimina una categoría o un tipo que todavía
tiene platos o bebidas: en la base, eliminarlo también borraría esos productos.
"""
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from inventario.models import CategoriaPlato, TipoBebida

from .permisos import PermisoDeModulo
from .views import _auditar


def _activo(valor):
    return "Activo" if valor else "Inactivo"


# ---------- CATEGORÍAS DE PLATOS ----------
class CategoriaPlatoSerializer(serializers.ModelSerializer):
    total_platos = serializers.SerializerMethodField()

    class Meta:
        model = CategoriaPlato
        fields = [
            "id_categoria_plato",
            "nombre_categoria_plato",
            "descripcion_categoria_plato",
            "estado_categoria_plato",
            "total_platos",
        ]
        read_only_fields = ["id_categoria_plato", "estado_categoria_plato"]
        # El nombre repetido se revisa abajo, sin importar mayúsculas
        extra_kwargs = {"nombre_categoria_plato": {"validators": []}}

    def get_total_platos(self, categoria):
        return categoria.plato_set.count()

    def validate_nombre_categoria_plato(self, nombre):
        nombre = nombre.strip().title()
        if not nombre:
            raise serializers.ValidationError("Ingresá el nombre de la categoría.")
        repetidas = CategoriaPlato.objects.filter(nombre_categoria_plato__iexact=nombre)
        if self.instance:
            repetidas = repetidas.exclude(pk=self.instance.pk)
        if repetidas.exists():
            raise serializers.ValidationError("Ya existe una categoría con ese nombre.")
        return nombre


def _describir_categoria(categoria):
    return (
        f"Nombre: {categoria.nombre_categoria_plato}, "
        f"Descripción: {categoria.descripcion_categoria_plato}, "
        f"Estado: {_activo(categoria.estado_categoria_plato)}"
    )


class CategoriaPlatoListaView(APIView):
    """GET /api/categorias-plato/ lista todas. POST crea una."""

    permission_classes = [PermisoDeModulo]
    modulo = "categorias"

    def get(self, request):
        categorias = CategoriaPlato.objects.order_by("nombre_categoria_plato")
        return Response(CategoriaPlatoSerializer(categorias, many=True).data)

    def post(self, request):
        serializer = CategoriaPlatoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            categoria = serializer.save()
            _auditar(request, "Categoria plato", "CREAR", categoria.pk, "", _describir_categoria(categoria))
        return Response(CategoriaPlatoSerializer(categoria).data, status=status.HTTP_201_CREATED)


class CategoriaPlatoDetalleView(APIView):
    """GET devuelve una con sus platos. PATCH la edita. DELETE la elimina si no tiene platos."""

    permission_classes = [PermisoDeModulo]
    modulo = "categorias"

    def get(self, request, pk):
        categoria = get_object_or_404(CategoriaPlato, pk=pk)
        datos = CategoriaPlatoSerializer(categoria).data
        datos["platos"] = list(
            categoria.plato_set.order_by("nombre_plato").values(
                "id_plato", "nombre_plato", "precio_plato", "estado_plato"
            )
        )
        return Response(datos)

    def patch(self, request, pk):
        categoria = get_object_or_404(CategoriaPlato, pk=pk)
        anterior = _describir_categoria(categoria)
        serializer = CategoriaPlatoSerializer(categoria, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            categoria = serializer.save()
            _auditar(request, "Categoria plato", "MODIFICAR", categoria.pk, anterior, _describir_categoria(categoria))
        return Response(CategoriaPlatoSerializer(categoria).data)

    def delete(self, request, pk):
        categoria = get_object_or_404(CategoriaPlato, pk=pk)
        if categoria.plato_set.exists():
            raise ValidationError(
                {
                    "detail": f'No se puede eliminar "{categoria.nombre_categoria_plato}" porque tiene platos. '
                    "Podés desactivarla."
                }
            )
        anterior = _describir_categoria(categoria)
        identificador = categoria.pk
        with transaction.atomic():
            categoria.delete()
            _auditar(request, "Categoria plato", "ELIMINAR", identificador, anterior, "Categoría eliminada")
        return Response(status=status.HTTP_204_NO_CONTENT)


class CategoriaPlatoEstadoView(APIView):
    """POST /api/categorias-plato/5/estado/: alterna entre activa e inactiva."""

    permission_classes = [PermisoDeModulo]
    modulo = "categorias"
    accion = "modificar"

    def post(self, request, pk):
        with transaction.atomic():
            categoria = get_object_or_404(CategoriaPlato.objects.select_for_update(), pk=pk)
            anterior = _activo(categoria.estado_categoria_plato)
            categoria.estado_categoria_plato = not categoria.estado_categoria_plato
            categoria.save()
            _auditar(
                request, "Categoria plato", "MODIFICAR", categoria.pk,
                f"Estado: {anterior}", f"Estado: {_activo(categoria.estado_categoria_plato)}",
            )
        return Response(CategoriaPlatoSerializer(categoria).data)


# ---------- TIPOS DE BEBIDA ----------
class TipoBebidaSerializer(serializers.ModelSerializer):
    total_bebidas = serializers.SerializerMethodField()

    class Meta:
        model = TipoBebida
        fields = [
            "id_tipo_bebida",
            "nombre_tipo_bebida",
            "descripcion_tipo_bebida",
            "estado_tipo_bebida",
            "total_bebidas",
        ]
        read_only_fields = ["id_tipo_bebida", "estado_tipo_bebida"]

    def get_total_bebidas(self, tipo):
        return tipo.bebida_set.count()

    def validate_nombre_tipo_bebida(self, nombre):
        nombre = nombre.strip().title()
        if not nombre:
            raise serializers.ValidationError("Ingresá el nombre del tipo de bebida.")
        repetidos = TipoBebida.objects.filter(nombre_tipo_bebida__iexact=nombre)
        if self.instance:
            repetidos = repetidos.exclude(pk=self.instance.pk)
        if repetidos.exists():
            raise serializers.ValidationError("Este tipo de bebida ya existe.")
        return nombre


def _describir_tipo(tipo):
    return (
        f"Nombre: {tipo.nombre_tipo_bebida}, Descripción: {tipo.descripcion_tipo_bebida}, "
        f"Estado: {_activo(tipo.estado_tipo_bebida)}"
    )


class TipoBebidaListaView(APIView):
    """GET /api/tipos-bebida/ lista todos (también lo usa el formulario de bebidas). POST crea uno."""

    permission_classes = [PermisoDeModulo]
    modulo = "bebidas"

    def get(self, request):
        tipos = TipoBebida.objects.order_by("nombre_tipo_bebida")
        return Response(TipoBebidaSerializer(tipos, many=True).data)

    def post(self, request):
        serializer = TipoBebidaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            tipo = serializer.save()
            _auditar(request, "Tipo de Bebida", "CREAR", tipo.pk, "", _describir_tipo(tipo))
        return Response(TipoBebidaSerializer(tipo).data, status=status.HTTP_201_CREATED)


class TipoBebidaDetalleView(APIView):
    """PATCH /api/tipos-bebida/5/ lo edita. DELETE lo elimina si no tiene bebidas."""

    permission_classes = [PermisoDeModulo]
    modulo = "bebidas"

    def patch(self, request, pk):
        tipo = get_object_or_404(TipoBebida, pk=pk)
        anterior = _describir_tipo(tipo)
        serializer = TipoBebidaSerializer(tipo, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            tipo = serializer.save()
            _auditar(request, "Tipo de Bebida", "MODIFICAR", tipo.pk, anterior, _describir_tipo(tipo))
        return Response(TipoBebidaSerializer(tipo).data)

    def delete(self, request, pk):
        tipo = get_object_or_404(TipoBebida, pk=pk)
        if tipo.bebida_set.exists():
            raise ValidationError(
                {"detail": f'No se puede eliminar "{tipo.nombre_tipo_bebida}" porque tiene bebidas. Podés desactivarlo.'}
            )
        anterior = _describir_tipo(tipo)
        identificador = tipo.pk
        with transaction.atomic():
            tipo.delete()
            _auditar(request, "Tipo de Bebida", "ELIMINAR", identificador, anterior, "Tipo eliminado")
        return Response(status=status.HTTP_204_NO_CONTENT)


class TipoBebidaEstadoView(APIView):
    """POST /api/tipos-bebida/5/estado/: alterna entre activo e inactivo."""

    permission_classes = [PermisoDeModulo]
    modulo = "bebidas"
    accion = "modificar"

    def post(self, request, pk):
        with transaction.atomic():
            tipo = get_object_or_404(TipoBebida.objects.select_for_update(), pk=pk)
            anterior = _activo(tipo.estado_tipo_bebida)
            tipo.estado_tipo_bebida = not tipo.estado_tipo_bebida
            tipo.save()
            _auditar(
                request, "Tipo de Bebida", "MODIFICAR", tipo.pk,
                f"Estado: {anterior}", f"Estado: {_activo(tipo.estado_tipo_bebida)}",
            )
        return Response(TipoBebidaSerializer(tipo).data)
