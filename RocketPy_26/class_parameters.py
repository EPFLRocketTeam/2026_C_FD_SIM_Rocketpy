"""
Reads simulation / environment parameters from the 'Parameters' sheet of the
Excel input file and populates a `Parameters` dataclass.
Every field has a default value. Section header rows (no numeric or string
value in column B) are automatically skipped.
String fields (version, save_files, write_to_file) are handled separately.
"""
from __future__ import annotations
from dataclasses import dataclass, fields
from pathlib import Path
from openpyxl import load_workbook

SHEET_NAME   = "Parameters "   # note: trailing space in the Excel sheet name
NAME_COLUMN  = "A"
VALUE_COLUMN = "B"
FIRST_DATA_ROW = 2


@dataclass
class Parameters:
    # ENREGISTREMENT
    version:       str   = "TEMPLATE"
    save_files:    bool  = True
    n_points:      int   = 1000
    write_to_file: bool  = False

    # SORTIES SOUHAITÉES (n'a d'effet que si write_to_file=True)
    output_general:         bool = True   # résultats généraux (dans la feuille Excel Simulation)
    output_euler_angles:    bool = False  # euler_angles.png
    output_stability:       bool = False  # stability_margin.png
    output_trajectory:      bool = False  # trajectory.png
    output_velocity:        bool = False  # velocity.png
    output_acceleration:    bool = False  # acceleration.png
    output_thrust_curve:    bool = False  # thrust_curve.png

    # ENVIRONNEMENT
    annee:     int   = 2026
    mois:      int   = 6
    jour:      int   = 2
    heure:     int   = 12
    minute:    int   = 0
    latitude:  float = 39.390150   # EuRoC
    longitude: float = -8.289145   # EuRoC
    elevation: float = 130.0

    # RAIL
    alpha_rail:      float = 6.0
    beta_rail:       float = 6.0
    l_rail:          float = 11.65
    coeff_fr_rail:   float = 0.5
    inclination_rail: float = 84.0
    heading_rail:    float = 144.0


def _try_to_float(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _try_to_bool(value) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        if value.strip().lower() == "true":
            return True
        if value.strip().lower() == "false":
            return False
    return None


def read_parameters(filepath: str | Path, sheet_name: str = SHEET_NAME) -> Parameters:
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    wb = load_workbook(filepath, data_only=True, read_only=True)
    # Try exact match first, then strip-match (handles trailing spaces)
    if sheet_name not in wb.sheetnames:
        stripped = {s.strip(): s for s in wb.sheetnames}
        if sheet_name.strip() in stripped:
            sheet_name = stripped[sheet_name.strip()]
        else:
            raise ValueError(
                f"Sheet {sheet_name!r} not found in {filepath}. "
                f"Available sheets: {wb.sheetnames}"
            )

    ws = wb[sheet_name]
    name_col_idx  = ord(NAME_COLUMN)  - ord("A") + 1
    value_col_idx = ord(VALUE_COLUMN) - ord("A") + 1

    # Field type map for casting
    field_types = {f.name: f.type for f in fields(Parameters)}

    file_values: dict[str, object] = {}
    for row in range(FIRST_DATA_ROW, ws.max_row + 1):
        name = ws.cell(row=row, column=name_col_idx).value
        if not isinstance(name, str):
            continue
        name = name.strip()
        if not name:
            continue

        raw = ws.cell(row=row, column=value_col_idx).value
        if raw is None:
            continue

        # Bool fields
        b = _try_to_bool(raw)
        if b is not None:
            file_values[name] = b
            continue

        # String fields (version)
        if isinstance(raw, str) and name in ("version",):
            file_values[name] = raw.strip()
            continue

        # Numeric fields
        parsed = _try_to_float(raw)
        if parsed is not None:
            file_values[name] = parsed

    valid = {f.name for f in fields(Parameters)}
    unknown = set(file_values) - valid
    if unknown:
        print(f"Warning [Parameters]: champs ignorés (inconnus) : {unknown}")

    # Cast floats to int where needed
    int_fields = {"annee", "mois", "jour", "heure", "minute", "n_points"}
    casted = {}
    for k, v in file_values.items():
        if k not in valid:
            continue
        if k in int_fields and isinstance(v, float):
            casted[k] = int(v)
        else:
            casted[k] = v

    return Parameters(**casted)
