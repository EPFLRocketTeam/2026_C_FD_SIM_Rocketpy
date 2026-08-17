"""
Reads structural / geometric rocket parameters from the 'Structure' sheet
of the Excel input file and populates a `Structure` dataclass.
Every field has a default value. Rows with section headers (no numeric value
in column B) are automatically skipped.
"""
from __future__ import annotations
from dataclasses import dataclass, fields
from pathlib import Path
from openpyxl import load_workbook

SHEET_NAME   = "Structure"
NAME_COLUMN  = "A"
VALUE_COLUMN = "B"
FIRST_DATA_ROW = 2


@dataclass
class Structure:
    # ROCKET
    mode:  int = 0  # Mode 0 : mode normal où on utilise toute les valeurs insérées; Mode 1: mode où on insère une masse et un CoM mesuré et les baies servent pour les masses additionelles
    l_center_of_mass: float = 266
    m_dry_measured: float = 84500
    r_rocket:     float = 0.1215
    drag_coeff_rocket: float = 0.38

    # BOAT TAIL
    top_r_bt:    float = 0.1215
    bottom_r_bt: float = 0.070
    l_bt:        float = 0.41755
    m_bt:        float = 1.0
    r_nozzle:    float = 0.04946

    # ENGINE BAY
    l_ebay: float = 0.756
    m_ebay: float = 26.476

    # LOX BAY
    pos_lox: float = 1.393
    l_lox: float = 0.388
    m_lox: float = 8.387

    # AEROCOVER
    pos_aerocover: float = 0.55
    m_aerocover:   float = 2.41
    l_aerocover:   float = 1.6558
    r_aerocover:   float = 0.03

    # PBAY 1
    pos_copv_mbay: float = 2.22531
    l_pbay1: float = 0.9
    m_pbay1: float = 11.049

    # ETH BAY
    pos_eth: float = 2.998
    l_eth: float = 0.388
    m_eth: float = 8.387

    # PBAY 2
    pos_copv_pbay: float = 3.64731
    l_pbay2: float = 0.9
    m_pbay2: float = 11.03

    # AV BAY
    l_avbay: float = 0.35
    m_avbay: float = 9.232

    # RE BAY
    l_rebay:  float = 0.715
    m_rebay:  float = 11.044
    drag_coeff_para_reefed:   float = 1.6
    drag_coeff_para_unreefed: float = 14.06
    trig_alt_para: float = 400.0

    # NOSE CONE
    l_nosecone: float = 1.003
    m_nosecone: float = 5.838

    # TANK (LOX et Ethanol partagent cette même géométrie)
    r_int: float = 0.115
    tank_spherical_caps: bool = False
    tank_volume: float = 0.016  # [m^3] volume interne total voulu
    h_cap: float = 0.05

    # COPV
    r_int_copv: float = 0.0858
    copv_spherical_caps: bool = False
    copv_volume:     float = 0.009

    # FINS
    n_fins:       float = 4.0
    env_fins:     float = 0.3
    rc_fins:      float = 0.671
    tc_fins:      float = 0.161
    pos_fins:     float = 1.1315
    cangle_fins:  float = 0.0
    sweep_l_fins: float = 0.539
    m_fins: float = 2.418786

    # RAIL BUTTON
    pos_sup_rb: float = 0.46280
    pos_inf_rb: float = 0.46279


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


def read_structure(filepath: str | Path, sheet_name: str = SHEET_NAME) -> Structure:
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    wb = load_workbook(filepath, data_only=True, read_only=True)
    if sheet_name not in wb.sheetnames:
        raise ValueError(
            f"Sheet {sheet_name!r} not found in {filepath}. "
            f"Available sheets: {wb.sheetnames}"
        )

    ws = wb[sheet_name]
    name_col_idx  = ord(NAME_COLUMN)  - ord("A") + 1
    value_col_idx = ord(VALUE_COLUMN) - ord("A") + 1

    bool_fields = {"tank_spherical_caps", "copv_spherical_caps"}

    file_values: dict[str, float | bool] = {}
    for row in range(FIRST_DATA_ROW, ws.max_row + 1):
        name = ws.cell(row=row, column=name_col_idx).value
        if not isinstance(name, str):
            continue
        name = name.strip()
        if not name:
            continue
        raw = ws.cell(row=row, column=value_col_idx).value

        if name in bool_fields:
            parsed_bool = _try_to_bool(raw)
            if parsed_bool is not None:
                file_values[name] = parsed_bool
            continue

        parsed = _try_to_float(raw)
        if parsed is not None:
            file_values[name] = parsed

    valid = {f.name for f in fields(Structure)}
    unknown = set(file_values) - valid
    if unknown:
        print(f"Warning [Structure]: champs ignorés (inconnus) : {unknown}")

    return Structure(**{k: v for k, v in file_values.items() if k in valid})
