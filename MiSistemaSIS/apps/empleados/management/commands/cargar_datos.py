# apps/empleados/management/commands/cargar_datos.py

from django.core.management.base import BaseCommand
from empleados.models import Cargo, TipoPermiso

class Command(BaseCommand):
    help = 'Carga cargos y permisos iniciales'

    def handle(self, *args, **options):
        
        # ==========================================
        # 1. CREAR CARGOS
        # ==========================================
        self.stdout.write("Creando Cargos...")
        
        cargos = ['Administrador', 'Gerente', 'Cajero', 'Mozo', 'Cocinero',]
        
        for nombre in cargos:
            cargo, created = Cargo.objects.get_or_create(nombre_cargo=nombre)
            if created:
                self.stdout.write(f'Cargo "{nombre}" creado')
            else:
                self.stdout.write(f'Cargo "{nombre}" ya existe')
        
        # 2. CREAR PERMISOS POR CARGO
        self.stdout.write("Creando permisos...")
        
        permisos = {
            'Administrador': [
                ('platos', 'leer'), ('platos', 'escribir'), ('platos', 'modificar'), ('platos', 'eliminar'),
                ('ingredientes', 'leer'), ('ingredientes', 'escribir'), ('ingredientes', 'modificar'), ('ingredientes', 'eliminar'),
                ('categorias', 'leer'), ('categorias', 'escribir'), ('categorias', 'modificar'), ('categorias', 'eliminar'),
                ('empleados', 'leer'), ('empleados', 'escribir'), ('empleados', 'modificar'), ('empleados', 'eliminar'),
                ('cargos', 'leer'), ('cargos', 'escribir'), ('cargos', 'modificar'), ('cargos', 'eliminar'),
            ],
            'Gerente': [
                ('platos', 'leer'), ('platos', 'escribir'), ('platos', 'modificar'),
                ('ingredientes', 'leer'), ('ingredientes', 'escribir'), ('ingredientes', 'modificar'),
                ('categorias', 'leer'), ('categorias', 'escribir'), ('categorias', 'modificar'),
                ('empleados', 'leer'), ('empleados', 'modificar'),
                ('ventas', 'leer'), ('gastos', 'leer'),
            ],
            'Cajero': [
                ('platos', 'leer'), ('ingredientes', 'leer'), ('categorias', 'leer'),
                ('ventas', 'leer'), ('ventas', 'escribir'),
                ('caja', 'leer'), ('caja', 'escribir'),
            ],
            'Mozo': [
                ('platos', 'leer'), ('categorias', 'leer'),
                ('comandas', 'leer'), ('comandas', 'escribir'), ('comandas', 'modificar'),
                ('mesas', 'leer'), ('mesas', 'escribir'), ('mesas', 'modificar'),
            ],
            'Cocinero': [
                ('platos', 'leer'), ('ingredientes', 'leer'), ('categorias', 'leer'),
            ],
        }
        
        for cargo_nombre, permisos_list in permisos.items():
            cargo = Cargo.objects.get(nombre_cargo=cargo_nombre)
            
            for modulo, accion in permisos_list:
                permiso, created = TipoPermiso.objects.get_or_create(
                    cargo=cargo,
                    modulo=modulo,
                    accion=accion
                )
                if created:
                    self.stdout.write(f'{cargo_nombre} ({modulo}.{accion})')
        
        self.stdout.write("\n" + "=" * 50)
        self.stdout.write(f"Cargos: {Cargo.objects.count()}")
        self.stdout.write(f"Permisos: {TipoPermiso.objects.count()}")
        self.stdout.write("=" * 50)
        self.stdout.write(self.style.SUCCESS('\n¡Datos cargados exitosamente!'))