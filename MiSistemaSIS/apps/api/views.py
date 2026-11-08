"""Vistas de la API que usa la web en React. Responden JSON, no páginas HTML."""
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from auditoria.models import LogAuditoria
from empleados.decorators import nivel_de, tiene_permiso
from empleados.models import TipoPermiso
from inventario.models import Bebida, CategoriaPlato, Ingrediente, Plato
from inventario.servicios import cambiar_estado_ingrediente, eliminar_bebida, eliminar_ingrediente, eliminar_plato
from ventas.models import Comanda, Mesa
from ventas.servicios import (
    ESTADOS_ABIERTOS,
    actualizar_comanda,
    cambiar_estado_comanda,
    cambiar_estado_mesa,
    crear_comanda,
    registrar_pago,
)

from .permisos import PermisoDeModulo
from .serializers import (
    BebidaSerializer,
    ComandaDetalleSerializer,
    ComandaSerializer,
    IngredienteSerializer,
    MesaSerializer,
    PlatoSerializer,
)
from .utilidades import filtrar_entre_fechas, rango_pedido, responder_paginado


def _auditar(request, tabla, accion, registro_id, anterior, actual):
    """Registra un cambio hecho desde la app en la auditoría."""
    LogAuditoria.objects.create(
        tabla=tabla,
        accion=accion,
        registro_id=registro_id,
        valores_anteriores=anterior,
        valores_actuales=f"Desde la app. {actual}",
        empleado=request.user.empleado,
    )


def _ejecutar(funcion, *args):
    """Convierte los errores de las reglas en una respuesta 400 con el mensaje."""
    try:
        return funcion(*args)
    except ValueError as error:
        raise ValidationError({"detail": str(error)})


class YoView(APIView):
    """GET /api/yo/: quién es el usuario y qué puede hacer. La web lo usa para mostrar u ocultar botones."""

    def get(self, request):
        empleado = request.user.empleado
        modulos = [clave for clave, _ in TipoPermiso._meta.get_field("modulo").choices]
        acciones = [clave for clave, _ in TipoPermiso._meta.get_field("accion").choices]
        return Response(
            {
                "nombre": empleado.get_full_name(),
                "usuario": request.user.username,
                "correo": empleado.correo,
                "telefono": empleado.telefono,
                "cargo": empleado.cargo.nombre_cargo if empleado.cargo else None,
                "nivel": nivel_de(request.user),
                # Ejemplo: ["ingredientes:leer", "ingredientes:escribir"]
                "permisos": [
                    f"{modulo}:{accion}"
                    for modulo in modulos
                    for accion in acciones
                    if tiene_permiso(request.user, modulo, accion)
                ],
            }
        )


class ResumenView(APIView):
    """GET /api/resumen/: los números de la pantalla de inicio."""

    def get(self, request):
        return Response(
            {
                "productos": Plato.objects.filter(estado_plato=True).count()
                + Bebida.objects.filter(disponible_bebida=True).count(),
                "mesas_ocupadas": Mesa.objects.filter(estado_mesa=False).count(),
                "mesas_totales": Mesa.objects.count(),
                "comandas_pendientes": Comanda.objects.filter(
                    estado_comanda__in=["pendiente", "en_preparacion"]
                ).count(),
                "comandas_en_preparacion": Comanda.objects.filter(
                    estado_comanda="en_preparacion"
                ).count(),
            }
        )


# ---------- INGREDIENTES ----------
def _descripcion_ingrediente(ingrediente):
    return (
        f"Nombre: {ingrediente.nombre_ingrediente}, "
        f"Unidad: {ingrediente.unidad_medida}, Costo: {ingrediente.costo_unitario}"
    )


class IngredienteListaView(generics.ListCreateAPIView):
    """GET /api/ingredientes/ lista todos. POST /api/ingredientes/ crea uno."""

    queryset = Ingrediente.objects.order_by("nombre_ingrediente")
    serializer_class = IngredienteSerializer
    permission_classes = [PermisoDeModulo]
    modulo = "ingredientes"

    def perform_create(self, serializer):
        # atomic(): si falla la auditoría, tampoco se guarda el ingrediente
        with transaction.atomic():
            ingrediente = serializer.save()
            _auditar(self.request, "Ingrediente", "CREAR", ingrediente.pk, "", _descripcion_ingrediente(ingrediente))


class IngredienteDetalleView(generics.RetrieveUpdateDestroyAPIView):
    """GET /api/ingredientes/5/ devuelve uno, PATCH lo edita y DELETE lo elimina.

    Solo se elimina si está no disponible hace 2 meses y ningún plato disponible lo usa.
    """

    queryset = Ingrediente.objects.all()
    serializer_class = IngredienteSerializer
    permission_classes = [PermisoDeModulo]
    modulo = "ingredientes"
    http_method_names = ["get", "patch", "delete", "head", "options"]

    def perform_destroy(self, instance):
        anterior, identificador = _descripcion_ingrediente(instance), instance.pk
        with transaction.atomic():
            _ejecutar(eliminar_ingrediente, instance)
            _auditar(self.request, "Ingrediente", "ELIMINAR", identificador, anterior, "Ingrediente eliminado")

    def perform_update(self, serializer):
        # Se lee antes de guardar para registrar el valor anterior real
        valores_viejos = _descripcion_ingrediente(serializer.instance)
        with transaction.atomic():
            ingrediente = serializer.save()
            _auditar(self.request, "Ingrediente", "MODIFICAR", ingrediente.pk, valores_viejos, _descripcion_ingrediente(ingrediente))


class IngredienteEstadoView(APIView):
    """POST /api/ingredientes/5/estado/: cambia entre disponible y no disponible."""

    permission_classes = [PermisoDeModulo]
    modulo = "ingredientes"
    accion = "modificar"  # Es un POST, pero modifica un registro que ya existe

    def post(self, request, pk):
        ingrediente = get_object_or_404(Ingrediente, pk=pk)
        motivo = str(request.data.get("motivo") or "Cambio desde la app")[:250]
        cambiar_estado_ingrediente(ingrediente, request.user.empleado, motivo)
        # context con request permite armar la dirección completa de la foto
        return Response(IngredienteSerializer(ingrediente, context={"request": request}).data)


# ---------- PLATOS ----------
def _descripcion_plato(plato):
    return f"Nombre: {plato.nombre_plato}, Precio: {plato.precio_plato}, Categoría: {plato.categoria}"


class CategoriasView(APIView):
    """GET /api/categorias/: categorías para el formulario de platos."""

    permission_classes = [PermisoDeModulo]
    modulo = "platos"

    def get(self, request):
        return Response(
            list(
                CategoriaPlato.objects.order_by("nombre_categoria_plato").values(
                    "id_categoria_plato", "nombre_categoria_plato", "estado_categoria_plato"
                )
            )
        )


class IngredientesParaPlatoView(APIView):
    """GET /api/platos/ingredientes/: ingredientes para elegir en el formulario de platos."""

    permission_classes = [PermisoDeModulo]
    modulo = "platos"

    def get(self, request):
        return Response(
            list(
                Ingrediente.objects.order_by("nombre_ingrediente").values(
                    "id_ingrediente", "nombre_ingrediente", "estado_ingrediente", "unidad_medida"
                )
            )
        )


class PlatoListaView(generics.ListCreateAPIView):
    """GET /api/platos/ lista todos. POST /api/platos/ crea uno."""

    queryset = Plato.objects.select_related("categoria").order_by("nombre_plato")
    serializer_class = PlatoSerializer
    permission_classes = [PermisoDeModulo]
    modulo = "platos"

    def perform_create(self, serializer):
        with transaction.atomic():
            plato = serializer.save()
            _auditar(self.request, "Plato", "CREAR", plato.pk, "", _descripcion_plato(plato))


class PlatoDetalleView(generics.RetrieveUpdateDestroyAPIView):
    """GET /api/platos/5/ devuelve uno, PATCH lo edita y DELETE lo elimina.

    Solo se elimina si está no disponible hace 2 meses. Las comandas viejas guardan su nombre y precio.
    """

    queryset = Plato.objects.select_related("categoria")
    serializer_class = PlatoSerializer
    permission_classes = [PermisoDeModulo]
    modulo = "platos"
    http_method_names = ["get", "patch", "delete", "head", "options"]

    def perform_destroy(self, instance):
        anterior, identificador = _descripcion_plato(instance), instance.pk
        with transaction.atomic():
            _ejecutar(eliminar_plato, instance)
            _auditar(self.request, "Plato", "ELIMINAR", identificador, anterior, "Plato eliminado")

    def perform_update(self, serializer):
        valores_viejos = _descripcion_plato(serializer.instance)
        with transaction.atomic():
            plato = serializer.save()
            _auditar(self.request, "Plato", "MODIFICAR", plato.pk, valores_viejos, _descripcion_plato(plato))


class PlatoEstadoView(APIView):
    """POST /api/platos/5/estado/: cambia entre disponible y no disponible."""

    permission_classes = [PermisoDeModulo]
    modulo = "platos"
    accion = "modificar"

    def post(self, request, pk):
        with transaction.atomic():
            plato = get_object_or_404(Plato, pk=pk)
            anterior = "Disponible" if plato.estado_plato else "No disponible"
            plato.estado_plato = not plato.estado_plato
            plato.save()
            actual = "Disponible" if plato.estado_plato else "No disponible"
            motivo = str(request.data.get("motivo") or "").strip()[:250]
            _auditar(request, "Plato", "MODIFICAR", plato.pk, f"Estado: {anterior}", f"Estado: {actual}" + (f". Motivo: {motivo}" if motivo else ""))
        return Response(PlatoSerializer(plato).data)


# ---------- BEBIDAS ----------
def _descripcion_bebida(bebida):
    return f"Nombre: {bebida.nombre_bebida}, Precio: {bebida.precio_bebida}"


class BebidaListaView(generics.ListCreateAPIView):
    """GET /api/bebidas/ lista todas. POST /api/bebidas/ crea una."""

    queryset = Bebida.objects.select_related("id_tipo_bebida").order_by("nombre_bebida")
    serializer_class = BebidaSerializer
    permission_classes = [PermisoDeModulo]
    modulo = "bebidas"

    def perform_create(self, serializer):
        with transaction.atomic():
            bebida = serializer.save()
            _auditar(self.request, "Bebida", "CREAR", bebida.pk, "", _descripcion_bebida(bebida))


class BebidaDetalleView(generics.RetrieveUpdateDestroyAPIView):
    """GET /api/bebidas/5/ devuelve una, PATCH la edita y DELETE la elimina.

    Solo se elimina si está no disponible hace 2 meses. Las comandas viejas guardan su nombre y precio.
    """

    queryset = Bebida.objects.select_related("id_tipo_bebida")
    serializer_class = BebidaSerializer
    permission_classes = [PermisoDeModulo]
    modulo = "bebidas"
    http_method_names = ["get", "patch", "delete", "head", "options"]

    def perform_destroy(self, instance):
        anterior, identificador = _descripcion_bebida(instance), instance.pk
        with transaction.atomic():
            _ejecutar(eliminar_bebida, instance)
            _auditar(self.request, "Bebida", "ELIMINAR", identificador, anterior, "Bebida eliminada")

    def perform_update(self, serializer):
        valores_viejos = _descripcion_bebida(serializer.instance)
        with transaction.atomic():
            bebida = serializer.save()
            _auditar(self.request, "Bebida", "MODIFICAR", bebida.pk, valores_viejos, _descripcion_bebida(bebida))


class BebidaEstadoView(APIView):
    """POST /api/bebidas/5/estado/: cambia entre disponible y no disponible."""

    permission_classes = [PermisoDeModulo]
    modulo = "bebidas"
    accion = "modificar"

    def post(self, request, pk):
        with transaction.atomic():
            bebida = get_object_or_404(Bebida, pk=pk)
            anterior = "Disponible" if bebida.disponible_bebida else "No disponible"
            bebida.disponible_bebida = not bebida.disponible_bebida
            bebida.save()
            actual = "Disponible" if bebida.disponible_bebida else "No disponible"
            motivo = str(request.data.get("motivo") or "").strip()[:250]
            _auditar(request, "Bebida", "MODIFICAR", bebida.pk, f"Estado: {anterior}", f"Estado: {actual}" + (f". Motivo: {motivo}" if motivo else ""))
        return Response(BebidaSerializer(bebida).data)


# ---------- MESAS ----------
def _describir_mesa(mesa):
    return f"N° {mesa.numero_mesa}, Ubicación: {mesa.ubicacion}"


class MesaListaView(generics.ListCreateAPIView):
    """GET /api/mesas/ lista las mesas con su estado y su comanda abierta. POST crea una."""

    queryset = Mesa.objects.order_by("numero_mesa")
    serializer_class = MesaSerializer
    permission_classes = [PermisoDeModulo]
    modulo = "mesas"

    def perform_create(self, serializer):
        with transaction.atomic():
            mesa = serializer.save()
            _auditar(self.request, "Mesa", "CREAR", mesa.pk, "", f"Mesa creada: {_describir_mesa(mesa)}")


class MesaDetalleView(generics.RetrieveUpdateDestroyAPIView):
    """GET /api/mesas/5/ devuelve una. PATCH la edita. DELETE la elimina si nunca tuvo comandas."""

    queryset = Mesa.objects.all()
    serializer_class = MesaSerializer
    permission_classes = [PermisoDeModulo]
    modulo = "mesas"
    http_method_names = ["get", "patch", "delete", "head", "options"]

    def perform_update(self, serializer):
        anterior = _describir_mesa(serializer.instance)
        with transaction.atomic():
            mesa = serializer.save()
            _auditar(self.request, "Mesa", "MODIFICAR", mesa.pk, anterior, _describir_mesa(mesa))

    def perform_destroy(self, mesa):
        # Las comandas guardan la mesa: borrarla rompería el historial
        if mesa.comandas.exists():
            raise ValidationError(
                {"detail": f"No se puede eliminar la mesa {mesa.numero_mesa} porque tiene comandas registradas."}
            )
        anterior = f"Mesa {_describir_mesa(mesa)} eliminada"
        identificador = mesa.pk
        with transaction.atomic():
            mesa.delete()
            _auditar(self.request, "Mesa", "ELIMINAR", identificador, anterior, "")


class MesaEstadoView(APIView):
    """POST /api/mesas/5/estado/: alterna entre disponible y ocupada."""

    permission_classes = [PermisoDeModulo]
    modulo = "mesas"
    accion = "modificar"

    def post(self, request, pk):
        mesa = _ejecutar(cambiar_estado_mesa, pk, request.user.empleado)
        return Response(MesaSerializer(mesa).data)


# ---------- COMANDAS ----------
class ComandaListaView(APIView):
    """GET /api/comandas/ lista las últimas 100. POST /api/comandas/ crea una.

    Filtros opcionales: ?mesa=5 y ?abiertas=1
    """

    permission_classes = [PermisoDeModulo]
    modulo = "comandas"

    def get(self, request):
        comandas = Comanda.objects.select_related("mesa", "empleado").order_by("-fecha_hora")
        mesa = request.query_params.get("mesa", "")
        if mesa.isdigit():
            comandas = comandas.filter(mesa_id=int(mesa))
        if request.query_params.get("abiertas") == "1":
            comandas = comandas.filter(estado_comanda__in=ESTADOS_ABIERTOS)
        return Response(ComandaSerializer(comandas[:100], many=True).data)

    def post(self, request):
        comanda = _ejecutar(
            crear_comanda,
            request.data.get("mesa"),
            request.user.empleado,
            str(request.data.get("observaciones") or "").strip(),
            request.data.get("items"),
        )
        return Response(ComandaDetalleSerializer(comanda).data, status=status.HTTP_201_CREATED)


class ComandaDetalleView(APIView):
    """GET /api/comandas/5/ devuelve una. PATCH /api/comandas/5/ cambia sus productos."""

    permission_classes = [PermisoDeModulo]
    modulo = "comandas"

    def get(self, request, pk):
        return Response(ComandaDetalleSerializer(get_object_or_404(Comanda, pk=pk)).data)

    def patch(self, request, pk):
        observaciones = request.data.get("observaciones")
        comanda = _ejecutar(
            actualizar_comanda,
            pk,
            request.user.empleado,
            None if observaciones is None else str(observaciones).strip(),
            request.data.get("items"),
        )
        return Response(ComandaDetalleSerializer(comanda).data)

    def delete(self, request, pk):
        """Elimina una comanda abierta y sin pagos, y libera la mesa. Requiere permiso de eliminar."""
        with transaction.atomic():
            comanda = get_object_or_404(Comanda.objects.select_for_update(), pk=pk)
            if not comanda.puede_modificarse:
                raise ValidationError(
                    {"detail": f"La comanda #{comanda.id_comanda} está cerrada o tiene pagos registrados: no se puede eliminar."}
                )
            anterior = f"Mesa: {comanda.mesa.numero_mesa}. Total: ${comanda.total_comanda}"
            comanda.mesa.estado_mesa = True
            comanda.mesa.save()
            comanda.delete()
            _auditar(request, "Comanda", "ELIMINAR", pk, anterior, "Comanda eliminada")
        return Response(status=status.HTTP_204_NO_CONTENT)


class ComandaConsultaView(APIView):
    """GET /api/comandas/consulta/: todas las comandas, por páginas y con filtros.

    Filtros: ?buscar=, ?estado=pendiente,pagado, ?mesa=5,7, ?fecha_desde=AAAA-MM-DD, ?fecha_hasta=
    """

    permission_classes = [PermisoDeModulo]
    modulo = "comandas"

    def get(self, request):
        comandas = Comanda.objects.select_related("mesa", "empleado").order_by("-fecha_hora")
        buscar = request.query_params.get("buscar", "").strip()
        if buscar:
            filtro = Q(empleado__nombre_empleado__icontains=buscar) | Q(
                empleado__apellido_empleado__icontains=buscar
            )
            if buscar.lstrip("#").isdigit():
                filtro |= Q(id_comanda=int(buscar.lstrip("#")))
            comandas = comandas.filter(filtro)
        estados = [e for e in request.query_params.get("estado", "").split(",") if e]
        if estados:
            comandas = comandas.filter(estado_comanda__in=estados)
        # Una o varias mesas: ?mesa=5 o ?mesa=5,7
        mesas = [int(m) for m in request.query_params.get("mesa", "").split(",") if m.isdigit()]
        if mesas:
            comandas = comandas.filter(mesa_id__in=mesas)
        desde, hasta = rango_pedido(request)
        comandas = filtrar_entre_fechas(comandas, "fecha_hora", desde, hasta)
        return responder_paginado(
            request, comandas, lambda comanda: ComandaSerializer(comanda).data,
            {"fecha_desde": desde, "fecha_hasta": hasta},
        )


class ComandaProductosView(APIView):
    """GET /api/comandas/productos/: lo que se puede pedir. Solo requiere ver comandas."""

    permission_classes = [PermisoDeModulo]
    modulo = "comandas"

    def get(self, request):
        platos = Plato.objects.filter(estado_plato=True).select_related("categoria").order_by("nombre_plato")
        bebidas = Bebida.objects.filter(disponible_bebida=True).select_related("id_tipo_bebida").order_by("nombre_bebida")
        return Response(
            [
                {
                    "tipo": "plato",
                    "id": plato.id_plato,
                    "nombre": plato.nombre_plato,
                    "precio": str(plato.precio_plato),
                    "categoria": plato.categoria.nombre_categoria_plato,
                }
                for plato in platos
            ]
            + [
                {
                    "tipo": "bebida",
                    "id": bebida.id_bebida,
                    "nombre": bebida.nombre_bebida,
                    "precio": str(bebida.precio_bebida),
                    "categoria": bebida.id_tipo_bebida.nombre_tipo_bebida,
                }
                for bebida in bebidas
            ]
        )


class ComandaEstadoView(APIView):
    """POST /api/comandas/5/estado/: cambia el estado. Para anular, requiere un motivo."""

    permission_classes = [PermisoDeModulo]
    modulo = "comandas"
    accion = "modificar"

    def post(self, request, pk):
        comanda = _ejecutar(
            cambiar_estado_comanda,
            pk,
            request.data.get("estado"),
            request.user.empleado,
            str(request.data.get("motivo") or ""),
        )
        return Response(ComandaDetalleSerializer(comanda).data)


class ComandaPagoView(APIView):
    """POST /api/comandas/5/pago/: registra un pago total o parcial."""

    permission_classes = [PermisoDeModulo]
    modulo = "comandas"
    accion = "modificar"

    def post(self, request, pk):
        with transaction.atomic():
            comanda, _, _ = _ejecutar(
                registrar_pago,
                pk,
                request.data.get("tipo_pago"),
                request.data.get("metodo_pago"),
                request.data.get("monto"),
                request.user.empleado,
            )
        return Response(ComandaDetalleSerializer(comanda).data)
