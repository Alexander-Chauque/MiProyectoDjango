from django.core.management.base import BaseCommand

from notificaciones.reglas import evaluar_cajas_abiertas, evaluar_comandas_demoradas

class Command(BaseCommand):
    help = "Evalúa las reglas que dependen del tiempo: comandas demoradas y cajas abiertas."

    def handle(self, *args, **options):
        comandas = evaluar_comandas_demoradas()
        cajas = evaluar_cajas_abiertas()
        self.stdout.write(
            self.style.SUCCESS(
                f"Alertas nuevas: {comandas} de comandas demoradas, {cajas} de cajas abiertas."
            )
        )
