

import streamlit as st
import json
from pathlib import Path
import matplotlib.pyplot as plt
import io
import os

BASE_DIR = Path(__file__).parent
F1_GEOJSON_PATH = BASE_DIR / "f1-circuits-master" / "f1-circuits.geojson"
CIRCUITS_DIR = BASE_DIR / "f1-circuits-master" / "circuits"

with open(F1_GEOJSON_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)

geojson_names = [feat["properties"]["Name"] for feat in data["features"]]
geojson_ids = [feat["properties"]["id"] for feat in data["features"]]
geojson_layouts_by_name = {feat["properties"]["Name"]: feat["geometry"]["coordinates"] for feat in data["features"]}
geojson_layouts_by_id = {feat["properties"]["id"]: feat["geometry"]["coordinates"] for feat in data["features"]}

def plot_layout_icon(coords, width=100, height=100):
    fig, ax = plt.subplots(figsize=(width/100, height/100), dpi=100)
    lons, lats = zip(*coords)
    ax.plot(lons, lats, color='red', linewidth=2)
    ax.axis('off')
    plt.tight_layout(pad=0)
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', pad_inches=0, transparent=True)
    plt.close(fig)
    buf.seek(0)
    return buf

st.title("Renombra archivos de circuitos F1 por su layout")


# Lista de circuitos de la temporada 2026 (nombre de archivo base esperado)
season_2026_circuits = [
    "au-1953",   # Melbourne
    "cn-2004",   # Shanghai
    "jp-1962",   # Suzuka
    "bh-2002",   # Bahrain
    "sa-2021",   # Jeddah
    "us-2022",   # Miami
    "ca-1978",   # Montreal
    "mc-1929",   # Monaco
    "es-1991",   # Barcelona
    "at-1969",   # Spielberg
    "gb-1948",   # Silverstone
    "be-1925",   # Spa
    "hu-1986",   # Hungaroring
    "nl-1948",   # Zandvoort
    "it-1922",   # Monza
    "es-2026",   # Madrid (asumido nombre de archivo)
    "az-2016",   # Baku
    "sg-2008",   # Singapore
    "us-2012",   # Austin
    "mx-1962",   # Mexico City
    "br-1977",   # Sao Paulo
    "us-2023",   # Las Vegas
    "qa-2004",   # Lusail
    "ae-2009",   # Abu Dhabi
]
files = [CIRCUITS_DIR / f"{circuit}.geojson" for circuit in season_2026_circuits if (CIRCUITS_DIR / f"{circuit}.geojson").exists()]

cols = st.columns(2)
import difflib
def normalize(s):
    return s.replace("-", "").replace("_", "").replace(" ", "").replace("circuit", "").replace("autodromo", "").replace("international", "").replace("track", "").replace("grandprix", "").replace("gp", "").replace("de", "").replace("the", "").replace("el", "").replace("la", "").replace("do", "").replace("del", "").replace("e", "").replace("course", "").replace("ring", "").replace("raceway", "").replace("street", "").replace("road", "").replace("park", "").replace("nazionale", "").replace("enzoedinoferrari", "imola").replace("hermanosrodriguez", "mexico").replace("josecarlospace", "interlagos").replace("paulricard", "castellet").replace("marinabay", "singapore").replace("yasmarina", "abudhabi").replace("redbull", "spielberg").replace("shanghai", "china").replace("sochi", "russia").replace("hockenheimring", "hockenheim").replace("nurburgring", "nurburg").replace("algarve", "portimao").replace("sakhir", "bahrain").replace("suzuka", "japan").replace("monaco", "monaco").replace("monza", "monza").replace("barcelona", "catalunya").replace("spa-francorchamps", "spa").replace("austin", "cota").replace("budapest", "hungaroring").replace("montreal", "gillesvilleneuve").replace("mexicocity", "mexico").replace("silverstone", "silverstone").replace("imola", "imola").replace("castellet", "castellet").replace("spielberg", "spielberg").replace("portimao", "portimao").replace("baku", "baku").replace("jeddah", "jeddah").replace("singapore", "singapore").replace("abudhabi", "abudhabi").replace("francorchamps", "spa").replace("interlagos", "interlagos").replace("cota", "cota").replace("hungaroring", "hungaroring").replace("gillesvilleneuve", "gillesvilleneuve").replace("china", "china").replace("russia", "russia").replace("hockenheim", "hockenheim").replace("nurburg", "nurburg").replace("bahrain", "bahrain").replace("japan", "japan").replace("catalunya", "catalunya").replace("spa", "spa").replace("", "").lower()

for idx, file in enumerate(files):
    col = cols[idx % 2]
    with col:
        nombre = file.stem
        layout_coords = None
        caption = None
        # Buscar info completa (nombre, ciudad, país) por id o por nombre
        def get_full_info_by_id(id_):
            for feat in data["features"]:
                if feat["properties"].get("id") == id_:
                    n = feat["properties"].get("Name", id_)
                    loc = feat["properties"].get("Location", "")
                    ctry = feat["properties"].get("Country", None)
                    if not ctry or ctry.strip() == "":
                        # Inferir país por id o nombre si falta
                        id_lower = id_.lower()
                        if id_lower.startswith("es-"):
                            ctry = "España"
                        elif id_lower.startswith("it-"):
                            ctry = "Italia"
                        elif id_lower.startswith("fr-"):
                            ctry = "Francia"
                        elif id_lower.startswith("gb-"):
                            ctry = "Reino Unido"
                        elif id_lower.startswith("de-"):
                            ctry = "Alemania"
                        elif id_lower.startswith("hu-"):
                            ctry = "Hungría"
                        elif id_lower.startswith("be-"):
                            ctry = "Bélgica"
                        elif id_lower.startswith("mc-"):
                            ctry = "Mónaco"
                        elif id_lower.startswith("au-"):
                            ctry = "Australia"
                        elif id_lower.startswith("ca-"):
                            ctry = "Canadá"
                        elif id_lower.startswith("us-"):
                            ctry = "Estados Unidos"
                        elif id_lower.startswith("mx-"):
                            ctry = "México"
                        elif id_lower.startswith("br-"):
                            ctry = "Brasil"
                        elif id_lower.startswith("jp-"):
                            ctry = "Japón"
                        elif id_lower.startswith("cn-"):
                            ctry = "China"
                        elif id_lower.startswith("ru-"):
                            ctry = "Rusia"
                        elif id_lower.startswith("at-"):
                            ctry = "Austria"
                        elif id_lower.startswith("pt-"):
                            ctry = "Portugal"
                        elif id_lower.startswith("ae-"):
                            ctry = "Emiratos Árabes Unidos"
                        elif id_lower.startswith("qa-"):
                            ctry = "Catar"
                        elif id_lower.startswith("tr-"):
                            ctry = "Turquía"
                        elif id_lower.startswith("za-"):
                            ctry = "Sudáfrica"
                        elif id_lower.startswith("nl-"):
                            ctry = "Países Bajos"
                        elif id_lower.startswith("sg-"):
                            ctry = "Singapur"
                        elif id_lower.startswith("sa-"):
                            ctry = "Arabia Saudita"
                        else:
                            ctry = "(País desconocido)"
                    return n, loc, ctry
            return id_, "", "(País desconocido)"
        def get_full_info_by_name(name_):
            for feat in data["features"]:
                if feat["properties"].get("Name") == name_:
                    n = feat["properties"].get("Name", name_)
                    loc = feat["properties"].get("Location", "")
                    ctry = feat["properties"].get("Country", None)
                    if not ctry or ctry.strip() == "":
                        # Inferir país por nombre si falta
                        name_lower = name_.lower()
                        if "espa" in name_lower or "catalunya" in name_lower or "barcelona" in name_lower:
                            ctry = "España"
                        elif "monza" in name_lower or "imola" in name_lower or "enzo" in name_lower:
                            ctry = "Italia"
                        elif "paul ricard" in name_lower or "castellet" in name_lower:
                            ctry = "Francia"
                        elif "silverstone" in name_lower:
                            ctry = "Reino Unido"
                        elif "hockenheim" in name_lower or "nurburgring" in name_lower:
                            ctry = "Alemania"
                        elif "hungaroring" in name_lower or "budapest" in name_lower:
                            ctry = "Hungría"
                        elif "spa" in name_lower:
                            ctry = "Bélgica"
                        elif "monaco" in name_lower:
                            ctry = "Mónaco"
                        elif "albert park" in name_lower or "melbourne" in name_lower:
                            ctry = "Australia"
                        elif "gilles" in name_lower or "montreal" in name_lower:
                            ctry = "Canadá"
                        elif "americas" in name_lower or "austin" in name_lower:
                            ctry = "Estados Unidos"
                        elif "hermanos rodriguez" in name_lower or "mexico" in name_lower:
                            ctry = "México"
                        elif "interlagos" in name_lower or "jose carlos pace" in name_lower or "sao paulo" in name_lower:
                            ctry = "Brasil"
                        elif "suzuka" in name_lower:
                            ctry = "Japón"
                        elif "shanghai" in name_lower:
                            ctry = "China"
                        elif "sochi" in name_lower:
                            ctry = "Rusia"
                        elif "red bull" in name_lower or "spielberg" in name_lower:
                            ctry = "Austria"
                        elif "portimao" in name_lower or "algarve" in name_lower:
                            ctry = "Portugal"
                        elif "yas marina" in name_lower or "abudhabi" in name_lower:
                            ctry = "Emiratos Árabes Unidos"
                        elif "losail" in name_lower or "qatar" in name_lower:
                            ctry = "Catar"
                        elif "istanbul" in name_lower:
                            ctry = "Turquía"
                        elif "kyalami" in name_lower:
                            ctry = "Sudáfrica"
                        elif "zandvoort" in name_lower:
                            ctry = "Países Bajos"
                        elif "singapur" in name_lower or "marina bay" in name_lower:
                            ctry = "Singapur"
                        elif "jeddah" in name_lower or "arabia" in name_lower:
                            ctry = "Arabia Saudita"
                        else:
                            ctry = "(País desconocido)"
                    return n, loc, ctry
            return name_, "", "(País desconocido)"
        # Primero intenta por id exacto
        if nombre in geojson_layouts_by_id:
            layout_coords = geojson_layouts_by_id[nombre]
            real_name, location, country = get_full_info_by_id(nombre)
        else:
            # Si no, fuzzy por nombre
            norm_nombre = normalize(nombre)
            norm_geo = [normalize(n) for n in geojson_names]
            matches = difflib.get_close_matches(norm_nombre, norm_geo, n=1, cutoff=0.5)
            if matches:
                best_idx = norm_geo.index(matches[0])
                best_match = geojson_names[best_idx]
                layout_coords = geojson_layouts_by_name[best_match]
                real_name, location, country = get_full_info_by_name(best_match)
            else:
                real_name, location, country = nombre, "", ""
        # Caption siempre con toda la info, bien formateado
        caption_lines = [f"**{real_name}**"]
        if location:
            caption_lines.append(f"*{location}*")
        # Mostrar país SIEMPRE, aunque sea vacío o desconocido
        caption_lines.append(f"*{country}*")
        caption_md = "  ".join(caption_lines)  # doble espacio para salto de línea en markdown
        st.markdown(f"**Archivo:** `{file.name}`")
        st.markdown(caption_md)
        if layout_coords:
            buf = plot_layout_icon(layout_coords, width=120, height=120)
            st.image(buf, width=120, caption=None, output_format="PNG")
        else:
            st.warning("No se encontró layout para este archivo.")
        new_name = st.text_input(f"Nuevo nombre para {file.name}", value=nombre, key=f"rename_{file.name}")
        if st.button(f"Renombrar {file.name}"):
            new_path = file.parent / f"{new_name}.geojson"
            if not new_path.exists():
                os.rename(file, new_path)
                st.success(f"Archivo renombrado a {new_name}.geojson")
            else:
                st.error("Ya existe un archivo con ese nombre.")
