"""Consulta segura de clasificaciones finales en OpenF1."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_BASE = "https://api.openf1.org/v1"
TIMEOUT_SECONDS = 35
MAX_ATTEMPTS = 3


class OpenF1Error(RuntimeError):
    """Error controlado al consultar o validar OpenF1."""


def _get_json(endpoint: str, **params):
    url = f"{API_BASE}/{endpoint}?{urlencode(params)}"
    last_error = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        request = Request(url, headers={"User-Agent": "TheBigPrixFantasy/1.0"})
        try:
            with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
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

    sesiones_validas = [s for s in sesiones if s.get("date_start") and not s.get("is_cancelled", False)]
    if not sesiones_validas:
        raise OpenF1Error("OpenF1 no devolvió sesiones de carrera válidas.")

    sesion = min(sesiones_validas, key=lambda s: abs(_as_utc(s["date_start"]) - inicio_local))
    diferencia_horas = abs((_as_utc(sesion["date_start"]) - inicio_local).total_seconds()) / 3600
    if diferencia_horas > 36:
        raise OpenF1Error(
            "No se encontró una carrera de OpenF1 que coincida con la fecha seleccionada."
        )

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
