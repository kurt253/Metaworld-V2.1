"""
data_service.py — Fictieve overheidsdatadienst (poort 5002)
Leest het FAS-sessietoken (cookie) en toont de registergegevens van de persoon.

Start: python Scripts/data_service.py
Of via: python Scripts/start_services.py
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import jwt
import pandas as pd
from flask import Flask, render_template_string, request, redirect

ROOT     = Path(__file__).resolve().parent.parent
SAVE_DIR = ROOT / "Generated Data"
CFG_PATH = ROOT / "config.json"

AUTH_SERVICE_URL = "http://localhost:5001"
JWT_ALGO         = "HS256"
AUDIENCE         = "metaworld-demo"

ACR_LABEL = {
    "urn:be:fedict:iam:fas:Level1": "Niveau 1 — Gebruikersnaam & wachtwoord",
    "urn:be:fedict:iam:fas:Level2": "Niveau 2 — Tweestapsverificatie (sms)",
    "urn:be:fedict:iam:fas:Level3": "Niveau 3 — Itsme® / authenticatie-app",
    "urn:be:fedict:iam:fas:Level4": "Niveau 4 — eID-kaart",
}

FIELD_LABELS = {
    "rijksregisternummer": "Rijksregisternummer",
    "bisnummer":           "Bisnummer",
    "voornaam":            "Voornaam",
    "familienaam":         "Familienaam",
    "geslacht":            "Geslacht",
    "geslacht_gekend":     "Geslacht gekend",
    "geboortedatum":       "Geboortedatum",
    "geboorteplaats":      "Geboorteplaats",
    "geboorteland":        "Geboorteland",
    "nationaliteit":       "Nationaliteitsgroep",
    "burgerlijke_staat":   "Burgerlijke staat",
    "overlijdensdatum":    "Overlijdensdatum",
}

GESLACHT_LABEL = {"M": "Man", "F": "Vrouw", "X": "Onbekend"}


def _jwt_secret() -> str:
    with open(CFG_PATH, encoding="utf-8") as f:
        cfg = json.load(f)
    return f"fas-belgique-{cfg['meta']['seed']}-fictief"


def _load_registers():
    rr_pad  = SAVE_DIR / "metaworld_rijksregister.json"
    bis_pad = SAVE_DIR / "metaworld_bisregister.json"
    rr  = pd.read_json(rr_pad,  convert_dates=False) if rr_pad.exists()  else pd.DataFrame()
    bis = pd.read_json(bis_pad, convert_dates=False) if bis_pad.exists() else pd.DataFrame()
    return rr, bis


def _row_to_dict(row) -> dict:
    """Converteer pandas Series naar dict. NaN/NaT → None zodat Jinja2 'is none' correct werkt."""
    result = {}
    for k, v in row.items():
        try:
            result[k] = None if pd.isna(v) else v
        except (TypeError, ValueError):
            result[k] = v
    return result


def _find_person(ssin: str, auth_type: str) -> dict | None:
    rr, bis = _load_registers()
    if auth_type == "rijksregister" and not rr.empty:
        rows = rr[rr["rijksregisternummer"] == ssin]
        if not rows.empty:
            return _row_to_dict(rows.iloc[0])
    if auth_type == "bisregister" and not bis.empty:
        rows = bis[bis["bisnummer"] == ssin]
        if not rows.empty:
            return _row_to_dict(rows.iloc[0])
    return None


# --------------------------------------------------------------------------- #
# HTML-templates
# --------------------------------------------------------------------------- #

_BASE_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Segoe UI', Arial, sans-serif; background: #f0f2f5; color: #1a1a1a; }
.topbar {
  height: 6px;
  background: linear-gradient(to right,
    #1a1a1a 33.3%, #F5DD00 33.3%, #F5DD00 66.6%, #EF001F 66.6%);
}
.header {
  background: #fff; border-bottom: 2px solid #e8e8e8;
  padding: 14px 32px; display: flex; align-items: center;
  justify-content: space-between;
}
.header-left { display: flex; align-items: center; gap: 14px; }
.header-brand { font-size: 20px; font-weight: 700; letter-spacing: -0.5px; }
.header-sub   { font-size: 11px; color: #888; margin-top: 2px; }
.header-user  { font-size: 13px; color: #555; }
.header-user code { font-family: monospace; font-size: 13px; color: #0066cc; }
.card {
  max-width: 700px; margin: 40px auto;
  background: #fff; border-radius: 6px;
  box-shadow: 0 2px 12px rgba(0,0,0,.10); overflow: hidden;
}
.card-header {
  background: #0066cc; color: #fff;
  padding: 20px 28px;
}
.card-header h1 { font-size: 20px; font-weight: 700; margin-bottom: 4px; }
.card-header p  { font-size: 13px; opacity: .85; }
.card-body { padding: 28px; }
.section-title {
  font-size: 12px; font-weight: 700; text-transform: uppercase;
  letter-spacing: 1px; color: #888; margin-bottom: 12px;
}
.info-table { width: 100%; border-collapse: collapse; }
.info-table tr:last-child td { border-bottom: none; }
.info-table td {
  padding: 10px 12px; border-bottom: 1px solid #f0f0f0;
  font-size: 14px; vertical-align: top;
}
.info-table td:first-child {
  font-weight: 600; color: #555; width: 38%; white-space: nowrap;
}
.divider { border: none; border-top: 1px solid #eee; margin: 22px 0; }
.badge {
  display: inline-block; font-size: 11px;
  padding: 3px 10px; border-radius: 12px; font-weight: 600;
}
.badge-green  { background: #e6f7ee; color: #1a9c4e; border: 1px solid #a3d9b8; }
.badge-orange { background: #fff3e0; color: #e65c00; border: 1px solid #ffcc80; }
.badge-red    { background: #fff3f3; color: #c00; border: 1px solid #f5b3b3; }
.badge-gray   { background: #f5f5f5; color: #555; border: 1px solid #ddd; }
.deceased-banner {
  background: #fff3f3; border: 1px solid #f5b3b3;
  border-radius: 4px; padding: 10px 14px;
  font-size: 13px; color: #c00; margin-bottom: 16px;
  display: flex; align-items: center; gap: 8px;
}
.value-mono { font-family: 'Courier New', monospace; font-size: 13px; }
.btn {
  display: inline-block; padding: 9px 18px;
  border-radius: 4px; font-size: 13px; font-weight: 600;
  cursor: pointer; text-decoration: none; border: none;
  transition: background .2s;
}
.btn-primary { background: #0066cc; color: #fff; }
.btn-primary:hover { background: #0052a3; }
.btn-outline { background: #fff; color: #0066cc; border: 1px solid #0066cc; }
.btn-outline:hover { background: #f0f6ff; }

/* Token sectie (inklappbaar via details) */
details { margin-top: 16px; }
summary {
  cursor: pointer; font-size: 12px; font-weight: 700;
  color: #0066cc; text-transform: uppercase; letter-spacing: 1px;
  user-select: none; padding: 4px 0;
}
.token-raw {
  background: #f7f8fa; border: 1px solid #e4e4e4; border-radius: 4px;
  padding: 12px; margin-top: 10px; word-break: break-all;
  font-family: 'Courier New', monospace; font-size: 11px; color: #444;
}

/* Geen-token pagina */
.no-token-card {
  max-width: 480px; margin: 80px auto;
  background: #fff; border-radius: 6px;
  box-shadow: 0 2px 12px rgba(0,0,0,.10);
  padding: 40px; text-align: center;
}
.no-token-icon { font-size: 48px; margin-bottom: 16px; }
.no-token-card h2 { font-size: 20px; margin-bottom: 10px; }
.no-token-card p  { font-size: 14px; color: #555; margin-bottom: 28px; line-height: 1.6; }
.footer { text-align: center; padding: 20px; font-size: 11px; color: #aaa; }
"""

_NO_TOKEN_HTML = """
<!DOCTYPE html>
<html lang="nl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Datadienst – niet aangemeld</title>
  <style>{{ css }}</style>
</head>
<body>
<div class="topbar"></div>
<div class="header">
  <div class="header-left">
    <div>
      <div class="header-brand">🇧🇪 Overheidsdatadienst</div>
      <div class="header-sub">Fictieve persoonsgegevensdienst — simulatie</div>
    </div>
  </div>
</div>

<div class="no-token-card">
  <div class="no-token-icon">🔒</div>
  <h2>Niet aangemeld</h2>
  <p>
    {{ message }}<br><br>
    Meld u aan via de federale authenticatiedienst om uw gegevens
    te raadplegen.
  </p>
  <a href="{{ auth_url }}" class="btn btn-primary">Aanmelden via FAS →</a>
</div>

<div class="footer">Fictief systeem · Metaworld v2</div>
</body>
</html>
"""

_DATA_HTML = """
<!DOCTYPE html>
<html lang="nl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Persoonsgegevens – Overheidsdatadienst (fictief)</title>
  <style>{{ css }}</style>
</head>
<body>
<div class="topbar"></div>
<div class="header">
  <div class="header-left">
    <div>
      <div class="header-brand">🇧🇪 Overheidsdatadienst</div>
      <div class="header-sub">Fictieve persoonsgegevensdienst — simulatie</div>
    </div>
  </div>
  <div class="header-user">
    Aangemeld als <code>{{ claims.ssin }}</code> &nbsp;
    <a href="{{ auth_url }}/logout" style="font-size:12px;color:#c00;">Afmelden</a>
  </div>
</div>

<div class="card">
  <div class="card-header">
    <h1>Persoonsgegevens</h1>
    <p>Authentiek uittreksel uit het fictieve rijksregister / bisregister</p>
  </div>

  <div class="card-body">

    {% if deceased %}
    <div class="deceased-banner">
      ⚠ Deze persoon is <strong>overleden</strong> op {{ person.overlijdensdatum }}.
    </div>
    {% endif %}

    <!-- Persoonsgegevens -->
    <div class="section-title">Persoonsgegevens</div>
    <table class="info-table">
      {% for field, label in field_labels.items() %}
        {% set show = field in person and (person[field] is not none or field == 'overlijdensdatum') %}
        {% if show %}
        <tr>
          <td>{{ label }}</td>
          <td>
            {% if field in ('rijksregisternummer', 'bisnummer') %}
              <span class="value-mono">{{ person[field] }}</span>
            {% elif field == 'geslacht' %}
              {{ geslacht_labels.get(person[field], person[field]) }}
            {% elif field == 'geslacht_gekend' %}
              {{ 'Ja' if person[field] else 'Nee' }}
            {% elif field == 'overlijdensdatum' %}
              {% if person[field] is none or person[field] == '' %}
                <span class="badge badge-green">Nog in leven</span>
              {% else %}
                {{ person[field] }}
                <span class="badge badge-red" style="margin-left:6px;">Overleden</span>
              {% endif %}
            {% elif field == 'burgerlijke_staat' %}
              {% set bs = person[field] | replace('_', ' ') | title %}
              <span class="badge badge-gray">{{ bs }}</span>
            {% else %}
              {{ person[field] }}
            {% endif %}
          </td>
        </tr>
        {% endif %}
      {% endfor %}
    </table>

    <!-- Woonadres -->
    {% if person.get('adres_straat') %}
    <hr class="divider">
    <div class="section-title">Woonadres</div>
    <table class="info-table">
      <tr>
        <td>Straat</td>
        <td>
          {{ person.adres_straat }} {{ person.adres_nr }}
          {% if person.get('adres_bus') %} bus {{ person.adres_bus }}{% endif %}
        </td>
      </tr>
      <tr>
        <td>Gemeente</td>
        <td>{{ person.adres_postcode }} {{ person.adres_gemeente }}</td>
      </tr>
      <tr>
        <td>Provincie / Gewest</td>
        <td>{{ person.adres_provincie }} &nbsp;·&nbsp; {{ person.adres_gewest }}</td>
      </tr>
    </table>
    {% endif %}

    <hr class="divider">

    <!-- Authenticatiegegevens -->
    <div class="section-title">Authenticatiegegevens</div>
    <table class="info-table">
      <tr>
        <td>SSIN</td>
        <td><span class="value-mono">{{ claims.ssin }}</span></td>
      </tr>
      <tr>
        <td>Registertype</td>
        <td>
          {% if claims.auth_type == 'rijksregister' %}
            <span class="badge badge-green">Rijksregister</span>
          {% else %}
            <span class="badge badge-orange">Bisregister</span>
          {% endif %}
        </td>
      </tr>
      <tr>
        <td>Authenticatieniveau</td>
        <td>{{ acr_label }}</td>
      </tr>
      <tr>
        <td>Federatie-ID (sub)</td>
        <td><span class="value-mono" style="font-size:12px;">{{ claims.sub }}</span></td>
      </tr>
      <tr>
        <td>Geldig tot</td>
        <td>{{ exp_local }}</td>
      </tr>
      <tr>
        <td>Uitgever (iss)</td>
        <td><span style="font-size:12px;">{{ claims.iss }}</span></td>
      </tr>
    </table>

    <details>
      <summary>Ruwe JWT tonen</summary>
      <div class="token-raw">{{ raw_token }}</div>
    </details>

    <hr class="divider">
    <a href="{{ auth_url }}/logout" class="btn btn-outline">Afmelden</a>
  </div>
</div>

<div class="footer">Fictief systeem · Alle gegevens zijn volledig fictief · Metaworld v2</div>
</body>
</html>
"""


# --------------------------------------------------------------------------- #
# Flask-routes
# --------------------------------------------------------------------------- #

app = Flask(__name__)


def _no_token(message: str):
    return render_template_string(
        _NO_TOKEN_HTML,
        css=_BASE_CSS,
        message=message,
        auth_url=AUTH_SERVICE_URL,
    ), 401


@app.route("/", methods=["GET"])
def index():
    raw_token = request.cookies.get("fas_token")

    if not raw_token:
        return _no_token("Er is geen sessietoken aanwezig in uw browser.")

    try:
        claims = jwt.decode(
            raw_token,
            _jwt_secret(),
            algorithms=[JWT_ALGO],
            audience=AUDIENCE,
        )
    except jwt.ExpiredSignatureError:
        return _no_token(
            "Uw sessietoken is verlopen. Meld u opnieuw aan."
        )
    except jwt.InvalidTokenError as exc:
        return _no_token(
            f"Het sessietoken is ongeldig ({exc}). Meld u opnieuw aan."
        )

    ssin      = claims.get("ssin", "")
    auth_type = claims.get("auth_type", "rijksregister")
    person    = _find_person(ssin, auth_type)

    if person is None:
        return _no_token(
            f"Het nummer '{ssin}' werd niet teruggevonden in de registerbestanden. "
            "Mogelijk zijn de bestanden gewijzigd of verwijderd na uw aanmelding."
        )

    exp_dt    = datetime.fromtimestamp(claims["exp"], tz=timezone.utc)
    exp_local = exp_dt.astimezone().strftime("%Y-%m-%d %H:%M:%S")
    acr_label = ACR_LABEL.get(claims.get("acr", ""), claims.get("acr", ""))
    deceased  = bool(person.get("overlijdensdatum"))

    return render_template_string(
        _DATA_HTML,
        css=_BASE_CSS,
        claims=claims,
        person=person,
        deceased=deceased,
        exp_local=exp_local,
        acr_label=acr_label,
        raw_token=raw_token,
        field_labels=FIELD_LABELS,
        geslacht_labels=GESLACHT_LABEL,
        auth_url=AUTH_SERVICE_URL,
    )


if __name__ == "__main__":
    print("=" * 60)
    print("  Overheidsdatadienst (fictief)")
    print("  http://localhost:5002")
    print("=" * 60)
    app.run(port=5002, debug=False)
