# metaworldV2 — Fictief Belgisch Register

## Doel
Volledig fictieve maar sociologisch realistische dataset van een Belgische bevolking:
rijksregister, bisregister en genealogische familiestructuren. Gebruikt voor demos,
oefendata en tests van authentificatiediensten.

---

## Directorystructuur

```
metaworldV2/
├── config.json                  # Centrale configuratie (aantallen, seed, namen, ...)
├── CLAUDE.md                    # Dit bestand
│
├── Notebooks/
│   ├── voorbereiding_data.ipynb # Notebook: data genereren, opslaan en rapporteren
│   └── export_naar_xls.ipynb   # Notebook: registers exporteren naar Excel
│
├── Scripts/
│   ├── generate_register.py     # Rijksregister + Bisregister genereren
│   ├── generate_families.py     # Familiestructuren genereren (4 generaties)
│   ├── generate_adressen.py     # Gedeelde adresgenerator (gebruikt door register + families)
│   ├── auth_service.py          # Flask: simuleert FAS/CSAM (poort 5001)
│   ├── data_service.py          # Flask: persoonsfiches na login (poort 5002)
│   └── start_services.py        # Start beide Flask-diensten
│
├── Streamlits/
│   └── demografie.py            # Streamlit dashboard (alleen lezen vanuit JSON)
│
└── Generated Data/
    ├── {prefix}_rijksregister.json
    ├── {prefix}_bisregister.json
    ├── {prefix}_families.json
    ├── {prefix}_dimona.json      # Dimona-aangiften (RSZ)
    ├── {prefix}_rsvz.json        # RSVZ-aansluitingen (zelfstandigen)
    └── {prefix}_rvw.json         # RVA-werkloosheidsperioden
```

---

## config.json — sleutelvelden

| Pad | Betekenis |
|---|---|
| `meta.seed` | Reproduceerbare seed voor alle generators |
| `meta.creation_date` | Referentiedatum voor leeftijden en overlijdens |
| `generation.counts.rijksregister` | **Aantal te genereren RR-personen** |
| `generation.counts.bisregister` | **Aantal te genereren BIS-personen** |
| `generation.counts.stamfamilies` | Stamkoppels generatie 0 |
| `generation.counts.stamsingles` | Stamsingles generatie 0 |
| `generation.deceased_fraction` | Kans op overlijden per persoon |
| `population.rijksregister.total` | Theoretisch Belgisch totaal (ref., niet gegenereerd) |
| `population.bisregister.total` | Idem voor bisregister |
| `demographics.nationality_groups` | Gewichten per nationaliteitsgroep (tellen op tot 1) |
| `demographics.age_distribution.bands` | Leeftijdsbanden met gewichten |

---

## Dataflow

```
config.json
    │
    ├─► generate_register.py  →  rijksregister DataFrame  ──────────────────────────┐
    ├─► generate_register.py  →  bisregister DataFrame    ──────────────────────────┤
    │                                                                                │
    └─► generate_families.py  →  muteert rr/bis in-place  ──────────────────────────┤
                               (burgerlijke_staat, familienaam, adres)              │
                               →  families list[dict] (slim: alleen relaties)  ─────┤
                                                                                     │
                                                             JSON-bestanden ◄────────┘
                                                             (Generated Data/)
                                                                │
                                                                └─► demografie.py (Streamlit)
                                                                    (joins families + registers)
                                                                └─► auth_service.py / data_service.py
```

**Enkelvoudige bron van waarheid:**
- Alle persoonsdata leeft uitsluitend in de registers (`_rijksregister.json`, `_bisregister.json`)
- `_families.json` bevat enkel relatie-velden: `rijksregisternummer, generatie, partner_rr, vader_rr, moeder_rr, kinderen_rr`
- De Streamlit verrijkt families on-the-fly via een join met de registers

---

## Scripts — publieke API

### `generate_register.py`

```python
generate_rijksregister(n=None, config_path=None) -> pd.DataFrame
# n=None → gebruikt config.generation.counts.rijksregister
# Kolommen: rijksregisternummer, voornaam, familienaam, geslacht, geboortedatum,
#           geboorteplaats, geboorteland, nationaliteit, burgerlijke_staat,
#           overlijdensdatum, adres_*

generate_bisregister(n=None, config_path=None) -> pd.DataFrame
# n=None → gebruikt config.generation.counts.bisregister
# Extra kolom: bisnummer (i.p.v. rijksregisternummer), geslacht_gekend
# BIS-nummers: maand +20 (geslacht onbekend) of +40 (geslacht bekend)
```

### `generate_families.py`

```python
generate_families(n_stamfamilies=None, n_stamsingles=None, seed=None, config_path=None,
                  rr_df=None, bis_df=None) -> list[dict]
# None → leest uit config.generation.counts.*  en  config.meta.seed
# Genereert 4 generaties (gen 0–3), koppelt ouders/kinderen/partners
#
# SCHRIJFT IN-PLACE terug naar rr_df / bis_df:
#   burgerlijke_staat  – op basis van relatiestatus
#   familienaam        – kinderen erven vadersnaam
#   adres_*            – koppels en minderjarigen delen huishoudadres
#
# Geretourneerde dict per persoon (gesorteerd gen 0→3, dalende afstamming):
#   rijksregisternummer, generatie, partner_rr, vader_rr, moeder_rr, kinderen_rr
```

### `generate_careers.py`

```python
generate_careers(rr_df=None, bis_df=None, seed=None, config_path=None)
    -> (dimona_records, rsvz_records, rvw_records)

# Genereert loopbanen voor alle personen in rr_df en bis_df.
# 200 beroepen verdeeld over: bediende (50), arbeider (50), ambtenaar (50), zelfstandige (50)
# Stadia: studentenjob (16+), professionele loopbaan (18+), pensioen (Belgische statistieken)
#
# dimona_records: Dimona-aangiften (RSZ) – type D/A/S, werkgever KBO, beroep, datum_in/uit
# rsvz_records  : RSVZ-aansluitingen – beroep, KBO onderneming, categorie H/B, datum_start/stop
# rvw_records   : RVA-perioden – type VW/TW, datum_begin/einde
# Elke persoon kan in meerdere bestanden voorkomen (gemengde loopbaan).
```

### `generate_adressen.py`

```python
genereer_adres(rng, config, gemeente=None) -> dict
# Geeft dict met adres_straat, adres_nr, adres_bus, adres_postcode,
#                adres_gemeente, adres_provincie, adres_gewest
```

---

## Notebook `Notebooks/voorbereiding_data.ipynb`

Gebruik dit notebook om data aan te maken en te inspecteren:

1. **Setup**: stel `PREFIX` in (naam van de output-bestanden)
2. **Config tonen**: controleert wat er gegenereerd zal worden
3. **Genereer rijksregister** via `generate_rijksregister()`
4. **Genereer bisregister** via `generate_bisregister()`
5. **Genereer families** via `generate_families(rr_df=rr, bis_df=bis)`
   (optioneel) **Genereer loopbanen** via `generate_careers(rr_df=rr, bis_df=bis)`
   → produceert `dimona`, `rsvz`, `rvw` lijsten; sla op als `{PREFIX}_dimona/rsvz/rvw.json`
   — muteert rr en bis in-place (burgerlijke_staat, familienaam, adres)
6. **Opslaan** naar `Generated Data/{PREFIX}_*.json`
   — sla rr en bis op ná families-generatie (bevatten nu de bijgewerkte waarden)
7. **Rapport**: roept `rapporteer_bestanden(SAVE_DIR, PREFIX)` aan — toont aantallen,
   geslachtsverdeling, nationaliteiten, generaties, overledenen, etc.

De rapportfunctie kan ook standalone worden uitgevoerd (onderste cel) zonder data opnieuw te genereren.

---

## Streamlit `demografie.py`

**Starten:** `streamlit run Streamlits/demografie.py`

- Leest **alleen** uit JSON-bestanden in `Generated Data/`
- Kiest bestand via prefix-dropdown in de sidebar
- Als geen bestanden bestaan → foutmelding + `st.stop()`
- Dashboard toont `len(rr)` en `len(bis)` — de werkelijke aantallen in de bestanden

**Tabs:**
| Tab | Inhoud |
|---|---|
| Dashboard | Piramide, nationaliteiten, overlijdens, bisregister-stats |
| Families | KPI's, generatieverdeling, overzichtstabellen |
| Persoonskaart | Zoeken op RRN/BIS-nr, stamboom |
| Diensten | Start/status Flask auth- en datadienst |
| Config aanpassen | Bewerk `config.json` incl. generatieparameters |

---

## Flask-diensten

| Service | Script | Poort | Functie |
|---|---|---|---|
| FAS/CSAM simulatie | `auth_service.py` | 5001 | Login met RRN + geboortedatum |
| Datadienst | `data_service.py` | 5002 | Persoonsfiche na authenticatie |

Beide diensten lezen de JSON-bestanden uit `Generated Data/`.

---

## Nummersystematiek

**Rijksregisternummer:** `JJMMDD-VVV.CC`
- VVV = volgummer (oneven = man, even = vrouw), van hoog naar laag (997, 995, ...)
- CC = controlegetal: 97 − (getal mod 97), bij geboorte ≥ 2000: prefix '2'

**BIS-nummer:** zelfde structuur maar maand + 20 (geslacht onbekend) of + 40 (geslacht bekend)

---

## Snelle referentie — typische workflow

```bash
# 1. Config aanpassen (optioneel)
#    → Streamlit > tab "Config aanpassen" of rechtstreeks config.json

# 2. Data genereren
#    → Jupyter: open Notebooks/voorbereiding_data.ipynb, run all

# 3. Dashboard bekijken
streamlit run Streamlits/demografie.py
```
