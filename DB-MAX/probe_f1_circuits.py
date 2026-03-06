from pathlib import Path

# Directorio base del proyecto (donde está este archivo)
BASE_DIR = Path(__file__).parent

# Se asume que "f1-circuits-master" está un nivel arriba de este proyecto
CIRCUITS_DIR = BASE_DIR.parent / "f1-circuits-master"

print(f"BASE_DIR: {BASE_DIR}")
print(f"CIRCUITS_DIR: {CIRCUITS_DIR}")
print(f"Existe CIRCUITS_DIR? {CIRCUITS_DIR.exists()}")

if not CIRCUITS_DIR.exists():
    print("No se encontró la carpeta f1-circuits-master un nivel arriba del proyecto.")
else:
    # Buscamos SVG/PNG/JPG dentro de la carpeta (recursivo)
    patterns = ["**/*.svg", "**/*.png", "**/*.jpg", "**/*.jpeg"]
    files = []
    for pattern in patterns:
        files.extend(CIRCUITS_DIR.glob(pattern))

    print(f"Total de archivos gráficos encontrados (svg/png/jpg/jpeg): {len(files)}")

    # Mostramos algunos ejemplos
    for path in files[:20]:
        print("-", path.relative_to(CIRCUITS_DIR))

    if not files:
        print("No se encontraron imágenes en la carpeta f1-circuits-master.")
