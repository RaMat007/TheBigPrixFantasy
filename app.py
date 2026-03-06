import streamlit as st
from datetime import datetime, time, timezone
from pathlib import Path
import pandas as pd
import altair as alt
from logger import get_logger
import crud
import f1db_integration
from rules import calcular_puntos, carrera_bloqueada
from auth import validar_login
from db import init_db
# --- Para layouts de pista ---
import json
import matplotlib.pyplot as plt
import io
import os


def _load_circuit_layouts():
    """Carga el GeoJSON de circuitos y devuelve un dict {nombre: coords}"""
    gj_path = os.path.join('f1-circuits-master', 'f1-circuits.geojson')
    if not os.path.exists(gj_path):
        return {}
    import unicodedata
    def normaliza(s):
        s = str(s).strip().lower()
        s = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
        return s
    layouts = {}
    with open(gj_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        for feature in data['features']:
            props = feature['properties']
            coords = feature['geometry']['coordinates']
            # Guardar por Name y Location normalizados
            for key in ['Name', 'Location']:
                val = props.get(key, '')
                if val:
                    norm = normaliza(val)
                    layouts[norm] = coords
            # También guardar por id si existe
            gid = props.get('id', None)
            if gid:
                layouts[normaliza(gid)] = coords
    return layouts

def _plot_layout_icon(coords, width=100, height=100):
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

# Cache layouts para no recargar en cada render
_CIRCUIT_LAYOUTS = _load_circuit_layouts()

logger = get_logger()

BASE_DIR = Path(__file__).parent
IMG_DIR_PISTAS = BASE_DIR / "data" / "img" / "pistas"
IMG_DIR_PILOTOS = BASE_DIR / "data" / "img" / "pilotos"

# Aseguramos que la base (y las nuevas columnas de carreras) estén migradas
init_db()


def _load_css():
    """Inyecta el CSS global si existe styles.css."""

    css_path = BASE_DIR / "styles.css"
    if css_path.exists():
        with open(css_path, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


def _get_piloto_image_path(codigo: str):
    """Devuelve la ruta a la imagen de un piloto si existe.

    Busca en data/img/pilotos usando variantes del código (VER, ver, Ver...) y
    extensiones comunes (png, jpg, jpeg, webp).
    """

    if not codigo:
        return None

    variants = {str(codigo), str(codigo).upper(), str(codigo).lower()}
    exts = ("png", "jpg", "jpeg", "webp")

    for slug in variants:
        for ext in exts:
            p = IMG_DIR_PILOTOS / f"{slug}.{ext}"
            if p.is_file():
                return str(p)

    return None


def _build_carreras_view(carreras_df, year_hint=2026, include_id=False):
    """Construye un DataFrame de carreras enriquecido con datos de F1DB.

    - Toma las columnas básicas de quiniela.db (round, nombre, inicio, opcionalmente id).
    - Agrega Kms, Vueltas y Pista usando f1db_integration.
    """

    base_cols = ["round", "nombre", "inicio"]
    if include_id and "id" in carreras_df.columns:
        base_cols = ["id"] + base_cols

    df_view = carreras_df[base_cols].copy()

    detalles_round = {}
    if year_hint is not None:
        try:
            detalles_round = f1db_integration.carreras_detalle_por_round(int(year_hint))
        except Exception as e:  # pragma: no cover - protección extra
            logger.error(f"Error obteniendo detalles de F1DB para year={year_hint}: {e}")
            detalles_round = {}

    df_view["Kms"] = df_view["round"].apply(
        lambda r: detalles_round.get(int(r), {}).get("track_length_km", "")
        if pd.notna(r)
        else ""
    )
    df_view["Vueltas"] = df_view["round"].apply(
        lambda r: detalles_round.get(int(r), {}).get("laps", "")
        if pd.notna(r)
        else ""
    )
    df_view["Pista"] = df_view["round"].apply(
        lambda r: detalles_round.get(int(r), {}).get("circuit_name", "")
        if pd.notna(r)
        else ""
    )

    # Si la tabla carreras ya tiene columnas propias, las usamos como override
    if "kms" in carreras_df.columns:
        df_view["Kms"] = carreras_df["kms"].where(carreras_df["kms"].notna(), df_view["Kms"])
    if "vueltas" in carreras_df.columns:
        df_view["Vueltas"] = carreras_df["vueltas"].where(carreras_df["vueltas"].notna(), df_view["Vueltas"])
    if "pista" in carreras_df.columns:
        df_view["Pista"] = carreras_df["pista"].where(carreras_df["pista"].notna(), df_view["Pista"])

    rename_map = {
        "round": "Round",
        "nombre": "Carrera",
        "inicio": "Inicio",
    }
    if include_id and "id" in df_view.columns:
        rename_map["id"] = "ID"

    # --- Agregar columna GeoJSON (código del archivo geojson en circuits) ---
    # Cargar mapeo circuit_name -> geojson id desde f1-locations-2026.json
    geojson_map = {}
    try:
        with open(os.path.join('f1-circuits-master', 'championships', 'f1-locations-2026.json'), 'r', encoding='utf-8') as f:
            locations = json.load(f)
            for loc in locations:
                # Normalizar nombre para comparar
                geojson_map[loc['name'].strip().lower()] = loc['id']
    except Exception as e:
        geojson_map = {}

    import unicodedata
    # Construir mapeo robusto usando todos los geojson
    geojson_dir = os.path.join('f1-circuits-master', 'circuits')
    geojson_files = [f for f in os.listdir(geojson_dir) if f.endswith('.geojson')]
    geojson_full_map = {}
    for fname in geojson_files:
        fpath = os.path.join(geojson_dir, fname)
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for feature in data['features']:
                    props = feature['properties']
                    gid = props.get('id', fname.replace('.geojson',''))
                    for key in ['Location', 'Name']:
                        val = props.get(key, '')
                        if val:
                            norm = ''.join(c for c in unicodedata.normalize('NFD', val.strip().lower()) if unicodedata.category(c) != 'Mn')
                            geojson_full_map[norm] = gid
        except Exception:
            continue
    def normaliza(s):
        s = str(s).strip().lower()
        s = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
        return s
    equivalencias_manual = {
        'melbourne': 'albert park circuit',
        'shanghai': 'shanghai international circuit',
        'suzuka': 'suzuka international racing course',
        'bahrain': 'bahrain international circuit',
        'jeddah': 'jeddah corniche circuit',
        'miami': 'miami international autodrome',
        'gilles villeneuve': 'circuit gilles-villeneuve',
        'montreal': 'circuit gilles-villeneuve',
        'monaco': 'circuit de monaco',
        'catalunya': 'circuit de barcelona-catalunya',
        'barcelona': 'circuit de barcelona-catalunya',
        'red bull ring': 'red bull ring',
        'silverstone': 'silverstone circuit',
        'spa-francorchamps': 'circuit de spa-francorchamps',
        'spa': 'circuit de spa-francorchamps',
        'hungaroring': 'hungaroring',
        'zandvoort': 'circuit zandvoort',
        'monza': 'autodromo nazionale monza',
        'madring': 'circuito de madring',
        'madrid': 'circuito de madring',
        'baku': 'baku city circuit',
        'marina bay': 'marina bay street circuit',
        'singapore': 'marina bay street circuit',
        'americas': 'circuit of the americas',
        'austin': 'circuit of the americas',
        'hermanos rodriguez': 'autodromo hermanos rodriguez',
        'mexico city': 'autodromo hermanos rodriguez',
        'jose carlos pace': 'autodromo jose carlos pace - interlagos',
        'interlagos': 'autodromo jose carlos pace - interlagos',
        'las vegas': 'las vegas street circuit',
        'lusail': 'losail international circuit',
        'yas marina': 'yas marina circuit',
    }
    def get_geojson_code(circuit_name):
        if not circuit_name:
            return ''
        nombre = normaliza(circuit_name)
        if nombre in geojson_full_map:
            return geojson_full_map[nombre]
        if nombre in equivalencias_manual:
            nombre_equiv = normaliza(equivalencias_manual[nombre])
            return geojson_full_map.get(nombre_equiv, '')
        return ''

    df_view["GeoJSON"] = df_view["Pista"].apply(get_geojson_code)

    df_view = df_view.rename(columns=rename_map)
    return df_view

# =========================
# CONFIG
# =========================
st.set_page_config(page_title="Quiniela F1", layout="wide")

_load_css()


# =========================
# LOGIN
# =========================
if "user_id" not in st.session_state:
    st.title("🏎️ TheBigPrixFantasy")

    tab_login, tab_registro = st.tabs(["Iniciar sesión", "Crear cuenta"])

    with tab_login:
        username = st.text_input("Usuario", key="login_user")
        password = st.text_input("Contraseña", type="password", key="login_pass")
        if st.button("Entrar", key="btn_login"):
            user = validar_login(username, password)
            if user:
                st.session_state.user_id = user["id"]
                st.session_state.username = user["username"]
                st.session_state.is_admin = user["is_admin"]
                st.rerun()
            else:
                st.error("Credenciales incorrectas")

    with tab_registro:
        st.subheader("Nueva cuenta")

        col1, col2 = st.columns(2)
        with col1:
            reg_nombre    = st.text_input("Nombre", key="reg_nombre")
            reg_correo    = st.text_input("Correo electrónico", key="reg_correo")
            reg_pass      = st.text_input("Contraseña", type="password", key="reg_pass")
        with col2:
            reg_apellido  = st.text_input("Apellido", key="reg_apellido")
            reg_escuderia = st.text_input("Nombre de escudería", help="Este será tu nombre de usuario", key="reg_escuderia")
            reg_pass2     = st.text_input("Confirmar contraseña", type="password", key="reg_pass2")

        if st.button("Crear cuenta", key="btn_registro"):
            if not all([reg_nombre, reg_apellido, reg_correo, reg_escuderia, reg_pass]):
                st.error("Completa todos los campos")
            elif reg_pass != reg_pass2:
                st.error("Las contraseñas no coinciden")
            else:
                try:
                    crud.crear_usuario(
                        username=reg_escuderia,
                        password=reg_pass,
                        nombre=reg_nombre,
                        apellido=reg_apellido,
                        correo=reg_correo,
                        escuderia=reg_escuderia,
                    )
                    st.success(f"✅ Cuenta creada. Ya puedes iniciar sesión como **{reg_escuderia}**")
                except Exception as e:
                    err = str(e).lower()
                    if "unique" in err or "duplicate" in err:
                        if "correo" in err:
                            st.error("Ese correo ya está registrado")
                        elif "escuderia" in err or "username" in err:
                            st.error("Ese nombre de escudería ya está en uso, elige otro")
                        else:
                            st.error("Uno de los datos ya está registrado (correo o escudería)")
                    else:
                        st.error(f"Error al crear cuenta: {e}")

    st.stop()


# =========================
# SIDEBAR
# =========================
st.sidebar.success(f"Usuario: {st.session_state.username}")

if st.sidebar.button("Cerrar sesión"):
    st.session_state.clear()
    st.rerun()

if st.session_state.is_admin:
    menu_opciones = ["Super Admin", "Dashboard", "Carreras", "Race View", "Bonos"]
else:
    menu_opciones = ["Dashboard", "Mi Pick", "Carreras", "Race View", "Bonos"]

menu = st.sidebar.selectbox("Menú", menu_opciones)

# =========================
# Carga temporada activa
# =========================
temporada = crud.obtener_temporada_activa()

if not temporada:
    st.error("No hay temporada activa")
    st.stop()

temporada_id = temporada["id"]

# Sincronizamos automáticamente datos de F1DB para la temporada actual (por ahora, 2026)
try:
    crud.actualizar_carreras_desde_f1db(temporada_id, year=2026)
except Exception as e:
    logger.error(f"No se pudo sincronizar carreras desde F1DB: {e}")

# =========================
# SUPER ADMIN
# =========================
if menu == "Super Admin" and st.session_state.is_admin:
    st.sidebar.markdown("**Modo Admin**")
    admin_menu = st.sidebar.radio(
        "Admin Menu", 
        ["Temporadas", "Pilotos", "Usuarios", "Carreras", "Resultados"]
    )

    # Temporadas
    if admin_menu == "Temporadas":
        st.subheader("Temporadas")

        nombre = st.text_input("Nombre")
        inicio = st.date_input("Inicio")
        fin = st.date_input("Fin")

        if st.button("Crear temporada"):
            crud.crear_temporada(
                nombre,
                inicio.isoformat(),
                fin.isoformat()
            )
            st.success("Temporada creada")
            st.rerun()

        st.divider()

        temporadas = crud.listar_temporadas()
        if temporadas.empty:
            st.info("No hay temporadas creadas.")
        else:
            for _, row in temporadas.iterrows():
                col1, col2, col3, col4, col5 = st.columns(5)
                col1.write(row["id"])
                col2.write(row["nombre"])
                col3.write(row["fecha_inicio"])
                col4.write(row["fecha_fin"])
                if row["activa"]:
                    col5.success("Activa")
                else:
                    if col5.button(f"Activar {row['id']}"):
                        crud.activar_temporada(row["id"])
                        st.success("Temporada activada")
                        st.rerun()

    # Pilotos
    if admin_menu == "Pilotos":
        st.subheader("Pilotos")

        pilotos = crud.listar_pilotos()
        st.dataframe(pilotos)

        st.divider()

        with st.expander("Agregar nuevo piloto"):
            codigo = st.text_input("Código (VER, NOR...)", key="new_codigo")
            nombre = st.text_input("Nombre", key="new_nombre")
            escuderia = st.text_input("Escudería", key="new_escuderia")
            if st.button("Crear piloto"):
                crud.crear_piloto(codigo, nombre, escuderia)
                st.success("Piloto creado")
        
        with st.expander("Editar piloto"):
            piloto_seleccionado = st.selectbox(
                "Seleccione piloto",
                pilotos["id"],
                format_func=lambda x: pilotos.loc[pilotos["id"] == x, "nombre"].values[0]
            )

            piloto = pilotos[pilotos["id"] == piloto_seleccionado].iloc[0]

            codigo_edit = st.text_input("Código", value=piloto["codigo"])
            nombre_edit = st.text_input("Nombre", value=piloto["nombre"])
            escuderia_edit = st.text_input("Escudería", value=piloto["escuderia"])
            activo_edit = st.checkbox("Activo", value=bool(piloto["activo"]))

            if st.button("Actualizar piloto"):
                crud.editar_piloto(
                    piloto_id=piloto_seleccionado,
                    codigo=codigo_edit,
                    nombre=nombre_edit,
                    escuderia=escuderia_edit,
                    activo=int(activo_edit)
                )
                st.success("Piloto actualizado")
                st.rerun()

    # Usuarios
    if admin_menu == "Usuarios":
        st.subheader("Usuarios")

        col1, col2 = st.columns(2)
        with col1:
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
        with col2:
            nombre = st.text_input("Nombre")
            apellido = st.text_input("Apellido")
            is_admin = st.checkbox("Is Admin")

        if st.button("Crear usuario"):
            if not username or not password:
                st.error("Username y password son obligatorios.")
            else:
                crud.crear_usuario(
                    username=username,
                    password=password,
                    is_admin=int(is_admin),
                    nombre=nombre or None,
                    apellido=apellido or None,
                )
                st.success("Usuario creado")
                st.rerun()

        usuarios = crud.listar_usuarios()
        if usuarios is None or usuarios.empty:
            st.info("No hay usuarios registrados.")
        else:
            # No mostramos el hash de password en la tabla
            cols_to_show = [
                c
                for c in ["id", "username", "nombre", "apellido", "is_admin", "created_at"]
                if c in usuarios.columns
            ]
            st.dataframe(usuarios[cols_to_show], use_container_width=True, hide_index=True)

            with st.expander("Editar usuario"):
                usuario_seleccionado = st.selectbox(
                    "Seleccione usuario",
                    usuarios["id"],
                    format_func=lambda uid: usuarios.loc[usuarios["id"] == uid, "username"].values[0],
                )

                usuario_rows = usuarios[usuarios["id"] == usuario_seleccionado]
                if usuario_rows.empty:
                    st.error("No se encontró el usuario seleccionado.")
                    nuevo_username = ""
                    nuevo_is_admin = False
                    nuevo_nombre = ""
                    nuevo_apellido = ""
                else:
                    usuario = usuario_rows.iloc[0]

                    nuevo_username = st.text_input("Nuevo username", value=usuario["username"])
                    nuevo_is_admin = st.checkbox("Nuevo is admin", value=bool(usuario["is_admin"]))
                    nuevo_nombre = st.text_input("Nombre", value=usuario.get("nombre", ""))
                    nuevo_apellido = st.text_input("Apellido", value=usuario.get("apellido", ""))

                nuevo_password = st.text_input("Nuevo password (opcional)", type="password")

                if st.button("Actualizar usuario") and not usuario_rows.empty:
                    if not nuevo_username:
                        st.error("El username no puede estar vacío.")
                    else:
                        crud.editar_usuario(
                            usuario_id=usuario_seleccionado,
                            username=nuevo_username,
                            is_admin=int(nuevo_is_admin),
                            new_password=nuevo_password or None,
                            nombre=nuevo_nombre,
                            apellido=nuevo_apellido,
                        )
                        st.success("Usuario actualizado")
                        st.rerun()

    # Carreras
    if admin_menu == "Carreras":
        st.subheader("Carreras")

        carreras = crud.listar_carreras_temporada(temporada_id)
        if carreras.empty:
            st.info("No hay carreras registradas.")
        else:
            # Vista admin enriquecida con datos de F1DB e incluyendo ID
            df_admin = _build_carreras_view(carreras, year_hint=2026, include_id=True)
            st.dataframe(df_admin, use_container_width=True, hide_index=True)

        with st.expander("Agregar nueva carrera"):

            round_num = st.number_input("Round", min_value=1, step=1)
            nombre = st.text_input("Nombre")
            fecha = st.date_input("Fecha")
            kms = st.number_input("Kms de pista", min_value=0.0, step=0.1)
            vueltas = st.number_input("Vueltas", min_value=0, step=1)
            pista = st.text_input("Pista (nombre del circuito)")
            hora = st.text_input("Hora de inicio (HH:MM)")

            if st.button("Crear carrera"):
                crud.crear_carrera(
                    temporada_id,
                    round_num,
                    nombre,
                    fecha.isoformat(),
                    kms,
                    int(vueltas) if vueltas is not None else None,
                    pista,
                    hora,
                )
                st.success("Carrera creada")
                st.rerun()

        with st.expander("Editar carrera"):
            carrera_seleccionada = st.selectbox(
                "Seleccione carrera",
                carreras["id"],
                format_func=lambda x: carreras.loc[carreras["id"] == x, "nombre"].values[0]
            )

            carrera = carreras[carreras["id"] == carrera_seleccionada].iloc[0]

            round_edit = st.number_input("Round", min_value=1, value=carrera["round"], step=1)
            nombre_edit = st.text_input("Nombre", value=carrera["nombre"])
            fecha_edit = st.date_input("Fecha", value=datetime.fromisoformat(carrera["inicio"]))
            kms_edit = st.number_input("Kms de pista", min_value=0.0, step=0.1, value=float(carrera.get("kms", 0) or 0))
            vueltas_edit = st.number_input("Vueltas", min_value=0, step=1, value=int(carrera.get("vueltas", 0) or 0))
            pista_edit = st.text_input("Pista (nombre del circuito)", value=carrera.get("pista", ""))
            hora_edit = st.text_input("Hora de inicio (HH:MM)", value=carrera.get("hora", ""))

            col1, col2 = st.columns(2)
            with col1:
                if st.button("Actualizar carrera"):
                    crud.editar_carrera(
                        carrera_id=carrera_seleccionada,
                        round_num=round_edit,
                        nombre=nombre_edit,
                        inicio=fecha_edit.isoformat(),
                        kms=kms_edit,
                        vueltas=int(vueltas_edit) if vueltas_edit is not None else None,
                        pista=pista_edit,
                        hora=hora_edit,
                    )
                    st.success("Carrera actualizada")
                    st.rerun()

            with col2:
                if st.button("Eliminar carrera"):
                    crud.eliminar_carrera(carrera_seleccionada)
                    st.success("Carrera eliminada")
                    st.rerun()

    # Resultados
    if admin_menu == "Resultados":
        st.title("🏁 Cargar resultados de carrera")

        # =========================
        # Selección de carrera
        # =========================
        carreras = crud.listar_carreras_temporada(temporada_id)

        if carreras.empty:
            st.info("No hay carreras registradas")
            st.stop()

        carrera_label_map = {
            f"R{c.round} — {c.nombre} ({c.inicio})": c.id
            for c in carreras.itertuples()
        }

        carrera_label = st.selectbox(
            "Seleccione carrera",
            carrera_label_map.keys()
        )

        carrera_id = carrera_label_map[carrera_label]

        st.divider()

        # =========================
        # Pilotos
        # =========================
        pilotos = crud.listar_pilotos(activos_only=True)

        if pilotos.empty:
            st.warning("No hay pilotos activos")
            st.stop()

        st.subheader("Resultados")

        # Opciones de posición: sin posición, DNF + 1..N (N = cantidad de pilotos)
        max_pos = len(pilotos)
        opciones_pos = ["-", "DNF"] + [str(i) for i in range(1, max_pos + 1)]

        # Obtener resultados previos (si existen)
        resultados_previos = crud.obtener_resultados_carrera(carrera_id)
        resultados_map = {
            r["piloto_id"]: r["posicion"]
            for r in resultados_previos
        }

        # Construir DataFrame compacto para edición tipo tabla
        df_resultados = pd.DataFrame({
            "piloto_id": pilotos["id"],
            "Piloto": pilotos.apply(lambda row: f"{row['codigo']} — {row['nombre']}", axis=1),
        })

        def _pos_to_str(pid):
            pos = resultados_map.get(pid)
            return "-" if pos is None else str(pos)

        df_resultados["Posición"] = df_resultados["piloto_id"].apply(_pos_to_str)

        df_edit = st.data_editor(
            df_resultados,
            hide_index=True,
            column_config={
                "Piloto": st.column_config.TextColumn("Piloto", disabled=True),
                "Posición": st.column_config.SelectboxColumn(
                    "Posición",
                    options=opciones_pos,
                    required=False,
                ),
            },
            use_container_width=True,
        )

        # Pasar a dict {piloto_id: posicion_int_or_None}
        resultados_input = {}
        for _, fila in df_edit.iterrows():
            pid = int(fila["piloto_id"])
            val = fila["Posición"]
            if val in (None, "-", "DNF"):
                resultados_input[pid] = None
            else:
                try:
                    resultados_input[pid] = int(val)
                except ValueError:
                    resultados_input[pid] = None

        # Guardar resultados
        if st.button("💾 Guardar resultados"):
            crud.borrar_resultados_carrera(carrera_id)

            for piloto_id, posicion in resultados_input.items():
                # Si no se seleccionó posición, no guardamos fila
                if posicion is None:
                    continue

                crud.guardar_resultado(
                    carrera_id,
                    piloto_id,
                    posicion
                )

            # Recalcular puntos para esta carrera
            crud.recalcular_puntos_carrera(carrera_id)

            st.success("Resultados y puntos guardados correctamente")
            st.rerun()
    
# =========================
# DASHBOARD
# =========================
if menu == "Dashboard":
    # Ficha de piloto seleccionado (pick actual para la próxima carrera)
    # Debe ir dentro de with col_izq:

    st.title("🏁 Dashboard")
    # =========================
    # PRÓXIMA CARRERA + MI PICK (lado a lado)
    # =========================

    proxima = crud.obtener_proxima_carrera(temporada_id)

    col_izq, col_der = st.columns(2)

    # Bloque Próxima carrera (izquierda)
    with col_izq:
        st.markdown("""
        <style>
        .f1-card-modern {
            background: linear-gradient(135deg, #23272f 80%, #2e3140 100%);
            border-radius: 20px;
            box-shadow: 0 6px 32px 0 rgba(0,0,0,0.18), 0 1.5px 8px 0 #00eaff33;
            padding: 28px 22px 22px 22px;
            margin-bottom: 22px;
            min-height: 260px;
            max-width: 370px;
            border: 2.5px solid #00eaff44;
            position: relative;
        }
        .f1-card-modern .f1-countdown {
            background: linear-gradient(90deg, #00eaff 0%, #0055ff 100%);
            color: #fff;
            border-radius: 14px 14px 0 0;
            font-size: 2.1rem;
            font-weight: 800;
            letter-spacing: 1.5px;
            text-align: center;
            margin: -28px -22px 18px -22px;
            padding: 18px 0 10px 0;
            box-shadow: 0 2px 12px #00eaff33;
        }
        .f1-card-modern .f1-card-header {
            font-weight: 700;
            font-size: 1.25rem;
            margin-bottom: 7px;
            color: #00eaff;
            letter-spacing: 0.7px;
        }
        .f1-card-modern .f1-card-title {
            font-size: 1.12rem;
            margin-bottom: 5px;
            color: #fff;
        }
        .f1-card-modern .f1-card-meta {
            font-size: 1.01rem;
            margin-bottom: 12px;
            color: #b0eaff;
        }
        .f1-card-modern .f1-card-footer {
            font-size: 0.98rem;
            color: #a0a0a0;
            display: flex;
            gap: 18px;
            justify-content: center;
        }
        .f1-card-modern .f1-layout-img {
            height: 120px;
            width: 120px;
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 0 auto 14px auto;
            background: #23272f;
            border-radius: 14px;
            overflow: hidden;
            box-shadow: 0 2px 12px #00eaff22;
        }
        </style>
        """, unsafe_allow_html=True)
        st.subheader("⏭️ Próxima Carrera")
        if not proxima:
            st.success("🎉 No hay más carreras pendientes")
        else:
            inicio = datetime.fromisoformat(proxima["inicio"]).replace(tzinfo=timezone.utc)
            ahora = datetime.now(timezone.utc)
            delta = inicio - ahora
            dias = delta.days
            horas, rem = divmod(delta.seconds, 3600)
            minutos, segundos = divmod(rem, 60)
            pista_name = str(proxima["pista"]).strip() if "pista" in proxima.keys() else ""
            carrera_nombre = proxima["nombre"] if "nombre" in proxima.keys() else ""
            kms = proxima["kms"] if "kms" in proxima.keys() else ""
            vueltas = proxima["vueltas"] if "vueltas" in proxima.keys() else ""
            round_val = proxima["round"] if "round" in proxima.keys() else ""
            inicio_str = proxima["inicio"] if "inicio" in proxima.keys() else ""
            import unicodedata
            def normaliza(s):
                s = str(s).strip().lower()
                s = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
                return s
            equivalencias_manual = {
                'melbourne': 'albert park circuit',
                'shanghai': 'shanghai international circuit',
                'suzuka': 'suzuka international racing course',
                'bahrain': 'bahrain international circuit',
                'jeddah': 'jeddah corniche circuit',
                'miami': 'miami international autodrome',
                'gilles villeneuve': 'circuit gilles-villeneuve',
                'montreal': 'circuit gilles-villeneuve',
                'monaco': 'circuit de monaco',
                'catalunya': 'circuit de barcelona-catalunya',
                'barcelona': 'circuit de barcelona-catalunya',
                'red bull ring': 'red bull ring',
                'silverstone': 'silverstone circuit',
                'spa-francorchamps': 'circuit de spa-francorchamps',
                'spa': 'circuit de spa-francorchamps',
                'hungaroring': 'hungaroring',
                'zandvoort': 'circuit zandvoort',
                'monza': 'autodromo nazionale monza',
                'madring': 'circuito de madring',
                'madrid': 'circuito de madring',
                'baku': 'baku city circuit',
                'marina bay': 'marina bay street circuit',
                'singapore': 'marina bay street circuit',
                'americas': 'circuit of the americas',
                'austin': 'circuit of the americas',
                'hermanos rodriguez': 'autodromo hermanos rodriguez',
                'mexico city': 'autodromo hermanos rodriguez',
                'jose carlos pace': 'autodromo jose carlos pace - interlagos',
                'interlagos': 'autodromo jose carlos pace - interlagos',
                'las vegas': 'las vegas street circuit',
                'lusail': 'losail international circuit',
                'yas marina': 'yas marina circuit',
            }
            pista_name_norm = normaliza(pista_name)
            layout_key = pista_name_norm
            if layout_key not in _CIRCUIT_LAYOUTS and pista_name_norm in equivalencias_manual:
                layout_key = normaliza(equivalencias_manual[pista_name_norm])
            img_html = ""
            if layout_key in _CIRCUIT_LAYOUTS:
                coords = _CIRCUIT_LAYOUTS[layout_key]
                layout_buf = _plot_layout_icon(coords, width=110, height=110)
                import base64
                layout_bytes = layout_buf.getvalue()
                layout_b64 = base64.b64encode(layout_bytes).decode('utf-8')
                img_html = f"<img src='data:image/png;base64,{layout_b64}' width='110' style='display:block;margin:auto;border-radius:8px;'/>"
            else:
                img_html = "<span style='color:#888;font-size:0.9rem;'>Sin layout</span>"
            st.markdown(f"""
            <div class="f1-card-modern">
                <div class="f1-countdown">{dias}d {horas:02}h {minutos:02}m {segundos:02}s</div>
                <div class="f1-layout-img">{img_html}</div>
                <div class="f1-card-header">R{round_val} · {pista_name}</div>
                <div class="f1-card-title">{carrera_nombre}</div>
                <div class="f1-card-meta">{inicio.strftime('%d %b %Y — %H:%M UTC')}</div>
                <div class="f1-card-footer">
                    <span>{kms} km</span>
                    <span>{vueltas} vueltas</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
            st.caption("⏱️ Picks se bloquean al iniciar la carrera")

    # Bloque Mi Pick (derecha, solo usuarios no-admin)
    with col_der:
        if not st.session_state.is_admin:
            st.subheader("Mi Pick (5° lugar)")

            if not proxima:
                st.info("No hay próxima carrera disponible para hacer pick.")
            else:
                pilotos = crud.listar_pilotos()
                if pilotos.empty:
                    st.info("No hay pilotos registrados.")
                else:
                    piloto_ids = pilotos["id"].tolist()

                    pick_existente = crud.obtener_pick_usuario(
                        st.session_state.user_id,
                        proxima["id"],
                    )

                    if pick_existente and pick_existente["piloto_id"] in piloto_ids:
                        index_inicial = piloto_ids.index(pick_existente["piloto_id"])
                    else:
                        index_inicial = 0

                    # Dropdown "escondido" que controla la tarjeta grande
                    piloto_id = st.selectbox(
                        label="",
                        options=piloto_ids,
                        index=index_inicial,
                        format_func=lambda x: pilotos.loc[pilotos["id"] == x, "nombre"].values[0],
                        key=f"dashboard_pick_{proxima['id']}",
                        label_visibility="collapsed",
                    )

                    piloto_sel = pilotos[pilotos["id"] == piloto_id].iloc[0]

                    img_path = _get_piloto_image_path(piloto_sel["codigo"])
                    if img_path:
                        st.image(img_path, width=180)

                    # Tarjeta grande con el pick actual (nombre + código + escudería)
                    st.markdown(f"""
                    <div style="
                        background:#222;
                        padding:24px;
                        border-radius:12px;
                        text-align:center;
                        color:white;
                        margin-bottom:8px;
                    ">
                        <h2 style="margin-bottom:4px;">{piloto_sel['nombre']}</h2>
                        <p style="margin:0; font-size:0.9rem;">Código: {piloto_sel['codigo']}</p>
                        <p style="margin:0; font-size:0.9rem;">Escudería: {piloto_sel['escuderia']}</p>
                    </div>
                    """, unsafe_allow_html=True)

                    if carrera_bloqueada(proxima["inicio"]):
                        st.warning("La carrera ya está bloqueada para picks. No puedes cambiar tu selección.")
                    else:
                        if st.button("Guardar Pick", key=f"dashboard_guardar_pick_{proxima['id']}"):
                            crud.guardar_pick(
                                st.session_state.user_id,
                                proxima["id"],
                                int(piloto_id),
                            )
                            st.success("Pick guardado correctamente.")
                            st.rerun()

            # Lista "Five Fives All Time" (top 5 pilotos más elegidos), muy compacta
            top_picks = crud.top_picks_global(temporada_id)

            if top_picks.empty:
                st.info("Aún no hay picks registrados")
            else:
                top5 = top_picks.head(5)
                items = []
                for i, row in enumerate(top5.itertuples(), start=1):
                    items.append(f"{i}. {row.piloto_nombre} — {row.pick_count} picks")

                lista_html = "<br/>".join(items)
                st.markdown(
                    f"""
                    <div style="margin-top:4px; font-size:0.85rem; line-height:1.05;">
                        <b>Five Fives All Time</b><br/>
                        {lista_html}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    st.divider()

    # =========================
    # TABLA GENERAL (STANDINGS + CARRERAS)
    # =========================
    st.subheader("📈 Standings General")

    progreso = crud.progreso_pilotos_temporada(temporada_id)

    if not progreso.empty:
        # Matriz resumen: filas = usuarios, columnas = carreras, con total al inicio
        matriz = (
            progreso
            .pivot_table(
                index="username",
                columns="round",
                values="puntos",
                aggfunc="sum",
                fill_value=0,
            )
            .sort_index(axis=1)
        )

        totales = progreso.groupby("username")["puntos"].sum()
        matriz.insert(0, "Total", totales)
        matriz = matriz.sort_values("Total", ascending=False)

        # Añadir ranking y decorar nombres con corona/medallas
        matriz = matriz.reset_index()  # username pasa a columna
        matriz["rank"] = matriz.index + 1

        def _decorar_usuario(row):
            nombre = row["username"]
            r = row["rank"]
            if r == 1:
                return f"{nombre} 🥇👑"
            if r == 2:
                return f"{nombre} 🥈"
            if r == 3:
                return f"{nombre} 🥉"
            return nombre

        matriz["Usuario"] = matriz.apply(_decorar_usuario, axis=1)

        # Asignar un color fijo por usuario (para tabla y gráfica)
        usernames = matriz["username"].tolist()

        palette = [
            "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
            "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
        ]
        user_color = {u: palette[i % len(palette)] for i, u in enumerate(usernames)}

        # Columnas de carreras (rounds)
        race_cols = [c for c in matriz.columns if isinstance(c, (int, float))]
        race_cols = sorted(race_cols)

        # Orden final: color, usuario, total, carreras
        columnas_finales = ["Usuario", "Total"] + race_cols
        matriz_display = matriz[columnas_finales].rename(
            columns={c: f"R{int(c)}" for c in race_cols}
        )
        # Columna visual de color como franja muy discreta (sin texto)
        row_colors = [user_color[u] for u in usernames]
        matriz_display.insert(0, "Color", "")
        matriz_display = matriz_display.rename(columns={"Color": " "})

        def _colorize_columns(col):
            if col.name == " ":
                return [f"background-color: {c}" for c in row_colors]
            return [""] * len(col)

        st.dataframe(
            matriz_display.style.apply(_colorize_columns, axis=0),
            use_container_width=True,
            hide_index=True,
        )

        # Gráfica de líneas usando puntos acumulados por round, con eje Y >= 0
        pivot_chart = (
            progreso
            .pivot(index="round", columns="username", values="puntos_acum")
            .sort_index()
        )

        chart_df = (
            pivot_chart
            .reset_index()
            .melt(id_vars=["round"], var_name="Usuario", value_name="PuntosAcum")
        )

        max_y = float(chart_df["PuntosAcum"].max() or 0)

        chart = (
            alt.Chart(chart_df)
            .mark_line(point=True)
            .encode(
                x=alt.X(
                    "round:Q",
                    title="Round",
                    axis=alt.Axis(grid=False),  # sin grid vertical
                ),
                y=alt.Y(
                    "PuntosAcum:Q",
                    title="Puntos acumulados",
                    scale=alt.Scale(domain=[0, max_y + 1 if max_y > 0 else 1]),
                    axis=alt.Axis(grid=True, tickCount=5),  # menos líneas horizontales
                ),
                color=alt.Color(
                    "Usuario:N",
                    scale=alt.Scale(
                        domain=list(user_color.keys()),
                        range=list(user_color.values()),
                    ),
                    legend=None,
                ),
            )
        )

        st.altair_chart(chart, use_container_width=True)
    else:
        st.info("Aún no hay carreras con puntos calculados.")
   
# =========================
# MI PICK
# =========================
elif menu == "Mi Pick":
    st.title("🎯 Mis Picks")

    st.subheader("Historial de mis picks (temporada actual)")

    historial = crud.historial_picks_usuario(
        st.session_state.user_id,
        temporada_id,
    )

    if historial.empty:
        st.info("Aún no has hecho picks en esta temporada.")
    else:
        df_hist = historial.copy()
        df_hist["inicio"] = pd.to_datetime(df_hist["inicio"], errors="coerce").dt.strftime("%d %b")
        df_hist = df_hist.rename(
            columns={
                "round": "R",
                "carrera": "Carrera",
                "inicio": "Fecha",
                "piloto_codigo": "Código",
                "piloto_nombre": "Piloto",
                "posicion_real": "Pos. Real",
                "puntos": "Puntos",
            }
        )

        st.dataframe(df_hist, use_container_width=True, hide_index=True)

        # Análisis simple
        total_puntos = int(historial["puntos"].sum())
        carreras_con_pick = len(historial)
        carreras_con_puntos = int((historial["puntos"] > 0).sum())
        promedio = historial["puntos"].mean() if carreras_con_pick > 0 else 0
        mejor = historial.sort_values("puntos", ascending=False).iloc[0]

        st.markdown("**Análisis rápido**")
        c1, c2, c3 = st.columns(3)
        c1.metric("Puntos totales", total_puntos)
        c2.metric("Promedio por carrera", f"{promedio:.1f}")
        c3.metric("Carreras con puntos", f"{carreras_con_puntos}/{carreras_con_pick}")

        st.caption(
            f"Mejor pick: R{int(mejor['round'])} — {mejor['piloto_nombre']} con {int(mejor['puntos'])} pts"
        )

    st.divider()

    # =========================
    # Pick único: 5° de la temporada
    # =========================
    st.subheader("Selección 5° lugar de la temporada")

    # Regla de bloqueo: hasta que arranca la 3ª carrera se puede editar;
    # una vez que la 3ª carrera está bloqueada, ya no se puede cambiar.
    carreras_temp = crud.listar_carreras_temporada(temporada_id)
    carrera_r3 = None
    if not carreras_temp.empty:
        r3 = carreras_temp[carreras_temp["round"] == 3]
        if not r3.empty:
            carrera_r3 = r3.iloc[0]

    temporada_bloqueada = False
    if carrera_r3 is not None:
        # Usamos la misma lógica de bloqueo que para los picks de carrera
        temporada_bloqueada = carrera_bloqueada(carrera_r3["inicio"])

    pilotos = crud.listar_pilotos()
    if pilotos.empty:
        st.info("No hay pilotos registrados.")
    else:
        piloto_ids = pilotos["id"].tolist()
        pick_temp = crud.obtener_pick_temporada(
            st.session_state.user_id,
            temporada_id,
        )

        piloto_id_inicial = None
        if pick_temp and pick_temp["piloto_id"] in piloto_ids:
            piloto_id_inicial = pick_temp["piloto_id"]

        if temporada_bloqueada:
            # Solo mostramos lo que quedó guardado (si es que hubo pick)
            if piloto_id_inicial is None:
                st.warning("La ventana para elegir el 5° de la temporada ya cerró y no registraste ningún pick.")
            else:
                piloto_sel = pilotos[pilotos["id"] == piloto_id_inicial].iloc[0]
                img_path = _get_piloto_image_path(piloto_sel["codigo"])
                if img_path:
                    st.image(img_path, width=180)
                st.markdown(f"""
                <div style="
                    background:#222;
                    padding:24px;
                    border-radius:12px;
                    text-align:center;
                    color:white;
                    margin-bottom:8px;
                ">
                    <h3 style="margin-bottom:4px;">{piloto_sel['nombre']}</h3>
                    <p style="margin:0; font-size:0.9rem;">Código: {piloto_sel['codigo']}</p>
                    <p style="margin:0; font-size:0.9rem;">Escudería: {piloto_sel['escuderia']}</p>
                </div>
                """, unsafe_allow_html=True)

                st.info("La selección de 5° de la temporada está bloqueada para el resto del año.")
        else:
            # Se puede elegir / editar hasta antes de que arranque la R3
            if piloto_id_inicial is not None:
                index_inicial = piloto_ids.index(piloto_id_inicial)
            else:
                index_inicial = 0

            piloto_id = st.selectbox(
                label="",
                options=piloto_ids,
                index=index_inicial,
                format_func=lambda x: pilotos.loc[pilotos["id"] == x, "nombre"].values[0],
                key=f"pick_temporada_{temporada_id}",
                label_visibility="collapsed",
            )

            piloto_sel = pilotos[pilotos["id"] == piloto_id].iloc[0]

            img_path = _get_piloto_image_path(piloto_sel["codigo"])
            if img_path:
                st.image(img_path, width=180)

            st.markdown(f"""
            <div style="
                background:#222;
                padding:24px;
                border-radius:12px;
                text-align:center;
                color:white;
                margin-bottom:8px;
            ">
                <h3 style="margin-bottom:4px;">{piloto_sel['nombre']}</h3>
                <p style="margin:0; font-size:0.9rem;">Código: {piloto_sel['codigo']}</p>
                <p style="margin:0; font-size:0.9rem;">Escudería: {piloto_sel['escuderia']}</p>
            </div>
            """, unsafe_allow_html=True)

            if st.button("Guardar selección de temporada"):
                crud.guardar_pick_temporada(
                    st.session_state.user_id,
                    temporada_id,
                    int(piloto_id),
                )
                st.success("Selección de temporada guardada correctamente.")
                st.rerun()

        st.caption("Si le atinas al 5° de la temporada, compartes el bono con todos los que eligieron al mismo piloto.")

# =========================
# CARRERAS
# =========================
elif menu == "Carreras":
    st.title("🏆 Grand Prixes")


    carreras = crud.listar_carreras_temporada(temporada_id)

    # Vista de calendario tipo tarjetas + tablas
    if carreras.empty:
        st.info("No hay carreras registradas.")
    else:
        # Construimos un view enriquecido para usar en tarjetas y tablas
        df_view = _build_carreras_view(carreras, year_hint=2026, include_id=st.session_state.is_admin)

        # ==== Grid de tarjetas de carreras (para todos) ====
        st.subheader("Calendario de la temporada")

        df_sorted = df_view.sort_values("Round") if "Round" in df_view.columns else df_view
        cols = st.columns(3)

        for idx, row in df_sorted.iterrows():
            col = cols[idx % 3]
            with col:
                # Usar el nombre original de pista de la base de datos
                pista_name = str(carreras.loc[carreras['id'] == row['ID'], 'pista'].values[0]) if 'ID' in row and 'pista' in carreras.columns else str(row.get('Pista', '')).strip()
                round_val = row.get("Round", None)

                img_candidates = []
                if pista_name:
                    slug = (
                        pista_name.lower()
                        .replace(" ", "-")
                        .replace("'", "")
                        .replace(".", "")
                    )
                    img_candidates.append(IMG_DIR_PISTAS / f"{slug}.png")
                    img_candidates.append(IMG_DIR_PISTAS / f"{slug}.jpg")

                if round_val is not None:
                    try:
                        r_int = int(round_val)
                        img_candidates.append(IMG_DIR_PISTAS / f"r{r_int}.png")
                        img_candidates.append(IMG_DIR_PISTAS / f"r{r_int}.jpg")
                    except Exception:
                        pass

                img_path = None
                for p in img_candidates:
                    if p.is_file():
                        img_path = p
                        break

                # Si no hay imagen, intentamos layout
                layout_buf = None
                if img_path is None and pista_name:
                    layout_key = pista_name.strip().lower()
                    if layout_key in _CIRCUIT_LAYOUTS:
                        coords = _CIRCUIT_LAYOUTS[layout_key]
                        if coords and len(coords) > 2:
                            layout_buf = _plot_layout_icon(coords, width=80, height=80)

                # Construir tarjeta con imagen/layout dentro del bloque principal
                carrera_nombre = row.get("Carrera", row.get("nombre", ""))
                inicio_str = row.get("Inicio", row.get("inicio", ""))
                kms = row.get("Kms", "")
                vueltas = row.get("Vueltas", "")
                # Buscar layout usando equivalencias manuales y normalización
                import unicodedata
                def normaliza(s):
                    s = str(s).strip().lower()
                    s = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
                    return s
                equivalencias_manual = {
                    'melbourne': 'albert park circuit',
                    'shanghai': 'shanghai international circuit',
                    'suzuka': 'suzuka international racing course',
                    'bahrain': 'bahrain international circuit',
                    'jeddah': 'jeddah corniche circuit',
                    'miami': 'miami international autodrome',
                    'gilles villeneuve': 'circuit gilles-villeneuve',
                    'montreal': 'circuit gilles-villeneuve',
                    'monaco': 'circuit de monaco',
                    'catalunya': 'circuit de barcelona-catalunya',
                    'barcelona': 'circuit de barcelona-catalunya',
                    'red bull ring': 'red bull ring',
                    'silverstone': 'silverstone circuit',
                    'spa-francorchamps': 'circuit de spa-francorchamps',
                    'spa': 'circuit de spa-francorchamps',
                    'hungaroring': 'hungaroring',
                    'zandvoort': 'circuit zandvoort',
                    'monza': 'autodromo nazionale monza',
                    'madring': 'circuito de madring',
                    'madrid': 'circuito de madring',
                    'baku': 'baku city circuit',
                    'marina bay': 'marina bay street circuit',
                    'singapore': 'marina bay street circuit',
                    'americas': 'circuit of the americas',
                    'austin': 'circuit of the americas',
                    'hermanos rodriguez': 'autodromo hermanos rodriguez',
                    'mexico city': 'autodromo hermanos rodriguez',
                    'jose carlos pace': 'autodromo jose carlos pace - interlagos',
                    'interlagos': 'autodromo jose carlos pace - interlagos',
                    'las vegas': 'las vegas street circuit',
                    'lusail': 'losail international circuit',
                    'yas marina': 'yas marina circuit',
                }
                pista_name_norm = normaliza(pista_name)
                layout_key = pista_name_norm
                if layout_key not in _CIRCUIT_LAYOUTS and pista_name_norm in equivalencias_manual:
                    layout_key = normaliza(equivalencias_manual[pista_name_norm])
                img_html = ""
                if img_path is not None:
                    img_html = f"<img src='file:///{img_path}' width='110' style='display:block;margin:auto;border-radius:6px;'/>"
                elif layout_key in _CIRCUIT_LAYOUTS:
                    coords = _CIRCUIT_LAYOUTS[layout_key]
                    layout_buf = _plot_layout_icon(coords, width=110, height=110)
                    import base64
                    layout_bytes = layout_buf.getvalue()
                    layout_b64 = base64.b64encode(layout_bytes).decode('utf-8')
                    img_html = f"<img src='data:image/png;base64,{layout_b64}' width='110' style='display:block;margin:auto;border-radius:6px;'/>"
                else:
                    img_html = "<span style='color:#888;font-size:0.9rem;'>Sin layout</span>"
                st.markdown(f"""
                <div class="f1-card" style="display:flex;flex-direction:column;align-items:center;justify-content:center;padding:18px;background:#23272f;border-radius:16px;margin-bottom:18px;min-height:240px;width:100%;max-width:340px;box-shadow:0 4px 16px rgba(0,0,0,0.13);">
                    <div style="height:120px;width:120px;display:flex;align-items:center;justify-content:center;margin-bottom:12px;background:#23272f;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.10);">
                        {img_html}
                    </div>
                    <div class="f1-card-header" style="font-weight:600;font-size:1.15rem;margin-bottom:6px;color:#fff;letter-spacing:0.5px;">R{int(round_val) if round_val is not None else ''} · {pista_name}</div>
                    <div class="f1-card-title" style="font-size:1.05rem;margin-bottom:4px;color:#e0e0e0;">{carrera_nombre}</div>
                    <div class="f1-card-meta" style="font-size:0.92rem;margin-bottom:10px;color:#b0b0b0;">{inicio_str}</div>
                    <div class="f1-card-footer" style="font-size:0.88rem;color:#a0a0a0;display:flex;gap:16px;">
                        <span>{kms} km</span>
                        <span>{vueltas} vueltas</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

        st.divider()

        # ==== Tablas: vista completa para admin, simplificada para jugadores ====
        if st.session_state.is_admin:
            st.subheader("Tabla completa de carreras")
            st.dataframe(df_view, use_container_width=True, hide_index=True)
        else:
            st.subheader("Lista de carreras")
            # Usuarios ven una versión sin ID pero con las mismas columnas extra
            cols_to_show = [c for c in df_view.columns if c != "ID"]
            # Mostrar la columna 'Pista' tal como está en la base de datos
            if "pista" in carreras.columns:
                df_view["Pista"] = carreras["pista"].where(carreras["pista"].notna(), df_view["Pista"])
            st.dataframe(df_view[cols_to_show], use_container_width=True, hide_index=True)

    # Solo los admins pueden editar carreras
    if not carreras.empty and st.session_state.is_admin:
        st.divider()

        st.subheader("Editar Carrera")
        carrera_seleccionada = st.selectbox(
            "Seleccione carrera",
            carreras["id"],
            format_func=lambda x: carreras.loc[carreras["id"] == x, "nombre"].values[0]
        )
        carrera = carreras[carreras["id"] == carrera_seleccionada].iloc[0]
        round_edit = st.number_input("Round", min_value=1, value=carrera["round"], step=1)
        nombre_edit = st.text_input("Nombre", value=carrera["nombre"])
        inicio_edit = st.date_input("Fecha", value=datetime.fromisoformat(carrera["inicio"]))
        if st.button("Actualizar carrera"):
            crud.editar_carrera(
                carrera_id=carrera_seleccionada,
                round_num=round_edit,
                nombre=nombre_edit,
                inicio=inicio_edit.isoformat()
            )
            st.success("Carrera actualizada")
            st.rerun()

# =========================
# RACE VIEW
# =========================
elif menu == "Race View":
    st.title("📊 Race View — picks históricos")

    historial_all = crud.historial_picks_temporada(temporada_id)

    if historial_all.empty:
        st.info("Aún no hay picks registrados en esta temporada.")
    else:
        df_all = historial_all[["username", "round", "piloto_codigo"]].copy()

        matriz = (
            df_all
            .pivot_table(
                index="username",
                columns="round",
                values="piloto_codigo",
                aggfunc="first",
                fill_value="",
            )
            .sort_index(axis=1)
        )

        matriz = matriz.reset_index()
        matriz = matriz.rename(columns={"username": "Usuario"})

        round_cols = [c for c in matriz.columns if isinstance(c, (int, float))]
        rename_map = {c: f"R{int(c)}" for c in round_cols}
        matriz = matriz.rename(columns=rename_map)

        st.dataframe(matriz, use_container_width=True, hide_index=True)

# =========================
# BONOS
# =========================
elif menu == "Bonos":
    st.title("💰 Bonos y logros")

    # Bono 5° de la temporada
    st.subheader("Bono 5° de la temporada")
    picks_temp = crud.listar_picks_temporada(temporada_id)

    if picks_temp.empty:
        st.info("Aún no hay picks de 5° de temporada registrados.")
    else:
        df_picks = picks_temp.rename(
            columns={
                "username": "Usuario",
                "piloto_codigo": "Código",
                "piloto_nombre": "Piloto",
            }
        )

        st.dataframe(df_picks, use_container_width=True, hide_index=True)

        dist = (
            df_picks.groupby(["Código", "Piloto"], as_index=False)["Usuario"]
            .count()
            .rename(columns={"Usuario": "Jugadores"})
            .sort_values("Jugadores", ascending=False)
        )

        st.markdown("**Distribución de picks por piloto (quién compartiría el bono):**")
        st.dataframe(dist, use_container_width=True, hide_index=True)

    # Mejores desempeños por carrera
    st.subheader("Mejores desempeños por carrera")
    top = crud.mejores_carreras_temporada(temporada_id, limit=10)

    if top.empty:
        st.info("Aún no hay puntos calculados en la temporada.")
    else:
        df_top = top.rename(
            columns={
                "username": "Usuario",
                "round": "R",
                "carrera": "Carrera",
                "puntos": "Puntos",
            }
        )

        st.dataframe(df_top, use_container_width=True, hide_index=True)
        st.caption("Top entradas individuales por carrera (puntos en una sola carrera).")

