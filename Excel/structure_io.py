"""
Reads structural / geometric rocket parameters from an Excel file and
populates a `Structure` dataclass. Every field has a default value matching
the previously-hardcoded number in the notebook.

The notebook then uses struct.<field> wherever it previously had a hardcoded
number, e.g.:
    pressure_tank_geometry = CylindricalTank(
        struct.pressure_tank_radius, struct.pressure_tank_height,
        spherical_caps=False
    )
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from pathlib import Path

from openpyxl import load_workbook


SHEET_NAME = "Structure"
NAME_COLUMN = "A"
VALUE_COLUMN = "B"
FIRST_DATA_ROW = 2 #rows above are just aesthetic 


@dataclass
class Structure:
    """All structural / geometric rocket parameters that the notebook reads.

    Defaults match the values previously hardcoded in the notebook.
    Add a field here AND in the spreadsheet to expose a new parameter.
    """
    # Tank (lox + ethanol use these — already on ipt, kept here for completeness
    # but commented out since they live in ipt.r_int / ipt.h_cyl. If you want to
    # move them here too, just uncomment.)
    # r_int: float = 0.115
    # h_cyl: float = 0.3851008075

    # Pressure tank (COPV)
    pressure_tank_radius: float = 0.0885   # = 0.177 / 2
    pressure_tank_height: float = 0.570

    # Engine
    nozzle_radius: float = 0.04946         # = 0.09892 / 2

    # Tank positions along the rocket axis [m from rocket base]
    lox_tank_position: float = 1.3375      # = 0.41755 + 0.756 + 0.388/2
    copv_1_position: float = 2.17655       # = 0.41755 + 0.756 + 0.388 + 0.900 - 0.570/2
    ethanol_tank_position: float = 2.66155 # = 0.41755 + 0.756 + 0.388 + 0.900 + 0.388/2
    copv_2_position: float = 3.50055       # = 0.41755 + 0.756 + 0.388 + 0.900 + 0.388 + 0.900 - 0.570/2

    # Rocket body
    rocket_radius: float = 0.1215          # = 0.243 / 2
    center_of_mass_without_motor: float = 2.59

    # Aerodynamics
    drag_coefficient: float = 0.380        # used for both power_off_drag and power_on_drag


def _try_to_float(value) -> float | None:
    """Return value as a float, or None if it can't be parsed.

    Handles: None, empty strings, strings like 'TBD', booleans, etc.
    Numbers come back as themselves.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        # bools pass isinstance(int) checks in Python, but we don't want them
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def read_structure(filepath: str | Path) -> Structure:
    """Read structural parameters from an Excel file.

    Looks at the `Structure` sheet. Reads (Name, Value) pairs starting at
    row FIRST_DATA_ROW. Any row whose Name matches a field of the Structure
    dataclass uses that row's Value. Unknown names are ignored.

    Missing files or sheets raise an error (you wanted to know if something
    went really wrong). Per-field problems (empty cells, unparseable strings)
    silently fall back to defaults.

    Args:
        filepath: path to the structure Excel file.

    Returns:
        A Structure instance with all fields populated (either from the file
        or from the dataclass defaults).
    """
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"Structure file not found: {filepath}")

    wb = load_workbook(filepath, data_only=True)
    if SHEET_NAME not in wb.sheetnames:
        raise ValueError(
            f"Sheet {SHEET_NAME!r} not found in {filepath}. "
            f"Available sheets: {wb.sheetnames}"
        )
    ws = wb[SHEET_NAME]

    # Build {name: value} from the file, skipping rows we can't make sense of.
    name_col_idx = ord(NAME_COLUMN) - ord("A") + 1
    value_col_idx = ord(VALUE_COLUMN) - ord("A") + 1
    file_values: dict[str, float] = {}
    for row in range(FIRST_DATA_ROW, ws.max_row + 1):
        name = ws.cell(row=row, column=name_col_idx).value
        if not isinstance(name, str):
            continue
        name = name.strip()
        if not name:
            continue
        raw_value = ws.cell(row=row, column=value_col_idx).value
        parsed = _try_to_float(raw_value)
        if parsed is not None:
            file_values[name] = parsed

    # Build a Structure, overriding defaults with anything we found in the file.
    valid_names = {f.name for f in fields(Structure)}
    overrides = {k: v for k, v in file_values.items() if k in valid_names}
    return Structure(**overrides)

