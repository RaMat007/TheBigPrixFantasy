# Script para renombrar archivos geojson de circuitos a los códigos personalizados de tu tabla
# Ajusta el mapeo de código original a tu código personalizado aquí

import os
from pathlib import Path

# Mapea el código original (ej: 'mx-1962') al código de tu tabla (ej: 'MEX')
ORIGINAL_TO_CUSTOM = {
    "au-1953": "AUS",
    "cn-2004": "CHN",
    "jp-1962": "JPN",
    "bh-2002": "QAT",
    "sa-2021": "SAU",
    "us-2022": "MIA",
    "ca-1978": "CAN",
    "mc-1929": "MON",
    "es-1991": "ESP",
    "at-1969": "AUT",
    "gb-1948": "GBR",
    "be-1925": "BEL",
    "hu-1986": "HUN",
    "nl-1948": "NED",
    "it-1922": "ITA2",
    "es-2026": "MAD",
    "az-2016": "AZE",
    "sg-2008": "SIN",
    "us-2012": "USA",
    "mx-1962": "MEX",
    "br-1940": "BRA",
    "us-2023": "LVG",
    "qa-2004": "QAT2",
    "ae-2009": "ABU"
}

CIRCUITS_DIR = Path(__file__).parent.parent / "f1-circuits-master" / "circuits"

for orig, custom in ORIGINAL_TO_CUSTOM.items():
    orig_path = CIRCUITS_DIR / f"{orig}.geojson"
    custom_path = CIRCUITS_DIR / f"{custom}.geojson"
    if orig_path.exists():
        if not custom_path.exists():
            os.rename(orig_path, custom_path)
            print(f"Renombrado: {orig_path.name} -> {custom_path.name}")
        else:
            print(f"Ya existe: {custom_path.name}, omitiendo {orig_path.name}")
    else:
        print(f"No existe: {orig_path.name}")
print("Renombrado terminado.")
