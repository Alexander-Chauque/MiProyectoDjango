
from django.conf import settings
from django.db import models


class LogAuditoria(models.Model):
    ACCIONES = [
        ('MODIFICACION', 'Modificación'),
        ('ANULACION', 'Anulación'),
    ]

    id_log = models.AutoField(primary_key=True)

    entidad = models.CharField(max_length=100)
    id_registro = models.CharField(max_length=100)
    accion = models.CharField(max_length=20, choices=ACCIONES)

    valores_anteriores = models.JSONField()
    valores_actuales = models.JSONField(null=True, blank=True)

    fecha_hora = models.DateTimeField(auto_now_add=True)

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='registros_auditoria'
    )

    class Meta:
        db_table = 'log_auditoria'
        ordering = ['-fecha_hora']
        verbose_name = 'Registro de auditoría'
        verbose_name_plural = 'Registros de auditoría'

    def __str__(self):
        return (
            f'{self.entidad} #{self.id_registro} - '
            f'{self.accion}'
        )