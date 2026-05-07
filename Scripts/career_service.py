"""
career_service.py — Fictieve loopbaandienst (poort 5003)
Geeft de loopbaan terug van de persoon wiens RRN/BIS-nummer in het JWT-token zit.

Authenticatie: Bearer-token in de Authorization-header
  Authorization: Bearer <jwt>

Endpoint:
  GET /loopbaan          →  volledige loopbaan (dimona + rsvz + rvw)
  GET /loopbaan/dimona   →  alleen Dimona-aangiften
  GET /loopbaan/rsvz     →  alleen RSVZ-aansluitingen
  GET /loopbaan/rvw      →  alleen RVA-werkloosheidsperioden
  GET /status            →  beschikbaarheid dienst + geladen bestanden

Start: python Scripts/career_service.py
Of via: python Scripts/start_services.py
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import jwt
from flask import Flask, jsonify, request

ROOT     = Path(__file__).resolve().parent.parent
SAVE_DIR = ROOT / "Generated Data"
CFG_PATH = ROOT / "config.json"

JWT_ALGO = "HS256"
AUDIENCE = "metaworld-demo"

app = Flask(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _jwt_secret() -> str:
    with open(CFG_PATH, encoding="utf-8") as f:
        cfg = json.load(f)
    return f"fas-belgique-{cfg['meta']['seed']}-fictief"


def _err(status: int, code: str, message: str):
    return jsonify({"error": {"code": code, "message": message}}), status


def _bearer_token() -> str | None:
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return header[7:].strip()
    return None


def _decode_token(raw: str) -> tuple[dict | None, tuple | None]:
    """
    Decodeert en valideert het JWT.
    Geeft (claims, None) bij succes of (None, fout-response) bij mislukking.
    """
    try:
        claims = jwt.decode(raw, _jwt_secret(), algorithms=[JWT_ALGO], audience=AUDIENCE)
        return claims, None
    except jwt.ExpiredSignatureError:
        return None, _err(401, "TOKEN_EXPIRED", "Het sessietoken is verlopen.")
    except jwt.InvalidTokenError as exc:
        return None, _err(401, "TOKEN_INVALID", f"Ongeldig token: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# Loopbaanindex (lazy, eenmalig geladen per prefix)
# ─────────────────────────────────────────────────────────────────────────────

@lru_cache(maxsize=4)
def _laad_index(prefix: str) -> dict[str, dict]:
    """
    Bouwt een dict {ssin: {"dimona": [...], "rsvz": [...], "rvw": [...]}}
    uit de drie loopbaan-JSON-bestanden voor het gegeven prefix.
    """
    index: dict[str, dict] = {}

    bestanden = {
        "dimona": SAVE_DIR / f"{prefix}_dimona.json",
        "rsvz":   SAVE_DIR / f"{prefix}_rsvz.json",
        "rvw":    SAVE_DIR / f"{prefix}_rvw.json",
    }

    for sleutel, pad in bestanden.items():
        if not pad.exists():
            continue
        with open(pad, encoding="utf-8") as f:
            records = json.load(f)
        for rec in records:
            ssin = str(rec.get("rijksregisternummer", ""))
            if not ssin:
                continue
            if ssin not in index:
                index[ssin] = {"dimona": [], "rsvz": [], "rvw": []}
            index[ssin][sleutel].append(rec)

    return index


def _loopbaan_van(ssin: str) -> dict | None:
    """Zoekt de loopbaan op voor één SSIN over alle beschikbare prefixen."""
    prefixen = {
        p.stem.replace("_dimona", "")
        for p in SAVE_DIR.glob("*_dimona.json")
    }
    if not prefixen:
        return None
    for prefix in sorted(prefixen):
        idx = _laad_index(prefix)
        if ssin in idx:
            return idx[ssin]
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/status", methods=["GET"])
def status():
    bestanden = {
        pad.name: pad.stat().st_size
        for pad in SAVE_DIR.glob("*.json")
        if any(pad.name.endswith(s) for s in ("_dimona.json", "_rsvz.json", "_rvw.json"))
    }
    return jsonify({
        "dienst":    "loopbaandienst",
        "versie":    "metaworldV2",
        "bestanden": bestanden,
        "beschikbaar": bool(bestanden),
    })


@app.route("/loopbaan", methods=["GET"])
def loopbaan():
    raw = _bearer_token()
    if not raw:
        return _err(401, "NO_TOKEN",
                    "Geef een geldig JWT mee via 'Authorization: Bearer <token>'.")

    claims, fout = _decode_token(raw)
    if fout:
        return fout

    ssin = claims.get("ssin", "")
    if not ssin:
        return _err(400, "NO_SSIN", "Het token bevat geen 'ssin'-claim.")

    data = _loopbaan_van(ssin)
    if data is None:
        return _err(404, "GEEN_LOOPBAANDATA",
                    f"Geen loopbaanbestanden gevonden. "
                    "Genereer eerst loopbanen via genereer_maatschappij.py.")

    return jsonify({
        "ssin":      ssin,
        "auth_type": claims.get("auth_type", "rijksregister"),
        "dimona":    data["dimona"],
        "rsvz":      data["rsvz"],
        "rvw":       data["rvw"],
    })


@app.route("/loopbaan/dimona", methods=["GET"])
def loopbaan_dimona():
    raw = _bearer_token()
    if not raw:
        return _err(401, "NO_TOKEN",
                    "Geef een geldig JWT mee via 'Authorization: Bearer <token>'.")

    claims, fout = _decode_token(raw)
    if fout:
        return fout

    ssin = claims.get("ssin", "")
    data = _loopbaan_van(ssin)
    if data is None:
        return _err(404, "GEEN_LOOPBAANDATA", "Geen loopbaanbestanden gevonden.")

    return jsonify({"ssin": ssin, "dimona": data["dimona"]})


@app.route("/loopbaan/rsvz", methods=["GET"])
def loopbaan_rsvz():
    raw = _bearer_token()
    if not raw:
        return _err(401, "NO_TOKEN",
                    "Geef een geldig JWT mee via 'Authorization: Bearer <token>'.")

    claims, fout = _decode_token(raw)
    if fout:
        return fout

    ssin = claims.get("ssin", "")
    data = _loopbaan_van(ssin)
    if data is None:
        return _err(404, "GEEN_LOOPBAANDATA", "Geen loopbaanbestanden gevonden.")

    return jsonify({"ssin": ssin, "rsvz": data["rsvz"]})


@app.route("/loopbaan/rvw", methods=["GET"])
def loopbaan_rvw():
    raw = _bearer_token()
    if not raw:
        return _err(401, "NO_TOKEN",
                    "Geef een geldig JWT mee via 'Authorization: Bearer <token>'.")

    claims, fout = _decode_token(raw)
    if fout:
        return fout

    ssin = claims.get("ssin", "")
    data = _loopbaan_van(ssin)
    if data is None:
        return _err(404, "GEEN_LOOPBAANDATA", "Geen loopbaanbestanden gevonden.")

    return jsonify({"ssin": ssin, "rvw": data["rvw"]})


# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  Loopbaandienst (fictief)")
    print("  http://localhost:5003")
    print()
    print("  GET /loopbaan          →  volledige loopbaan")
    print("  GET /loopbaan/dimona   →  Dimona-aangiften")
    print("  GET /loopbaan/rsvz     →  RSVZ-aansluitingen")
    print("  GET /loopbaan/rvw      →  RVA-perioden")
    print("  GET /status            →  dienststatus")
    print()
    print("  Header: Authorization: Bearer <jwt>")
    print("  Stoppen: Ctrl+C")
    print("=" * 60)
    app.run(port=5003, debug=False)
