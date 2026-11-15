"""Plano del local de Los Cardones, tomado del plano que entregó el restaurante.

Las medidas están en los píxeles del plano original; la vista las pasa a porcentajes
para que el dibujo se adapte al ancho de la pantalla. Cada mesa se une con la mesa
cargada en el sistema por su número.

Numeración: se respetan las 11 mesas que ya estaban cargadas (patio 6-10; salón 2, 3, 4,
11, 13 y 14). Para cambiar la disposición del local, se edita solo este archivo.
"""

# Parte del plano que se dibuja (x, y, ancho, alto)
LIENZO = (190, 140, 1810, 425)

MESA_LADO = 54

# Zonas: el patio de afuera y el interior del local
ZONAS = [
    {"nombre": "Patio", "x": 196, "y": 168, "ancho": 172, "alto": 380, "clase": "zona-patio"},
    {"nombre": "Salón", "x": 397, "y": 155, "ancho": 1228, "alto": 405, "clase": "zona-salon"},
    {"nombre": "Cocina y servicios", "x": 1627, "y": 155, "ancho": 363, "alto": 405, "clase": "zona-servicio"},
]

# Elementos fijos, como referencia para ubicarse
ELEMENTOS = [
    {"nombre": "Escenario", "x": 839, "y": 453, "ancho": 308, "alto": 81, "clase": "elemento-destacado"},
    {"nombre": "Barra de caja", "x": 1310, "y": 217, "ancho": 199, "alto": 64, "clase": "elemento-destacado"},
    {"nombre": "Barra de tragos", "x": 1566, "y": 288, "ancho": 59, "alto": 152, "clase": "elemento-destacado elemento-vertical"},
    {"nombre": "Vajilla", "x": 1667, "y": 155, "ancho": 185, "alto": 53, "clase": ""},
    {"nombre": "Depósito 2", "x": 1889, "y": 155, "ancho": 99, "alto": 98, "clase": ""},
    {"nombre": "Emplatados", "x": 1662, "y": 271, "ancho": 145, "alto": 54, "clase": ""},
    {"nombre": "Hornos", "x": 1635, "y": 363, "ancho": 46, "alto": 71, "clase": ""},
    {"nombre": "Cocinas", "x": 1689, "y": 363, "ancho": 82, "alto": 71, "clase": ""},
    {"nombre": "Parrilla", "x": 1780, "y": 363, "ancho": 82, "alto": 71, "clase": ""},
    {"nombre": "Depósito", "x": 1892, "y": 313, "ancho": 91, "alto": 90, "clase": ""},
    {"nombre": "Baño hombres", "x": 1627, "y": 444, "ancho": 162, "alto": 53, "clase": ""},
    {"nombre": "Baño de cocina", "x": 1789, "y": 444, "ancho": 201, "alto": 53, "clase": ""},
    {"nombre": "Baño damas", "x": 1753, "y": 497, "ancho": 181, "alto": 63, "clase": ""},
]

# Centro de cada pilar
PILARES = [(640, 199), (966, 199), (640, 299), (966, 299), (1246, 299), (640, 534), (1328, 534)]
PILAR_DIAMETRO = 36


def _fila(numeros, xs, y, capacidades, ubicacion):
    return [
        {"numero": n, "x": x, "y": y, "capacidad": c, "ubicacion": ubicacion}
        for n, x, c in zip(numeros, xs, capacidades)
    ]


# Mesas: número, posición (esquina superior izquierda), lugares y ubicación
MESAS = [
    # Patio (afuera, a la izquierda del local)
    *_fila([5, 6], [206, 297], 182, [4, 4], "patio"),
    *_fila([7, 8], [206, 297], 291, [4, 4], "patio"),
    *_fila([9], [206], 381, [4], "patio"),
    *_fila([10, 12], [206, 306], 481, [4, 4], "patio"),
    # Salón, fila de arriba
    *_fila([1, 2, 3, 4, 11, 13, 14, 15], [468, 549, 694, 785, 857, 1002, 1084, 1156], 173, [4] * 8, "salon"),
    # Salón, segunda fila
    *_fila([16], [468], 254, [2], "salon"),
    *_fila([17, 18, 19, 20, 21, 22], [694, 776, 857, 1002, 1084, 1156], 263, [3, 2, 2, 3, 2, 2], "salon"),
    # Salón, a la izquierda del escenario
    *_fila([23, 24, 25, 26, 27], [413, 486, 558, 658, 731], 417, [4, 4, 4, 4, 6], "salon"),
    *_fila([28, 29, 30, 31, 32], [413, 486, 558, 658, 731], 489, [4] * 5, "salon"),
    # Salón, a la derecha del escenario
    *_fila([33, 34, 35, 36, 37], [1183, 1256, 1364, 1427, 1491], 417, [6, 4, 4, 4, 4], "salon"),
    *_fila([38, 39, 40, 41, 42], [1183, 1256, 1364, 1427, 1491], 489, [4, 4, 4, 4, 6], "salon"),
]


def a_porcentajes(x, y, ancho, alto):
    """Posición dentro del lienzo, en porcentajes (left, top, width, height)."""
    lx, ly, lancho, lalto = LIENZO
    return {
        "left": round((x - lx) * 100 / lancho, 3),
        "top": round((y - ly) * 100 / lalto, 3),
        "width": round(ancho * 100 / lancho, 3),
        "height": round(alto * 100 / lalto, 3),
    }
