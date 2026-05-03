"""
auth_service.py — Fictieve Federale Authenticatiedienst (poort 5001)
Simuleert CSAM/FAS op basis van de fictieve registers in Generated Data/.

Start: python Scripts/auth_service.py
Of via: python Scripts/start_services.py
"""

import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
import pandas as pd
from flask import Flask, make_response, redirect, render_template_string, request

ROOT     = Path(__file__).resolve().parent.parent
SAVE_DIR = ROOT / "Generated Data"
CFG_PATH = ROOT / "config.json"

SESSION_HOURS    = 8
DATA_SERVICE_URL = "http://localhost:5002"
JWT_ALGO         = "HS256"
AUDIENCE         = "metaworld-demo"

ACR = {
    1: "urn:be:fedict:iam:fas:Level1",
    2: "urn:be:fedict:iam:fas:Level2",
    3: "urn:be:fedict:iam:fas:Level3",
    4: "urn:be:fedict:iam:fas:Level4",
}
ACR_LABEL = {
    1: "Gebruikersnaam & wachtwoord",
    2: "Tweestapsverificatie (sms / e-mail)",
    3: "Itsme® / authenticatie-app",
    4: "eID-kaart (hoogste beveiliging)",
}


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
  background: #fff;
  border-bottom: 2px solid #e8e8e8;
  padding: 14px 32px;
  display: flex; align-items: center; gap: 14px;
}
.header-brand { font-size: 20px; font-weight: 700; letter-spacing: -0.5px; }
.header-sub   { font-size: 11px; color: #888; margin-top: 2px; }
.card {
  max-width: 520px; margin: 48px auto;
  background: #fff; border-radius: 6px;
  box-shadow: 0 2px 12px rgba(0,0,0,.10); padding: 40px;
}
h1 { font-size: 22px; margin-bottom: 6px; }
.lead { color: #555; font-size: 14px; margin-bottom: 28px; line-height: 1.5; }
.alert {
  padding: 10px 14px; border-radius: 4px;
  font-size: 13px; margin-bottom: 20px;
}
.alert-error { background:#fff3f3; border:1px solid #f5b3b3; color:#c00; }
.alert-warn  { background:#fffbe6; border:1px solid #ffe066; color:#7a5c00; }
.form-group { margin-bottom: 20px; }
.form-label { display:block; font-size:13px; font-weight:600; margin-bottom:6px; }
.form-input {
  width:100%; padding:10px 12px;
  border:1px solid #ccc; border-radius:4px;
  font-size:15px; font-family:monospace; letter-spacing:1px;
  transition: border-color .2s;
}
.form-input:focus { outline:none; border-color:#0066cc; box-shadow:0 0 0 3px rgba(0,102,204,.15); }
.level-grid { display:flex; flex-direction:column; gap:8px; }
.level-item {
  display:flex; align-items:flex-start; gap:10px;
  padding:10px 12px; border:1px solid #ddd; border-radius:4px;
  cursor:pointer; transition: border-color .15s, background .15s;
}
.level-item:hover { border-color:#aac4e8; background:#f8fbff; }
.level-item input { margin-top:3px; accent-color:#0066cc; flex-shrink:0; }
.level-title { font-size:13px; font-weight:600; }
.level-desc  { font-size:12px; color:#777; margin-top:2px; }
.btn {
  display:block; width:100%; padding:12px;
  background:#0066cc; color:#fff;
  border:none; border-radius:4px; font-size:15px;
  font-weight:600; cursor:pointer; margin-top:26px;
  text-align:center; text-decoration:none;
  transition: background .2s;
}
.btn:hover { background:#0052a3; }
.btn-outline {
  background:#fff; color:#0066cc; border:1px solid #0066cc;
}
.btn-outline:hover { background:#f0f6ff; }
.badge {
  display:inline-block; font-size:11px;
  background:#fff8e1; border:1px solid #ffe082; color:#7a5c00;
  padding:3px 10px; border-radius:12px; margin-bottom:18px;
}
.token-box {
  background:#f7f8fa; border:1px solid #e4e4e4; border-radius:4px;
  padding:16px; margin:20px 0; overflow:auto;
}
.token-box code {
  font-size:11px; word-break:break-all; color:#333;
  font-family:'Courier New', monospace;
}
.info-table { width:100%; border-collapse:collapse; font-size:13px; }
.info-table td { padding:7px 10px; border-bottom:1px solid #eee; vertical-align:top; }
.info-table td:first-child { font-weight:600; color:#555; width:40%; white-space:nowrap; }
.success-mark {
  width:56px; height:56px; border-radius:50%;
  background:#e6f7ee; color:#1a9c4e; font-size:26px;
  display:flex; align-items:center; justify-content:center;
  margin-bottom:16px;
}
.divider { border:none; border-top:1px solid #eee; margin:24px 0; }
.footer {
  text-align:center; padding:20px;
  font-size:11px; color:#aaa;
}
"""

_LOGIN_HTML = """
<!DOCTYPE html>
<html lang="nl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Aanmelden – FAS (fictief)</title>
  <style>{{ css }}</style>
</head>
<body>
<div class="topbar"></div>
<div class="header">
  <div>
    <div class="header-brand">🇧🇪 FAS</div>
    <div class="header-sub">Federale Authenticatiedienst — fictieve simulatie</div>
  </div>
</div>

<div class="card">
  <span class="badge">⚠ Fictief systeem · testomgeving · geen echte data</span>
  <h1>Meld u aan bij uw overheid</h1>
  <p class="lead">
    Geef uw rijksregisternummer of bisnummer in en kies uw authenticatieniveau.
    Na aanmelding ontvangt u een geldig sessietoken (JWT).
  </p>

  {% if error %}
  <div class="alert alert-error">❌ {{ error }}</div>
  {% endif %}

  {% if warn %}
  <div class="alert alert-warn">⚠ {{ warn }}</div>
  {% endif %}

  <form method="POST" action="/authenticate" autocomplete="off">
    <div class="form-group">
      <label class="form-label" for="nummer">Rijksregisternummer of bisnummer</label>
      <input class="form-input" type="text" id="nummer" name="nummer"
             placeholder="75.06.08-997.02" value="{{ nummer }}" autofocus required>
    </div>

    <div class="form-group">
      <label class="form-label">Authenticatieniveau</label>
      <div class="level-grid">
        {% for lvl in [1, 2, 3, 4] %}
        <label class="level-item">
          <input type="radio" name="level" value="{{ lvl }}"
                 {% if lvl == selected_level %}checked{% endif %}>
          <div>
            <div class="level-title">Niveau {{ lvl }}</div>
            <div class="level-desc">{{ level_labels[lvl] }}</div>
          </div>
        </label>
        {% endfor %}
      </div>
    </div>

    <button type="submit" class="btn">Aanmelden →</button>
  </form>
</div>

<div class="footer">
  Fictief systeem · Alle gegevens zijn volledig fictief · Metaworld v2
</div>
</body>
</html>
"""

_SUCCESS_HTML = """
<!DOCTYPE html>
<html lang="nl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Aanmelding geslaagd – FAS (fictief)</title>
  <style>{{ css }}</style>
</head>
<body>
<div class="topbar"></div>
<div class="header">
  <div>
    <div class="header-brand">🇧🇪 FAS</div>
    <div class="header-sub">Federale Authenticatiedienst — fictieve simulatie</div>
  </div>
</div>

<div class="card">
  <div class="success-mark">✓</div>
  <h1>Aanmelding geslaagd</h1>
  <p class="lead">
    Uw sessietoken is aangemaakt en opgeslagen als cookie <code>fas_token</code>.
    Het token is geldig voor <strong>{{ session_hours }} uur</strong>.
  </p>

  <hr class="divider">
  <strong style="font-size:13px;color:#555;">Tokeninhoud (JWT-claims)</strong>
  <table class="info-table" style="margin-top:10px;">
    <tr><td>Uitgever (iss)</td><td>{{ claims.iss }}</td></tr>
    <tr><td>SSIN</td><td><code>{{ claims.ssin }}</code></td></tr>
    <tr><td>Registertype</td><td>{{ claims.auth_type }}</td></tr>
    <tr><td>Niveau (acr)</td><td><code style="font-size:11px;">{{ claims.acr }}</code></td></tr>
    <tr><td>Federatie-ID (sub)</td><td><code style="font-size:11px;">{{ claims.sub }}</code></td></tr>
    <tr><td>Geldig tot</td><td>{{ exp_local }}</td></tr>
  </table>

  <hr class="divider">
  <strong style="font-size:13px;color:#555;">Ruwe JWT</strong>
  <div class="token-box">
    <code>{{ token }}</code>
  </div>

  <a href="{{ data_url }}" class="btn">Ga naar de datadienst →</a>
  <a href="/" class="btn btn-outline" style="margin-top:10px;">Opnieuw aanmelden</a>
</div>

<div class="footer">
  Fictief systeem · Alle gegevens zijn volledig fictief · Metaworld v2
</div>
</body>
</html>
"""


# --------------------------------------------------------------------------- #
# Flask-routes
# --------------------------------------------------------------------------- #

app = Flask(__name__)


@app.route("/", methods=["GET"])
def login():
    return render_template_string(
        _LOGIN_HTML,
        css=_BASE_CSS,
        error=None, warn=None, nummer="",
        selected_level=3, level_labels=ACR_LABEL,
    )


@app.route("/authenticate", methods=["POST"])
def authenticate():
    nummer = request.form.get("nummer", "").strip()
    level  = int(request.form.get("level", 3))

    def _fail(error=None, warn=None):
        return render_template_string(
            _LOGIN_HTML,
            css=_BASE_CSS,
            error=error, warn=warn, nummer=nummer,
            selected_level=level, level_labels=ACR_LABEL,
        ), 400

    if not nummer:
        return _fail(error="Vul een rijksregisternummer of bisnummer in.")

    rr, bis = _load_registers()
    if rr.empty and bis.empty:
        return _fail(warn=(
            "Er zijn geen registerbestanden gevonden in 'Generated Data/'. "
            "Genereer en bewaar eerst een register via de Streamlit-app."
        ))

    auth_type = None
    if not rr.empty and nummer in rr["rijksregisternummer"].values:
        auth_type = "rijksregister"
    elif not bis.empty and nummer in bis["bisnummer"].values:
        auth_type = "bisregister"

    if auth_type is None:
        return _fail(error=(
            f"Het nummer '{nummer}' werd niet gevonden in het rijksregister "
            "of bisregister. Controleer het formaat (bv. 75.06.08-997.02)."
        ))

    now     = datetime.now(timezone.utc)
    exp     = now + timedelta(hours=SESSION_HOURS)
    fed_id  = str(uuid.uuid4())
    sub     = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"metaworld:{nummer}"))

    claims = {
        "iss":       "https://fas.belgium.be/oidc",
        "sub":       sub,
        "aud":       AUDIENCE,
        "iat":       int(now.timestamp()),
        "exp":       int(exp.timestamp()),
        "acr":       ACR[level],
        "ssin":      nummer,
        "auth_type": auth_type,
        "fedID":     fed_id,
        "locale":    "nl",
    }

    token = jwt.encode(claims, _jwt_secret(), algorithm=JWT_ALGO)

    exp_local = exp.astimezone().strftime("%Y-%m-%d %H:%M:%S")

    resp = make_response(
        render_template_string(
            _SUCCESS_HTML,
            css=_BASE_CSS,
            claims=claims,
            token=token,
            exp_local=exp_local,
            session_hours=SESSION_HOURS,
            data_url=DATA_SERVICE_URL,
        )
    )
    resp.set_cookie(
        "fas_token", token,
        max_age=SESSION_HOURS * 3600,
        httponly=True,
        samesite="Lax",
    )
    return resp


@app.route("/logout")
def logout():
    resp = make_response(redirect("/"))
    resp.delete_cookie("fas_token")
    return resp


if __name__ == "__main__":
    print("=" * 60)
    print("  FAS – Fictieve Federale Authenticatiedienst")
    print("  http://localhost:5001")
    print("=" * 60)
    app.run(port=5001, debug=False)
