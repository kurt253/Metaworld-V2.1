"""
generate_careers.py
Genereert loopbanen voor alle personen in het rijksregister en bisregister.

Output (3 lijsten van dicts, elk als apart JSON-bestand):
  dimona_records  – Dimona-aangiften (RSZ) voor werknemers, arbeiders, ambtenaren
                    én studentenjobs
  rsvz_records    – RSVZ-aansluitingen voor zelfstandigen
  rvw_records     – RVA-werkloosheidsperioden

Een persoon kan in meerdere bestanden voorkomen (gemengde loopbaan).
Gesorteerd op rijksregisternummer (dalende afstamming niet van toepassing hier).
"""
from __future__ import annotations

import json
import random
import pandas as pd
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent


# ─────────────────────────────────────────────────────────────────────────────
# 200 beroepen verdeeld over 4 categorieën
# ─────────────────────────────────────────────────────────────────────────────

BEROEPEN: dict[str, list[dict]] = {
    "bediende": [
        {"naam": "accountant",                      "nace": "6920"},
        {"naam": "advocaat-medewerker",             "nace": "6910"},
        {"naam": "apothekersassistent",             "nace": "4773"},
        {"naam": "bankbediende",                    "nace": "6419"},
        {"naam": "boekhouder",                      "nace": "6920"},
        {"naam": "bedrijfsanalist",                 "nace": "7022"},
        {"naam": "business analyst",                "nace": "6209"},
        {"naam": "communicatieadviseur",            "nace": "7021"},
        {"naam": "consultant (loondienst)",         "nace": "7022"},
        {"naam": "copywriter",                      "nace": "7310"},
        {"naam": "customer service medewerker",     "nace": "8220"},
        {"naam": "data-analist",                    "nace": "6209"},
        {"naam": "dossierbeheerder",                "nace": "8299"},
        {"naam": "financieel analist",              "nace": "6619"},
        {"naam": "grafisch ontwerper (loondienst)", "nace": "7410"},
        {"naam": "HR-medewerker",                   "nace": "7810"},
        {"naam": "ICT-beheerder",                   "nace": "6209"},
        {"naam": "ICT-projectleider",               "nace": "6201"},
        {"naam": "ingenieur bouwkunde",             "nace": "7111"},
        {"naam": "ingenieur elektronica",           "nace": "7112"},
        {"naam": "ingenieur informatica",           "nace": "6201"},
        {"naam": "ingenieur mechanica",             "nace": "7112"},
        {"naam": "journalist (loondienst)",         "nace": "5813"},
        {"naam": "jurist (loondienst)",             "nace": "6910"},
        {"naam": "klantenbeheerder",                "nace": "7022"},
        {"naam": "laboratoriumtechnicus",           "nace": "7219"},
        {"naam": "logistiek coördinator",           "nace": "5229"},
        {"naam": "managementassistent",             "nace": "8211"},
        {"naam": "marketeer",                       "nace": "7310"},
        {"naam": "notariaatsklerk",                 "nace": "6910"},
        {"naam": "paralegaal",                      "nace": "6910"},
        {"naam": "pedagoog (loondienst)",           "nace": "8559"},
        {"naam": "projectleider",                   "nace": "7022"},
        {"naam": "psycholoog (loondienst)",         "nace": "8690"},
        {"naam": "receptionist",                    "nace": "8211"},
        {"naam": "sales manager",                   "nace": "7022"},
        {"naam": "secretaris",                      "nace": "8211"},
        {"naam": "sociaal assistent",               "nace": "8810"},
        {"naam": "softwareontwikkelaar",            "nace": "6201"},
        {"naam": "systeemanalist",                  "nace": "6202"},
        {"naam": "technisch tekenaar",              "nace": "7112"},
        {"naam": "tolk (loondienst)",               "nace": "7430"},
        {"naam": "trainer (loondienst)",            "nace": "8559"},
        {"naam": "transportplanner",                "nace": "5229"},
        {"naam": "UX designer",                     "nace": "7410"},
        {"naam": "verzekeringsadviseur",            "nace": "6622"},
        {"naam": "verpleegkundige (loondienst)",    "nace": "8610"},
        {"naam": "vertaler (loondienst)",           "nace": "7430"},
        {"naam": "web developer",                   "nace": "6201"},
        {"naam": "zorgcoördinator",                 "nace": "8710"},
    ],
    "arbeider": [
        {"naam": "bakker",                          "nace": "1071"},
        {"naam": "bouwvakker",                      "nace": "4120"},
        {"naam": "chauffeur",                       "nace": "4941"},
        {"naam": "elektricien (loondienst)",        "nace": "4321"},
        {"naam": "fietskoerier",                    "nace": "5320"},
        {"naam": "garagist (loondienst)",           "nace": "4520"},
        {"naam": "glazenwasser",                    "nace": "8121"},
        {"naam": "havenarbeider",                   "nace": "5224"},
        {"naam": "hovenier (loondienst)",           "nace": "8130"},
        {"naam": "huismeester",                     "nace": "8110"},
        {"naam": "installateur verwarmingstoestellen", "nace": "4322"},
        {"naam": "ketelmaker",                      "nace": "2530"},
        {"naam": "kapper (loondienst)",             "nace": "9602"},
        {"naam": "keukenhulp",                      "nace": "5610"},
        {"naam": "koerierschauffeur",               "nace": "5320"},
        {"naam": "kraanbestuurder",                 "nace": "4399"},
        {"naam": "lasser",                          "nace": "2511"},
        {"naam": "loodgieter (loondienst)",         "nace": "4322"},
        {"naam": "magazijnier",                     "nace": "5210"},
        {"naam": "maler",                           "nace": "4334"},
        {"naam": "metaalbewerker",                  "nace": "2599"},
        {"naam": "metselaar",                       "nace": "4311"},
        {"naam": "monteur",                         "nace": "3317"},
        {"naam": "meubelmaker",                     "nace": "3101"},
        {"naam": "operator productie",              "nace": "2599"},
        {"naam": "pakhuiswerker",                   "nace": "5210"},
        {"naam": "pijpfitter",                      "nace": "4322"},
        {"naam": "plaatwerker",                     "nace": "2511"},
        {"naam": "postbode",                        "nace": "5310"},
        {"naam": "productiemedewerker",             "nace": "2899"},
        {"naam": "rioolarbeider",                   "nace": "3700"},
        {"naam": "ruwbouwer",                       "nace": "4120"},
        {"naam": "schilder (loondienst)",           "nace": "4334"},
        {"naam": "schoonmaker",                     "nace": "8121"},
        {"naam": "slachthuis medewerker",           "nace": "1011"},
        {"naam": "snijder",                         "nace": "1011"},
        {"naam": "stukadoor",                       "nace": "4331"},
        {"naam": "technisch onderhoudsmonteur",     "nace": "3319"},
        {"naam": "tegelzetter",                     "nace": "4333"},
        {"naam": "timmerman (loondienst)",          "nace": "4332"},
        {"naam": "transportmedewerker",             "nace": "4941"},
        {"naam": "tuinier (loondienst)",            "nace": "8130"},
        {"naam": "veiligheidspersoneel",            "nace": "8010"},
        {"naam": "verhuizer",                       "nace": "4942"},
        {"naam": "vloerlegger",                     "nace": "4333"},
        {"naam": "weefster",                        "nace": "1310"},
        {"naam": "werfopzichter",                   "nace": "4120"},
        {"naam": "zandstraalspuiter",               "nace": "4312"},
        {"naam": "zwembadopzichter",                "nace": "9311"},
        {"naam": "grutterij medewerker",            "nace": "4711"},
    ],
    "ambtenaar": [
        {"naam": "belastingambtenaar",              "nace": "8411"},
        {"naam": "burgemeester",                    "nace": "8411"},
        {"naam": "cipier",                          "nace": "8423"},
        {"naam": "douanier",                        "nace": "8411"},
        {"naam": "gemeentesecretaris",              "nace": "8411"},
        {"naam": "griffier rechtbank",              "nace": "8423"},
        {"naam": "inspecteur ruimtelijke ordening", "nace": "8411"},
        {"naam": "jeugdopbouwwerker OCMW",          "nace": "8899"},
        {"naam": "justitieassistent",               "nace": "8423"},
        {"naam": "kadasterbeheerder",               "nace": "8411"},
        {"naam": "leerkracht basisonderwijs",       "nace": "8520"},
        {"naam": "leerkracht secundair onderwijs",  "nace": "8531"},
        {"naam": "leerkracht hoger onderwijs",      "nace": "8542"},
        {"naam": "legerofficier",                   "nace": "8422"},
        {"naam": "medewerker burgerzaken",          "nace": "8411"},
        {"naam": "medewerker OCMW",                 "nace": "8899"},
        {"naam": "medewerker sociale zekerheid",    "nace": "8412"},
        {"naam": "medewerker RVA",                  "nace": "8412"},
        {"naam": "milieu-ambtenaar",                "nace": "8411"},
        {"naam": "officier van justitie",           "nace": "8423"},
        {"naam": "ontvanger der belastingen",       "nace": "8411"},
        {"naam": "parketmedewerker",                "nace": "8423"},
        {"naam": "pensioenadviseur (overheid)",     "nace": "8412"},
        {"naam": "politieagent",                    "nace": "8424"},
        {"naam": "politiecommissaris",              "nace": "8424"},
        {"naam": "postambtenaar",                   "nace": "5310"},
        {"naam": "rechter",                         "nace": "8423"},
        {"naam": "rijksambtenaar",                  "nace": "8411"},
        {"naam": "ruimtelijk planner",              "nace": "7111"},
        {"naam": "schooldirecteur (gemeentelijk)",  "nace": "8520"},
        {"naam": "secretaris-generaal",             "nace": "8411"},
        {"naam": "sociaal inspecteur",              "nace": "8412"},
        {"naam": "stedenbouwkundige",               "nace": "7111"},
        {"naam": "universiteitsprofessor",          "nace": "8542"},
        {"naam": "verkeersagent",                   "nace": "8424"},
        {"naam": "vrederechter",                    "nace": "8423"},
        {"naam": "waterambtenaar",                  "nace": "3600"},
        {"naam": "welzijnswerker (publiek)",        "nace": "8899"},
        {"naam": "wetenschappelijk medewerker",     "nace": "7219"},
        {"naam": "ziekenhuisverpleegkundige (publiek)", "nace": "8610"},
        {"naam": "directeur openbaar ziekenhuis",   "nace": "8610"},
        {"naam": "gevangenisdirecteur",             "nace": "8423"},
        {"naam": "jobcoach VDAB",                   "nace": "7810"},
        {"naam": "adviseur Kind en Gezin",          "nace": "8891"},
        {"naam": "medewerker FOD Financiën",        "nace": "8411"},
        {"naam": "medewerker RIZIV",                "nace": "8412"},
        {"naam": "medewerker RSVZ (ambtenaar)",     "nace": "8412"},
        {"naam": "archivaris gemeente",             "nace": "9101"},
        {"naam": "coördinator lokale politie",      "nace": "8424"},
        {"naam": "diplomaat",                       "nace": "8421"},
    ],
    "zelfstandige": [
        {"naam": "aannemer",                        "nace": "4120"},
        {"naam": "advocaat",                        "nace": "6910"},
        {"naam": "apotheker (eigen apotheek)",      "nace": "4773"},
        {"naam": "architect",                       "nace": "7111"},
        {"naam": "arts-specialist",                 "nace": "8621"},
        {"naam": "automatiseerder",                 "nace": "2825"},
        {"naam": "bakker (eigen zaak)",             "nace": "1071"},
        {"naam": "boekhoudkantoor eigenaar",        "nace": "6920"},
        {"naam": "chiropractor",                    "nace": "8690"},
        {"naam": "coach",                           "nace": "8559"},
        {"naam": "consultant (zelfstandig)",        "nace": "7022"},
        {"naam": "dierenarts",                      "nace": "7500"},
        {"naam": "drukker (eigen zaak)",            "nace": "1812"},
        {"naam": "estheticienne",                   "nace": "9602"},
        {"naam": "eventorganisator",                "nace": "8230"},
        {"naam": "fietsenmaker",                    "nace": "9529"},
        {"naam": "financieel adviseur (zelfstandig)", "nace": "6619"},
        {"naam": "fotograaf",                       "nace": "7420"},
        {"naam": "fysiotherapeut",                  "nace": "8690"},
        {"naam": "grafisch ontwerper (zelfstandig)", "nace": "7410"},
        {"naam": "gids (zelfstandig)",              "nace": "7990"},
        {"naam": "handelaar",                       "nace": "4719"},
        {"naam": "herstellingsbedrijf eigenaar",    "nace": "3314"},
        {"naam": "horecaondernemer",                "nace": "5610"},
        {"naam": "huisarts",                        "nace": "8621"},
        {"naam": "installateur (zelfstandig)",      "nace": "4321"},
        {"naam": "interieurarchitect",              "nace": "7410"},
        {"naam": "IT-freelancer",                   "nace": "6201"},
        {"naam": "journalist (freelance)",          "nace": "5813"},
        {"naam": "kapper (eigen zaak)",             "nace": "9602"},
        {"naam": "kinderpsycholoog (zelfstandig)",  "nace": "8690"},
        {"naam": "klimaattechnicus (zelfstandig)",  "nace": "4322"},
        {"naam": "kunstenaar",                      "nace": "9003"},
        {"naam": "landmeter",                       "nace": "7112"},
        {"naam": "logopedist",                      "nace": "8690"},
        {"naam": "makelaar",                        "nace": "6831"},
        {"naam": "massagetherapeut",                "nace": "9604"},
        {"naam": "notaris (zelfstandig)",           "nace": "6910"},
        {"naam": "opticien",                        "nace": "4778"},
        {"naam": "psycholoog (zelfstandig)",        "nace": "8690"},
        {"naam": "schrijver/auteur",                "nace": "9003"},
        {"naam": "slager (eigen zaak)",             "nace": "1011"},
        {"naam": "tandarts",                        "nace": "8623"},
        {"naam": "tatoeëerder",                     "nace": "9602"},
        {"naam": "textielhandelaar",                "nace": "4641"},
        {"naam": "tuinarchitect",                   "nace": "7111"},
        {"naam": "uitvaartondernemer",              "nace": "9603"},
        {"naam": "vastgoedontwikkelaar",            "nace": "4110"},
        {"naam": "verzekeringsmakelaar",            "nace": "6622"},
        {"naam": "webdesigner (zelfstandig)",       "nace": "7410"},
    ],
}

# Gewichten per categorie (som = 1)
_CAT_GEWICHTEN = {
    "bediende":    0.35,
    "arbeider":    0.25,
    "ambtenaar":   0.20,
    "zelfstandige": 0.20,
}

# Dimona-type per categorie (zelfstandige → None: geen Dimona)
_DIMONA_TYPE = {"bediende": "D", "arbeider": "A", "ambtenaar": "D"}

# Fictieve werkgevernamen-componenten
_WG_NAAM_A = ["Van der", "De", "Noord", "West", "Euro", "Bel", "Tech", "Pro", "Multi", "Uni",
               "Alpha", "Delta", "Sigma", "Nova", "Inter", "Trans", "All", "First", "Top", "New"]
_WG_NAAM_B = ["groep", "solutions", "services", "consulting", "industries", "tech", "care",
               "build", "connect", "works", "flex", "plus", "net", "soft", "corp", "hub"]
_WG_SUFFIX  = [" NV", " BV", " SA", " BVBA", " SRL", " CV", " VZW", " GCV"]

# Overheidsarbeidsgevers (voor ambtenaren)
_OVERHEID_WG = [
    ("Gemeente Brussel",   "0214.638.483", "8411"),
    ("Stad Antwerpen",     "0207.725.666", "8411"),
    ("Stad Gent",          "0264.737.962", "8411"),
    ("Stad Luik",          "0222.453.231", "8411"),
    ("Federale Overheidsdienst Financiën", "0316.381.101", "8411"),
    ("FOD Justitie",       "0671.516.647", "8423"),
    ("FOD Binnenlandse Zaken", "0316.813.705", "8411"),
    ("NMBS",               "0203.430.226", "4910"),
    ("Bpost",              "0214.596.464", "5310"),
    ("RIZIV",              "0206.732.437", "8412"),
    ("RVA",                "0206.732.596", "8412"),
    ("Politiezone Antwerpen", "0248.631.491", "8424"),
    ("UZ Gent",            "0247.833.952", "8610"),
    ("KU Leuven",          "0419.052.173", "8542"),
    ("UGent",              "0248.015.142", "8542"),
    ("VUB",                "0553.478.073", "8542"),
    ("Defensie",           "0202.861.985", "8422"),
    ("OCMW Brussel",       "0203.552.608", "8899"),
    ("Agentschap Zorg en Gezondheid", "0316.380.632", "8412"),
    ("VDAB",               "0244.250.928", "7810"),
]


# ─────────────────────────────────────────────────────────────────────────────
# Hulpfuncties
# ─────────────────────────────────────────────────────────────────────────────

def _load_config(config_path=None) -> dict:
    path = Path(config_path) if config_path else ROOT / "config.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _kbo(rng: random.Random) -> str:
    n = rng.randint(100_000_000, 999_999_999)
    s = f"0{n}"
    return f"{s[:4]}.{s[4:7]}.{s[7:]}"


def _werkgever(rng: random.Random, cat: str) -> tuple[str, str, str]:
    """Geeft (naam, kbo, nace) terug voor een willekeurige werkgever."""
    if cat == "ambtenaar":
        naam, kbo, nace = rng.choice(_OVERHEID_WG)
        return naam, kbo, nace
    a = rng.choice(_WG_NAAM_A)
    b = rng.choice(_WG_NAAM_B)
    suf = rng.choice(_WG_SUFFIX)
    return f"{a} {b}{suf}", _kbo(rng), "7022"


def _studie_einde_leeftijd(rng: random.Random, geboortejaar: int) -> int:
    """Realistische Belgische studieduur naar geboortejaar."""
    if geboortejaar < 1960:
        return rng.choices([16, 18, 21], weights=[0.30, 0.40, 0.30])[0]
    return rng.choices([18, 21, 23, 26], weights=[0.20, 0.40, 0.28, 0.12])[0]


def _pensioen_leeftijd(rng: random.Random) -> int:
    """Belgische effectieve pensioenleeftijd (verdeling o.b.v. statistieken)."""
    return rng.choices(
        [60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70],
        weights=[0.04, 0.05, 0.12, 0.12, 0.10, 0.32, 0.12, 0.08, 0.03, 0.01, 0.01],
    )[0]


def _datum_plus_maanden(d: date, maanden: int) -> date:
    m = d.month - 1 + maanden
    return date(d.year + m // 12, m % 12 + 1, min(d.day, 28))


def _eerste_dag_volgend_kwartaal(d: date) -> date:
    kw = (d.month - 1) // 3
    if kw == 3:
        return date(d.year + 1, 1, 1)
    return date(d.year, kw * 3 + 4, 1)


# ─────────────────────────────────────────────────────────────────────────────
# Career generator
# ─────────────────────────────────────────────────────────────────────────────

class CareerGenerator:

    def __init__(self, config_path=None, seed: int = 42):
        cfg       = _load_config(config_path)
        self.rng  = random.Random(seed + 7777)
        self.ref  = date.fromisoformat(cfg["meta"]["creation_date"])
        self._cat_keys    = list(_CAT_GEWICHTEN.keys())
        self._cat_weights = list(_CAT_GEWICHTEN.values())

    # ── categorie kiezen ─────────────────────────────────────────────────────

    def _kies_categorie(self, studie_leeftijd: int) -> str:
        if studie_leeftijd <= 18:
            # Minder opgeleid → meer kans op arbeider
            return self.rng.choices(
                ["bediende", "arbeider", "ambtenaar", "zelfstandige"],
                weights=[0.25, 0.42, 0.15, 0.18],
            )[0]
        if studie_leeftijd >= 23:
            # Hoog opgeleid → meer kans op bediende/zelfstandige
            return self.rng.choices(
                ["bediende", "arbeider", "ambtenaar", "zelfstandige"],
                weights=[0.38, 0.08, 0.24, 0.30],
            )[0]
        return self.rng.choices(self._cat_keys, weights=self._cat_weights)[0]

    # ── studentenjobs ────────────────────────────────────────────────────────

    def _studentenjobs(
        self, rrn: str, birth: date, studie_einde: date, career_einde: date
    ) -> list[dict]:
        rng = self.rng
        start_student = date(birth.year + 16, birth.month, birth.day)
        if start_student >= career_einde or not (rng.random() < 0.60):
            return []
        records = []
        cursor = max(start_student, date(start_student.year, 6, 1))
        max_einde = min(studie_einde, career_einde)
        n_jobs = rng.randint(1, 3)
        for _ in range(n_jobs):
            if cursor >= max_einde:
                break
            duur = rng.randint(6, 12)  # weken
            job_start = date(cursor.year, rng.choice([6, 7, 8]), rng.randint(1, 15))
            if job_start >= max_einde:
                break
            job_einde = job_start + timedelta(weeks=duur)
            if job_einde > max_einde:
                job_einde = max_einde
            naam_wg, kbo_wg, _ = _werkgever(rng, "bediende")
            beroep = rng.choice(["jobstudent horeca", "jobstudent retail", "jobstudent logistiek",
                                  "jobstudent administratie", "jobstudent callcenter"])
            records.append({
                "rijksregisternummer": rrn,
                "type":                "S",
                "kbo_werkgever":       kbo_wg,
                "naam_werkgever":      naam_wg,
                "sector_nace":         "5610",
                "beroep":              beroep,
                "datum_in":            job_start.isoformat(),
                "datum_uit":           job_einde.isoformat(),
                "reden_uit":           "E",
            })
            cursor = date(job_einde.year + 1, 6, 1)
        return records

    # ── loondienst-loopbaan (bediende/arbeider/ambtenaar) ────────────────────

    def _loondienst(
        self, rrn: str, cat: str, start: date, pensioen: date,
        career_einde: date, gepensioneerd: bool,
        dimona_out: list, rvw_out: list,
    ) -> None:
        rng     = self.rng
        cursor  = start
        effectief_einde = min(pensioen, career_einde)
        beroepen_cat = BEROEPEN[cat]
        n_jobs  = rng.randint(1, 5)

        for job_nr in range(n_jobs):
            if cursor >= effectief_einde:
                break
            beroep_info = rng.choice(beroepen_cat)
            naam_wg, kbo_wg, _ = _werkgever(rng, cat)
            nace = beroep_info["nace"]

            # Duur van de job: 1–15 jaar, minder kans op heel kort
            duur_jr = rng.choices(
                [1, 2, 3, 5, 8, 12, 15],
                weights=[0.05, 0.10, 0.15, 0.25, 0.20, 0.15, 0.10],
            )[0]
            job_einde = _datum_plus_maanden(cursor, duur_jr * 12)

            is_last = (job_nr == n_jobs - 1)
            if is_last or job_einde >= effectief_einde:
                job_einde = effectief_einde
                reden = "P" if gepensioneerd and job_einde == pensioen else (
                    "OD" if career_einde < self.ref else "E"
                )
            else:
                reden = "O"

            dimona_out.append({
                "rijksregisternummer": rrn,
                "type":               _DIMONA_TYPE.get(cat, "D"),
                "kbo_werkgever":      kbo_wg,
                "naam_werkgever":     naam_wg,
                "sector_nace":        nace,
                "beroep":             beroep_info["naam"],
                "categorie":          cat,
                "datum_in":           cursor.isoformat(),
                "datum_uit":          job_einde.isoformat() if reden != "E" or job_einde < self.ref else None,
                "reden_uit":          reden if reden != "E" else None,
            })

            # Werkloosheidsperiode tussen jobs?
            if reden == "O" and rng.random() < 0.18:
                wl_start = job_einde
                wl_mnd   = rng.randint(2, 12)
                wl_einde = _datum_plus_maanden(wl_start, wl_mnd)
                if wl_einde < effectief_einde:
                    rvw_out.append({
                        "rijksregisternummer": rrn,
                        "type":       rng.choices(["VW", "TW"], weights=[0.80, 0.20])[0],
                        "datum_begin": wl_start.isoformat(),
                        "datum_einde": wl_einde.isoformat(),
                        "uitkering":   rng.choices(["A1", "A2", "B"], weights=[0.50, 0.30, 0.20])[0],
                    })
                    cursor = wl_einde
                else:
                    cursor = job_einde
            else:
                cursor = job_einde

    # ── zelfstandige-loopbaan ────────────────────────────────────────────────

    def _zelfstandige(
        self, rrn: str, start: date, pensioen: date,
        career_einde: date, gepensioneerd: bool,
        rsvz_out: list, dimona_out: list, rvw_out: list,
    ) -> None:
        rng = self.rng
        effectief_einde = min(pensioen, career_einde)
        beroepen_zz = BEROEPEN["zelfstandige"]

        # Eventueel vooraf in loondienst (40% kans)
        cursor = start
        if rng.random() < 0.40:
            jaren_loondienst = rng.randint(2, 8)
            overgang = _datum_plus_maanden(cursor, jaren_loondienst * 12)
            if overgang < effectief_einde:
                self._loondienst(rrn, rng.choices(["bediende", "arbeider"], weights=[0.70, 0.30])[0],
                                 cursor, overgang, overgang, False, dimona_out, rvw_out)
                cursor = overgang

        if cursor >= effectief_einde:
            return

        beroep_info = rng.choice(beroepen_zz)
        kbo_onderneming = _kbo(rng)

        # Meerdere aansluitingen mogelijk (bijberoep → hoofdberoep, of stopzetting + nieuwe)
        n_aansl = rng.choices([1, 2], weights=[0.80, 0.20])[0]
        for aansl_nr in range(n_aansl):
            if cursor >= effectief_einde:
                break
            if aansl_nr > 0:
                beroep_info = rng.choice(beroepen_zz)
                kbo_onderneming = _kbo(rng)

            is_last = (aansl_nr == n_aansl - 1)
            if is_last:
                aansl_einde = effectief_einde
                reden = "P" if gepensioneerd and aansl_einde == pensioen else (
                    "OD" if career_einde < self.ref else None
                )
            else:
                duur_jr = rng.randint(3, 12)
                aansl_einde = _datum_plus_maanden(cursor, duur_jr * 12)
                if aansl_einde >= effectief_einde:
                    aansl_einde = effectief_einde
                    reden = "P" if gepensioneerd else None
                else:
                    reden = "S"

            categorie = rng.choices(["H", "B"], weights=[0.85, 0.15])[0]

            rsvz_out.append({
                "rijksregisternummer": rrn,
                "beroep":              beroep_info["naam"],
                "activiteit_nace":     beroep_info["nace"],
                "kbo_onderneming":     kbo_onderneming,
                "categorie":           categorie,
                "datum_start":         cursor.isoformat(),
                "datum_stop":          aansl_einde.isoformat() if reden else (
                    None if aansl_einde >= self.ref else aansl_einde.isoformat()
                ),
                "reden_stop":          reden,
            })
            cursor = aansl_einde

    # ── hoofdroutine per persoon ──────────────────────────────────────────────

    def _verwerk_persoon(
        self, rrn: str, geboortedatum: str, overlijdensdatum
    ) -> Optional[dict]:
        rng = self.rng

        try:
            birth = date.fromisoformat(str(geboortedatum)[:10])
        except (ValueError, TypeError):
            return None

        ovl = None
        if overlijdensdatum and str(overlijdensdatum) not in ("", "None", "nan"):
            try:
                ovl = date.fromisoformat(str(overlijdensdatum)[:10])
            except (ValueError, TypeError):
                pass

        career_einde = ovl if ovl else self.ref
        leeftijd_bij_einde = (career_einde - birth).days // 365

        if leeftijd_bij_einde < 16:
            return None

        studie_lft    = _studie_einde_leeftijd(rng, birth.year)
        studie_einde  = date(birth.year + studie_lft, birth.month, birth.day)
        if studie_einde > career_einde:
            studie_einde = career_einde

        pensioen_lft  = _pensioen_leeftijd(rng)
        pensioen_datum = date(birth.year + pensioen_lft, birth.month, birth.day)
        gepensioneerd  = pensioen_datum <= career_einde

        dimona: list[dict] = []
        rsvz:   list[dict] = []
        rvw:    list[dict] = []

        # Student jobs
        if leeftijd_bij_einde >= 16:
            dimona += self._studentenjobs(rrn, birth, studie_einde, career_einde)

        # Professionele loopbaan
        career_start = studie_einde
        if career_start < date(birth.year + 18, birth.month, birth.day):
            career_start = date(birth.year + 18, birth.month, birth.day)

        if career_start >= career_einde:
            pass
        else:
            cat = self._kies_categorie(studie_lft)
            if cat == "zelfstandige":
                self._zelfstandige(rrn, career_start, pensioen_datum,
                                   career_einde, gepensioneerd, rsvz, dimona, rvw)
            else:
                self._loondienst(rrn, cat, career_start, pensioen_datum,
                                 career_einde, gepensioneerd, dimona, rvw)

        if not dimona and not rsvz and not rvw:
            return None

        return {"dimona": dimona, "rsvz": rsvz, "rvw": rvw}

    # ── publieke methode ──────────────────────────────────────────────────────

    def genereer(
        self,
        rr_df:  pd.DataFrame,
        bis_df: pd.DataFrame,
    ) -> tuple[list[dict], list[dict], list[dict]]:
        """
        Genereert loopbaandata voor alle personen.

        Returns
        -------
        (dimona_records, rsvz_records, rvw_records)
        Elk een lijst van flat dicts (één rij per aangifte/aansluiting/periode).
        """
        dimona_all: list[dict] = []
        rsvz_all:   list[dict] = []
        rvw_all:    list[dict] = []

        for df, nr_col in [(rr_df, "rijksregisternummer"), (bis_df, "bisnummer")]:
            if df is None or df.empty or nr_col not in df.columns:
                continue
            for _, row in df.iterrows():
                rrn = str(row[nr_col])
                res = self._verwerk_persoon(
                    rrn,
                    row.get("geboortedatum"),
                    row.get("overlijdensdatum"),
                )
                if res is None:
                    continue
                dimona_all += res["dimona"]
                rsvz_all   += res["rsvz"]
                rvw_all    += res["rvw"]

        return dimona_all, rsvz_all, rvw_all


# ─────────────────────────────────────────────────────────────────────────────
# Publieke interface
# ─────────────────────────────────────────────────────────────────────────────

def generate_careers(
    rr_df:  Optional[pd.DataFrame] = None,
    bis_df: Optional[pd.DataFrame] = None,
    seed:   Optional[int] = None,
    config_path=None,
) -> tuple[list[dict], list[dict], list[dict]]:
    """
    Genereer loopbaandata voor alle personen.

    Laadt rr_df/bis_df automatisch uit Generated Data/ als ze None zijn.

    Returns
    -------
    (dimona_records, rsvz_records, rvw_records)
    """
    cfg = _load_config(config_path)
    if seed is None:
        seed = cfg["meta"]["seed"]

    if rr_df is None:
        save_dir = ROOT / "Generated Data"
        rr_path  = save_dir / "metaworld_rijksregister.json"
        bis_path = save_dir / "metaworld_bisregister.json"
        if not rr_path.exists():
            raise FileNotFoundError(
                "Geen rijksregisterbestand gevonden. "
                "Genereer registers eerst via voorbereiding_data.ipynb."
            )
        rr_df  = pd.read_json(rr_path,  convert_dates=False)
        bis_df = pd.read_json(bis_path, convert_dates=False) if bis_path.exists() else pd.DataFrame()
    if bis_df is None:
        bis_df = pd.DataFrame()

    return CareerGenerator(config_path=config_path, seed=seed).genereer(rr_df, bis_df)


# ─────────────────────────────────────────────────────────────────────────────
# Standalone uitvoering
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    import sys
    import time

    prefix   = sys.argv[1] if len(sys.argv) > 1 else "metaworld"
    save_dir = ROOT / "Generated Data"

    rr_path  = save_dir / f"{prefix}_rijksregister.json"
    bis_path = save_dir / f"{prefix}_bisregister.json"

    if not rr_path.exists():
        print(f"FOUT: {rr_path} niet gevonden.")
        print("Genereer eerst de registers via voorbereiding_data.ipynb of genereer_maatschappij.py.")
        sys.exit(1)

    print("=" * 50)
    print("  metaworldV2 — Genereer loopbanen")
    print(f"  Prefix: {prefix}")
    print("=" * 50)

    print("\n[Stap 1] Registers laden ...")
    rr_df  = pd.read_json(rr_path,  convert_dates=False)
    bis_df = pd.read_json(bis_path, convert_dates=False) if bis_path.exists() else pd.DataFrame()
    print(f"  RR : {len(rr_df):,} personen")
    print(f"  BIS: {len(bis_df):,} personen")

    print("\n[Stap 2] Loopbanen genereren ...")
    t = time.time()
    dimona, rsvz, rvw = generate_careers(rr_df=rr_df, bis_df=bis_df)
    elapsed = time.time() - t
    print(f"  Dimona : {len(dimona):,} records")
    print(f"  RSVZ   : {len(rsvz):,} records")
    print(f"  RVW    : {len(rvw):,} records")
    print(f"  ({elapsed:.1f}s)")

    print("\n[Stap 3] Opslaan ...")
    save_dir.mkdir(exist_ok=True)
    for naam, data in [
        (f"{prefix}_dimona.json", dimona),
        (f"{prefix}_rsvz.json",   rsvz),
        (f"{prefix}_rvw.json",    rvw),
    ]:
        pad = save_dir / naam
        with open(pad, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        print(f"  → {naam}  ({len(data):,} records)")

    print("\nKlaar.")


if __name__ == "__main__":
    main()
