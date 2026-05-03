"""
generate_register.py
Genereert een fictief Belgisch rijksregister en bisregister op basis van config.json.
Alle output is reproduceerbaar via de seed in de config.
Elke persoon krijgt een naam, burgerlijke staat en woonadres.
"""
from __future__ import annotations

import json
import sys
import random
import pandas as pd
from pathlib import Path
from datetime import date, timedelta
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate_adressen import genereer_adres  # noqa: E402

# ─────────────────────────────────────────────────────────────────────────────
# Nationaliteit → namengroep
# ─────────────────────────────────────────────────────────────────────────────

_NAAM_GROEP: dict[str, list[str]] = {
    "Belgisch":           ["Vlaams_Nederlands", "Frans_Waals", "Duits"],
    "EU_overig":          ["Frans_Waals", "Duits", "Oost_Europees"],
    "Marokkaans":         ["Marokkaans_Arabisch"],
    "Turks":              ["Turks"],
    "Congolees":          ["Congolees_Afrikaans"],
    "Oost_Europees":      ["Oost_Europees"],
    "Aziatisch":          ["Aziatisch"],
    "Latijns_Amerikaans": ["Frans_Waals"],
    "Overig":             ["Vlaams_Nederlands", "Frans_Waals"],
}

_FAMILIENAAM_GROEP: dict[str, list[str]] = {
    "Belgisch":           ["Vlaams_Nederlands", "Frans_Waals", "Duits"],
    "EU_overig":          ["Frans_Waals", "Duits", "Oost_Europees"],
    "Marokkaans":         ["Marokkaans"],
    "Turks":              ["Turks"],
    "Congolees":          ["Congolees_Afrikaans"],
    "Oost_Europees":      ["Oost_Europees"],
    "Aziatisch":          ["Aziatisch"],
    "Latijns_Amerikaans": ["Frans_Waals"],
    "Overig":             ["Vlaams_Nederlands", "Frans_Waals"],
}


# ─────────────────────────────────────────────────────────────────────────────
# Hulpfuncties
# ─────────────────────────────────────────────────────────────────────────────

def _load_config(config_path=None) -> dict:
    path = Path(config_path) if config_path else ROOT / "config.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _controlcijfer(yymmdd: str, seq: int, born_2000_or_later: bool) -> int:
    """97 - (getal mod 97). Voor >= 2000 wordt '2' vooraan toegevoegd."""
    base = ("2" if born_2000_or_later else "") + yymmdd + f"{seq:03d}"
    return 97 - (int(base) % 97)


def _format_nr(yymmdd: str, seq: int, cc: int) -> str:
    return f"{yymmdd[:2]}.{yymmdd[2:4]}.{yymmdd[4:6]}-{seq:03d}.{cc:02d}"


def _random_birthdate(rng: random.Random, bands: list[dict], ref: date) -> date:
    weights = [b["weight"] for b in bands]
    band = rng.choices(bands, weights=weights)[0]
    age = rng.randint(band["min"], min(band["max"], 110))
    year = ref.year - age
    month = rng.randint(1, 12)
    day = rng.randint(1, 28)
    return date(year, month, day)


def _pick_municipality(rng: random.Random, gemeenten: list[dict]) -> dict:
    weights = [g["inwoners"] for g in gemeenten]
    return rng.choices(gemeenten, weights=weights)[0]


def _random_death_date(rng: random.Random, birth_date: date, ref: date) -> date | None:
    """Willekeurige overlijdensdatum na 18e verjaardag en voor referentiedatum."""
    earliest = date(birth_date.year + 18, birth_date.month, birth_date.day)
    if earliest >= ref:
        return None
    delta = (ref - earliest).days
    return earliest + timedelta(days=rng.randint(0, delta))


def _pick_voornaam(
    rng: random.Random, geslacht: str, nat: str,
    namen_m: dict, namen_v: dict,
) -> str:
    groepen = _NAAM_GROEP.get(nat, ["Vlaams_Nederlands"])
    groep   = rng.choice(groepen)
    pool    = (namen_m if geslacht == "M" else namen_v).get(
        groep,
        (namen_m if geslacht == "M" else namen_v)["Vlaams_Nederlands"],
    )
    return rng.choice(pool)


def _pick_familienaam(rng: random.Random, nat: str, familienamen: dict) -> str:
    groepen = _FAMILIENAAM_GROEP.get(nat, ["Vlaams_Nederlands"])
    groep   = rng.choice(groepen)
    return rng.choice(familienamen.get(groep, familienamen["Vlaams_Nederlands"]))


def _burgerlijke_staat(rng: random.Random, birth: date, ref: date) -> str:
    """Realistisch Belgische verdeling naar leeftijd."""
    age = (ref - birth).days // 365
    if age < 16:
        return "ongehuwd"
    if age < 25:
        return rng.choices(
            ["ongehuwd", "wettelijk_samenwonend"],
            weights=[0.91, 0.09],
        )[0]
    if age < 35:
        return rng.choices(
            ["ongehuwd", "gehuwd", "wettelijk_samenwonend", "gescheiden"],
            weights=[0.40, 0.36, 0.15, 0.09],
        )[0]
    if age < 55:
        return rng.choices(
            ["ongehuwd", "gehuwd", "wettelijk_samenwonend", "gescheiden", "weduwe_weduwnaar"],
            weights=[0.18, 0.52, 0.09, 0.16, 0.05],
        )[0]
    if age < 70:
        return rng.choices(
            ["ongehuwd", "gehuwd", "wettelijk_samenwonend", "gescheiden", "weduwe_weduwnaar"],
            weights=[0.10, 0.55, 0.05, 0.14, 0.16],
        )[0]
    return rng.choices(
        ["ongehuwd", "gehuwd", "wettelijk_samenwonend", "gescheiden", "weduwe_weduwnaar"],
        weights=[0.07, 0.44, 0.03, 0.12, 0.34],
    )[0]


# ─────────────────────────────────────────────────────────────────────────────
# Rijksregister
# ─────────────────────────────────────────────────────────────────────────────

def generate_rijksregister(n: int | None = None, config_path=None) -> pd.DataFrame:
    """
    Genereert n personen voor het fictieve rijksregister.

    Sequentienummers lopen van hoog naar laag per geboortedatum:
      - mannen: 997, 995, 993, ...
      - vrouwen: 998, 996, 994, ...

    Parameters
    ----------
    n : int, optioneel
        Aantal te genereren personen. Standaard = generation.max_persons uit config.
    config_path : str of Path, optioneel
        Pad naar config.json.

    Returns
    -------
    pd.DataFrame met kolommen:
        rijksregisternummer, voornaam, familienaam, geslacht, geboortedatum,
        geboorteplaats, geboorteland, nationaliteit, burgerlijke_staat,
        overlijdensdatum, adres_straat, adres_nr, adres_bus, adres_postcode,
        adres_gemeente, adres_provincie, adres_gewest
    """
    cfg = _load_config(config_path)
    rng = random.Random(cfg["meta"]["seed"])
    ref = date.fromisoformat(cfg["meta"]["creation_date"])
    n   = n if n is not None else cfg["generation"]["counts"]["rijksregister"]

    bands         = cfg["demographics"]["age_distribution"]["bands"]
    gender_ratio  = cfg["demographics"]["gender_ratio"]["male"]
    nat_cfg       = cfg["demographics"]["nationality_groups"]
    nat_keys      = [k for k in nat_cfg if k != "comment"]
    nat_weights   = [nat_cfg[k] for k in nat_keys]
    deceased_p    = cfg["generation"]["deceased_fraction"]
    gemeenten     = cfg["locations"]["belgische_gemeenten"]
    buitenland    = cfg["locations"]["buitenlandse_geboorteplaatsen"]
    namen_m       = cfg["names"]["voornamen_mannelijk"]
    namen_v       = cfg["names"]["voornamen_vrouwelijk"]
    familienamen  = cfg["names"]["familienamen"]

    seq_m: dict[str, int] = defaultdict(lambda: 997)
    seq_f: dict[str, int] = defaultdict(lambda: 998)

    records = []

    for _ in range(n):
        gender  = "M" if rng.random() < gender_ratio else "F"
        birth   = _random_birthdate(rng, bands, ref)
        yy      = f"{birth.year % 100:02d}"
        mm      = f"{birth.month:02d}"
        dd      = f"{birth.day:02d}"
        yymmdd  = yy + mm + dd
        born_2k = birth.year >= 2000

        if gender == "M":
            seq = seq_m[yymmdd]
            seq_m[yymmdd] = max(1, seq_m[yymmdd] - 2)
        else:
            seq = seq_f[yymmdd]
            seq_f[yymmdd] = max(2, seq_f[yymmdd] - 2)

        cc = _controlcijfer(yymmdd, seq, born_2k)
        rr = _format_nr(yymmdd, seq, cc)

        nationality = rng.choices(nat_keys, weights=nat_weights)[0]

        if nationality == "Belgisch" or rng.random() < 0.80:
            gem = _pick_municipality(rng, gemeenten)
            geboorteplaats, geboorteland = gem["naam"], "België"
        else:
            bp = rng.choice(buitenland)
            geboorteplaats, geboorteland = bp["stad"], bp["land"]

        overlijden = None
        if rng.random() < deceased_p:
            overlijden = _random_death_date(rng, birth, ref)

        voornaam    = _pick_voornaam(rng, gender, nationality, namen_m, namen_v)
        familienaam = _pick_familienaam(rng, nationality, familienamen)
        status      = _burgerlijke_staat(rng, birth, ref)
        adres       = genereer_adres(rng, cfg)

        records.append({
            "rijksregisternummer": rr,
            "voornaam":            voornaam,
            "familienaam":         familienaam,
            "geslacht":            gender,
            "geboortedatum":       birth.isoformat(),
            "geboorteplaats":      geboorteplaats,
            "geboorteland":        geboorteland,
            "nationaliteit":       nationality,
            "burgerlijke_staat":   status,
            "overlijdensdatum":    overlijden.isoformat() if overlijden else None,
            **adres,
        })

    return pd.DataFrame(records)


# ─────────────────────────────────────────────────────────────────────────────
# Bisregister
# ─────────────────────────────────────────────────────────────────────────────

def generate_bisregister(n: int | None = None, config_path=None) -> pd.DataFrame:
    """
    Genereert n personen voor het fictieve bisregister.

    BIS-nummers: maand + 20 (geslacht onbekend) of + 40 (geslacht bekend).

    Parameters
    ----------
    n : int, optioneel
        Aantal te genereren personen. Standaard = population.bisregister.total // 10.
    config_path : str of Path, optioneel
        Pad naar config.json.

    Returns
    -------
    pd.DataFrame met kolommen:
        bisnummer, voornaam, familienaam, geslacht, geslacht_gekend,
        geboortedatum, geboorteplaats, geboorteland, nationaliteit,
        burgerlijke_staat, adres_*
    """
    cfg = _load_config(config_path)
    rng = random.Random(cfg["meta"]["seed"] + 999)
    ref = date.fromisoformat(cfg["meta"]["creation_date"])
    n   = n if n is not None else cfg["generation"]["counts"]["bisregister"]

    bands         = cfg["demographics"]["age_distribution"]["bands"]
    gender_ratio  = cfg["demographics"]["gender_ratio"]["male"]
    gemeenten     = cfg["locations"]["belgische_gemeenten"]
    buitenland    = cfg["locations"]["buitenlandse_geboorteplaatsen"]
    bis_cfg       = cfg["rijksregisternummer"]["bis_prefix_offset"]
    namen_m       = cfg["names"]["voornamen_mannelijk"]
    namen_v       = cfg["names"]["voornamen_vrouwelijk"]
    familienamen  = cfg["names"]["familienamen"]

    bis_nat = {
        "Marokkaans":         0.15,
        "Turks":              0.10,
        "Congolees":          0.12,
        "Oost_Europees":      0.08,
        "Aziatisch":          0.20,
        "Latijns_Amerikaans": 0.12,
        "Overig":             0.23,
    }
    nat_keys    = list(bis_nat.keys())
    nat_weights = list(bis_nat.values())

    seq_m: dict[str, int] = defaultdict(lambda: 997)
    seq_f: dict[str, int] = defaultdict(lambda: 998)

    records = []

    for _ in range(n):
        gender       = "M" if rng.random() < gender_ratio else "F"
        gender_known = rng.random() < 0.85
        birth        = _random_birthdate(rng, bands, ref)
        yy           = f"{birth.year % 100:02d}"
        dd           = f"{birth.day:02d}"

        offset     = bis_cfg["known_gender"] if gender_known else bis_cfg["unknown_gender"]
        mm_bis     = f"{birth.month + offset:02d}"
        yymmdd_bis = yy + mm_bis + dd
        born_2k    = birth.year >= 2000

        if gender == "M":
            seq = seq_m[yymmdd_bis]
            seq_m[yymmdd_bis] = max(1, seq_m[yymmdd_bis] - 2)
        else:
            seq = seq_f[yymmdd_bis]
            seq_f[yymmdd_bis] = max(2, seq_f[yymmdd_bis] - 2)

        cc     = _controlcijfer(yymmdd_bis, seq, born_2k)
        bis_nr = _format_nr(yymmdd_bis, seq, cc)

        nationality = rng.choices(nat_keys, weights=nat_weights)[0]

        if rng.random() < 0.75:
            bp = rng.choice(buitenland)
            geboorteplaats, geboorteland = bp["stad"], bp["land"]
        else:
            gem = _pick_municipality(rng, gemeenten)
            geboorteplaats, geboorteland = gem["naam"], "België"

        voornaam    = _pick_voornaam(rng, gender, nationality, namen_m, namen_v)
        familienaam = _pick_familienaam(rng, nationality, familienamen)
        status      = _burgerlijke_staat(rng, birth, ref)
        adres       = genereer_adres(rng, cfg)

        records.append({
            "bisnummer":         bis_nr,
            "voornaam":          voornaam,
            "familienaam":       familienaam,
            "geslacht":          gender if gender_known else "X",
            "geslacht_gekend":   gender_known,
            "geboortedatum":     birth.isoformat(),
            "geboorteplaats":    geboorteplaats,
            "geboorteland":      geboorteland,
            "nationaliteit":     nationality,
            "burgerlijke_staat": status,
            **adres,
        })

    return pd.DataFrame(records)
