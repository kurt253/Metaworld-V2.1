# metaworldV2 — Fictief Belgisch Bevolkingsregister

Volledig fictieve maar sociologisch realistische dataset van een Belgische bevolking:
rijksregister, bisregister, genealogische familiestructuren en loopbanen.
Bedoeld voor demos, oefendata en het testen van authenticatiediensten.

> **Alle gegenereerde data is 100% fictief.**
> Geen enkele naam, geboortedatum of identificatienummer correspondeert met een echte persoon.

---

## Inhoudsopgave

1. [Vereisten & installatie](#1-vereisten--installatie)
2. [Snelle start](#2-snelle-start)
3. [Projectstructuur](#3-projectstructuur)
4. [Configuratie](#4-configuratie)
5. [Data genereren](#5-data-genereren)
6. [Architectuur — enkelvoudige bron van waarheid](#6-architectuur--enkelvoudige-bron-van-waarheid)
7. [Streamlit dashboard](#7-streamlit-dashboard)
8. [Flask-diensten](#8-flask-diensten)
9. [REST API — loopbaandienst](#9-rest-api--loopbaandienst)
10. [Testen met Postman](#10-testen-met-postman)
11. [Nummersystematiek](#11-nummersystematiek)
12. [Scripts — API-overzicht](#12-scripts--api-overzicht)
13. [Dataflow](#13-dataflow)

---

## 1. Vereisten & installatie

**Vereisten:** Python 3.9 of hoger

```bash
# 1. Map uitpakken of repository klonen
cd metaworldV2

# 2. Virtuele omgeving aanmaken (aanbevolen)
python -m venv .venv

# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

# 3. Afhankelijkheden installeren
pip install -r requirements.txt
```

---

## 2. Snelle start

```bash
# Stap 1 — volledige maatschappij genereren (registers + families + loopbanen)
python Scripts/genereer_maatschappij.py

# Stap 2 — dashboard bekijken
streamlit run Streamlits/demografie.py

# Stap 3 — alle REST-diensten starten (optioneel)
python Scripts/start_services.py
```

Na stap 1 staan alle JSON-bestanden klaar in `Generated Data/`.
Na stap 3 zijn drie diensten bereikbaar:

| Dienst | URL |
|---|---|
| FAS / aanmelden | http://localhost:5001 |
| Persoonsgegevens | http://localhost:5002 |
| Loopbaandata (REST) | http://localhost:5003 |

---

## 3. Projectstructuur

```
metaworldV2/
├── config.json                     # Centrale configuratie
├── CLAUDE.md                       # Ontwikkelaarsdocumentatie
├── README.md                       # Dit bestand
├── requirements.txt                # Python-afhankelijkheden
│
├── Scripts/
│   ├── generate_register.py        # Rijksregister + bisregister genereren
│   ├── generate_families.py        # Familiestructuren (4 generaties)
│   ├── generate_careers.py         # Loopbanen (Dimona / RSVZ / RVW)
│   ├── generate_adressen.py        # Gedeelde adresgenerator
│   ├── genereer_maatschappij.py    # Alles in één run genereren
│   ├── auth_service.py             # Flask FAS/CSAM-simulatie  (poort 5001)
│   ├── data_service.py             # Flask persoonsgegevens    (poort 5002)
│   ├── career_service.py           # Flask loopbaan REST API   (poort 5003)
│   └── start_services.py           # Start alle drie diensten
│
├── Notebooks/
│   ├── voorbereiding_data.ipynb    # Data genereren, opslaan en rapporteren
│   └── export_naar_xls.ipynb       # Registers exporteren naar Excel
│
├── Streamlits/
│   └── demografie.py               # Streamlit dashboard (read-only)
│
└── Generated Data/
    ├── {prefix}_rijksregister.json  # Alle persoonsdata RR
    ├── {prefix}_bisregister.json    # Alle persoonsdata BIS
    ├── {prefix}_families.json       # Relaties (partner, ouders, kinderen)
    ├── {prefix}_dimona.json         # Dimona-aangiften (RSZ)
    ├── {prefix}_rsvz.json           # RSVZ-aansluitingen (zelfstandigen)
    └── {prefix}_rvw.json            # RVA-werkloosheidsperioden
```

---

## 4. Configuratie

Alle parameters staan in `config.json`. Aanpassen kan rechtstreeks of via
het Streamlit-dashboard (tab **Config aanpassen**).

### Sleutelvelden

| Pad | Betekenis |
|---|---|
| `meta.seed` | Reproduceerbare seed — zelfde seed geeft altijd identieke data |
| `meta.creation_date` | Referentiedatum voor leeftijden en overlijdens |
| `generation.counts.rijksregister` | Aantal te genereren RR-personen |
| `generation.counts.bisregister` | Aantal te genereren BIS-personen |
| `generation.counts.stamfamilies` | Stamkoppels generatie 0 |
| `generation.counts.stamsingles` | Stamsingles generatie 0 |
| `generation.deceased_fraction` | Kans op overlijden per persoon |
| `demographics.nationality_groups` | Gewichten per nationaliteitsgroep (som = 1) |
| `demographics.age_distribution.bands` | Leeftijdsbanden met gewichten |

### Standaardwaarden

| Parameter | Waarde |
|---|---|
| Rijksregister | 100.000 personen |
| Bisregister | 10.000 personen |
| Stamfamilies | 300 koppels |
| Stamsingles | 60 personen |
| Seed | 42 |
| Referentiedatum | 2026-05-01 |

---

## 5. Data genereren

### Optie A — alles in één run (aanbevolen)

```bash
python Scripts/genereer_maatschappij.py [PREFIX]
```

Genereert in volgorde:

| Stap | Wat |
|---|---|
| 1 | Rijksregister |
| 2 | Bisregister |
| 3 | Familiestructuren (4 generaties) — schrijft burgerlijke staat, familienaam en adres terug naar de registers |
| 4 | Loopbanen (Dimona / RSVZ / RVW) |
| 5 | Alle 6 JSON-bestanden opslaan |

### Optie B — via Jupyter (meer controle)

Open `Notebooks/voorbereiding_data.ipynb` en doorloop de cellen:

1. **Setup** — stel `PREFIX` in
2. **Config tonen**
3. **Rijksregister** genereren via `generate_rijksregister()`
4. **Bisregister** genereren via `generate_bisregister()`
5. **Families** genereren via `generate_families(rr_df, bis_df)`
   — muteert registers in-place: burgerlijke staat, familienaam, adres
6. **Loopbanen** genereren via `generate_careers(rr_df, bis_df)`
   → Dimona, RSVZ, RVW
7. **Opslaan** naar `Generated Data/{PREFIX}_*.json`
   — registers opslaan ná families (bevatten de bijgewerkte velden)
8. **Rapport** — aantallen, geslacht, nationaliteiten, generaties, overledenen

### Optie C — enkel loopbanen (her)genereren

```bash
python Scripts/generate_careers.py [PREFIX]
```

Leest bestaande registers en genereert enkel `_dimona`, `_rsvz` en `_rvw` opnieuw.

---

## 6. Architectuur — enkelvoudige bron van waarheid

Alle **persoonsdata** leeft uitsluitend in de registers. Andere bestanden
bevatten enkel verwijzingen via het rijksregisternummer.

| Bestand | Bevat |
|---|---|
| `_rijksregister.json` | Alle persoonsvelden (naam, adres, burgerlijke staat, …) |
| `_bisregister.json` | Idem + `bisnummer`, `geslacht_gekend` |
| `_families.json` | Enkel: `rijksregisternummer`, `generatie`, `partner_rr`, `vader_rr`, `moeder_rr`, `kinderen_rr` |
| `_dimona.json` | Dimona-aangiften gekoppeld via `rijksregisternummer` |
| `_rsvz.json` | RSVZ-aansluitingen gekoppeld via `rijksregisternummer` |
| `_rvw.json` | RVA-perioden gekoppeld via `rijksregisternummer` |

Het Streamlit-dashboard en de REST API verrijken de relatiebestanden on-the-fly
via een join met de registers.

---

## 7. Streamlit dashboard

```bash
streamlit run Streamlits/demografie.py
```

Leest **alleen** uit `Generated Data/`. Kies het dataset via de prefix-dropdown
in de sidebar.

| Tab | Inhoud |
|---|---|
| Dashboard | Bevolkingspiramide, nationaliteiten, overlijdens, bisregister-statistieken |
| Families | KPI's, generatieverdeling, overzichtstabellen |
| Persoonskaart | Zoeken op RRN of BIS-nummer, stamboom, loopbaanoverzicht |
| Diensten | Start/status van de Flask-diensten |
| Config aanpassen | Bewerk `config.json` inclusief generatieparameters |

### Zoekfilters op de Persoonskaart

Via **Op kenmerken** kan worden gefilterd op:

- Naam, gemeente, nationaliteit, geslacht, burgerlijke staat
- **Beroep** — vrije tekstzoekopdracht in loopbaandata
- **Statuut** — bediende / arbeider / ambtenaar / zelfstandige
- **Zelfstandige** — huidig / ooit / nooit

---

## 8. Flask-diensten

Simuleren een vereenvoudigde FAS/CSAM-authenticatiestroom.

| Service | Script | Poort | Functie |
|---|---|---|---|
| Auth-dienst (FAS/CSAM) | `auth_service.py` | 5001 | Login met RRN + geboortedatum, geeft JWT-cookie terug |
| Datadienst | `data_service.py` | 5002 | HTML-persoonsfiche na authenticatie met JWT-cookie |
| Loopbaandienst | `career_service.py` | 5003 | JSON loopbaandata via Bearer-token |

```bash
# Alle drie tegelijk starten
python Scripts/start_services.py

# Of afzonderlijk
python Scripts/auth_service.py
python Scripts/data_service.py
python Scripts/career_service.py
```

### Authenticatieflow

1. **Aanmelden** — POST naar `http://localhost:5001/authenticate` met RRN + geboortedatum
2. **JWT-cookie** — auth-dienst valideert de combinatie en zet cookie `fas_token` in de browser
   De JWT bevat: `ssin`, `auth_type`, `acr` (authenticatieniveau 1–4), `sub`, `iss`, `exp`
   De JWT bevat **geen** persoonsdata — enkel de identiteit van de sessie
3. **Persoonsgegevens** — browser navigeert naar `http://localhost:5002`
   Data-dienst decodeert de JWT, haalt `ssin` eruit en zoekt de persoon op in de JSON-bestanden
4. **Loopbaan** — REST-aanroep naar `http://localhost:5003/loopbaan` met de JWT als Bearer-token
   Career-dienst decodeert de JWT, haalt `ssin` eruit en zoekt loopbaanrecords op in de JSON-bestanden

> De persoonsdata leeft uitsluitend in de JSON-bestanden op de server.
> De JWT dient enkel als bewijs van authenticatie en draagt het rijksregisternummer
> mee als sleutel voor de registeropzoeking.

---

## 9. REST API — loopbaandienst

**Base URL:** `http://localhost:5003`

**Authenticatie:** elke beveiligde aanroep vereist een geldig JWT als Bearer-token:

```
Authorization: Bearer <jwt>
```

### Endpoints

| Methode | Pad | Auth | Beschrijving |
|---|---|---|---|
| GET | `/loopbaan` | Ja | Volledige loopbaan: dimona + rsvz + rvw |
| GET | `/loopbaan/dimona` | Ja | Alleen RSZ Dimona-aangiften |
| GET | `/loopbaan/rsvz` | Ja | Alleen RSVZ-aansluitingen (zelfstandigen) |
| GET | `/loopbaan/rvw` | Ja | Alleen RVA-werkloosheidsperioden |
| GET | `/status` | Nee | Dienststatus en beschikbare bestanden |

### Voorbeeldrespons `GET /loopbaan`

```json
{
  "ssin": "75.06.08-997.02",
  "auth_type": "rijksregister",
  "dimona": [
    {
      "rijksregisternummer": "75.06.08-997.02",
      "type": "D",
      "kbo_werkgever": "0123.456.789",
      "naam_werkgever": "Groep Janssen NV",
      "sector_nace": "6209",
      "beroep": "ICT-beheerder",
      "categorie": "bediende",
      "datum_in": "1998-09-01",
      "datum_uit": "2005-03-31",
      "reden_uit": "O"
    }
  ],
  "rsvz": [],
  "rvw": []
}
```

### Foutmeldingen

| HTTP | `error.code` | Oorzaak |
|---|---|---|
| 401 | `NO_TOKEN` | `Authorization`-header ontbreekt |
| 401 | `TOKEN_EXPIRED` | JWT ouder dan 8 uur — haal nieuw token op |
| 401 | `TOKEN_INVALID` | JWT ongeldig of verkeerd gekopieerd |
| 404 | `GEEN_LOOPBAANDATA` | Loopbaan-JSON-bestanden nog niet gegenereerd |

### Dimona-codes

| Veld | Waarden |
|---|---|
| `type` | `D` (dienstbode/arbeider), `A` (ambtenaar), `S` (student) |
| `reden_uit` | `O` (ontslag/overgang), `P` (pensioen), `OD` (overlijden), `E` (einde contract), `null` (nog actief) |

### RSVZ-codes

| Veld | Waarden |
|---|---|
| `categorie` | `H` (hoofdberoep), `B` (bijberoep) |
| `reden_stop` | `P` (pensioen), `OD` (overlijden), `S` (stopzetting), `null` (nog actief) |

---

## 10. Testen met Postman

### Vereisten

- Alle diensten draaien: `python Scripts/start_services.py`
- Data is gegenereerd: `python Scripts/genereer_maatschappij.py`
- Een geldig rijksregisternummer — te vinden via het Streamlit-dashboard
- Postman-environment aangemaakt (bv. **Metaworld**) en ingesteld als actief

---

### Stap 1 — Token ophalen

| Veld | Waarde |
|---|---|
| Methode | `POST` |
| URL | `http://localhost:5001/authenticate` |
| Body-type | `form-data` |

Velden onder **Body → form-data**:

| Key | Value | Toelichting |
|---|---|---|
| `nummer` | `75.06.08-997.02` | Vervang door een geldig RRN uit jouw dataset |
| `level` | `3` | Authenticatieniveau 1–4 (optioneel, standaard 3) |

Klik **Send**. Het JWT-token staat:
- Als cookie `fas_token` in **Cookies** (response-tabblad)
- Zichtbaar in de HTML-broncode van het antwoord

**Token automatisch opslaan** — voeg dit toe onder het tabblad **Tests** van de request:

```javascript
const cookie = pm.cookies.get("fas_token");
if (cookie) {
    pm.environment.set("jwt_token", cookie);
    console.log("Token opgeslagen:", cookie.substring(0, 40) + "...");
}
```

> Zorg dat Postman cookies mag opslaan voor `localhost`:
> **Settings → Cookies** → voeg `localhost` toe aan de whitelist.

---

### Stap 2 — Volledige loopbaan opvragen

| Veld | Waarde |
|---|---|
| Methode | `GET` |
| URL | `http://localhost:5003/loopbaan` |

Onder **Headers**:

| Key | Value |
|---|---|
| `Authorization` | `Bearer {{jwt_token}}` |

Klik **Send**. De response bevat de volledige loopbaan als JSON
(zie voorbeeldrespons in sectie 9).

---

### Stap 3 — Deelresultaten opvragen

Vervang de URL om een specifiek deel op te vragen — gebruik telkens
dezelfde `Authorization: Bearer {{jwt_token}}`-header:

| URL | Wat je terugkrijgt |
|---|---|
| `http://localhost:5003/loopbaan/dimona` | RSZ Dimona-aangiften |
| `http://localhost:5003/loopbaan/rsvz` | RSVZ-aansluitingen (zelfstandigen) |
| `http://localhost:5003/loopbaan/rvw` | RVA-werkloosheidsperioden |
| `http://localhost:5003/status` | Dienststatus *(geen token nodig)* |

---

### Stap 4 — Collection bouwen (optioneel)

Om snel te wisselen tussen personen:

1. Maak een Postman **Collection** aan met de vier loopbaan-requests
2. Voeg in de **Pre-request Script** van de collection een token-refresh toe
   als `{{jwt_token}}` leeg of verlopen is
3. Gebruik **Collection Runner** om meerdere RRN's in batch te testen

---

## 11. Nummersystematiek

### Rijksregisternummer — `JJMMDD-VVV.CC`

| Deel | Betekenis |
|---|---|
| `JJMMDD` | Geboortedatum (2-cijferig jaar) |
| `VVV` | Volgnummer — oneven = man, even = vrouw (telt af: 997, 995, …) |
| `CC` | Controlegetal: `97 − (getal mod 97)` |

Bij geboorte **vanaf 2000**: het 11-cijferige getal wordt voorafgegaan door `2`
voor de modulo-berekening.

### BIS-nummer

Identieke structuur als rijksregisternummer, maar de maand wordt verhoogd:

| Situatie | Maand + |
|---|---|
| Geslacht onbekend | +20 |
| Geslacht bekend | +40 |

---

## 12. Scripts — API-overzicht

### `generate_register.py`

```python
generate_rijksregister(n=None, config_path=None) -> pd.DataFrame
# Kolommen: rijksregisternummer, voornaam, familienaam, geslacht, geboortedatum,
#           geboorteplaats, geboorteland, nationaliteit, burgerlijke_staat,
#           overlijdensdatum, adres_straat, adres_nr, adres_bus,
#           adres_postcode, adres_gemeente, adres_provincie, adres_gewest

generate_bisregister(n=None, config_path=None) -> pd.DataFrame
# Zelfde kolommen + bisnummer (i.p.v. rijksregisternummer) en geslacht_gekend
```

### `generate_families.py`

```python
generate_families(n_stamfamilies=None, n_stamsingles=None, seed=None,
                  config_path=None, rr_df=None, bis_df=None) -> list[dict]
# Genereert 4 generaties (gen 0–3), koppelt partners / ouders / kinderen
#
# Schrijft IN-PLACE terug naar rr_df / bis_df:
#   burgerlijke_staat, familienaam, adres_*
#
# Retourneert per persoon alleen de relatievelden:
#   rijksregisternummer, generatie, partner_rr, vader_rr, moeder_rr, kinderen_rr
```

### `generate_careers.py`

```python
generate_careers(rr_df=None, bis_df=None, seed=None, config_path=None)
    -> (dimona_records, rsvz_records, rvw_records)
# 200 beroepen: bediende (50) / arbeider (50) / ambtenaar (50) / zelfstandige (50)
# Stadia: studentenjob (16+), professionele loopbaan (18+), pensioen (Belgische statistieken)
#
# dimona_records : RSZ Dimona-aangiften     — type D/A/S
# rsvz_records   : RSVZ-aansluitingen      — categorie H (hoofdberoep) / B (bijberoep)
# rvw_records    : RVA-werkloosheidsperioden — type VW/TW
```

### `generate_adressen.py`

```python
genereer_adres(rng, config, gemeente=None) -> dict
# Retourneert: adres_straat, adres_nr, adres_bus,
#              adres_postcode, adres_gemeente, adres_provincie, adres_gewest
```

---

## 13. Dataflow

```
config.json
    │
    ├─► generate_register.py  ──►  rijksregister DataFrame  ──────────────────┐
    ├─► generate_register.py  ──►  bisregister DataFrame    ──────────────────┤
    │                                                                          │
    ├─► generate_families.py  ──►  muteert rr/bis in-place                   │
    │                          ──►  families list[dict]  ─────────────────────┤
    │                                                                          │
    └─► generate_careers.py   ──►  dimona / rsvz / rvw  ─────────────────────┤
                                                                               ▼
                                                              Generated Data/ (JSON)
                                                                    │
                              ┌─────────────────────────────────────┤
                              │                                     │
                              ▼                                     ▼
                     demografie.py                       Flask-diensten
                     (Streamlit)                    ┌────────────────────────┐
                     read-only                      │ :5001  auth_service    │
                     joins on-the-fly               │ :5002  data_service    │
                                                    │ :5003  career_service  │
                                                    └────────────────────────┘
```

---

## Licentie

Uitsluitend bedoeld voor interne demos, oefendata en testen. Niet voor productiegebruik.
