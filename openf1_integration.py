"""Consulta segura de clasificaciones finales en OpenF1."""

from __future__ import annotations

import json
import ssl
import time
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import certifi


API_BASE = "https://api.openf1.org/v1"
TIMEOUT_SECONDS = 35
MAX_ATTEMPTS = 3


class OpenF1Error(RuntimeError):
    """Error controlado al consultar o validar OpenF1."""


def _get_json(endpoint: str, **params):
    url = f"{API_BASE}/{endpoint}?{urlencode(params)}"
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    last_error = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        request = Request(url, headers={"User-Agent": "TheBigPrixFantasy/1.0"})
        try:
            with urlopen(request, timeout=TIMEOUT_SECONDS, context=ssl_context) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            last_error = exc
            # 429 y errores del servidor suelen ser transitorios.
            if exc.code not in (429, 500, 502, 503, 504):
                raise OpenF1Error(f"OpenF1 respondió con HTTP {exc.code}.") from exc
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc

        if attempt < MAX_ATTEMPTS:
            time.sleep(attempt)

    if isinstance(last_error, HTTPError):
        detalle = f"HTTP {last_error.code}"
    elif isinstance(last_error, URLError):
        detalle = str(last_error.reason)
    elif isinstance(last_error, TimeoutError):
        detalle = "tiempo de espera agotado"
    else:
        detalle = "respuesta JSON inválida"
    raise OpenF1Error(
        f"OpenF1 no respondió después de {MAX_ATTEMPTS} intentos ({detalle}). Intenta nuevamente."
    ) from last_error


def _as_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _meeting_for_race(carrera: dict, sesiones: list[dict]) -> tuple[dict, list[dict]]:
    """Encuentra el meeting de una carrera local con una tolerancia segura."""
    inicio_local = _as_utc(carrera["inicio"])
    carreras_api = [
        s for s in sesiones
        if s.get("session_name") == "Race" and s.get("date_start")
        and not s.get("is_cancelled", False)
    ]
    if not carreras_api:
        raise OpenF1Error("OpenF1 no devolvió carreras válidas para esa temporada.")

    carrera_api = min(carreras_api, key=lambda s: abs(_as_utc(s["date_start"]) - inicio_local))
    diferencia_horas = abs((_as_utc(carrera_api["date_start"]) - inicio_local).total_seconds()) / 3600
    if diferencia_horas > 36:
        raise OpenF1Error("No se encontró un fin de semana de OpenF1 que coincida con la carrera.")

    meeting_key = carrera_api.get("meeting_key")
    return carrera_api, [s for s in sesiones if s.get("meeting_key") == meeting_key]


def obtener_alineacion(carrera: dict) -> dict:
    """Obtiene la parrilla de la sesión más reciente disponible del GP.

    La actualización nunca se aplica aquí: el administrador recibe una vista
    previa y debe confirmarla. Esto evita que una consulta cambie picks.
    """
    if not carrera.get("inicio"):
        raise OpenF1Error("La carrera seleccionada no tiene fecha de inicio.")

    inicio_local = _as_utc(carrera["inicio"])
    sesiones = _get_json("sessions", year=inicio_local.year)
    carrera_api, sesiones_gp = _meeting_for_race(carrera, sesiones)
    ahora = datetime.now(timezone.utc)

    disponibles = [
        s for s in sesiones_gp
        if s.get("date_start")
        and _as_utc(s["date_start"]) <= ahora
        and s.get("session_name") != "Race"
        and not s.get("is_cancelled", False)
    ]
    disponibles.sort(key=lambda s: _as_utc(s["date_start"]), reverse=True)

    for sesion in disponibles:
        pilotos = _get_json("drivers", session_key=sesion["session_key"])
        alineacion = []
        vistos = set()
        for piloto in pilotos:
            codigo = str(piloto.get("name_acronym") or "").strip().upper()
            if not codigo or codigo in vistos:
                continue
            vistos.add(codigo)
            alineacion.append(
                {
                    "codigo": codigo,
                    "nombre": str(
                        piloto.get("full_name") or piloto.get("broadcast_name") or codigo
                    ).strip(),
                    "escuderia": str(piloto.get("team_name") or "").strip(),
                    "foto_url": piloto.get("headshot_url"),
                    "color_escuderia": str(piloto.get("team_colour") or "").strip(),
                    "numero": piloto.get("driver_number"),
                }
            )

        # Una sesión incompleta no es una base segura para reemplazar la parrilla.
        if len(alineacion) >= 20:
            alineacion.sort(key=lambda p: (p["escuderia"], p["nombre"]))
            return {
                "session_key": sesion["session_key"],
                "sesion": sesion.get("session_name") or "Sesión",
                "fecha": sesion.get("date_start") or "",
                "carrera": carrera_api.get("country_name") or carrera_api.get("location") or "Carrera",
                "circuito": carrera_api.get("circuit_short_name") or "",
                "alineacion": alineacion,
            }

    raise OpenF1Error(
        "Todavía no hay una sesión completa disponible para confirmar la alineación de este GP."
    )


def obtener_clasificacion(carrera: dict) -> dict:
    """Obtiene la carrera OpenF1 más cercana por fecha y su clasificación final.

    La coincidencia se limita a 36 horas para impedir que una selección errónea
    termine cargando los resultados de otro Grand Prix.
    """
    if not carrera.get("inicio"):
        raise OpenF1Error("La carrera seleccionada no tiene fecha de inicio.")

    inicio_local = _as_utc(carrera["inicio"])
    sesiones = _get_json("sessions", year=inicio_local.year, session_name="Race")
    if not sesiones:
        raise OpenF1Error(f"OpenF1 no devolvió carreras para {inicio_local.year}.")

    sesion, _ = _meeting_for_race(carrera, sesiones)

    if sesion.get("date_end") and _as_utc(sesion["date_end"]) > datetime.now(timezone.utc):
        raise OpenF1Error("La carrera seleccionada todavía no ha terminado.")

    session_key = sesion["session_key"]
    clasificacion = _get_json("session_result", session_key=session_key)
    if not clasificacion:
        raise OpenF1Error("La clasificación final todavía no está disponible.")

    pilotos = _get_json("drivers", session_key=session_key)
    codigos = {
        int(p["driver_number"]): str(p.get("name_acronym") or "").upper()
        for p in pilotos
        if p.get("driver_number") is not None
    }
    nombres = {
        int(p["driver_number"]): str(p.get("full_name") or p.get("broadcast_name") or "")
        for p in pilotos
        if p.get("driver_number") is not None
    }

    resultados = []
    for fila in clasificacion:
        numero = fila.get("driver_number")
        posicion = fila.get("position")
        if numero is None:
            continue
        numero = int(numero)
        resultados.append(
            {
                "codigo": codigos.get(numero, ""),
                "nombre": nombres.get(numero, f"Auto #{numero}"),
                "numero": numero,
                "posicion": int(posicion) if posicion is not None else None,
                "dnf": bool(fila.get("dnf", False)),
                "dns": bool(fila.get("dns", False)),
                "dsq": bool(fila.get("dsq", False)),
            }
        )

    posiciones = [r["posicion"] for r in resultados if r["posicion"] is not None]
    if not resultados or len(posiciones) != len(set(posiciones)):
        raise OpenF1Error("La clasificación recibida está vacía o contiene posiciones repetidas.")
    if any(not r["codigo"] for r in resultados):
        raise OpenF1Error("OpenF1 devolvió pilotos sin código identificable.")

    resultados.sort(key=lambda r: r["posicion"] if r["posicion"] is not None else 999)
    return {
        "session_key": session_key,
        "carrera": sesion.get("country_name") or sesion.get("location") or "Carrera",
        "circuito": sesion.get("circuit_short_name") or "",
        "fecha": sesion.get("date_start") or "",
        "resultados": resultados,
    }
