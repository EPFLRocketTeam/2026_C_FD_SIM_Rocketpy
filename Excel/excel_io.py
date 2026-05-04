from __future__ import annotations
from dataclasses import dataclass, fields
import numpy as np
from typing import Tuple
import pandas as pd

@dataclass(frozen=True)
class _BlockSpec:
    sheet: str
    cols: str                            # Excel column range, e.g. "B:N"
    first_data_row: int                  # 1-indexed Excel row of Firehorn 1 (row 0 of the DataFrame)
    aux_rows: tuple[int, ...] = ()       # 1-indexed Excel rows to drop between Firehorn 1 and the first sim row

# Layout reference (input workbook):
#   Config:  R2 = headers, R3 = Firehorn 1, R4..R49 = CONFIG1..CONFIG46 in column C
#   Budget:  each block has pretty headers / sub-headers / Firehorn 1 / aux row / sim rows
# We read positionally — column letters are translated to integer offsets within `cols`.
DEFAULT_BLOCKS: dict[str, _BlockSpec] = {
    "cfg":        _BlockSpec(sheet="Config", cols="B:N", first_data_row=3),
    "timings":    _BlockSpec(sheet="Budget", cols="B:J", first_data_row=4,   aux_rows=(5,)),
    "pressurant": _BlockSpec(sheet="Budget", cols="B:G", first_data_row=57,  aux_rows=(58,)),
    "oxidizer":   _BlockSpec(sheet="Budget", cols="B:V", first_data_row=110, aux_rows=(111,)),
    "fuel":       _BlockSpec(sheet="Budget", cols="B:V", first_data_row=163, aux_rows=(164,)),
}

# Column C of every block holds the per-row config_id (e.g. "2026_C_PR_B3_CONFIG1").
_CONFIG_ID_COL = "C"

def _col_to_num(letter: str) -> int:
    """'A' -> 1, 'B' -> 2, ..., 'Z' -> 26, 'AA' -> 27, ..."""
    n = 0
    for c in letter.upper():
        n = n * 26 + ord(c) - ord('A') + 1
    return n

def _offset(letter: str, cols: str) -> int:
    """0-indexed position of `letter` within an Excel range like 'B:N'."""
    start = cols.split(":")[0]
    return _col_to_num(letter) - _col_to_num(start)

def _read_block(file: str, spec: _BlockSpec, nsims: int) -> pd.DataFrame:
    """Read one rectangular table from the workbook (no header parsing — positional)."""
    skiprows = list(range(spec.first_data_row - 1)) + [r - 1 for r in spec.aux_rows]
    return pd.read_excel(
        file,
        spec.sheet,
        header=None,
        usecols=spec.cols,
        skiprows=skiprows,
        nrows=nsims,
    )

def dfs_from_excel(
    file: str,
    nsims: int = 44,
    blocks: dict[str, _BlockSpec] = DEFAULT_BLOCKS,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Read the 5 simulation tables (config, timings, pressurant, ox, fuel)."""
    return (
        _read_block(file, blocks["cfg"], nsims),
        _read_block(file, blocks["timings"], nsims),
        _read_block(file, blocks["pressurant"], nsims),
        _read_block(file, blocks["oxidizer"], nsims),
        _read_block(file, blocks["fuel"], nsims),
    )

# --- HELPERS ---
def _get_or_default(row: pd.Series | None, idx: int, default: float) -> float:
    """Return row.iloc[idx], falling back to `default` if row is None or value is NaN."""
    if row is None:
        return default
    val = row.iloc[idx]
    return default if pd.isna(val) else val

# --- INPUT DATA CLASS --- 
@dataclass
class Input:
    # General
    Version:str
    savefiles:bool
    N_points:int                            # Number of data points for the curves
    run_environment:bool
    write_to_file:bool
    out_filename:str

    # Propellant tanks geometry             # [m], height of the tank cylindrical part
    r_int:float                             # [m], tank diameter
    h_cyl:float                             # [m], height of the tank cylindrical part
    h_cap:float                             # [m], height of the tank bulkhead ellipse

    # Hold-down
    ## Geometry
    alpha:float                             # [°], angle between launch vehicle (launch rail) and gravity vector
    beta:float                              # [°], angle between launch vehicle axis and hold down cable axis
    l_rail:float                            # [m], launch rail length

    ## other
    g:float                                 # [m/s^2], gravity
    F_HD_break:float                        # [N], force at which the hold-down pin breaks (0 : no hold-down)
    mu:float                                # [-], friction coefficient between the rail and rail-button
    m_dry:float                             # [kg], launch vehicle dry mass (weighted 84.4 w. 3U)
    m_additions:float                       # [kg] additions of new mass components since rocket weighting

    # Propellant Masses
    OF_ratio:float                          # [-]
    ISP:float                               # [s]
    Thrust:float                            # [N]
    Total_impulse:float                     # [Ns] Modify this value (from: 36250 config 6 in https://docs.google.com/spreadsheets/d/1_r804lrg8Qi8M8p9dzCOJfm_6ZMJX5gqe4yg1-POdDs/edit?gid=1764341437#gid=1764341437)
    fraction_film_cooling:float             # [-]
    mass_flow_rate:float                    # [kg/s]
    mass_flow_rate_ethanol:float            # [kg/s]
    mass_flow_rate_ethanol_ignition:float   # [kg/s]
    mass_flow_rate_film_cooling:float       # [kg/s]
    mass_flow_rate_ethanol_burn:float       # [kg/s]
    mass_flow_rate_lox_boil_off:float       # [kg/s]
    mass_flow_rate_lox_ignition:float       # [kg/s]
    mass_flow_rate_lox_prechill:float       # [kg/s]
    mass_flow_rate_lox_burn:float           # [kg/s
    burn_time:float                         # [s]
    propellant_mass:float                   # [kg]
    hold_time:float                         # [s]
    prechill_time:float                     # [s]
    ignition_delay:float                    # [s]
    ramp_up_time:float                      # [s]
    cutoff_time:float                       # [s]
    ramp_down_time:float                    # [s]

    ## Fuel (ethanol)
    m_fuel_delay:float                      # [kg]
    m_fuel_cutoff:float                     # [kg]
    m_fuel_burn:float                       # [kg], fuel mass corresponding to free volume
    m_fuel_end:float                        # [kg], fixed volume (we add m_fuel_cutoff since it is in the tank during the flight and technically used at the end of the burn without producing thust, we accept the extra mass for recovery phase)
    m_fuel_total:float                      # [kg], total mass in tanks
    rho_fuel:float                          # [kg/m^3], fuel density

    ## Oxidizer (lox)
    m_ox_boil_off:float                     # [kg]
    m_ox_prechill:float                     # [kg]
    m_ox_delay:float                        # [kg]
    m_ox_end:float                          # [kg], fixed volume
    m_ox_burn:float                         # [kg], oxidizer mass corresponding to free volume
    m_ox_total:float                        # [kg], total mass in tanks
    rho_ox:float                            # [kg/m^3], oxidizer density

    ## Pressurant (N2)
    m_n2_copv:float                         # [kg], pressurant mass fixed volume

    ## Wet mass (on pad right after filling)
    wet_mass:float                          # [kg]

    # thrust Curve
    ## Force
    F_full_thrust:float                     # [N], peak thrust
    F_derating:float                        # [N], constant thrust after ramp-up until derating starts
    F_ramp_down:float                       # [N], thrust at the end of the derating phase
    F_shutdown:float                        # [N], no thrust delivered at the end

    ## Timings
    t_full_thrust:float                     # [s], ramp-up duration
    t_ramp_down:float                       # [s], time at which ramp-down starts
    t_derating:float                        # [s], time at which constant thrust stops and derating starts
    t_shutdown:float                        # [s], time at which engine stops delivering thrust

    # ---- Field-to-Excel-column mappings ----
    # Each entry: python_attr_name -> (excel_column_letter, default_if_missing).
    # Letters are absolute Excel columns; resolved positionally inside `cols`.
    # Defaults are Firehorn 1 reference values, used when the cell is blank/NaN.
    _FIELDS_CFG = {
        "m_dry":          ("D", 84.4),    # Dry mass [kg]
        "Thrust":         ("E", 6308),    # Nominal Thrust [N]  (header in sheet is misspelled "Thurst")
        "ISP":            ("F", 198),     # ISP [s]
        "OF_ratio":       ("G", 1.463),   # core O/F [-]
        "ramp_up_time":   ("K", 0.361),   # Ramp up time [s]
        "ramp_down_time": ("L", 0.171),   # Ramp down time [s]
        "Total_impulse":  ("N", 36167),   # Total impulse [Ns]
    }

    _FIELDS_TIMINGS = {
        "hold_time":       ("D", 300),    # Hold / duration
        "prechill_time":   ("E", 0.2),    # Prechill / duration
        "ignition_delay":  ("F", -0.05),  # Ignition / ignition_delay
        "cutoff_time":     ("I", 0.025),  # Cutoff / delay
    }

    _FIELDS_PRESSURANT = {
        "m_n2_copv": ("F", 2.605),        # Mass [kg] / m_n2_copv
    }

    # mass_flow_rate_lox_burn is intentionally not read here — it is overwritten
    # in _compute_derived (= mass_flow_rate / (1 + 1/OF_ratio)).
    _FIELDS_OXIDIZER = {
        "rho_ox":                       ("D", 1154),   # ρ_ox
        "mass_flow_rate_lox_boil_off":  ("H", 0.001),  # ṁ_ox_boil-off
        "mass_flow_rate_lox_ignition":  ("I", 4.313),  # ṁ_ox_ignition
        "mass_flow_rate_lox_prechill":  ("J", 4.313),  # ṁ_ox_prechill
        "m_ox_end":                     ("R", 2.67),   # m_ox_end
    }

    _FIELDS_FUEL = {
        "rho_fuel":                         ("D", 810),    # ρ_fuel
        "fraction_film_cooling":            ("G", 0.0733), # frac_film_cooling
        "mass_flow_rate_ethanol_ignition":  ("I", 0),      # ṁ_fuel_ignition
        "m_fuel_delay":                     ("O", 0),      # m_fuel_delay
        "m_fuel_end":                       ("R", 0.527),  # m_fuel_end
    }
    
    def __init__(
        self,
        cfg: pd.Series | None = None,
        bgt_timings: pd.Series | None = None,
        bgt_pressurant: pd.Series | None = None,
        bgt_oxidizer: pd.Series | None = None,
        bgt_fuel: pd.Series | None = None,
    ) -> None:
        """Build an Input from the 5 row Series (one row per block).

        Each Series is one row from the corresponding DataFrame returned by
        dfs_from_excel(). Missing or NaN values are replaced with Firehorn 1
        reference defaults (see _FIELDS_* dicts). Pass None to use defaults
        for an entire block.
        """
        self._set_constants()
        self._read_from_rows(cfg, bgt_timings, bgt_pressurant, bgt_oxidizer, bgt_fuel)
        self._compute_derived()
 
    # ----- Init helpers -----
    def _set_constants(self) -> None:
        """Set values that don't depend on the simulation row."""
        # Identity (overridden by from_dfs when built from a spreadsheet row)
        self.config_id = None

        # General
        self.Version = "CH"
        self.savefiles = True
        self.N_points = 1000
        self.run_environment = True
        self.write_to_file = False
        self.out_filename = "output_CH.csv"
 
        # Propellant tank geometry
        self.r_int = 0.115
        self.h_cyl = 0.3851008075
        self.h_cap = 0.05
 
        # Hold-down geometry
        self.alpha = 6
        self.beta = 6
        self.l_rail = 11.65
 
        # Hold-down other
        self.g = 9.81
        self.F_HD_break = 3300
        self.mu = 0.5
        self.m_additions = 0
 
    def _read_from_rows(
        self,
        cfg: pd.Series | None,
        timings: pd.Series | None,
        pressurant: pd.Series | None,
        oxidizer: pd.Series | None,
        fuel: pd.Series | None,
    ) -> None:
        """Pull each field from the appropriate row by Excel column letter."""
        for row, spec, mapping in (
            (cfg,        DEFAULT_BLOCKS["cfg"],        self._FIELDS_CFG),
            (timings,    DEFAULT_BLOCKS["timings"],    self._FIELDS_TIMINGS),
            (pressurant, DEFAULT_BLOCKS["pressurant"], self._FIELDS_PRESSURANT),
            (oxidizer,   DEFAULT_BLOCKS["oxidizer"],   self._FIELDS_OXIDIZER),
            (fuel,       DEFAULT_BLOCKS["fuel"],       self._FIELDS_FUEL),
        ):
            for attr_name, (col_letter, default) in mapping.items():
                idx = _offset(col_letter, spec.cols)
                setattr(self, attr_name, _get_or_default(row, idx, default))
 
    def _compute_derived(self) -> None:
        """Compute values derived from the raw inputs."""
        # General mass flow / burn time
        self.mass_flow_rate = self.Thrust / (self.ISP * self.g)
        self.burn_time = self.Total_impulse / self.Thrust
        self.propellant_mass = self.mass_flow_rate * self.burn_time
 
        # Fuel (ethanol) mass flow rates
        self.mass_flow_rate_ethanol = self.mass_flow_rate / (1 + self.OF_ratio)
        self.mass_flow_rate_film_cooling = (
            self.mass_flow_rate_ethanol * self.fraction_film_cooling
        )
        self.mass_flow_rate_ethanol_burn = (
            self.mass_flow_rate_ethanol + self.mass_flow_rate_film_cooling
        )
 
        # Oxidizer (LOX) mass flow rate during burn
        self.mass_flow_rate_lox_burn = self.mass_flow_rate / (1 + 1 / self.OF_ratio)
 
        # Fuel masses
        self.m_fuel_cutoff = self.mass_flow_rate_ethanol_burn * self.cutoff_time
        self.m_fuel_burn = self.mass_flow_rate_ethanol_burn * self.burn_time
        # m_fuel_end already includes the fixed volume; we add the cutoff residual.
        # (The residual stays in the tank during flight and is technically used at
        # the end of the burn without producing thrust; we accept the extra mass
        # for the recovery phase.)
        self.m_fuel_end += self.m_fuel_cutoff
        self.m_fuel_total = self.m_fuel_delay + self.m_fuel_burn + self.m_fuel_end
 
        # Oxidizer masses
        self.m_ox_boil_off = self.mass_flow_rate_lox_boil_off * self.hold_time
        self.m_ox_prechill = self.mass_flow_rate_lox_prechill * self.prechill_time
        self.m_ox_delay = self.mass_flow_rate_lox_ignition * abs(self.ignition_delay)
        self.m_ox_burn = self.mass_flow_rate_lox_burn * self.burn_time
        self.m_ox_total = (
            self.m_ox_boil_off
            + self.m_ox_prechill
            + self.m_ox_delay
            + self.m_ox_burn
            + self.m_ox_end
        )
 
        # Wet mass on the pad
        self.wet_mass = (
            self.m_dry + self.m_fuel_total + self.m_ox_total + 2 * self.m_n2_copv
        )
 
        # Thrust curve forces (currently flat — peak thrust through the burn)
        self.F_full_thrust = self.Thrust
        self.F_derating = self.Thrust
        self.F_ramp_down = self.Thrust
        self.F_shutdown = 0
 
        # Thrust curve timings
        self.t_full_thrust = self.ramp_up_time
        self.t_ramp_down = self.burn_time
        self.t_derating = self.t_ramp_down - 0.001
        self.t_shutdown = self.t_ramp_down + self.ramp_down_time

#--- PUBLIC METHODS ---
    def display(self) -> None:
        for field in fields(self):
            field_name = field.name
            field_value = getattr(self, field_name)
            print(f"{field_name}: {field_value}")
        return
    
    @classmethod
    def from_dfs(
        cls,
        dfs: Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame],
        row: int,
    ) -> Input:
        """Build an Input from the 5 DataFrames returned by `dfs_from_excel()`.

        `row` is the 0-indexed DataFrame row, NOT the Excel row.
        Row 0 is Firehorn 1 (reference data, no config_id).
        Rows 1+ are the simulation configs (CONFIG1, CONFIG2, ...).

        After construction, `instance.config_id` holds the per-row config id
        from column C of the Config sheet, or None for the Firehorn 1 row.
        """
        rows = [df.iloc[row] for df in dfs]
        instance = cls(*rows)
        cfg_spec = DEFAULT_BLOCKS["cfg"]
        cid = rows[0].iloc[_offset(_CONFIG_ID_COL, cfg_spec.cols)]
        instance.config_id = None if pd.isna(cid) else str(cid)
        return instance
    


    


