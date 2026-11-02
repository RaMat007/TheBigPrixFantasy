"""Consultas del dashboard React y guardado manual de picks.

LIGHTS OUT = inicio UTC de la carrera, sin margen previo.
No crea tablas, no calcula puntos y no ejecuta auto-picks.
"""
from datetime import datetime, timezone

from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field
from psycopg2.extras import RealDictCursor
from db import get_connection


class ManualPick(BaseModel):
    carrera_id: int = Field(gt=0)
    piloto_id: int = Field(gt=0)


def _utc(raw):
    value = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def install_dashboard_routes(app, current_user):
    @app.get("/api/dashboard")
    def dashboard(user=Depends(current_user)):
        conn = get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT id FROM temporadas WHERE activa=1 LIMIT 1")
                active = cur.fetchone()
                if not active:
                    return {"next_race": None, "my_pick": None, "standings": [],
                            "rounds": [], "top_fives": [], "remaining": 0}
                sid = active["id"]
                now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
                cur.execute("""
                    SELECT id, round, nombre, inicio, pista
                    FROM carreras
                    WHERE temporada_id=%s AND NOT cancelada AND inicio>%s
                    ORDER BY inicio ASC LIMIT 1
                """, (sid, now))
                next_race = cur.fetchone()
                cur.execute("""
                    SELECT COUNT(*) AS count FROM carreras
                    WHERE temporada_id=%s AND NOT cancelada AND inicio>%s
                """, (sid, now))
                remaining = int(cur.fetchone()["count"])
                my_pick = None
                if next_race:
                    cur.execute("""
                        SELECT p.piloto_id, p.auto_asignado, d.codigo, d.nombre,
                               d.escuderia, d.foto_url
                        FROM picks p JOIN pilotos d ON d.id=p.piloto_id
                        WHERE p.usuario_id=%s AND p.carrera_id=%s
                    """, (user["id"], next_race["id"]))
                    my_pick = cur.fetchone()
                cur.execute("""
                    SELECT u.id, u.username,
                           COALESCE(NULLIF(u.escuderia,''),u.username) AS escuderia,
                           COALESCE(SUM(sc.puntos),0)::integer AS total
                    FROM usuarios u
                    LEFT JOIN (
                        SELECT pt.usuario_id, pt.puntos FROM puntos pt
                        JOIN carreras c ON c.id=pt.carrera_id
                        WHERE c.temporada_id=%s AND NOT c.cancelada
                    ) sc ON sc.usuario_id=u.id
                    WHERE u.is_admin=0
                    GROUP BY u.id,u.username,u.escuderia
                    ORDER BY total DESC,u.username ASC
                """, (sid,))
                standings = [dict(row) for row in cur.fetchall()]
                cur.execute("""
                    SELECT pt.usuario_id, c.round, pt.puntos
                    FROM puntos pt JOIN carreras c ON c.id=pt.carrera_id
                    JOIN usuarios u ON u.id=pt.usuario_id
                    WHERE c.temporada_id=%s AND NOT c.cancelada AND u.is_admin=0
                    ORDER BY c.round
                """, (sid,))
                point_rows = cur.fetchall()
                rounds = sorted({int(row["round"]) for row in point_rows})
                scores = {}
                for row in point_rows:
                    scores.setdefault(row["usuario_id"], {})[str(row["round"])] = int(row["puntos"] or 0)
                previous_rounds = rounds[:-1]
                previous = sorted(standings, key=lambda item: (
                    -sum(scores.get(item["id"], {}).get(str(r), 0) for r in previous_rounds),
                    item["username"]
                ))
                previous_positions = {item["id"]: i+1 for i,item in enumerate(previous)}
                for index, item in enumerate(standings):
                    item["position"] = index + 1
                    item["change"] = (previous_positions[item["id"]] - index - 1) if len(rounds)>1 else None
                    item["scores"] = scores.get(item["id"], {})
                cur.execute("""
                    SELECT d.codigo, d.nombre, COUNT(*)::integer AS picks
                    FROM picks p JOIN pilotos d ON d.id=p.piloto_id
                    JOIN carreras c ON c.id=p.carrera_id
                    WHERE c.temporada_id=%s AND NOT c.cancelada
                      AND EXISTS (SELECT 1 FROM resultados r WHERE r.carrera_id=c.id)
                    GROUP BY d.id,d.codigo,d.nombre
                    ORDER BY picks DESC,d.nombre ASC LIMIT 5
                """, (sid,))
                top_fives = [dict(row) for row in cur.fetchall()]
                return {"next_race": dict(next_race) if next_race else None,
                        "my_pick": dict(my_pick) if my_pick else None,
                        "standings": standings, "rounds": rounds,
                        "top_fives": top_fives, "remaining": remaining}
        finally:
            conn.close()

    @app.post("/api/me/pick")
    def save_pick(body: ManualPick, user=Depends(current_user)):
        if user["is_admin"]:
            raise HTTPException(403, detail="Los administradores no participan en los picks")
        conn = get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT c.id,c.temporada_id,c.inicio
                    FROM carreras c JOIN temporadas t ON t.id=c.temporada_id
                    WHERE c.id=%s AND t.activa=1 AND NOT c.cancelada
                    FOR UPDATE OF c
                """, (body.carrera_id,))
                race = cur.fetchone()
                if not race:
                    raise HTTPException(404, detail="Carrera no disponible")
                now = datetime.now(timezone.utc)
                if now >= _utc(race["inicio"]):
                    raise HTTPException(409, detail="LIGHTS OUT: la selección está cerrada")
                cur.execute("""
                    SELECT id FROM carreras
                    WHERE temporada_id=%s AND NOT cancelada AND inicio>%s
                    ORDER BY inicio ASC LIMIT 1
                """, (race["temporada_id"], now.replace(tzinfo=None).isoformat()))
                next_row = cur.fetchone()
                if not next_row or next_row["id"] != body.carrera_id:
                    raise HTTPException(409, detail="Solo se permite elegir para la próxima carrera")
                cur.execute("SELECT id FROM pilotos WHERE id=%s AND activo=1", (body.piloto_id,))
                if not cur.fetchone():
                    raise HTTPException(422, detail="Piloto no disponible")
                cur.execute("SELECT 1 FROM resultados WHERE carrera_id=%s LIMIT 1", (body.carrera_id,))
                if cur.fetchone():
                    raise HTTPException(409, detail="La carrera ya tiene resultados")
                cur.execute("""
                    INSERT INTO picks (usuario_id,carrera_id,piloto_id,timestamp,auto_asignado)
                    VALUES (%s,%s,%s,%s,0)
                    ON CONFLICT (usuario_id,carrera_id)
                    DO UPDATE SET piloto_id=EXCLUDED.piloto_id,
                                  timestamp=EXCLUDED.timestamp,
                                  auto_asignado=0
                """, (user["id"], body.carrera_id, body.piloto_id,
                      now.replace(tzinfo=None).isoformat()))
            conn.commit()
            return {"ok": True}
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
