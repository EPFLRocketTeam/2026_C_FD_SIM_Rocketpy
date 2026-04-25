"""
Excel I/O for the RocketPy propellant budget / simulations campaign file.

Target file: 2026_C_SE_PROPELLANT_BUDGET_CDR.xlsx
Target sheet: "Simulations"

Layout:
  Row 2: top-level headers (Simulations inputs / Simulations outputs)
  Row 3: sub-headers (Mass total, Mass remaining, Full, Ramp up, ...)
  Row 4: "Firehorn 1" reference row.
      NOT a simulation to run — it's the historical Firehorn 1 flight data,
      kept here for reference. Whenever a cell in a simulation row is empty,
      we fall back to the corresponding cell in row 4 instead of skipping
      the row.
  Rows 5-52: simulation configs, grouped into 5 campaigns:
      THRUST1  (rows 5-16)
      THRUST2  (rows 17-28)
      IMPULSE1 (rows 29-34)
      IMPULSE2 (rows 35-40)
      ISP      (rows 41-48)
      (rows 49-52 are empty placeholders)
"""

from __future__ import annotations

# `datetime` is used to detect cells that Excel silently auto-converted from
# numbers into dates (e.g. typing "1.5" into a cell with European locale can
# become "1 May"). We need the datetime module to check `isinstance(value, dt.datetime)`.
import datetime as dt

from dataclasses import dataclass

from pathlib import Path

from openpyxl import load_workbook


# ---------- File layout constants ----------
SHEET_NAME = "Simulations"
FIREHORN1_ROW = 4                # Reference row used as fallback for empty cells
FIRST_CONFIG_ROW = 5
LAST_CONFIG_ROW = 52

# Input columns (what we READ to feed the simulator)
COL_CAMPAIGN = "B"               # e.g. "THRUST1" — only set on the first row of each group
COL_CONFIG_ID = "C"              # e.g. "2026_C_PR_B3_CONFIG4"
COL_N2_MASS = "D"                # N2 mass total [kg]
COL_OX_MASS_TOTAL = "E"          # Oxidizer mass total [kg]
COL_OX_MASS_REMAINING = "F"      # Oxidizer mass remaining [kg]
COL_FUEL_MASS_TOTAL = "G"        # Fuel mass total [kg]
COL_FUEL_MASS_REMAINING = "H"    # Fuel mass remaining [kg]
COL_THRUST_FULL = "I"            # Thrust full [N]
COL_TOTAL_IMPULSE = "K"          # Total Impulse [Ns]
COL_RAMP_UP = "L"                # Timing: ramp up [s]
COL_BURN_TIME = "M"              # Timing: burn time [s]
COL_RAMP_DOWN = "N"              # Timing: ramp down [s]
COL_INPUT_DESCRIPTION = "O"

# Output columns (what we WRITE after running the simulator)
COL_APOGEE = "S"                 # Apogee [m]
COL_STATIC_MARGIN = "T"          # Rail exit static margin [c]
COL_RAIL_EXIT_VELOCITY = "U"     # Rail exit velocity [m/s]


# ---------- Data classes ----------
@dataclass
class SimulationInputs:
    """One row of simulation inputs from the Simulations sheet."""
    row: int
    campaign: str | None
    config_id: str
    n2_mass_kg: float
    ox_mass_total_kg: float
    ox_mass_remaining_kg: float
    fuel_mass_total_kg: float
    fuel_mass_remaining_kg: float
    thrust_full_N: float
    total_impulse_Ns: float
    ramp_up_s: float
    burn_time_s: float
    ramp_down_s: float
    description: str | None = None


@dataclass
class SimulationOutputs:
    """Outputs produced by running RocketPy for one config."""
    config_id: str              # used to locate the correct row in the sheet
    apogee_m: float
    rail_exit_static_margin: float
    rail_exit_velocity_ms: float


# ---------- Helpers ----------
def _to_float(value, cell_ref: str = "?") -> float:
    """Coerce a cell value to float, handling common Excel messiness."""
    if value is None:
        raise ValueError(f"Cell {cell_ref} is empty")
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        # Handle European decimal commas, e.g. "5,774" -> 5.774
        return float(value.replace(",", "."))
    if isinstance(value, dt.datetime):
        raise ValueError(
            f"Cell {cell_ref} contains a date ({value}) instead of a number. "
            "Likely an Excel auto-conversion bug (e.g. '1.5' -> May 1). "
            "Fix the cell in Excel by formatting it as a Number."
        )
    raise TypeError(f"Cell {cell_ref} has unexpected type {type(value).__name__}: {value!r}")


def _get_cell(ws, col: str, row: int):
    """Read a cell by column letter and row number."""
    return ws[f"{col}{row}"].value


def _get_with_fallback(ws, col: str, row: int) -> float:
    """Read a numeric cell. If it's empty, fall back to the same column on
    the Firehorn 1 reference row.

    Logs a [fallback] message whenever the substitution happens, so it's
    clear in the output which values came from row 4 vs. the actual row.
    Raises ValueError if BOTH the data row and Firehorn 1 are empty.
    """
    raw = _get_cell(ws, col, row)
    if raw is not None:
        return _to_float(raw, f"{col}{row}")

    # Cell is empty — try the Firehorn 1 fallback.
    fallback_raw = _get_cell(ws, col, FIREHORN1_ROW)
    if fallback_raw is None:
        raise ValueError(
            f"Cell {col}{row} is empty AND the Firehorn 1 fallback "
            f"({col}{FIREHORN1_ROW}) is also empty."
        )
    fallback_value = _to_float(fallback_raw, f"{col}{FIREHORN1_ROW}")
    print(f"  [fallback] row {row}, col {col}: empty -> using Firehorn 1 value {fallback_value}")
    return fallback_value


# ---------- Reading ----------
def read_all_configs(filepath: str | Path) -> list[SimulationInputs]:
    """Read every simulation config from the Simulations sheet.

    Empty cells are filled in from the Firehorn 1 reference row (row 4)
    via _get_with_fallback().
    """
    wb = load_workbook(filepath, data_only=True)
    if SHEET_NAME not in wb.sheetnames:
        raise ValueError(f"Sheet {SHEET_NAME!r} not found. Available: {wb.sheetnames}")
    ws = wb[SHEET_NAME]

    current_campaign: str | None = None
    results: list[SimulationInputs] = []

    for row in range(FIRST_CONFIG_ROW, LAST_CONFIG_ROW + 1):
        config_id = _get_cell(ws, COL_CONFIG_ID, row)
        if config_id is None:
            continue  # truly empty rows still get skipped; only known configs use fallbacks

        # Campaign name only appears on the first row of each group;
        # carry it forward for subsequent rows in the same group.
        campaign_cell = _get_cell(ws, COL_CAMPAIGN, row)
        if campaign_cell is not None:
            current_campaign = str(campaign_cell)

        try:
            sim = SimulationInputs(
                row=row,
                campaign=current_campaign,
                config_id=str(config_id),
                n2_mass_kg=_get_with_fallback(ws, COL_N2_MASS, row),
                ox_mass_total_kg=_get_with_fallback(ws, COL_OX_MASS_TOTAL, row),
                ox_mass_remaining_kg=_get_with_fallback(ws, COL_OX_MASS_REMAINING, row),
                fuel_mass_total_kg=_get_with_fallback(ws, COL_FUEL_MASS_TOTAL, row),
                fuel_mass_remaining_kg=_get_with_fallback(ws, COL_FUEL_MASS_REMAINING, row),
                thrust_full_N=_get_with_fallback(ws, COL_THRUST_FULL, row),
                total_impulse_Ns=_get_with_fallback(ws, COL_TOTAL_IMPULSE, row),
                ramp_up_s=_get_with_fallback(ws, COL_RAMP_UP, row),
                burn_time_s=_get_with_fallback(ws, COL_BURN_TIME, row),
                ramp_down_s=_get_with_fallback(ws, COL_RAMP_DOWN, row),
                description=_get_cell(ws, COL_INPUT_DESCRIPTION, row),
            )
        except (ValueError, TypeError) as e:
            # Row has missing or malformed data that even the fallback couldn't
            # rescue; skip it with a warning instead of crashing the whole read.
            print(f"  [skip] row {row} ({config_id}): {e}")
            continue

        results.append(sim)

    return results


def read_config_by_id(filepath: str | Path, config_id: str) -> SimulationInputs:
    """Read a single config by its ID (e.g. '2026_C_PR_B3_CONFIG4')."""
    for cfg in read_all_configs(filepath):
        if cfg.config_id == config_id:
            return cfg
    raise KeyError(f"Config {config_id!r} not found in {filepath}")

# ---------- Quick self-test ----------
if __name__ == "__main__":
    import sys

    # Default filename matches the current CDR version of the file.
    path = sys.argv[1] if len(sys.argv) > 1 else "2026_C_SE_PROPELLANT_BUDGET_CDR.xlsx"

    print(f"=== Reading all configs from {path} ===")
    configs = read_all_configs(path)
    print(f"\nGot {len(configs)} configs.\n")
    for cfg in configs:
        campaign = cfg.campaign or "?"
        print(f"  row {cfg.row:2d} | {campaign:8s} | {cfg.config_id:30s} "
              f"| thrust={cfg.thrust_full_N:5.0f}N | impulse={cfg.total_impulse_Ns:6.0f}Ns "
              f"| burn={cfg.burn_time_s:.2f}s")

    # Example of what writing back would look like.
    # Uncomment to actually write (modifies the file!):
    # example_outputs = [
    #     SimulationOutputs(
    #         config_id="2025_C_PR_B3_CONFIG4",
    #         apogee_m=9999.0,
    #         rail_exit_static_margin=8.888,
    #         rail_exit_velocity_ms=77.7,
    #     ),
    # ]
    # write_outputs(path, example_outputs)
    # print(f"\nWrote {len(example_outputs)} outputs back to {path}")