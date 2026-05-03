# metaworldV2 — Fictief Belgisch Bevolkingsregister

Volledig fictieve maar sociologisch realistische dataset van een Belgische bevolking: rijksregister, bisregister en genealogische familiestructuren. Gebruikt voor demos, oefendata en tests van authenticatiediensten.

> **Alle gegenereerde data is 100% fictief.** Geen enkele naam, geboortedatum of identificatienummer correspondeert met een echte persoon.

---

## Inhoud

- [Vereisten](#vereisten)
- [Installatie](#installatie)
- [Snelle start](#snelle-start)
- [Projectstructuur](#projectstructuur)
- [Configuratie](#configuratie)
- [Data genereren](#data-genereren)
- [Streamlit dashboard](#streamlit-dashboard)
- [Flask-diensten](#flask-diensten)
- [Nummersystematiek](#nummersystematiek)
- [Scripts — API-overzicht](#scripts--api-overzicht)

---

## Vereisten

- Python 3.9 of hoger
- pip

---

## Installatie

```bash
# 1. Repository klonen of map uitpakken
cd metaworldV2

# 2. Virtuele omgeving aanmaken (aanbevolen)
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# 3. Afhankelijkheden installeren
pip install -r requirements.txt
```

---

## Snelle start

```bash
# Stap 1 — data genereren via Jupyter
jupyter notebook Notebooks/voorbereiding_data.ipynb
# Stel PREFIX in, run all cells → JSON-bestanden worden aangemaakt in Generated Data/

# Stap 2 — dashboard bekijken
streamlit run Streamlits/demografie.py

# Stap 3 — Flask-diensten starten (optioneel)
python Scripts/start_services.py
# auth_service  → http://localhost:5001
# data_service  → http://localhost:5002
```

---

## Projectstructuur

```
metaworldV2/
├── config.json                     # Centrale configuratie (aantallen, seed, namen, ...)
├── CLAUDE.md                       # Ontwikkelaarsdocumentatie
├── README.md                       # Dit bestand
├── requirements.txt                # Python-afhankelijkheden
│
├── Notebooks/
│   ├── voorbereiding_data.ipynb    # Data genereren, opslaan en rapporteren
│   └── export_naar_xls.ipynb       # Registers exporteren naar Excel
│
├── Scripts/
│   ├── generate_register.py        # Rijksregister + bisregister genereren
│   ├── generate_families.py        # Familiestructuren genereren (4 generaties)
│   ├── generate_adressen.py        # Gedeelde adresgenerator
│   ├── genereer_maatschappij.py    # Volledige maatschappij in één run genereren
│   ├── auth_service.py             # Flask: simuleert FAS/CSAM (poort 5001)
│   ├── data_service.py             # Flask: persoonsfiches na login (poort 5002)
│   └── start_services.py           # Start beide Flask-diensten tegelijk
│
├── Streamlits/
│   └── demografie.py               # Streamlit dashboard (alleen lezen vanuit JSON)
│
└── Generated Data/
    ├── {prefix}_rijksregister.json
    ├── {prefix}_bisregister.json
    └── {prefix}_families.json
```

---

## Configuratie

Alle generatieparameters staan in `config.json`. De belangrijkste velden:

| Pad | Betekenis |
|-----|-----------|
| `meta.seed` | Reproduceerbare seed voor alle generators |
| `meta.creation_date` | Referentiedatum voor leeftijden en overlijdens |
| `generation.counts.rijksregister` | Aantal te genereren RR-personen |
| `generation.counts.bisregister` | Aantal te genereren BIS-personen |
| `generation.counts.stamfamilies` | Stamkoppels generatie 0 |
| `generation.counts.stamsingles` | Stamsingles generatie 0 |
| `generation.deceased_fraction` | Kans op overlijden per persoon |
| `demographics.nationality_groups` | Gewichten per nationaliteitsgroep (som = 1) |
| `demographics.age_distribution.bands` | Leeftijdsbanden met gewichten |

De config kan rechtstreeks worden bewerkt of via het Streamlit-dashboard (tab **Config aanpassen**).

### Standaardwaarden

| Parameter | Waarde |
|-----------|--------|
| Rijksregister | 100.000 personen |
| Bisregister | 10.000 personen |
| Stamfamilies | 300 koppels |
| Stamsingles | 60 personen |
| Seed | 42 |
| Referentiedatum | 2026-05-01 |

---

## Data genereren

### Via Jupyter (aanbevolen)

Open `Notebooks/voorbereiding_data.ipynb` en doorloop de cellen:

1. **Setup** — stel `PREFIX` in (naam voor de output-bestanden)
2. **Config tonen** — controleert generatieparameters
3. **Rijksregister genereren** — via `generate_rijksregister()`
4. **Bisregister genereren** — via `generate_bisregister()`
5. **Families genereren** — via `generate_families()`
6. **Opslaan** — naar `Generated Data/{PREFIX}_*.json`
7. **Rapport** — toont aantallen, geslachtsverdeling, nationaliteiten, generaties, overledenen

### Via script

```python
import sys
sys.path.insert(0, "Scripts")

from generate_register import generate_rijksregister, generate_bisregister
from generate_families import generate_families

rr  = generate_rijksregister()   # leest aantallen uit config.json
bis = generate_bisregister()
fam = generate_families()
```

### Volledige maatschappij in één keer

```bash
python Scripts/genereer_maatschappij.py
```

---

## Streamlit dashboard

```bash
streamlit run Streamlits/demografie.py
```

Het dashboard leest **alleen** uit JSON-bestanden in `Generated Data/`. Kies het dataset via de prefix-dropdown in de sidebar.

| Tab | Inhoud |
|-----|--------|
| Dashboard | Bevolkingspiramide, nationaliteiten, overlijdens, bisregister-statistieken |
| Families | KPI's, generatieverdeling, overzichtstabellen |
| Persoonskaart | Zoeken op RRN of BIS-nummer, stamboomweergave |
| Diensten | Start/status van de Flask auth- en datadienst |
| Config aanpassen | Bewerk `config.json` inclusief generatieparameters |

---

## Flask-diensten

Simuleren een vereenvoudigde FAS/CSAM-stroom (Belgische overheidsauthenticatie).

| Service | Script | Poort | Functie |
|---------|--------|-------|---------|
| Auth-dienst (FAS/CSAM) | `auth_service.py` | 5001 | Login met RRN + geboortedatum, geeft JWT terug |
| Data-dienst | `data_service.py` | 5002 | Persoonsfiche opvragen na authenticatie met JWT |

### Starten

```bash
# Beide diensten tegelijk
python Scripts/start_services.py

# Of afzonderlijk
python Scripts/auth_service.py
python Scripts/data_service.py
```

### Loginflow

1. POST naar `http://localhost:5001/login` met `rijksregisternummer` en `geboortedatum`
2. Bij succes: JWT-token in antwoord
3. GET naar `http://localhost:5002/persoon` met `Authorization: Bearer <token>`
4. Antwoord: volledige persoonsfiche als JSON

---

## Nummersystematiek

### Rijksregisternummer — `JJMMDD-VVV.CC`

| Deel | Betekenis |
|------|-----------|
| `JJMMDD` | Geboortedatum (2-cijferig jaar) |
| `VVV` | Volgnummer: oneven = man, even = vrouw (telt van hoog naar laag: 997, 995, …) |
| `CC` | Controlegetal: `97 − (getal mod 97)` |

Bij geboorte vanaf 2000: het 11-cijferige getal wordt voorafgegaan door `2` voor de modulo-berekening.

### BIS-nummer

Zelfde structuur als rijksregisternummer, maar de maand wordt verhoogd:

| Situatie | Verhoging |
|----------|-----------|
| Geslacht onbekend | Maand + 20 |
| Geslacht bekend | Maand + 40 |

---

## Scripts — API-overzicht

### `generate_register.py`

```python
generate_rijksregister(n=None, config_path=None) -> pd.DataFrame
# n=None → gebruikt config.generation.counts.rijksregister
# Kolommen: rijksregisternummer, voornaam, familienaam, geslacht, geboortedatum,
#           geboorteplaats, geboorteland, nationaliteit, burgerlijke_staat,
#           overlijdensdatum, adres_straat, adres_nr, adres_bus,
#           adres_postcode, adres_gemeente, adres_provincie, adres_gewest

generate_bisregister(n=None, config_path=None) -> pd.DataFrame
# Extra kolom: bisnummer (i.p.v. rijksregisternummer), geslacht_gekend
```

### `generate_families.py`

```python
generate_families(n_stamfamilies=None, n_stamsingles=None, seed=None, config_path=None) -> list[dict]
# None → leest uit config.generation.counts.* en config.meta.seed
# Genereert 4 generaties (gen 0–3)
# Kolommen: rijksregisternummer, voornaam, familienaam, geslacht, geboortedatum,
#           nationaliteit, burgerlijke_staat, generatie, partner_rr, vader_rr,
#           moeder_rr, kinderen_rr (list), overlijdensdatum, adres_*
```

### `generate_adressen.py`

```python
genereer_adres(rng, config, gemeente=None) -> dict
# Retourneert: adres_straat, adres_nr, adres_bus,
#              adres_postcode, adres_gemeente, adres_provincie, adres_gewest
```

---

## Dataflow

```
config.json
    │
    ├─► generate_register.py  →  rijksregister DataFrame  ─┐
    ├─► generate_register.py  →  bisregister DataFrame    ─┼─► JSON-bestanden (Generated Data/)
    └─► generate_families.py  →  families list[dict]      ─┘
                                                             │
                                                             ├─► demografie.py  (Streamlit, read-only)
                                                             ├─► auth_service.py (Flask, poort 5001)
                                                             └─► data_service.py (Flask, poort 5002)
```

---

## Licentie

Uitsluitend bedoeld voor interne demos, oefendata en testen. Niet voor productiegebruik.
