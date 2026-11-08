"""Finanzas en la API: categorías de gasto, métodos de pago, cajas, gastos y ventas.

Usa las mismas reglas que la web de Django. Todo pide el permiso del módulo "caja",
salvo las ventas, que piden el del módulo "ventas".
"""
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from finanzas.models import Venta, caja, categoria_gasto, gasto, metodo_pago
from ventas.models import Comanda

from .permisos import PermisoDeModulo
from .utilidades import filtrar_entre_fechas, leer_monto, leer_texto, rango_pedido, responder_paginado
from .views import _auditar

MAXIMO_OBSERVACIONES = 1000


def _activo(valor):
    return "Activo" if valor else "Inactivo"


def _nombre(empleado):
    return empleado.get_full_name() if empleado else None


def _caja_abierta():
    return caja.objects.filter(estado_caja="abierto").first()


# ---------- CATEGORÍAS DE GASTO ----------
class CategoriaGastoSerializer(serializers.ModelSerializer):
    total_gastos = serializers.SerializerMethodField()

    class Meta:
        model = categoria_gasto
        fields = [
            "id_categoria_gasto",
            "nombre_categoria_gasto",
            "descripcion_categoria_gasto",
            "estado_categoria_gasto",
            "total_gastos",
        ]
        read_only_fields = ["id_categoria_gasto", "estado_categoria_gasto"]
        extra_kwargs = {"nombre_categoria_gasto": {"validators": []}}

    def get_total_gastos(self, categoria):
        return categoria.gastos.count()

    def validate_nombre_categoria_gasto(self, nombre):
        nombre = nombre.strip().title()
        if not nombre:
            raise serializers.ValidationError("El nombre de la categoría es obligatorio.")
        repetidas = categoria_gasto.objects.filter(nombre_categoria_gasto__iexact=nombre)
        if self.instance:
            repetidas = repetidas.exclude(pk=self.instance.pk)
        if repetidas.exists():
            raise serializers.ValidationError("Ya existe una categoría con ese nombre.")
        return nombre


def _describir_categoria(categoria):
    return (
        f"Nombre: {categoria.nombre_categoria_gasto}, "
        f"Descripción: {categoria.descripcion_categoria_gasto}, "
        f"Estado: {categoria.estado_categoria_gasto}"
    )


class CategoriaGastoListaView(APIView):
    """GET /api/categorias-gasto/ lista todas. POST crea una."""

    permission_classes = [PermisoDeModulo]
    modulo = "caja"

    def get(self, request):
        categorias = categoria_gasto.objects.order_by("nombre_categoria_gasto")
        return Response(CategoriaGastoSerializer(categorias, many=True).data)

    def post(self, request):
        serializer = CategoriaGastoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            categoria = serializer.save()
            _auditar(request, "Categoria gastos", "CREAR", categoria.pk, "", _describir_categoria(categoria))
        return Response(CategoriaGastoSerializer(categoria).data, status=status.HTTP_201_CREATED)


class CategoriaGastoDetalleView(APIView):
    """PATCH la edita y DELETE la elimina. Ninguno se permite si ya tiene gastos."""

    permission_classes = [PermisoDeModulo]
    modulo = "caja"

    def _sin_gastos(self, categoria, accion):
        if categoria.gastos.exists():
            raise ValidationError(
                {"detail": f"No se puede {accion} esta categoría porque ya tiene gastos asociados."}
            )

    def patch(self, request, pk):
        categoria = get_object_or_404(categoria_gasto, pk=pk)
        self._sin_gastos(categoria, "modificar")
        anterior = _describir_categoria(categoria)
        serializer = CategoriaGastoSerializer(categoria, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            categoria = serializer.save()
            _auditar(request, "Categoria gastos", "MODIFICAR", categoria.pk, anterior, _describir_categoria(categoria))
        return Response(CategoriaGastoSerializer(categoria).data)

    def delete(self, request, pk):
        categoria = get_object_or_404(categoria_gasto, pk=pk)
        self._sin_gastos(categoria, "eliminar")
        anterior = _describir_categoria(categoria)
        identificador = categoria.pk
        with transaction.atomic():
            # La web registra la eliminación de categorías como ANULAR
            _auditar(request, "Categoria gastos", "ANULAR", identificador, anterior, "Categoría eliminada")
            categoria.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CategoriaGastoEstadoView(APIView):
    """POST /api/categorias-gasto/5/estado/: alterna entre activa e inactiva."""

    permission_classes = [PermisoDeModulo]
    modulo = "caja"
    accion = "modificar"

    def post(self, request, pk):
        with transaction.atomic():
            categoria = get_object_or_404(categoria_gasto.objects.select_for_update(), pk=pk)
            anterior = _describir_categoria(categoria)
            categoria.estado_categoria_gasto = not categoria.estado_categoria_gasto
            categoria.save(update_fields=["estado_categoria_gasto"])
            # Igual que la web: desactivar es ANULAR y reactivar es MODIFICAR
            accion = "MODIFICAR" if categoria.estado_categoria_gasto else "ANULAR"
            _auditar(request, "Categoria gastos", accion, categoria.pk, anterior, _describir_categoria(categoria))
        return Response(CategoriaGastoSerializer(categoria).data)


# ---------- MÉTODOS DE PAGO ----------
class MetodoPagoSerializer(serializers.ModelSerializer):
    total_ventas = serializers.SerializerMethodField()

    class Meta:
        model = metodo_pago
        fields = [
            "id_metodo_pago",
            "nombre_metodo_pago",
            "descripcion_metodo_pago",
            "estado_metodo_pago",
            "total_ventas",
        ]
        read_only_fields = ["id_metodo_pago", "estado_metodo_pago"]
        extra_kwargs = {"nombre_metodo_pago": {"validators": []}}

    def get_total_ventas(self, metodo):
        return Venta.objects.filter(metodo_pago_venta=metodo).count()

    def validate_nombre_metodo_pago(self, nombre):
        nombre = nombre.strip().title()
        if not nombre:
            raise serializers.ValidationError("El nombre del método de pago es obligatorio.")
        repetidos = metodo_pago.objects.filter(nombre_metodo_pago__iexact=nombre)
        if self.instance:
            repetidos = repetidos.exclude(pk=self.instance.pk)
        if repetidos.exists():
            raise serializers.ValidationError("Ya existe un método de pago con ese nombre.")
        return nombre


def _describir_metodo(metodo):
    return f"Nombre: {metodo.nombre_metodo_pago}, Estado: {_activo(metodo.estado_metodo_pago)}"


class MetodoPagoListaView(APIView):
    """GET /api/metodos-pago/ lista todos. POST crea uno."""

    permission_classes = [PermisoDeModulo]
    modulo = "caja"

    def get(self, request):
        metodos = metodo_pago.objects.order_by("nombre_metodo_pago")
        return Response(MetodoPagoSerializer(metodos, many=True).data)

    def post(self, request):
        serializer = MetodoPagoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            metodo = serializer.save()
            _auditar(request, "Metodo de pago", "CREAR", metodo.pk, "", _describir_metodo(metodo))
        return Response(MetodoPagoSerializer(metodo).data, status=status.HTTP_201_CREATED)


class MetodoPagoDetalleView(APIView):
    """PATCH lo edita. DELETE lo elimina si no tiene ventas."""

    permission_classes = [PermisoDeModulo]
    modulo = "caja"

    def patch(self, request, pk):
        metodo = get_object_or_404(metodo_pago, pk=pk)
        anterior = _describir_metodo(metodo)
        serializer = MetodoPagoSerializer(metodo, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            metodo = serializer.save()
            _auditar(request, "Metodo de pago", "MODIFICAR", metodo.pk, anterior, _describir_metodo(metodo))
        return Response(MetodoPagoSerializer(metodo).data)

    def delete(self, request, pk):
        metodo = get_object_or_404(metodo_pago, pk=pk)
        if Venta.objects.filter(metodo_pago_venta=metodo).exists():
            raise ValidationError(
                {"detail": f'No se puede eliminar "{metodo.nombre_metodo_pago}" porque está asociado a una o más ventas.'}
            )
        anterior = _describir_metodo(metodo)
        identificador = metodo.pk
        with transaction.atomic():
            metodo.delete()
            _auditar(request, "Metodo de pago", "ELIMINAR", identificador, anterior, "Método eliminado")
        return Response(status=status.HTTP_204_NO_CONTENT)


class MetodoPagoEstadoView(APIView):
    """POST /api/metodos-pago/5/estado/: alterna entre activo e inactivo."""

    permission_classes = [PermisoDeModulo]
    modulo = "caja"
    accion = "modificar"

    def post(self, request, pk):
        with transaction.atomic():
            metodo = get_object_or_404(metodo_pago.objects.select_for_update(), pk=pk)
            anterior = _describir_metodo(metodo)
            metodo.estado_metodo_pago = not metodo.estado_metodo_pago
            metodo.save()
            _auditar(request, "Metodo de pago", "MODIFICAR", metodo.pk, anterior, _describir_metodo(metodo))
        return Response(MetodoPagoSerializer(metodo).data)


# ---------- CAJAS ----------
def _caja_a_dict(c):
    return {
        "id_caja": c.id_caja,
        "estado_caja": c.estado_caja,
        "fecha_apertura": c.fecha_apertura,
        "empleado_apertura": _nombre(c.empleado_apertura),
        "saldo_inicial": str(c.saldo_inicial),
        "observaciones_apertura": c.observaciones_apertura,
        "fecha_arqueo": c.fecha_arqueo,
        "empleado_arqueo": _nombre(c.empleado_arqueamiento),
        "saldo_esperado": str(c.saldo_esperado),
        "saldo_contado": str(c.saldo_contado),
        "diferencia_caja": str(c.diferencia_caja),
        "observaciones_arqueo": c.observaciones_arqueo,
        "fecha_cierre": c.fecha_cierre,
        "empleado_cierre": _nombre(c.empleado_cierre),
        "saldo_final": str(c.saldo_final),
        "observaciones_cierre": c.observaciones_cierre,
    }


def _gasto_a_dict(g):
    return {
        "id_gasto": g.id_gasto,
        "descripcion_gasto": g.descripcion_gasto,
        "monto_gasto": str(g.monto_gasto),
        "fecha_hora_gasto": g.fecha_hora_gasto,
        "caja": g.caja_gasto_id,
        "caja_abierta": g.caja_gasto.estado_caja == "abierto",
        "categoria": g.cat_gasto_id,
        "categoria_nombre": g.cat_gasto.nombre_categoria_gasto,
        "empleado": _nombre(g.empleado_gasto),
    }


def _cajas():
    return caja.objects.select_related("empleado_apertura", "empleado_cierre", "empleado_arqueamiento")


class CajaListaView(APIView):
    """GET /api/cajas/ lista por páginas (?buscar, ?estado, ?fecha_desde, ?fecha_hasta). POST abre una."""

    permission_classes = [PermisoDeModulo]
    modulo = "caja"

    def get(self, request):
        cajas = _cajas().order_by("-fecha_apertura")
        buscar = request.query_params.get("buscar", "").strip()
        if buscar:
            filtro = Q(empleado_apertura__nombre_empleado__icontains=buscar) | Q(
                empleado_apertura__apellido_empleado__icontains=buscar
            )
            if buscar.isdigit():
                filtro |= Q(id_caja=int(buscar))
            cajas = cajas.filter(filtro)
        estado = request.query_params.get("estado", "")
        if estado in ("abierto", "cerrado"):
            cajas = cajas.filter(estado_caja=estado)
        desde, hasta = rango_pedido(request)
        cajas = filtrar_entre_fechas(cajas, "fecha_apertura", desde, hasta)
        abierta = _caja_abierta()
        return responder_paginado(
            request, cajas, _caja_a_dict, {"caja_abierta": abierta.id_caja if abierta else None}
        )

    def post(self, request):
        saldo = leer_monto(
            request.data.get("saldo_inicial"), "saldo_inicial",
            "El saldo inicial debe ser un número válido y no negativo.", permitir_cero=True,
        )
        observaciones = leer_texto(
            request, "observaciones_apertura", MAXIMO_OBSERVACIONES, "Las observaciones de apertura"
        )
        with transaction.atomic():
            # Bloquea las cajas abiertas para que dos personas no abran una a la vez
            abierta = caja.objects.select_for_update().filter(estado_caja="abierto").first()
            if abierta:
                raise ValidationError(
                    {"detail": f"No se puede abrir otra caja. La caja N.º {abierta.id_caja} ya se encuentra abierta."}
                )
            nueva = caja.objects.create(
                empleado_apertura=request.user.empleado,
                saldo_inicial=saldo,
                observaciones_apertura=observaciones,
                observaciones_caja=observaciones,
                estado_caja="abierto",
            )
            _auditar(request, "Caja", "CREAR", nueva.pk, "", f"Caja abierta. Saldo inicial: ${saldo}")
        return Response(_caja_a_dict(_cajas().get(pk=nueva.pk)), status=status.HTTP_201_CREATED)


class CajaDetalleView(APIView):
    """GET /api/cajas/5/: la caja, sus gastos y el saldo que debería haber."""

    permission_classes = [PermisoDeModulo]
    modulo = "caja"

    def get(self, request, pk):
        actual = get_object_or_404(_cajas(), pk=pk)
        datos = _caja_a_dict(actual)
        gastos = actual.gastos.select_related("cat_gasto", "empleado_gasto", "caja_gasto").order_by(
            "-fecha_hora_gasto"
        )
        datos["gastos"] = [_gasto_a_dict(g) for g in gastos]
        datos["total_egresos"] = str(actual.calcular_total_egresos())
        datos["saldo_esperado_actual"] = str(actual.calcular_saldo_esperado())
        datos["total_ventas"] = str(sum((v.total_venta for v in actual.ventas.all()), 0))
        return Response(datos)


class CajaArqueoView(APIView):
    """POST /api/cajas/5/arqueo/ con {saldo_contado, observaciones_arqueo}."""

    permission_classes = [PermisoDeModulo]
    modulo = "caja"
    accion = "modificar"

    def post(self, request, pk):
        contado = leer_monto(
            request.data.get("saldo_contado"), "saldo_contado",
            "El saldo contado debe ser un número válido y no negativo.", permitir_cero=True,
        )
        observaciones = leer_texto(
            request, "observaciones_arqueo", MAXIMO_OBSERVACIONES, "Las observaciones de arqueo"
        )
        with transaction.atomic():
            actual = get_object_or_404(caja.objects.select_for_update(), pk=pk)
            try:
                actual.realizar_arqueo(contado, request.user.empleado, observaciones)
            except ValueError as error:
                raise ValidationError({"detail": str(error)})
            _auditar(
                request, "Caja", "MODIFICAR", actual.pk, "",
                f"Arqueo. Esperado: ${actual.saldo_esperado}. Contado: ${actual.saldo_contado}. "
                f"Diferencia: ${actual.diferencia_caja}",
            )
        return Response(_caja_a_dict(_cajas().get(pk=pk)))


class CajaCierreView(APIView):
    """POST /api/cajas/5/cierre/ con {observaciones_cierre}."""

    permission_classes = [PermisoDeModulo]
    modulo = "caja"
    accion = "modificar"

    def post(self, request, pk):
        observaciones = leer_texto(
            request, "observaciones_cierre", MAXIMO_OBSERVACIONES, "Las observaciones de cierre"
        )
        with transaction.atomic():
            actual = get_object_or_404(caja.objects.select_for_update(), pk=pk)
            try:
                actual.cerrar_caja(request.user.empleado, observaciones)
            except ValueError as error:
                raise ValidationError({"detail": str(error)})
            _auditar(
                request, "Caja", "MODIFICAR", actual.pk, "Estado: abierto",
                f"Estado: cerrado. Saldo final: ${actual.saldo_final}",
            )
        return Response(_caja_a_dict(_cajas().get(pk=pk)))


# ---------- GASTOS ----------
def _gastos():
    return gasto.objects.select_related("caja_gasto", "cat_gasto", "empleado_gasto")


def _describir_gasto(g):
    return f"Descripción: {g.descripcion_gasto}, Monto: ${g.monto_gasto}, Categoría: {g.cat_gasto}"


def _leer_gasto(request, categoria_actual=None):
    """Valida descripción, monto y categoría. Una categoría inactiva solo vale si el gasto ya la tenía."""
    descripcion = leer_texto(request, "descripcion_gasto")
    if not descripcion:
        raise ValidationError({"descripcion_gasto": ["La descripción es obligatoria."]})
    monto = leer_monto(
        request.data.get("monto_gasto"), "monto_gasto", "El monto debe ser un número válido mayor que cero."
    )
    identificador = str(request.data.get("cat_gasto") or "")
    categoria = (
        categoria_gasto.objects.filter(pk=int(identificador)).first() if identificador.isdigit() else None
    )
    if not categoria or (not categoria.estado_categoria_gasto and categoria.pk != categoria_actual):
        raise ValidationError({"cat_gasto": ["Seleccioná una categoría de gasto activa."]})
    return descripcion, monto, categoria


class GastoListaView(APIView):
    """GET /api/gastos/ lista por páginas (?buscar). POST registra uno en la caja abierta."""

    permission_classes = [PermisoDeModulo]
    modulo = "caja"

    def get(self, request):
        gastos = _gastos().order_by("-fecha_hora_gasto")
        buscar = request.query_params.get("buscar", "").strip()
        if buscar:
            gastos = gastos.filter(
                Q(descripcion_gasto__icontains=buscar) | Q(cat_gasto__nombre_categoria_gasto__icontains=buscar)
            )
        abierta = _caja_abierta()
        return responder_paginado(
            request, gastos, _gasto_a_dict, {"caja_abierta": abierta.id_caja if abierta else None}
        )

    def post(self, request):
        descripcion, monto, categoria = _leer_gasto(request)
        with transaction.atomic():
            abierta = caja.objects.select_for_update().filter(estado_caja="abierto").first()
            if not abierta:
                raise ValidationError(
                    {"detail": "No hay una caja abierta. Debés abrir una caja antes de registrar gastos."}
                )
            nuevo = gasto.objects.create(
                descripcion_gasto=descripcion,
                monto_gasto=monto,
                caja_gasto=abierta,
                cat_gasto=categoria,
                empleado_gasto=request.user.empleado,
            )
            _auditar(request, "Gasto", "CREAR", nuevo.pk, "", f"Caja {abierta.id_caja}. {_describir_gasto(nuevo)}")
        return Response(_gasto_a_dict(_gastos().get(pk=nuevo.pk)), status=status.HTTP_201_CREATED)


class GastoDetalleView(APIView):
    """GET devuelve uno. PATCH lo edita y DELETE lo elimina, solo si su caja sigue abierta."""

    permission_classes = [PermisoDeModulo]
    modulo = "caja"

    def get(self, request, pk):
        return Response(_gasto_a_dict(get_object_or_404(_gastos(), pk=pk)))

    def _exigir_caja_abierta(self, actual, accion):
        if actual.caja_gasto.estado_caja != "abierto":
            raise ValidationError({"detail": f"No se pueden {accion} gastos de una caja cerrada."})

    def patch(self, request, pk):
        actual = get_object_or_404(_gastos(), pk=pk)
        self._exigir_caja_abierta(actual, "modificar")
        descripcion, monto, categoria = _leer_gasto(request, actual.cat_gasto_id)
        anterior = _describir_gasto(actual)
        with transaction.atomic():
            actual.descripcion_gasto = descripcion
            actual.monto_gasto = monto
            actual.cat_gasto = categoria
            actual.save()
            _auditar(request, "Gasto", "MODIFICAR", actual.pk, anterior, _describir_gasto(actual))
        return Response(_gasto_a_dict(actual))

    def delete(self, request, pk):
        actual = get_object_or_404(_gastos(), pk=pk)
        self._exigir_caja_abierta(actual, "eliminar")
        anterior = _describir_gasto(actual)
        with transaction.atomic():
            actual.delete()
            _auditar(request, "Gasto", "ELIMINAR", pk, anterior, "Gasto eliminado")
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------- VENTAS ----------
def _venta_a_dict(v):
    return {
        "id_venta": v.id_venta,
        "fecha_venta": v.fecha_venta,
        "comanda": v.comanda_id,
        "mesa": v.comanda.mesa.numero_mesa,
        "metodo": v.metodo_pago_venta.nombre_metodo_pago,
        "caja": v.caja_venta_id,
        "empleado": _nombre(v.empleado_venta),
        "total_venta": str(v.total_venta),
        "monto_recibido": str(v.monto_recibido),
        "vuelto": str(v.vuelto),
    }


def _comandas_para_vender():
    """Comandas entregadas, sin venta y con saldo: las mismas que ofrece la web."""
    return (
        Comanda.objects.filter(estado_comanda="entregado", ventas__isnull=True)
        .select_related("mesa")
        .order_by("fecha_hora")
    )


class VentaListaView(APIView):
    """GET /api/ventas/ lista por páginas, con lo necesario para registrar una. POST registra una."""

    permission_classes = [PermisoDeModulo]
    modulo = "ventas"

    def get(self, request):
        ventas = Venta.objects.select_related(
            "comanda__mesa", "metodo_pago_venta", "empleado_venta"
        ).order_by("-fecha_venta")
        desde, hasta = rango_pedido(request)
        ventas = filtrar_entre_fechas(ventas, "fecha_venta", desde, hasta)
        abierta = _caja_abierta()
        pendientes = [
            {
                "id_comanda": comanda.id_comanda,
                "mesa": comanda.mesa.numero_mesa,
                "saldo": str(comanda.saldo_pendiente),
            }
            for comanda in _comandas_para_vender()
            if comanda.saldo_pendiente > 0
        ]
        metodos = list(
            metodo_pago.objects.filter(estado_metodo_pago=True)
            .order_by("nombre_metodo_pago")
            .values("id_metodo_pago", "nombre_metodo_pago")
        )
        return responder_paginado(
            request, ventas, _venta_a_dict,
            {
                "caja_abierta": abierta.id_caja if abierta else None,
                "comandas_pendientes": pendientes,
                "metodos_pago": metodos,
            },
        )

    def post(self, request):
        recibido = leer_monto(
            request.data.get("monto_recibido"), "monto_recibido",
            "El monto recibido no es válido.", permitir_cero=True,
        )
        metodo_id = str(request.data.get("metodo_pago") or "")
        comanda_id = str(request.data.get("comanda") or "")
        if not comanda_id.isdigit():
            raise ValidationError({"comanda": ["Seleccioná una comanda."]})
        metodo = (
            metodo_pago.objects.filter(pk=int(metodo_id), estado_metodo_pago=True).first()
            if metodo_id.isdigit()
            else None
        )
        if not metodo:
            raise ValidationError({"metodo_pago": ["Seleccioná un método de pago activo."]})

        with transaction.atomic():
            # Bloquea la comanda para que no se cobre dos veces a la vez
            comanda = get_object_or_404(
                Comanda.objects.select_for_update().select_related("mesa"), pk=int(comanda_id)
            )
            if Venta.objects.filter(comanda=comanda).exists():
                raise ValidationError({"detail": "Esta comanda ya tiene una venta registrada."})
            if comanda.estado_comanda != "entregado":
                raise ValidationError({"detail": "Solo se pueden vender comandas entregadas."})
            abierta = caja.objects.select_for_update().filter(estado_caja="abierto").first()
            if not abierta:
                raise ValidationError(
                    {"detail": "No se puede registrar la venta porque no hay una caja abierta."}
                )
            # Si ya hubo pagos parciales, solo se cobra lo que falta
            total = comanda.saldo_pendiente
            if total <= 0:
                raise ValidationError({"detail": "El total de la comanda no es válido."})
            if recibido < total:
                raise ValidationError({"monto_recibido": ["El monto recibido es menor al total de la comanda."]})

            venta = Venta.objects.create(
                comanda=comanda,
                metodo_pago_venta=metodo,
                caja_venta=abierta,
                empleado_venta=request.user.empleado,
                total_venta=total,
                monto_recibido=recibido,
                vuelto=recibido - total,
            )
            comanda.estado_comanda = "pagado"
            comanda.save(update_fields=["estado_comanda"])
            comanda.mesa.estado_mesa = True
            comanda.mesa.save(update_fields=["estado_mesa"])
            _auditar(
                request, "Venta", "CREAR", venta.pk, "",
                f"Comanda #{comanda.id_comanda}. Total: ${total}. Método: {metodo}. Caja: {abierta.id_caja}",
            )
        venta = Venta.objects.select_related("comanda__mesa", "metodo_pago_venta", "empleado_venta").get(pk=venta.pk)
        return Response(_venta_a_dict(venta), status=status.HTTP_201_CREATED)
