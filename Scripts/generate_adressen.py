"""
generate_adressen.py
Gedeelde module voor het genereren van fictieve Belgische woonadressen.
Wordt gebruikt door generate_register.py en generate_families.py.
"""
from __future__ import annotations

import random

# NIS-code → eerste/hoofd-postcode van de gemeente
_NIS_POSTCODE: dict[str, int] = {
    "11002": 2000,  # Antwerpen
    "44021": 9000,  # Gent
    "21004": 1000,  # Brussel
    "62063": 4000,  # Luik
    "31005": 8000,  # Brugge
    "52011": 6000,  # Charleroi
    "92094": 5000,  # Namen
    "24062": 3000,  # Leuven
    "41002": 9300,  # Aalst
    "71022": 3500,  # Hasselt
    "34022": 8500,  # Kortrijk
    "12025": 2800,  # Mechelen
    "55022": 7100,  # La Louvière
    "21015": 1030,  # Schaarbeek
    "21001": 1070,  # Anderlecht
    "46021": 9100,  # Sint-Niklaas
    "53053": 7000,  # Bergen
    "36015": 8800,  # Roeselare
    "13040": 2300,  # Turnhout
    "71016": 3600,  # Genk
    "62096": 4100,  # Seraing
    "21011": 1080,  # Molenbeek / Sint-Jans-Molenbeek
    "21009": 1050,  # Ixelles
    "42006": 9200,  # Dendermonde
    "33011": 8900,  # Ieper
    "73083": 3700,  # Tongeren
    "81001": 6700,  # Arlon
    "63023": 4700,  # Eupen
    "71053": 3800,  # Sint-Truiden
}

_BUS_NUMMERS = ["A", "B", "C", "1", "2", "3", "10", "11", "21", "101", "201"]


def genereer_adres(
    rng: random.Random,
    config: dict,
    gemeente: dict | None = None,
) -> dict:
    """
    Genereer een fictief Belgisch woonadres.

    Parameters
    ----------
    rng      : seeded Random instance
    config   : geladen config.json
    gemeente : optioneel dict {naam, nis, provincie, gewest, inwoners}
               als None → willekeurig gekozen naar inwoners-gewicht

    Returns
    -------
    dict met adres_straat, adres_nr, adres_bus, adres_postcode,
         adres_gemeente, adres_provincie, adres_gewest
    """
    if gemeente is None:
        gemeenten = config["locations"]["belgische_gemeenten"]
        gemeente  = rng.choices(
            gemeenten, weights=[g["inwoners"] for g in gemeenten]
        )[0]

    prefix = rng.choice(config["adressen"]["straatnamen_prefix"])
    stype  = rng.choice(config["adressen"]["straatnaamtypes"])
    straat = prefix + stype.lower()
    nr     = rng.randint(1, config["adressen"]["huisnummer_max"])

    bus = None
    if rng.random() < config["adressen"]["bus_kans"]:
        bus = rng.choice(_BUS_NUMMERS)

    postcode = _NIS_POSTCODE.get(str(gemeente.get("nis", "")), 9999)

    return {
        "adres_straat":    straat,
        "adres_nr":        nr,
        "adres_bus":       bus,
        "adres_postcode":  postcode,
        "adres_gemeente":  gemeente["naam"],
        "adres_provincie": gemeente["provincie"],
        "adres_gewest":    gemeente["gewest"],
    }
