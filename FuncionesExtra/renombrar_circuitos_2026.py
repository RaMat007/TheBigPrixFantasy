# Script para renombrar archivos geojson de circuitos F1 a los códigos de la temporada 2026
import os
from pathlib import Path

# Mapeo de nombres actuales a códigos deseados
# Formato: 'nombre_actual_sin_extension': 'codigo_deseado'
rename_map = {
    # Ejemplo: 'nombre_viejo': 'nuevo_codigo',
    # Llena este diccionario con los nombres actuales y los códigos de tu lista
    'au-1953': 'au-1953',   # Melbourne
    'cn-2004': 'cn-2004',   # Shanghai
    'jp-1962': 'jp-1962',   # Suzuka
    'bh-2002': 'bh-2002',   # Bahrain
    'sa-2021': 'sa-2021',   # Jeddah
    'us-2022': 'us-2022',   # Miami
    'ca-1978': 'ca-1978',   # Montreal
    'mc-1929': 'mc-1929',   # Monaco
    'es-1991': 'es-1991',   # Barcelona
    'at-1969': 'at-1969',   # Spielberg
    'gb-1948': 'gb-1948',   # Silverstone
    'be-1925': 'be-1925',   # Spa
    'hu-1986': 'hu-1986',   # Hungaroring
    'nl-1948': 'nl-1948',   # Zandvoort
    'it-1922': 'it-1922',   # Monza
    'es-2026': 'es-2026',   # Madrid
    'az-2016': 'az-2016',   # Baku
    'sg-2008': 'sg-2008',   # Singapore
    'us-2012': 'us-2012',   # Austin
    'mx-1962': 'mx-1962',   # Mexico City
    'br-1977': 'br-1977',   # Sao Paulo
    'us-2023': 'us-2023',   # Las Vegas
    'qa-2004': 'qa-2004',   # Lusail
    'ae-2009': 'ae-2009',   # Abu Dhabi
}

CIRCUITS_DIR = Path(__file__).parent / 'f1-circuits-master' / 'circuits'

for old, new in rename_map.items():
    old_path = CIRCUITS_DIR / f'{old}.geojson'
    new_path = CIRCUITS_DIR / f'{new}.geojson'
    if old_path.exists() and old != new:
        if not new_path.exists():
            os.rename(old_path, new_path)
            print(f'Renombrado: {old_path.name} -> {new_path.name}')
        else:
            print(f'Ya existe: {new_path.name}, omitiendo {old_path.name}')
    elif not old_path.exists():
        print(f'No encontrado: {old_path.name}')
    else:
        print(f'Sin cambios: {old_path.name}')
print('Renombrado completado.')
