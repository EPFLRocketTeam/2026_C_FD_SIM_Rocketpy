from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from openpyxl import load_workbook


SHEET_NAME = "Simulations"
HEADER_ROW = 2
CONFIG_ID_COLUMN = "C"
FIRST_DATA_ROW = 3


# Map of (Excel header text) -> (function that extracts the value from a Flight object).
# Each extractor is a lambda that takes (flight, ipt) and returns a number, or None
# if that quantity isn't computable from this flight.
OUTPUT_EXTRACTORS = {
    # Always-on
    "Static margin rail exit [c]":   lambda fl, ipt: float(fl.static_margin(fl.out_of_rail_time)),
    "Rail exit velocity [m/s]":      lambda fl, ipt: float(fl.out_of_rail_velocity),
    "Apogee AGL [m]":                lambda fl, ipt: float(fl.altitude(fl.apogee_time)),

    # Trajectory
    "Apogee ASL [m]":                lambda fl, ipt: float(fl.apogee),
    "Max velocity [m/s]":            lambda fl, ipt: float(fl.max_speed),
    "Max acceleration [m/s^2]":      lambda fl, ipt: float(fl.max_acceleration),
    "Max Mach [-]":                  lambda fl, ipt: float(fl.max_mach_number),
    "Time to apogee [s]":            lambda fl, ipt: float(fl.apogee_time),
    "Total flight time [s]":         lambda fl, ipt: float(fl.t_final),

    # Stability
    "Static margin liftoff [c]":     lambda fl, ipt: float(fl.static_margin(0)),
    "Min static margin [c]":         lambda fl, ipt: _min_static_margin(fl),

    # Loads
    "Max dynamic pressure [Pa]":     lambda fl, ipt: float(fl.max_dynamic_pressure),
    "Max thrust load [N]":           lambda fl, ipt: _safe_attr(fl, "max_thrust"),
}


def _min_static_margin(flight, n_samples: int = 200) -> float:
    """Sample static margin over the flight to find its minimum."""
    t_samples = np.linspace(0, flight.t_final, n_samples)
    margins = [float(flight.static_margin(t)) for t in t_samples]
    return float(min(margins))


def _safe_attr(obj, name: str):
    """Return obj.name if it exists and is callable->number or a number, else None."""
    if not hasattr(obj, name):
        return None
    val = getattr(obj, name)
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _build_header_to_column(ws) -> dict[str, str]:
    """Read the header row and build {header_text: column_letter}."""
    return {
        cell.value: cell.column_letter
        for cell in ws[HEADER_ROW]
        if cell.value is not None
    }


def _find_row_by_config_id(ws, config_id: str) -> int | None:
    """Return the 1-indexed row whose config_id column matches, or None."""
    for r in range(FIRST_DATA_ROW, ws.max_row + 1):
        if ws[f"{CONFIG_ID_COLUMN}{r}"].value == config_id:
            return r
    return None


def write_flight_outputs(
    filepath: str | Path,
    config_id: str,
    flight,
    ipt: Any = None,
    overwrite_existing: bool = True,
) -> dict[str, Any]:
    """Write all extractable outputs from `flight` into the row matching `config_id`.

    Args:
        filepath: path to the Excel workbook to update (modified in place).
        config_id: scenario identifier — must match a value in column C.
        flight: a RocketPy Flight object that has already been run.
        ipt: optional Input dataclass — passed to extractors that might need it.
        overwrite_existing: if True (default), overwrite cells that already have values.
                            if False, only write to currently-empty cells.

    Returns:
        A dict {header_text: written_value} of everything that got written,
        useful for sanity-check printing in the notebook.

    Raises:
        ValueError: if the sheet doesn't exist, or no row matches config_id.
    """
    wb = load_workbook(filepath)
    if SHEET_NAME not in wb.sheetnames:
        raise ValueError(f"Sheet {SHEET_NAME!r} not found. Available: {wb.sheetnames}")
    ws = wb[SHEET_NAME]

    row = _find_row_by_config_id(ws, config_id)
    if row is None:
        raise ValueError(
            f"config_id {config_id!r} not found in column {CONFIG_ID_COLUMN} "
            f"of sheet {SHEET_NAME!r}. "
            f"Make sure the spreadsheet has a row for this scenario."
        )

    headers = _build_header_to_column(ws)

    written: dict[str, Any] = {}
    skipped_no_header: list[str] = []

    for header_text, extractor in OUTPUT_EXTRACTORS.items():
        col = headers.get(header_text)
        if col is None:
            skipped_no_header.append(header_text)
            continue

        # Try to compute the value. If the extractor fails, log and skip
        # rather than crashing — one missing attribute shouldn't kill the write.
        try:
            value = extractor(flight, ipt)
        except Exception as e:
            print(f"  [skip] {header_text}: extractor raised {type(e).__name__}: {e}")
            continue

        if value is None:
            continue

        target_cell = f"{col}{row}"
        existing = ws[target_cell].value
        if existing is not None and not overwrite_existing:
            continue

        ws[target_cell] = value
        written[header_text] = value

    wb.save(filepath)

    if skipped_no_header:
        print(f"  [info] {len(skipped_no_header)} output(s) had no matching header in the sheet "
              f"and were skipped: {skipped_no_header}")
    print(f"  Wrote {len(written)} outputs to row {row} ({config_id})")
    return written