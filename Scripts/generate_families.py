"""
generate_families.py
Legt familierelaties tussen bestaande rijksregister- en bisregisterpersonen.

Personen worden NIET opnieuw aangemaakt: naam, adres, geboortedatum enz.
komen rechtstreeks uit de doorgegeven DataFrames.
Wat wordt toegevoegd: generatie, partner_rr, vader_rr, moeder_rr, kinderen_rr.

Generaties op basis van leeftijd (t.o.v. creation_date):
  0  – geboren ≤ ref_jaar − 70   (stamouders)
  1  – geboren ref_jaar−69 … ref_jaar−46
  2  – geboren ref_jaar−45 … ref_jaar−21
  3  – geboren ≥ ref_jaar − 20
"""
from __future__ import annotations

import json
import random
import pandas as pd
from datetime import date
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent


# ─────────────────────────────────────────────────────────────────────────────
# Config / helpers
# ─────────────────────────────────────────────────────────────────────────────

def _load_config(config_path=None) -> dict:
    path = Path(config_path) if config_path else ROOT / "config.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _find_latest_registers(config_path=None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Laad het metaworld rijksregister + bisregister van schijf."""
    save_dir = ROOT / "Generated Data"
    rr_pad  = save_dir / "metaworld_rijksregister.json"
    bis_pad = save_dir / "metaworld_bisregister.json"
    if not rr_pad.exists():
        raise FileNotFoundError(
            "Geen rijksregisterbestand gevonden (metaworld_rijksregister.json). "
            "Genereer het rijksregister eerst via voorbereiding_data.ipynb."
        )
    rr_df  = pd.read_json(rr_pad,  convert_dates=False)
    bis_df = pd.read_json(bis_pad, convert_dates=False) if bis_pad.exists() else pd.DataFrame()
    return rr_df, bis_df


def _clean(v):
    """Zet NaN om naar None."""
    try:
        return None if pd.isna(v) else v
    except (TypeError, ValueError):
        return v


# ─────────────────────────────────────────────────────────────────────────────
# Generator
# ─────────────────────────────────────────────────────────────────────────────

class FamilyGenerator:

    def __init__(
        self,
        rr_df: pd.DataFrame,
        bis_df: pd.DataFrame,
        config_path=None,
        seed: int = 42,
    ):
        cfg      = _load_config(config_path)
        self.rng = random.Random(seed)
        self.ref = date.fromisoformat(cfg["meta"]["creation_date"])

        # Generatiegrenswaarden (geboortejaar) op basis van referentiedatum
        ry = self.ref.year
        self._grenzen = {
            0: (None,    ry - 70),
            1: (ry - 69, ry - 46),
            2: (ry - 45, ry - 21),
            3: (ry - 20, None),
        }

        # Pool per generatie per geslacht: lijst van persoon-dicts
        self._pool: dict[int, dict[str, list[dict]]] = {
            g: {"M": [], "F": []} for g in range(4)
        }
        # Personen die in het familiessysteem zitten: nummer → dict
        self._systeem: dict[str, dict] = {}

        self._vul_pool(rr_df, nr_kolom="rijksregisternummer", exclude_gen0=False)
        if not bis_df.empty:
            # BIS: enkel M/F, niet als gen-0 stamouder
            self._vul_pool(bis_df, nr_kolom="bisnummer",
                           exclude_gen0=True, only_mf=True)

        for gen_pools in self._pool.values():
            for lst in gen_pools.values():
                self.rng.shuffle(lst)

    # ── pool opbouwen ────────────────────────────────────────────────────────

    def _generatie(self, jaar: int) -> Optional[int]:
        for gen, (min_j, max_j) in self._grenzen.items():
            ok_min = (min_j is None or jaar >= min_j)
            ok_max = (max_j is None or jaar <= max_j)
            if ok_min and ok_max:
                return gen
        return None

    def _vul_pool(
        self,
        df: pd.DataFrame,
        nr_kolom: str,
        exclude_gen0: bool = False,
        only_mf: bool = False,
    ) -> None:
        for _, row in df.iterrows():
            nr       = str(row[nr_kolom])
            geslacht = str(_clean(row.get("geslacht")) or "X")
            if only_mf and geslacht not in ("M", "F"):
                continue

            geboortedatum = str(_clean(row.get("geboortedatum")) or "")
            try:
                jaar = int(geboortedatum[:4])
            except (ValueError, IndexError):
                continue

            gen = self._generatie(jaar)
            if gen is None:
                continue
            if exclude_gen0 and gen == 0:
                continue
            if geslacht not in ("M", "F"):
                continue  # only use M/F for coupling

            p: dict = {
                "rijksregisternummer": nr,
                "voornaam":          _clean(row.get("voornaam")),
                "familienaam":       _clean(row.get("familienaam")),
                "volledige_naam":    f"{_clean(row.get('voornaam')) or ''} "
                                     f"{_clean(row.get('familienaam')) or ''}".strip(),
                "geslacht":          geslacht,
                "geboortedatum":     _clean(row.get("geboortedatum")),
                "geboorteplaats":    _clean(row.get("geboorteplaats")),
                "geboorteland":      _clean(row.get("geboorteland")),
                "nationaliteit":     _clean(row.get("nationaliteit")),
                "burgerlijke_staat": _clean(row.get("burgerlijke_staat")),
                "overlijdensdatum":  _clean(row.get("overlijdensdatum")),
                "adres_straat":      _clean(row.get("adres_straat")),
                "adres_nr":          _clean(row.get("adres_nr")),
                "adres_bus":         _clean(row.get("adres_bus")),
                "adres_postcode":    _clean(row.get("adres_postcode")),
                "adres_gemeente":    _clean(row.get("adres_gemeente")),
                "adres_provincie":   _clean(row.get("adres_provincie")),
                "adres_gewest":      _clean(row.get("adres_gewest")),
                # Relatie-velden
                "generatie":    gen,
                "partner_rr":   None,
                "vader_rr":     None,
                "moeder_rr":    None,
                "kinderen_rr":  [],
            }
            self._pool[gen][geslacht].append(p)

    # ── selectie uit de pool ─────────────────────────────────────────────────

    def _neem(self, gen: int, geslacht: str, n: int) -> list[dict]:
        """
        Neem tot n personen uit pool[gen][geslacht].
        Voegt ze toe aan self._systeem. Geeft minder terug als pool leeg is.
        """
        pool = self._pool[gen][geslacht]
        gekozen, pool[:] = pool[:n], pool[n:]
        for p in gekozen:
            self._systeem[p["rijksregisternummer"]] = p
        return gekozen

    def _neem_kinderen(self, gen: int, n: int) -> list[dict]:
        """Neem n kinderen (wisselend M/F) uit de pool."""
        n_m = n // 2 + (1 if self.rng.random() < 0.5 and n % 2 else 0)
        n_f = n - n_m
        return self._neem(gen, "M", n_m) + self._neem(gen, "F", n_f)

    # ── relaties leggen ──────────────────────────────────────────────────────

    def _koppel(self, man: dict, vrouw: dict) -> None:
        rel = self.rng.choices(
            ["gehuwd", "wettelijk_samenwonend"], weights=[0.70, 0.30]
        )[0]
        man["partner_rr"]        = vrouw["rijksregisternummer"]
        vrouw["partner_rr"]      = man["rijksregisternummer"]
        man["burgerlijke_staat"]   = rel
        vrouw["burgerlijke_staat"] = rel

    def _leeftijdsverschil_ok(self, ouder: dict, kind: dict, min_verschil: int = 16) -> bool:
        try:
            jaar_ouder = int(str(ouder["geboortedatum"])[:4])
            jaar_kind  = int(str(kind["geboortedatum"])[:4])
            return (jaar_kind - jaar_ouder) >= min_verschil
        except (ValueError, TypeError, AttributeError):
            return False

    def _wijs_kind_toe(
        self, vader: dict, moeder: dict, kind: dict, gen: int
    ) -> bool:
        if not (self._leeftijdsverschil_ok(vader, kind)
                and self._leeftijdsverschil_ok(moeder, kind)):
            return False
        kind["vader_rr"]  = vader["rijksregisternummer"]
        kind["moeder_rr"] = moeder["rijksregisternummer"]
        kind["generatie"] = gen
        vader["kinderen_rr"].append(kind["rijksregisternummer"])
        moeder["kinderen_rr"].append(kind["rijksregisternummer"])
        kind["familienaam"]    = vader["familienaam"]
        kind["volledige_naam"] = f"{kind['voornaam'] or ''} {kind['familienaam'] or ''}".strip()
        return True

    # ── generaties opbouwen ──────────────────────────────────────────────────

    def genereer(
        self,
        n_stamfamilies: int = 300,
        n_stamsingles:  int = 60,
    ) -> list[dict]:

        # ── Generatie 0: stamkoppels + stamsingles ────────────────────────────
        mannen_0  = self._neem(0, "M", n_stamfamilies)
        vrouwen_0 = self._neem(0, "F", n_stamfamilies)
        n_sing_m  = n_stamsingles // 2
        n_sing_f  = n_stamsingles - n_sing_m
        singles_0 = self._neem(0, "M", n_sing_m) + self._neem(0, "F", n_sing_f)

        for p in singles_0:
            self._systeem[p["rijksregisternummer"]] = p
            p["burgerlijke_staat"] = self.rng.choices(
                ["ongehuwd", "gescheiden", "weduwe_weduwnaar"],
                weights=[0.30, 0.30, 0.40],
            )[0]

        for man, vrouw in zip(mannen_0, vrouwen_0):
            self._koppel(man, vrouw)
            n_k = self.rng.choices(
                [2, 3, 4, 5], weights=[0.25, 0.40, 0.25, 0.10]
            )[0]
            for kind in self._neem_kinderen(1, n_k):
                self._wijs_kind_toe(man, vrouw, kind, 1)

        # ── Generatie 1: koppels + kinderen ──────────────────────────────────
        gen1 = [p for p in self._systeem.values() if p["generatie"] == 1]
        self.rng.shuffle(gen1)
        mannen_1  = [p for p in gen1 if p["geslacht"] == "M"]
        vrouwen_1 = [p for p in gen1 if p["geslacht"] == "F"]

        n_koppels_1 = int(min(len(mannen_1), len(vrouwen_1)) * 0.75)
        for man, vrouw in zip(mannen_1[:n_koppels_1], vrouwen_1[:n_koppels_1]):
            self._koppel(man, vrouw)
            n_k = self.rng.choices(
                [0, 1, 2, 3, 4], weights=[0.10, 0.25, 0.40, 0.18, 0.07]
            )[0]
            for kind in self._neem_kinderen(2, n_k):
                self._wijs_kind_toe(man, vrouw, kind, 2)

        # Alleenstaande gen-1 krijgen realistische staat
        for p in gen1:
            if p["partner_rr"] is None and p["burgerlijke_staat"] == "ongehuwd":
                try:
                    leeftijd = (self.ref - date.fromisoformat(p["geboortedatum"])).days // 365
                except (ValueError, TypeError):
                    leeftijd = 40
                if leeftijd >= 30:
                    p["burgerlijke_staat"] = self.rng.choices(
                        ["ongehuwd", "gescheiden", "weduwe_weduwnaar"],
                        weights=[0.50, 0.35, 0.15],
                    )[0]

        # ── Generatie 2: koppels + kinderen ──────────────────────────────────
        gen2 = [p for p in self._systeem.values() if p["generatie"] == 2]
        self.rng.shuffle(gen2)
        mannen_2  = [p for p in gen2 if p["geslacht"] == "M"]
        vrouwen_2 = [p for p in gen2 if p["geslacht"] == "F"]

        n_koppels_2 = int(min(len(mannen_2), len(vrouwen_2)) * 0.55)
        for man, vrouw in zip(mannen_2[:n_koppels_2], vrouwen_2[:n_koppels_2]):
            try:
                leeftijd_v = (self.ref - date.fromisoformat(vrouw["geboortedatum"])).days // 365
            except (ValueError, TypeError):
                leeftijd_v = 25
            if leeftijd_v < 18:
                continue
            self._koppel(man, vrouw)
            n_k = self.rng.choices(
                [0, 1, 2, 3], weights=[0.20, 0.40, 0.30, 0.10]
            )[0]
            for kind in self._neem_kinderen(3, n_k):
                self._wijs_kind_toe(man, vrouw, kind, 3)

        # ── Generatie 3: sommigen vormen al een koppel ───────────────────────
        gen3 = [
            p for p in self._systeem.values()
            if p["generatie"] == 3 and p["partner_rr"] is None
        ]
        self.rng.shuffle(gen3)
        mannen_3  = [p for p in gen3 if p["geslacht"] == "M"]
        vrouwen_3 = [p for p in gen3 if p["geslacht"] == "F"]

        for man, vrouw in zip(mannen_3, vrouwen_3):
            try:
                am = (self.ref - date.fromisoformat(man["geboortedatum"])).days // 365
                av = (self.ref - date.fromisoformat(vrouw["geboortedatum"])).days // 365
            except (ValueError, TypeError):
                continue
            if am >= 22 and av >= 20 and self.rng.random() < 0.30:
                self._koppel(man, vrouw)

        self._pas_adressen_aan()
        return list(self._systeem.values())

    # ── adressen toewijzen op basis van gezinsstructuur ──────────────────────

    def _pas_adressen_aan(self) -> None:
        """
        Pas adressen aan op basis van de gezinsrelaties:
          - Koppels (gehuwd / wettelijk_samenwonend) wonen op hetzelfde adres.
            De vrouw erft het adres van de man.
          - Kinderen < 18 wonen bij de ouders (vader bij voorkeur, anders moeder).
            Ze erven het adres nadat koppels al zijn samengevoegd, zodat ze
            automatisch het gecombineerde koppel-adres krijgen.
          - Alleenstaanden ≥ 18 houden hun eigen adres.
        """
        _VELDEN = [
            "adres_straat", "adres_nr", "adres_bus",
            "adres_postcode", "adres_gemeente", "adres_provincie", "adres_gewest",
        ]

        def _kopieer(van: dict, naar: dict) -> None:
            for v in _VELDEN:
                naar[v] = van.get(v)

        # Stap 1: koppels delen adres — vrouw krijgt adres van man
        for p in self._systeem.values():
            if p.get("partner_rr") and p["geslacht"] == "F":
                man = self._systeem.get(p["partner_rr"])
                if man:
                    _kopieer(man, p)

        # Stap 2: kinderen < 18 krijgen het adres van de ouder
        # (ouder-adres is al bijgewerkt in stap 1)
        for p in self._systeem.values():
            try:
                leeftijd = (self.ref - date.fromisoformat(p["geboortedatum"])).days // 365
            except (ValueError, TypeError):
                continue
            if leeftijd < 18:
                ouder_rr = p.get("vader_rr") or p.get("moeder_rr")
                if ouder_rr:
                    ouder = self._systeem.get(ouder_rr)
                    if ouder:
                        _kopieer(ouder, p)


# ─────────────────────────────────────────────────────────────────────────────
# Publieke interface
# ─────────────────────────────────────────────────────────────────────────────

def pas_familienamen_aan(
    families: list[dict],
    rr_df: pd.DataFrame,
    bis_df: Optional[pd.DataFrame] = None,
) -> None:
    """
    Schrijft de familienamen uit de familiestructuur terug naar de register-DataFrames.
    Werkt in-place. Roep aan na generate_families(), vóór het opslaan van de registers.
    """
    naam_map: dict[str, str] = {
        str(p["rijksregisternummer"]): p["familienaam"]
        for p in families
        if p.get("rijksregisternummer") and p.get("familienaam")
    }
    for df, nr_col in [(rr_df, "rijksregisternummer"), (bis_df, "bisnummer")]:
        if df is None or df.empty or nr_col not in df.columns:
            continue
        mask = df[nr_col].astype(str).isin(naam_map)
        df.loc[mask, "familienaam"] = df.loc[mask, nr_col].astype(str).map(naam_map)


def generate_families(
    n_stamfamilies: Optional[int] = None,
    n_stamsingles:  Optional[int] = None,
    seed:           Optional[int] = None,
    config_path=None,
    rr_df:  Optional[pd.DataFrame] = None,
    bis_df: Optional[pd.DataFrame] = None,
) -> list[dict]:
    """
    Leg familierelaties tussen bestaande rijksregister- en bisregisterpersonen.

    Parameters
    ----------
    n_stamfamilies : aantal stamkoppels generatie 0 (standaard: uit config)
    n_stamsingles  : aantal alleenstaande stamouders generatie 0 (standaard: uit config)
    seed           : willekeurige seed (standaard: uit config)
    config_path    : pad naar config.json (optioneel)
    rr_df          : rijksregister DataFrame; indien None wordt het meest recente
                     bestand in 'Generated Data/' geladen
    bis_df         : bisregister DataFrame; indien None wordt het meest recente
                     bestand geladen

    Returns
    -------
    list[dict] – één dict per persoon in het familiessysteem
    """
    cfg    = _load_config(config_path)
    counts = cfg["generation"]["counts"]
    if n_stamfamilies is None:
        n_stamfamilies = counts["stamfamilies"]
    if n_stamsingles is None:
        n_stamsingles = counts["stamsingles"]
    if seed is None:
        seed = cfg["meta"]["seed"]

    if rr_df is None:
        rr_df, bis_auto = _find_latest_registers(config_path)
        if bis_df is None:
            bis_df = bis_auto
    if bis_df is None:
        bis_df = pd.DataFrame()

    return FamilyGenerator(
        rr_df=rr_df,
        bis_df=bis_df,
        config_path=config_path,
        seed=seed,
    ).genereer(
        n_stamfamilies=n_stamfamilies,
        n_stamsingles=n_stamsingles,
    )
