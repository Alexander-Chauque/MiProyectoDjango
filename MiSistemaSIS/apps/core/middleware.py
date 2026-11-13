from urllib.parse import urlsplit

# Clave de la sesión donde se guarda la última dirección de cada listado
CLAVE_SESION = "listados_recordados"

# Rutas que no se tienen en cuenta
RUTAS_EXCLUIDAS = ("/api/", "/admin/", "/static/", "/media/")


class RecordarListadoMiddleware:
    """
    Vuelve a la misma página y a los mismos filtros después de guardar.

    1. Cada vez que se ve un listado con parámetros, por ejemplo
       /inventario/platos/listar/?page=3&buscar=empanada, se guarda en la sesión
       con la ruta sin parámetros como clave.
    2. Cuando una vista termina con redirect("inventario:listar_platos"),
       la respuesta lleva a /inventario/platos/listar/, sin parámetros.
       El middleware cambia ese destino por la dirección guardada.

    Así, después de editar, cambiar de estado o eliminar algo en la página 3,
    se vuelve a la página 3 y no a la 1. Las vistas no cambian.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if request.path.startswith(RUTAS_EXCLUIDAS) or not hasattr(request, "session"):
            return response

        if request.method == "GET" and response.status_code == 200:
            self._recordar(request, response)
        elif response.status_code in (301, 302, 303):
            self._corregir_redireccion(request, response)

        return response

    def _recordar(self, request, response):
        # Solo páginas HTML: un PDF o un Excel no son el listado
        if not response.get("Content-Type", "").startswith("text/html"):
            return

        guardados = request.session.get(CLAVE_SESION, {})
        if request.GET:
            direccion = request.get_full_path()
            if guardados.get(request.path) != direccion:
                guardados[request.path] = direccion
                request.session[CLAVE_SESION] = guardados
        elif request.path in guardados:
            # Se abrió el listado sin filtros (por ejemplo, "Limpiar filtros")
            del guardados[request.path]
            request.session[CLAVE_SESION] = guardados

    def _corregir_redireccion(self, request, response):
        destino = urlsplit(response.get("Location", ""))

        # Solo redirecciones dentro del sistema y sin parámetros propios
        if destino.netloc and destino.netloc != request.get_host():
            return
        if destino.query:
            return

        guardada = request.session.get(CLAVE_SESION, {}).get(destino.path)
        if guardada:
            response["Location"] = guardada
