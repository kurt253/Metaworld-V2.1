"""
genereer_maatschappij.py
Genereert in de juiste volgorde het volledige fictieve Belgische register:
  1. Rijksregister
  2. Bisregister
  3. Familiestructuren (4 generaties)
  4. Opslaan naar Generated Data/

Gebruik:
  python Scripts/genereer_maatschappij.py [PREFIX]

  PREFIX  Naam van de outputbestanden (standaard: "metaworld")
"""
from __future__ import annotations

import sys
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from generate_register  import generate_rijksregister, generate_bisregister
from generate_families  import generate_families, pas_familienamen_aan


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _stap(nr: int, omschrijving: str) -> None:
    print(f"\n[Stap {nr}] {omschrijving}")
    print("─" * 50)


def _ok(label: str, n: int, elapsed: float) -> None:
    print(f"  ✓  {label}: {n:,} records  ({elapsed:.1f}s)")


def _rapporteer(rr_df, bis_df, families: list[dict]) -> None:
    print("\n" + "═" * 50)
    print("  RAPPORT")
    print("═" * 50)

    # Rijksregister
    rr_m = (rr_df["geslacht"] == "M").sum()
    rr_v = (rr_df["geslacht"] == "F").sum()
    rr_dead = rr_df["overlijdensdatum"].notna().sum()
    print(f"\nRijksregister  : {len(rr_df):>8,} personen")
    print(f"  Mannen       : {rr_m:>8,}")
    print(f"  Vrouwen      : {rr_v:>8,}")
    print(f"  Overledenen  : {rr_dead:>8,}")

    # Top-5 nationaliteiten
    top_nat = rr_df["nationaliteit"].value_counts().head(5)
    print("  Nationaliteiten (top 5):")
    for nat, cnt in top_nat.items():
        print(f"    {nat:<25} {cnt:>7,}")

    # Bisregister
    print(f"\nBisregister    : {len(bis_df):>8,} personen")
    if not bis_df.empty and "overlijdensdatum" in bis_df.columns:
        bis_dead = bis_df["overlijdensdatum"].notna().sum()
        print(f"  Overledenen  : {bis_dead:>8,}")

    # Families
    import pandas as pd
    fam_df = pd.DataFrame(families)
    gen_counts = fam_df["generatie"].value_counts().sort_index()
    n_met_ouders = fam_df["vader_rr"].notna().sum()
    n_koppels = (fam_df["partner_rr"].notna()).sum() // 2
    print(f"\nFamilies       : {len(families):>8,} personen in systeem")
    print(f"  Koppels      : {n_koppels:>8,}")
    print(f"  Met ouders   : {n_met_ouders:>8,}")
    print("  Per generatie:")
    for gen, cnt in gen_counts.items():
        print(f"    Gen {gen}        : {cnt:>7,}")

    print()


# ─────────────────────────────────────────────────────────────────────────────
# Hoofdprogramma
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    prefix = sys.argv[1] if len(sys.argv) > 1 else "metaworld"
    save_dir = ROOT / "Generated Data"
    save_dir.mkdir(exist_ok=True)

    config_path = ROOT / "config.json"
    with open(config_path, encoding="utf-8") as f:
        cfg = json.load(f)
    counts = cfg["generation"]["counts"]

    print("=" * 50)
    print(f"  metaworldV2 — Genereer maatschappij")
    print(f"  Prefix     : {prefix}")
    print(f"  RR-personen: {counts['rijksregister']:,}")
    print(f"  BIS-pers.  : {counts['bisregister']:,}")
    print(f"  Stamfam.   : {counts['stamfamilies']}")
    print(f"  Stamsingles: {counts['stamsingles']}")
    print("=" * 50)

    # ── Stap 1: Rijksregister ────────────────────────────────────────────────
    _stap(1, "Rijksregister genereren")
    t = time.time()
    rr_df = generate_rijksregister(config_path=config_path)
    _ok("Rijksregister", len(rr_df), time.time() - t)

    # ── Stap 2: Bisregister ──────────────────────────────────────────────────
    _stap(2, "Bisregister genereren")
    t = time.time()
    bis_df = generate_bisregister(config_path=config_path)
    _ok("Bisregister", len(bis_df), time.time() - t)

    # ── Stap 3: Familiestructuren ────────────────────────────────────────────
    _stap(3, "Familiestructuren genereren (4 generaties)")
    t = time.time()
    families = generate_families(
        config_path=config_path,
        rr_df=rr_df,
        bis_df=bis_df,
    )
    _ok("Families", len(families), time.time() - t)

    # ── Familienamen terugschrijven naar registers ────────────────────────────
    pas_familienamen_aan(families, rr_df, bis_df)

    # ── Stap 4: Opslaan ──────────────────────────────────────────────────────
    _stap(4, "Opslaan naar Generated Data/")
    t = time.time()

    rr_pad  = save_dir / f"{prefix}_rijksregister.json"
    bis_pad = save_dir / f"{prefix}_bisregister.json"
    fam_pad = save_dir / f"{prefix}_families.json"

    rr_df.to_json(rr_pad,   orient="records", force_ascii=False, indent=2)
    bis_df.to_json(bis_pad, orient="records", force_ascii=False, indent=2)
    with open(fam_pad, "w", encoding="utf-8") as f:
        json.dump(families, f, ensure_ascii=False, indent=2, default=str)

    print(f"  → {rr_pad.name}")
    print(f"  → {bis_pad.name}")
    print(f"  → {fam_pad.name}")
    print(f"  Opgeslagen in {time.time() - t:.1f}s")

    # ── Rapport ──────────────────────────────────────────────────────────────
    _rapporteer(rr_df, bis_df, families)


if __name__ == "__main__":
    main()
