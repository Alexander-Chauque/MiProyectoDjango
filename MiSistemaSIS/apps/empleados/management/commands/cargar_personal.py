"""
Carga los cargos de la peña y personal de ejemplo para cada uno.

    python manage.py cargar_personal

Solo Mozo y Administrador ingresan al sistema. El resto del personal queda
registrado (para sueldos, asistencia, etc.), pero no puede iniciar sesión.
Se puede correr varias veces: lo que ya existe no se duplica.
"""
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction

from empleados.models import Cargo, Empleado

# nombre, descripción, nivel de acceso, puede ingresar al sistema
CARGOS = [
    ("Administrador", "Encargado del local. Administra todo el sistema.", 5, True),
    ("Mozo", "Toma los pedidos en el salón y cobra las comandas.", 2, True),
    ("Jefe De Cocina", "Organiza la cocina y el menú.", 1, False),
    ("Cocinero", "Prepara los platos de la carta.", 1, False),
    ("Ayudante De Cocina", "Asiste en la preparación y el armado de los platos.", 1, False),
    ("Parrillero", "Se encarga de la parrilla.", 1, False),
    ("Bartender", "Prepara las bebidas y los tragos en la barra.", 1, False),
    ("Bachero", "Lava la vajilla y mantiene limpia la cocina.", 1, False),
]

# nombre, apellido, dni, cargo. Los correos son @example.com: un dominio
# reservado, así las alertas por correo no le llegan a nadie real.
PERSONAL = [
    ("Lucía", "Flores", "40111222", "Mozo"),
    ("Martín", "Romero", "39222333", "Mozo"),
    ("Ramón", "Tolaba", "28333444", "Jefe De Cocina"),
    ("Rosa", "Mamani", "33444555", "Cocinero"),
    ("Diego", "Guanuco", "42555666", "Ayudante De Cocina"),
    ("Hugo", "Chocobar", "30666777", "Parrillero"),
    ("Valeria", "Ríos", "41777888", "Bartender"),
    ("Néstor", "Quispe", "37888999", "Bachero"),
]

# Contraseña temporal para quienes ingresan: la cambian al primer ingreso
CLAVE_TEMPORAL = "Cardones#2026"

SIN_TILDES = str.maketrans("áéíóúñÁÉÍÓÚÑ", "aeiounAEIOUN")


class Command(BaseCommand):
    help = "Carga los cargos de la peña y personal de ejemplo (solo Mozo y Administrador ingresan)"

    @transaction.atomic
    def handle(self, *args, **options):
        cargos = {}
        for nombre, descripcion, nivel, acceso in CARGOS:
            cargo = Cargo.objects.filter(nombre_cargo__iexact=nombre).first()
            if cargo is None:
                cargo = Cargo.objects.create(
                    nombre_cargo=nombre,
                    descripcion_cargo=descripcion,
                    nivel_acceso=nivel,
                    acceso_sistema=acceso,
                )
                self.stdout.write(f"Cargo creado: {nombre}")
            else:
                # Al existente solo se le ajusta el acceso; nivel, sueldo y permisos no se tocan
                cambios = []
                if cargo.acceso_sistema != acceso:
                    cargo.acceso_sistema = acceso
                    cambios.append("acceso_sistema")
                if not cargo.descripcion_cargo:
                    cargo.descripcion_cargo = descripcion
                    cambios.append("descripcion_cargo")
                if cambios:
                    cargo.save(update_fields=cambios)
                self.stdout.write(f"Cargo existente: {cargo.nombre_cargo}")
            cargos[nombre] = cargo

        for nombre, apellido, dni, nombre_cargo in PERSONAL:
            if Empleado.objects.filter(dni=dni).exists():
                self.stdout.write(f"Ya existe: {nombre} {apellido}")
                continue
            cargo = cargos[nombre_cargo]
            correo = f"{nombre}.{apellido}".lower().translate(SIN_TILDES) + "@example.com"
            empleado = Empleado(
                nombre_empleado=nombre,
                apellido_empleado=apellido,
                dni=dni,
                correo=correo,
                cargo=cargo,
            )
            empleado.user_auto = empleado.generate_user_auto()
            # Sin acceso: la cuenta existe, pero sin contraseña con la que entrar
            clave = CLAVE_TEMPORAL if cargo.acceso_sistema else None
            empleado.user = User.objects.create_user(
                username=empleado.user_auto,
                email=correo,
                password=clave,
                first_name=nombre,
                last_name=apellido,
            )
            empleado.debe_cambiar_contrasena = cargo.acceso_sistema
            empleado.save()
            acceso = f"ingresa con la clave temporal {CLAVE_TEMPORAL}" if clave else "sin acceso al sistema"
            self.stdout.write(f"Empleado creado: {nombre} {apellido} ({nombre_cargo}) - usuario {empleado.user_auto}, {acceso}")

        self.stdout.write(self.style.SUCCESS("Listo."))
