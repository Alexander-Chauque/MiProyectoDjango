# ============================================================
# SCRIPT DE CARGA DE DATOS FALTANTES
# Ejecutar con: Get-Content cargar_datos.py | python manage.py shell
# ============================================================

from empleados.models import PermisoXCargo, Cargo, TipoPermiso
from inventario.models import Ingrediente, DetallePlato, Plato, Bebida
from ventas.models import DetalleComanda, Comanda, Mesa

print("=" * 60)
print("INICIANDO CARGA DE DATOS FALTANTES")
print("=" * 60)

# ============================================================
# 1. PERMISOS X CARGO
# ============================================================
print("\nCargando Permisos por Cargo...")
permisos_x_cargo_data = [
    (407, 7, 40), (408, 7, 39), (409, 7, 20), (410, 7, 18), (411, 7, 17), (412, 7, 19),
    (413, 7, 12), (414, 7, 10), (415, 7, 9), (416, 7, 11), (417, 7, 53), (418, 7, 44),
    (419, 7, 43), (420, 7, 45), (421, 7, 16), (422, 7, 14), (423, 7, 13), (424, 7, 15),
    (425, 7, 33), (426, 7, 8), (427, 7, 6), (428, 7, 5), (429, 7, 7), (430, 7, 52),
    (431, 7, 47), (432, 7, 46), (433, 7, 48), (434, 7, 4), (435, 7, 2), (436, 7, 1),
    (437, 7, 3), (438, 7, 38), (439, 7, 32),
    (440, 4, 1), (441, 4, 9), (442, 4, 46), (443, 4, 48), (444, 4, 43), (445, 4, 44), (446, 4, 45),
]

creados_pxc = 0
for id_pxc, cargo_id, tp_id in permisos_x_cargo_data:
    try:
        cargo = Cargo.objects.get(id_cargo=cargo_id)
        tp = TipoPermiso.objects.get(id_tipo_permiso=tp_id)
        obj, created = PermisoXCargo.objects.get_or_create(
            id_permiso_x_cargo=id_pxc,
            defaults={'cargo': cargo, 'tipo_permiso': tp}
        )
        if created:
            creados_pxc += 1
    except Exception as e:
        print("  Error en PxC " + str(id_pxc) + ": " + str(e))
print("  Permisos x Cargo cargados: " + str(creados_pxc) + " (Total: " + str(PermisoXCargo.objects.count()) + ")")

# ============================================================
# 2. INGREDIENTES FALTANTES
# ============================================================
print("\nCargando Ingredientes faltantes...")
ingredientes_faltantes = [
    (32, 'Tomate', 'gramos', 5000.00, 0),
    (33, 'Zapallo', 'kg', 5000.00, 0),
    (34, 'Carne', 'kg', 12000.00, 0),
    (35, 'Cebolla', 'kg', 2000.00, 0),
    (36, 'Pollo', 'Kg', 80000.00, 0),
    (37, 'Papa', 'Kg', 1000.00, 0),
    (39, 'Sal', 'Kg', 500.00, 0),
    (40, 'Pimienta', 'Kg', 3000.00, 0),
    (41, 'Ajo', 'kg', 2500.00, 0),
    (42, 'Morrón', 'Kg', 3500.00, 0),
    (43, 'Limón', 'Kg', 1800.00, 0),
    (44, 'Pan', 'Un', 500.00, 0),
    (45, 'Leche', 'L', 1200.00, 0),
    (46, 'Queso', 'Kg', 9000.00, 0),
    (47, 'Huevo', 'Un', 300.00, 0),
    (48, 'Harina', 'Kg', 1500.00, 0),
    (49, 'Arroz', 'Kg', 500.00, 0),
    (50, 'Fideo', 'Kg', 900.00, 0),
    (63, 'Choclo', 'unidad', 1500.00, 0),
    (64, 'Harina De Maíz', 'G', 900.00, 0),
    (65, 'Pastas', 'G', 900.00, 0),
    (66, 'Crema', 'G', 2000.00, 0),
    (67, 'Queso Mozzarella', 'G', 10000.00, 0),
    (68, 'Queso Roquefort', 'G', 15000.00, 0),
    (69, 'Pimienta Blanca', 'G', 2900.00, 0),
    (70, 'Lomo', 'G', 8000.00, 0),
    (71, 'Champioñes', 'G', 6000.00, 0),
    (72, 'Perejil', 'Unidad', 1000.00, 0),
    (73, 'Pan Rallado', 'G', 1100.00, 0),
    (74, 'Chorizo', 'Kg', 7200.00, 0),
    (75, 'Costilla', 'Kg', 16000.00, 0),
    (76, 'Vacío', 'Kg', 15000.00, 0),
    (77, 'Morcilla', 'Kg', 6000.00, 0),
    (78, 'Carne De Ternera', 'kg', 8000.00, 1),
    (79, 'Carne De Pollo', 'kg', 4500.00, 1),
    (80, 'Carne De Cerdo', 'kg', 6000.00, 1),
    (81, 'Carne De Cabrito', 'kg', 9000.00, 1),
    (82, 'Carne Picada', 'kg', 5000.00, 1),
    (83, 'Bife De Chorizo', 'kg', 12000.00, 1),
    (84, 'Matambre', 'kg', 7000.00, 1),
    (85, 'Milanesa De Ternera', 'kg', 9000.00, 1),
    (86, 'Chinchulín', 'kg', 6000.00, 1),
    (87, 'Riñón', 'kg', 4000.00, 1),
    (88, 'Corazón', 'kg', 4000.00, 1),
    (89, 'Falda', 'kg', 7000.00, 1),
    (90, 'Zanahoria', 'kg', 900.00, 1),
    (91, 'Lechuga', 'kg', 1000.00, 1),
    (92, 'Batata', 'kg', 1100.00, 1),
    (93, 'Cayote', 'kg', 1200.00, 1),
    (94, 'Tallarines', 'kg', 2500.00, 1),
]

creados_ing = 0
for id_i, nombre, unidad, costo, estado in ingredientes_faltantes:
    obj, created = Ingrediente.objects.get_or_create(
        id_ingrediente=id_i,
        defaults={'nombre_ingrediente': nombre, 'unidad_medida': unidad,
                  'costo_unitario': costo, 'estado_ingrediente': estado}
    )
    if created:
        creados_ing += 1
print("  Ingredientes cargados: " + str(creados_ing) + " (Total: " + str(Ingrediente.objects.count()) + ")")

# ============================================================
# 3. DETALLE PLATO
# ============================================================
print("\nCargando Detalle Plato (recetas)...")
detalle_plato_data = [
    (2, 1, 34, 1),
    (21, 1, 50, 2), (22, 1, 36, 2), (23, 1, 46, 2), (24, 1, 39, 2), (25, 1, 32, 2),
    (26, 1, 82, 5), (27, 1, 35, 5), (28, 1, 47, 5), (29, 1, 105, 5), (30, 1, 104, 5), (31, 1, 48, 5),
    (32, 1, 46, 6), (33, 1, 48, 6), (34, 1, 47, 6),
    (35, 1, 79, 7), (36, 1, 35, 7), (37, 1, 47, 7), (38, 1, 105, 7), (39, 1, 48, 7),
    (40, 1, 99, 8), (41, 1, 48, 8), (42, 1, 47, 8),
    (43, 1, 63, 9), (44, 1, 35, 9), (45, 1, 46, 9), (46, 1, 45, 9), (47, 1, 102, 9),
    (48, 1, 80, 10), (49, 1, 63, 10), (50, 1, 35, 10), (51, 1, 104, 10), (52, 1, 105, 10),
    (53, 1, 125, 11), (54, 1, 63, 11), (55, 1, 35, 11), (56, 1, 104, 11),
    (57, 1, 33, 12), (58, 1, 63, 12), (59, 1, 80, 12), (60, 1, 78, 12), (61, 1, 35, 12), (62, 1, 104, 12), (63, 1, 105, 12),
    (64, 1, 81, 13), (65, 1, 35, 13), (66, 1, 32, 13), (67, 1, 42, 13), (68, 1, 41, 13), (69, 1, 126, 13),
    (70, 1, 94, 14), (71, 1, 113, 14), (72, 1, 46, 14),
    (73, 1, 95, 15), (74, 1, 113, 15), (75, 1, 46, 15),
    (76, 1, 96, 16), (77, 1, 113, 16), (78, 1, 46, 16),
    (79, 1, 97, 17), (80, 1, 113, 17), (81, 1, 46, 17),
    (82, 1, 98, 18), (83, 1, 113, 18), (84, 1, 46, 18),
    (85, 1, 131, 19), (86, 1, 41, 19), (87, 1, 72, 19), (88, 1, 118, 19), (89, 1, 37, 19),
    (90, 1, 79, 20), (91, 1, 42, 20), (92, 1, 35, 20), (93, 1, 90, 20), (94, 1, 127, 20),
    (95, 1, 78, 21), (96, 1, 42, 21), (97, 1, 35, 21), (98, 1, 90, 21), (99, 1, 127, 21),
    (100, 1, 70, 22), (101, 1, 128, 22), (102, 1, 66, 22), (103, 1, 37, 22),
    (104, 1, 70, 23), (105, 1, 40, 23), (106, 1, 66, 23), (107, 1, 37, 23),
    (108, 1, 70, 24), (109, 1, 37, 24), (110, 1, 47, 24),
    (111, 1, 70, 25), (112, 1, 129, 25), (113, 1, 66, 25), (114, 1, 37, 25),
    (115, 1, 70, 26), (116, 1, 114, 26), (117, 1, 66, 26), (118, 1, 37, 26),
    (119, 1, 70, 27), (120, 1, 37, 27), (121, 1, 42, 27), (122, 1, 35, 27),
    (123, 1, 79, 28), (124, 1, 114, 28), (125, 1, 37, 28),
    (126, 1, 79, 29), (127, 1, 129, 29), (128, 1, 66, 29), (129, 1, 37, 29),
    (130, 1, 79, 30), (131, 1, 41, 30), (132, 1, 72, 30), (133, 1, 37, 30),
    (134, 1, 79, 31), (135, 1, 32, 31), (136, 1, 35, 31), (137, 1, 42, 31), (138, 1, 37, 31),
    (139, 1, 85, 32), (140, 1, 73, 32), (141, 1, 47, 32), (142, 1, 37, 32),
    (143, 1, 85, 33), (144, 1, 73, 33), (145, 1, 47, 33), (146, 1, 46, 33), (147, 1, 107, 33), (148, 1, 103, 33), (149, 1, 37, 33),
    (150, 1, 85, 34), (151, 1, 73, 34), (152, 1, 47, 34), (153, 1, 47, 34), (154, 1, 37, 34),
    (155, 1, 85, 35), (156, 1, 73, 35), (157, 1, 47, 35), (158, 1, 46, 35), (159, 1, 66, 35), (160, 1, 37, 35),
    (161, 1, 85, 36), (162, 1, 73, 36), (163, 1, 47, 36), (164, 1, 37, 36),
    (165, 1, 84, 37), (166, 1, 37, 37),
    (167, 1, 84, 38), (168, 1, 46, 38), (169, 1, 107, 38), (170, 1, 103, 38), (171, 1, 37, 38),
    (172, 1, 83, 39), (173, 1, 37, 39),
    (174, 1, 75, 40), (175, 1, 37, 40),
    (176, 1, 76, 41), (177, 1, 37, 41),
    (178, 1, 75, 42), (179, 1, 37, 42),
    (180, 1, 74, 43), (181, 1, 44, 43),
    (182, 1, 86, 44), (183, 1, 44, 44),
    (184, 1, 77, 45), (185, 1, 44, 45),
    (186, 1, 75, 46), (187, 1, 89, 46), (188, 1, 80, 46), (189, 1, 79, 46), (190, 1, 74, 46), (191, 1, 77, 46), (192, 1, 86, 46), (193, 1, 87, 46), (194, 1, 88, 46),
    (195, 1, 81, 47), (196, 1, 37, 47), (197, 1, 63, 47), (198, 1, 126, 47),
    (199, 1, 37, 48),
    (201, 1, 37, 49), (203, 1, 39, 49),
    (204, 1, 37, 50), (205, 1, 66, 50), (206, 1, 46, 50),
    (207, 1, 37, 51), (209, 1, 39, 51), (210, 1, 40, 51),
    (211, 1, 37, 52), (213, 1, 39, 52), (214, 1, 103, 52),
    (215, 1, 37, 53), (216, 1, 101, 53), (217, 1, 66, 53),
    (218, 1, 37, 54), (219, 1, 45, 54), (220, 1, 102, 54),
    (221, 1, 49, 55), (222, 1, 90, 55), (223, 1, 42, 55), (224, 1, 35, 55),
    (225, 1, 91, 56), (226, 1, 32, 56), (227, 1, 35, 56), (228, 1, 90, 56),
    (229, 1, 47, 57), (230, 1, 45, 57), (231, 1, 120, 57),
    (232, 1, 44, 58), (233, 1, 47, 58), (234, 1, 45, 58), (235, 1, 120, 58),
    (236, 1, 121, 59), (237, 1, 46, 59),
    (238, 1, 122, 60), (239, 1, 123, 60), (240, 1, 46, 61),
    (241, 1, 93, 61), (242, 1, 123, 61), (243, 1, 124, 61),
    (244, 1, 48, 62), (245, 1, 47, 62), (246, 1, 124, 62),
    (247, 1, 130, 63), (248, 1, 120, 63),
    (249, 1, 119, 64),
    (250, 1, 119, 65), (251, 1, 93, 65), (252, 1, 123, 65),
]

creados_dp = 0
for id_dp, cantidad, ing_id, plato_id in detalle_plato_data:
    try:
        ing = Ingrediente.objects.get(id_ingrediente=ing_id)
        plato = Plato.objects.get(id_plato=plato_id)
        obj, created = DetallePlato.objects.get_or_create(
            id_detalle_plato=id_dp,
            defaults={'cantidad': cantidad, 'ingrediente': ing, 'plato': plato}
        )
        if created:
            creados_dp += 1
    except Exception as e:
        print("  Error en DP " + str(id_dp) + ": " + str(e))
print("  Detalle Plato cargados: " + str(creados_dp) + " (Total: " + str(DetallePlato.objects.count()) + ")")

# ============================================================
# 4. DETALLE COMANDA
# ============================================================
print("\nCargando Detalle Comanda...")
detalles_comanda_data = [
    (7, 1, 5, 1, 1, 1),
    (8, 5, 5, 11, 1, 1),
]

creados_dc = 0
for id_dc, beb_id, com_id, plato_id, cant_beb, cant_pla in detalles_comanda_data:
    try:
        bebida = Bebida.objects.get(id_bebida=beb_id) if beb_id else None
        comanda = Comanda.objects.get(id_comanda=com_id)
        plato = Plato.objects.get(id_plato=plato_id) if plato_id else None
        obj, created = DetalleComanda.objects.get_or_create(
            id_detalle_com=id_dc,
            defaults={'bebida': bebida, 'comanda': comanda, 'plato': plato,
                      'cant_bebida': cant_beb, 'cant_plato': cant_pla}
        )
        if created:
            creados_dc += 1
    except Exception as e:
        print("  Error en DetalleComanda " + str(id_dc) + ": " + str(e))
print("  Detalle Comanda cargados: " + str(creados_dc) + " (Total: " + str(DetalleComanda.objects.count()) + ")")

# ============================================================
# RESUMEN FINAL
# ============================================================
print("\n" + "=" * 60)
print("CARGA COMPLETA")
print("=" * 60)
print("Permisos x Cargo:   " + str(PermisoXCargo.objects.count()))
print("Ingredientes:       " + str(Ingrediente.objects.count()))
print("Detalle Plato:      " + str(DetallePlato.objects.count()))
print("Detalle Comanda:    " + str(DetalleComanda.objects.count()))
print("=" * 60)