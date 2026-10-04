from datetime import datetime


# =========================
# PUNTOS
# =========================

def calcular_puntos(posicion):
    if posicion == 5:
        return 20
    if posicion in (4, 6):
        return 15
    if posicion in (3, 7):
        return 10
    if posicion in (2, 8):
        return 5
    if posicion in (1, 9):
        return 1
    return 0


# =========================
# BLOQUEO DE PICKS
# =========================

def carrera_bloqueada(fecha_carrera, margen_minutos=15):
    now = datetime.now()
    fecha_carrera_dt = datetime.fromisoformat(fecha_carrera)
    delta = fecha_carrera_dt - now
    return delta.total_seconds() <= margen_minutos * 60


# =========================
# AUTO-PICK
# =========================

def calcular_autopicks(usuarios, picks_existentes, pilotos):
    """
    usuarios: lista de filas usuarios
    picks_existentes: set/list de usuario_id con pick
    pilotos: lista de filas pilotos
    """
    autopicks = []

    pilotos_ids = [p["id"] if isinstance(p, dict) else p[0] for p in pilotos]

    for u in usuarios:
        uid = u["id"] if isinstance(u, dict) else u[0]
        if uid not in picks_existentes:
            autopicks.append((uid, pilotos_ids))

    return autopicks


# =========================
# TEMPORADAS
# =========================

def temporada_en_curso(fecha_inicio, fecha_fin):
    now = datetime.now()
    return fecha_inicio <= now <= fecha_fin
