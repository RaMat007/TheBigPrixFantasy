from crud import crear_carrera

TEMPORADA_ID = 1

calendario = [
    (1, "Melbpurne, AUS", "2026-03-08"),
    (2, "Shanghai, CHI", "2026-03-15"),
    (3, "Suzuka, JAP", "2026-03-29"),
    (4, "Bahréin, SAK", "2026-04-12"),
    (5, "Jeddah, SAU", "2026-04-19"),
    (6, "Miami, USA", "2026-05-03"),
    (7, "Montreal, CAN", "2026-05-24"),
    (8, "Monaco, MON", "2026-06-07"),
    (9, "Barcelona, ESP", "2026-06-14"),
    (10, "Spielberg, AUT", "2026-06-28"),
    (11, "Silverstone, GBR", "2026-07-05"),
    (12, "Spa, BEL", "2026-07-19"),
    (13, "Hungaroring, HUN", "2026-07-26"),
    (14, "Zandvoort, NED", "2026-08-23"),
    (15, "Monza, ITA", "2026-09-06"),
    (16, "Madrid, ESP", "2026-09-13"),
    (17, "Baku, AZE", "2026-09-27"),
    (18, "Singapore, SGP", "2026-10-11"),
    (19, "Austin, USA", "2026-10-25"),
    (20, "Mexico City, MEX", "2026-11-01"),
    (21, "Sao Paulo, BRA", "2026-11-08"),
    (22, "Las Vegas, USA", "2026-11-21"),
    (23, "Lusaail, QAT", "2026-11-29"),
    (24, "Abu Dhabi, UAE", "2026-12-06")
]

for r, nombre, fecha in calendario:
    crear_carrera(TEMPORADA_ID, r, nombre, fecha)

print("Calendario cargado")
