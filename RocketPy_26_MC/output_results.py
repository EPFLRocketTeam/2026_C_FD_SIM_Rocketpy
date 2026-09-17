"""
output_results.py

Écrit les résultats de vol dans des fichiers CSV séparés, un par catégorie
(Structure, Propellant, Parameters, Simulation), pour reproduire la logique
des 4 feuilles de l'Excel d'origine tout en restant en CSV.
"""
from __future__ import annotations

import csv
import dataclasses
import math
from pathlib import Path
from typing import Any

from output_into_excel import OUTPUT_STRUCTURE, EXTRACTORS


def _round_value(value, sig: int = 4):
    """Arrondit à un nombre raisonnable de chiffres significatifs, pour
    éviter les valeurs à 15 décimales dans le CSV."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return value
    if value == 0 or not math.isfinite(value):
        return value
    digits = sig - int(math.floor(math.log10(abs(value)))) - 1
    return round(value, max(digits, 0))


def write_dataclass_csv(obj: Any, sheet_name: str, directory: str | Path) -> Path:
    """Écrit les champs d'une dataclass (Structure, Propellant ou Parameters)
    dans '{sheet_name}.csv', au format Parameter,Value — l'équivalent d'une
    feuille Excel dédiée à cette catégorie."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    filepath = directory / f"{sheet_name}.csv"

    with open(filepath, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Parameter", "Value"])
        for field in dataclasses.fields(obj):
            writer.writerow([field.name, _round_value(getattr(obj, field.name))])

    return filepath


def write_flight_outputs_csv(
    flight: Any,
    version: str,
    directory: str | Path = ".",
    dry_mass: float | None = None,
    wet_mass: float | None = None,
    nominal_total_impulse: float | None = None,
) -> Path:
    """Écrit les résultats du vol dans 'Simulation.csv' — l'équivalent de la
    feuille 'Simulation' de l'Excel d'origine. Inclut dry_mass/wet_mass en
    tête si fournis. Si nominal_total_impulse est fourni, il remplace la
    valeur 'Total impulse' calculée par RocketPy (qui exclut la phase
    hold-down) par l'impulsion nominale demandée (qui l'inclut)."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    filepath = directory / "Simulation.csv"

    rows: list[list[str]] = []

    if dry_mass is not None or wet_mass is not None:
        rows.append(["MASS", ""])
        if dry_mass is not None:
            rows.append(["Dry mass [kg]", _round_value(dry_mass)])
        if wet_mass is not None:
            rows.append(["Wet mass (initial) [kg]", _round_value(wet_mass)])

    first_section = not rows
    for label, key in OUTPUT_STRUCTURE:
        if key == "TITRE":
            if not first_section:
                rows.append(["", ""])  # ligne vide entre les sections
            rows.append([label.upper(), ""])
            first_section = False
            continue

        if key == "total_impulse" and nominal_total_impulse is not None:
            rows.append([label, _round_value(nominal_total_impulse)])
            continue

        extractor = EXTRACTORS.get(key)
        try:
            value = extractor(flight)
        except Exception:
            continue
        if value is None:
            continue

        rows.append([label, _round_value(value)])

    with open(filepath, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Parameter", "Value"])
        writer.writerows(rows)

    print(f"CSV results file written: {filepath}")
    return filepath


def write_all_outputs(structure, propellant, parameters, flight, version: str, directory: str | Path = ".") -> dict[str, Path]:
    """Écrit les 4 fichiers CSV (Structure, Propellant, Parameters, Simulation),
    reproduisant les 4 feuilles de l'Excel d'origine. Retourne un dict des
    chemins créés."""
    paths = {
        "structure": write_dataclass_csv(structure, "Structure", directory),
        "propellant": write_dataclass_csv(propellant, "Propellant", directory),
        "parameters": write_dataclass_csv(parameters, "Parameters", directory),
        "simulation": write_flight_outputs_csv(flight, version, directory),
    }
    return paths
