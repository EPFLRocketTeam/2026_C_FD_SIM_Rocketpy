"""
Excel I/O for the RocketPy propellant budget / simulations campaign file.

Target file: 2026_C_SE_PROPELLANT_BUDGET_CDR.xlsx
Target sheet: "Simulations"

Layout:
  Row 2: top-level headers (Simulations inputs / Simulations outputs)
  Row 3: sub-headers (Mass total, Mass remaining, Full, Derated, Ramp up, ...)
  Row 4: "Firehorn 1" reference row (NOT a simulation to run)
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

# `dataclass` is a decorator that turns a plain class into a typed data
# container — it auto-generates the __init__, __repr__, and equality methods
# so we don't have to write them by hand.
from dataclasses import dataclass

# `Path` is Python's modern way to represent a filesystem path. We only use
# it in type hints (`str | Path`) so callers can pass either a plain string
# or a Path object — both work.
from pathlib import Path

from openpyxl import load_workbook


# ---------- File layout constants ----------
SHEET_NAME = "Simulations"
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
COL_THRUST_DERATED = "J"         # Thrust derated [N] — may be "ND" (Not Derated) for engines that run at constant thrust
COL_TOTAL_IMPULSE = "K"          # Total Impulse [Ns]
COL_RAMP_UP = "L"                # Timing: ramp up [s]
COL_BURN_TIME = "M"              # Timing: burn time [s]
COL_RAMP_DOWN = "N"              # Timing: ramp down [s]
COL_INPUT_DESCRIPTION = "O"

# Output columns (what we WRITE after running the simulator)
# Apogee = maximum altitude the rocket reaches before falling back down.
# Static margin = rocket stability metric at rail exit, in calibers.
# Rail exit velocity = speed when the rocket clears the launch rail.
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
    # Derated thrust can be the string "ND" (Not Derated) — for engines that
    # don't step thrust down partway through the burn. Hence the float-or-str type.
    thrust_derated_N: float | str
    total_impulse_Ns: float
    ramp_up_s: float
    burn_time_s: float
    ramp_down_s: float
    description: str | None = None

    def is_placeholder(self) -> bool:
        """Return True if this row looks like an unfilled stub config.

        Some rows in the spreadsheet have placeholder values (thrust = 1 N,
        burn time = 0.3 s) — they're rows the engineers haven't filled in
        with real data yet. We skip them when running simulations because
        they'd either crash the sim or produce meaningless results.

        This method is defined on the dataclass so we can write
        `sim.is_placeholder()` in the filter logic below — more readable
        than a standalone function.
        """
        return self.thrust_full_N == 1 and self.burn_time_s <= 0.3


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

# ---------- Reading ----------
def read_all_configs(filepath: str | Path, skip_placeholders: bool = True) -> list[SimulationInputs]:
    """Read every simulation config from the Simulations sheet.

    Parameters
    ----------
    filepath : path to the propellant budget xlsx file
    skip_placeholders : if True, omit rows that look like stub configs
                        (thrust=1, burn_time<=0.3). Default: True.
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
            continue  # skip empty rows

        # Campaign name only appears on the first row of each group;
        # carry it forward for subsequent rows in the same group.
        campaign_cell = _get_cell(ws, COL_CAMPAIGN, row)
        if campaign_cell is not None:
            current_campaign = str(campaign_cell)

        try:
            # Derated thrust can be the string "ND" for non-derated engines.
            derated_raw = _get_cell(ws, COL_THRUST_DERATED, row)
            derated: float | str
            if isinstance(derated_raw, str):
                derated = derated_raw
            else:
                derated = _to_float(derated_raw, f"{COL_THRUST_DERATED}{row}")

            sim = SimulationInputs(
                row=row,
                campaign=current_campaign,
                config_id=str(config_id),
                n2_mass_kg=_to_float(_get_cell(ws, COL_N2_MASS, row), f"{COL_N2_MASS}{row}"),
                ox_mass_total_kg=_to_float(_get_cell(ws, COL_OX_MASS_TOTAL, row), f"{COL_OX_MASS_TOTAL}{row}"),
                ox_mass_remaining_kg=_to_float(_get_cell(ws, COL_OX_MASS_REMAINING, row), f"{COL_OX_MASS_REMAINING}{row}"),
                fuel_mass_total_kg=_to_float(_get_cell(ws, COL_FUEL_MASS_TOTAL, row), f"{COL_FUEL_MASS_TOTAL}{row}"),
                fuel_mass_remaining_kg=_to_float(_get_cell(ws, COL_FUEL_MASS_REMAINING, row), f"{COL_FUEL_MASS_REMAINING}{row}"),
                thrust_full_N=_to_float(_get_cell(ws, COL_THRUST_FULL, row), f"{COL_THRUST_FULL}{row}"),
                thrust_derated_N=derated,
                total_impulse_Ns=_to_float(_get_cell(ws, COL_TOTAL_IMPULSE, row), f"{COL_TOTAL_IMPULSE}{row}"),
                ramp_up_s=_to_float(_get_cell(ws, COL_RAMP_UP, row), f"{COL_RAMP_UP}{row}"),
                burn_time_s=_to_float(_get_cell(ws, COL_BURN_TIME, row), f"{COL_BURN_TIME}{row}"),
                ramp_down_s=_to_float(_get_cell(ws, COL_RAMP_DOWN, row), f"{COL_RAMP_DOWN}{row}"),
                description=_get_cell(ws, COL_INPUT_DESCRIPTION, row),
            )
        except (ValueError, TypeError) as e:
            # Row has missing or malformed data; skip it with a warning
            # instead of crashing the whole read.
            print(f"  [skip] row {row} ({config_id}): {e}")
            continue

        if skip_placeholders and sim.is_placeholder():
            continue

        results.append(sim)

    return results


def read_config_by_id(filepath: str | Path, config_id: str) -> SimulationInputs:
    """Read a single config by its ID (e.g. '2026_C_PR_B3_CONFIG4')."""
    for cfg in read_all_configs(filepath, skip_placeholders=False):
        if cfg.config_id == config_id:
            return cfg
    raise KeyError(f"Config {config_id!r} not found in {filepath}")


# ---------- Writing ----------
def write_outputs(
    filepath: str | Path,
    outputs: list[SimulationOutputs],
) -> None:
    """Write simulation outputs to the correct rows, matched by config_id."""
    # No data_only here — we want to preserve formulas in cells we don't touch.
    wb = load_workbook(filepath)
    if SHEET_NAME not in wb.sheetnames:
        raise ValueError(f"Sheet {SHEET_NAME!r} not found. Available: {wb.sheetnames}")
    ws = wb[SHEET_NAME]

    # Build a lookup from config_id to row number by scanning the sheet.
    # Matching outputs to rows by config_id (not hardcoded row numbers)
    # keeps the writer robust even if rows get reordered later.
    id_to_row: dict[str, int] = {}
    for row in range(FIRST_CONFIG_ROW, LAST_CONFIG_ROW + 1):
        cid = _get_cell(ws, COL_CONFIG_ID, row)
        if cid is not None:
            id_to_row[str(cid)] = row

    missing = [o.config_id for o in outputs if o.config_id not in id_to_row]
    if missing:
        raise ValueError(f"These config_ids were not found in the sheet: {missing}")

    for out in outputs:
        row = id_to_row[out.config_id]
        ws[f"{COL_APOGEE}{row}"] = out.apogee_m
        ws[f"{COL_STATIC_MARGIN}{row}"] = out.rail_exit_static_margin
        ws[f"{COL_RAIL_EXIT_VELOCITY}{row}"] = out.rail_exit_velocity_ms

    wb.save(filepath)

# ---------- Quick self-test ----------
if __name__ == "__main__":
    import sys

    # Default filename matches the current CDR version of the file.
    path = sys.argv[1] if len(sys.argv) > 1 else "2026_C_SE_PROPELLANT_BUDGET_CDR.xlsx"

    print(f"=== Reading all real configs from {path} ===")
    configs = read_all_configs(path, skip_placeholders=True)
    print(f"Got {len(configs)} real configs (placeholders skipped).\n")
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