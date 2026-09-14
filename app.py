import runpy
from pathlib import Path

import streamlit as st

from native_auth import get_usuario_by_email


APP_CORE = Path(__file__).with_name("app_core.py")


def _auth_configurada() -> bool:
    try:
        auth = st.secrets["auth"]
        required = (
            "redirect_uri",
            "cookie_secret",
            "client_id",
            "client_secret",
            "server_metadata_url",
        )
        return all(str(auth.get(key, "")).strip() for key in required)
    except Exception:
        return False


def _cargar_usuario_interno(user: dict) -> None:
    st.session_state.user_id = user["id"]
    st.session_state.username = user["username"]
    st.session_state.is_admin = user["is_admin"]
    st.session_state.escuderia = user.get("escuderia", "")
    st.session_state.foto_perfil = user.get("foto_perfil", "")


# Configuramos la página aquí porque este archivo es ahora el entrypoint.
st.set_page_config(page_title="Quiniela F1", layout="wide")

# El logout de la app histórica deja esta bandera antes del rerun.
# La convertimos en un logout OIDC real para eliminar la cookie nativa de Streamlit.
if st.session_state.pop("_logout_pending", False):
    for key in ("user_id", "username", "is_admin", "escuderia", "foto_perfil"):
        st.session_state.pop(key, None)
    st.logout()
    st.stop()

if not _auth_configurada():
    st.title("🏎️ TheBigPrixFantasy")
    st.error("La autenticación con Google todavía no está configurada en los Secrets de Streamlit.")
    st.caption("Faltan los valores OIDC de Google: redirect_uri, cookie_secret, client_id, client_secret y server_metadata_url.")
    st.stop()

if not st.user.is_logged_in:
    st.title("🏎️ TheBigPrixFantasy")
    st.write("Inicia sesión con la cuenta de Google asociada a tu usuario de TheBigPrixFantasy.")
    st.button("Continuar con Google", on_click=st.login, type="primary")
    st.stop()

email = str(getattr(st.user, "email", "") or "").strip().lower()
if not email:
    st.error("Google no devolvió un correo electrónico para esta cuenta.")
    st.button("Cerrar sesión", on_click=st.logout)
    st.stop()

usuario = get_usuario_by_email(email)
if not usuario:
    st.error(f"El correo {email} no está vinculado a ningún usuario de TheBigPrixFantasy.")
    st.caption("Usa la cuenta de Google cuyo correo coincide con el correo registrado en tu perfil.")
    st.button("Cerrar sesión", on_click=st.logout)
    st.stop()

_cargar_usuario_interno(usuario)

# app_core.py conserva toda la lógica actual de la quiniela. Ya llega con
# user_id cargado, por lo que su login histórico no participa en la sesión.
# Evitamos además que intente volver a configurar la página por segunda vez.
_original_set_page_config = st.set_page_config
st.set_page_config = lambda *args, **kwargs: None
try:
    runpy.run_path(str(APP_CORE), run_name="__main__")
finally:
    st.set_page_config = _original_set_page_config
