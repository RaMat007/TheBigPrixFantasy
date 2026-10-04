# Operación y recuperación de Big Prix

## Activación del proceso programado

En GitHub → Settings → Secrets and variables → Actions, crear:

- `DATABASE_URL`: la misma URL de conexión de la base Healthy que usa Streamlit. No guardar la URL en código ni en commits.
- `BACKUP_ENCRYPTION_KEY`: una clave larga y exclusiva. Conservarla también fuera de GitHub; sin ella no se puede descifrar la copia externa.

En Actions → Mantenimiento Big Prix → Run workflow, ejecutar una vez. El cron solicita ejecuciones cada 20 minutos; GitHub puede retrasarlas. La app mostrará la hora de la última ejecución en Super Admin → Control de temporada → Resultados automáticos.

En repositorios públicos GitHub puede desactivar los schedules después de 60 días sin actividad en el repositorio. Revisar la última ejecución en la app y reactivar el workflow en Actions si ocurre.

El proceso hace respaldo diario, prepara picks automáticos del próximo GP antes del cierre y consulta resultados de los últimos siete días. Funciona sin visitas a Streamlit. La app también hace mantenimiento al abrirse; la consulta de resultados puede iniciarse manualmente en Control de temporada.

## Qué se conserva

- Respaldo inicial, diarios por 60 días y respaldo antes de cambiar calendario, picks, resultados o revisiones. Los respaldos previos a modificaciones no se purgan automáticamente.
- Historial de cambios de picks, carreras, resultados, puntos y revisiones, con usuario y UTC. BASELINE indica el estado encontrado cuando se activó el historial; no reconstruye modificaciones anteriores.
- Copia externa cifrada del respaldo diario, en los artifacts de GitHub Actions, con retención de 60 días. Descargar periódicamente una copia si se requiere conservación mayor.
- Los resultados importados no reasignan ni crean picks históricos.

## Resultados automáticos

Se usa la sesión `Race` de OpenF1: identidad de GP, inicio a no más de 36 horas, final de sesión confirmado, al menos 20 participantes identificados y clasificación con Top 5 completo. Se consulta desde tres horas después del inicio. La disponibilidad depende de OpenF1; si falta información, queda Pendiente y se reintenta.

Una clasificación nueva validada se publica y recalcula los puntos dentro de una transacción con respaldo. Si cambia una clasificación existente, queda en Revisión y requiere aprobación en Control de temporada. Las sanciones posteriores no cambian puntos silenciosamente.

Los GP terminados sin picks se muestran como pendientes de recuperación. No se crean elecciones aleatorias retrospectivas ni se trasladan picks por número de ronda.

## Calendario

Control de temporada → Calendario permite consultar una propuesta de OpenF1 o editar fechas UTC, nombre y cancelación. Se muestra Antes/Después y se exige motivo/fuente al aplicar. Se conservan todos los IDs; las rondas se ordenan por fecha. La ausencia en OpenF1 nunca se interpreta como cancelación.

## Recuperación

Control de temporada → Respaldos permite descargar y comparar una versión. Recuperar picks ausentes inserta solo los registros que no existen en el mismo ID de GP y recalcula puntos. No sobrescribe elecciones actuales.

Para descifrar un artifact en una máquina local, con la clave original en `BACKUP_ENCRYPTION_KEY`:

```bash
openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 \
  -in bigprix_YYYYMMDD.json.enc -out bigprix_respaldo.json \
  -pass env:BACKUP_ENCRYPTION_KEY
```

La copia JSON incluye datos sensibles de la aplicación. Para recuperación completa de una base caída, restaurar sus tablas y secuencias en una base aislada antes de cambiar la URL de producción. La app ofrece recuperación selectiva de picks; no hace un reemplazo destructivo de todas las tablas desde un botón.
