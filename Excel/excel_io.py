from __future__ import annotations
from dataclasses import dataclass, fields
import pandas as pd
import numpy as np

@dataclass(frozen=True)
class _BlockSpec:
    sheet: str
    cols: str        # Excel column range, e.g. "B:M"
    header_row: int  # 1-indexed row containing the column headers
    first_data_row: int  # 1-indexed row of the first data row
 
DEFAULT_BLOCKS: dict[str, _BlockSpec] = {
    "cfg":        _BlockSpec(sheet="Config", cols="B:M", header_row=1,   first_data_row=3),
    "timings":    _BlockSpec(sheet="Budget", cols="B:I", header_row=2,   first_data_row=5),
    "pressurant": _BlockSpec(sheet="Budget", cols="B:F", header_row=55,  first_data_row=58),
    "oxidizer":   _BlockSpec(sheet="Budget", cols="B:V", header_row=108, first_data_row=111),
    "fuel":       _BlockSpec(sheet="Budget", cols="B:V", header_row=161, first_data_row=164),
}

def _read_block(file: str, spec: _BlockSpec, nsims: int) -> pd.DataFrame:
    """Read one rectangular table from the workbook."""
    skiprows = (list(range(spec.header_row - 1)) + list(range(spec.header_row, spec.first_data_row - 1)))
    return pd.read_excel(
        file,
        spec.sheet,
        header=0,
        usecols=spec.cols,
        skiprows=skiprows,
        index_col=0,
        nrows=nsims,
    )

def dfs_from_excel(
    file: str,
    nsims: int = 44,
    blocks: dict[str, _BlockSpec] = DEFAULT_BLOCKS,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Read the 5 simulation tables (config, timings, pressurant, ox, fuel)."""
    return (
        _read_block(file, blocks["cfg"], nsims),
        _read_block(file, blocks["timings"], nsims),
        _read_block(file, blocks["pressurant"], nsims),
        _read_block(file, blocks["oxidizer"], nsims),
        _read_block(file, blocks["fuel"], nsims),
    )

# --- HELPERS --- 
def _get_or_default(d: dict, key: str, default: float|bool|str) -> float|bool|str:
    val = d.get(key, default)
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
    # Each entry: python_attr_name -> (excel_column_header, default_if_missing).
    # The defaults are Firehorn 1 reference values.
    _FIELDS_CONSTANTS:dict[str,tuple[str,float|bool|str]] = {
        # General
        "Version":         ("Version",                  "CH"),
        "savefiles":       ("savefiles",                True),
        "N_points":        ("number of points",         1000),
        "run_environment": ("run environment",          True),
        "write_to_file":   ("write to file",            False),
        "out_filename":    ("output file",              "output_CH.csv"),
 
        # Propellant tank geometry
        "r_int":           ("interior radius",          0.115),
        "h_cyl":           ("cylinder height",          0.3851008075),
        "h_cap":           ("cap height",               0.05),
 
        # Hold-down geometry
        "alpha":           ("alpha",                    6),
        "beta":            ("beta",                     6),
        "l_rail":          ("rail length",              11.65),
 
        # Hold-down other
        "g":               ("g",                        9.81),
        "F_HD_break":      ("hold-down break force",    3300),
        "mu":              ("button-rail friction",     0.5),
        "m_additions":     ("mass additions",           0),
    }

    _FIELDS_CFG = {
        "m_dry":          ("Dry mass [kg]",       84.4),
        "Thrust":         ("Nominal Thrust [N]",  6308),
        "ISP":            ("ISP [s]",             198),
        "OF_ratio":       ("core O/F [-]",        1.463),
        "ramp_up_time":   ("Ramp up time [s]",    0.361),
        "ramp_down_time": ("Ramp down time [s]",  0.2),
        "Total_impulse":  ("Total impulse [Ns]",  36167),
        "hold_time":      ("Hold",                300),
    }
 
    _FIELDS_TIMINGS = {
        "prechill_time":   ("prechill_time",   0.2),
        "ignition_delay":  ("ignition_delay", -0.05),
        "cutoff_time":     ("cutoff_time",     0.025),
    }
 
    _FIELDS_PRESSURANT = {
        "m_n2_copv": ("m_n2_copv", 2.605),
    }
 
    _FIELDS_OXIDIZER = {
        "rho_ox":                       ("rho_ox",          1154),
        "mass_flow_rate_lox_boil_off":  ("mf_ox_boil_off",  0.001),
        "mass_flow_rate_lox_ignition":  ("mf_ox_ignition",  4.313),
        "mass_flow_rate_lox_prechill":  ("mf_ox_prechill",  4.313),
        "mass_flow_rate_lox_burn":      ("mf_ox_burn",      1.879),
        "m_ox_end":                     ("m_ox_end",        2.67),
    }
 
    _FIELDS_FUEL = {
        "rho_fuel":                         ("rho_fuel",          810),
        "fraction_film_cooling":            ("frac_film_cooling", 0.0733),
        "mass_flow_rate_ethanol_ignition":  ("mf_fuel_ignition",  0),
        "m_fuel_delay":                     ("m_fuel_delay",      0),
        "m_fuel_end":                       ("m_fuel_end",        0.527),
    }
    
    def __init__(
        self,
        const: dict[str, float|bool|str] = {},
        cfg: dict[str, float] = {},
        bgt_timings: dict[str, float] = {},
        bgt_pressurant: dict[str, float] = {},
        bgt_oxidizer: dict[str, float] = {},
        bgt_fuel: dict[str, float] = {},
    ) -> None:
        """Build an Input from the 5 input dictionaries.
 
        Each dict is one row from the corresponding DataFrame returned by
        dfs_from_excel(). Missing or NaN values are replaced with Firehorn 1
        reference defaults (see _FIELDS_* dicts).
        """
        self._read_from_dicts(const, cfg, bgt_timings, bgt_pressurant, bgt_oxidizer, bgt_fuel)
        self._compute_derived()
 
    # ----- Init helpers -----
    def _read_from_dicts(
        self,
        const:dict, cfg:dict, timings:dict, pressurant:dict, oxidizer:dict, fuel:dict,
    ) -> None:
        """Pull each field from the appropriate input dict, applying defaults."""
        for source, mapping in (
            (const,      self._FIELDS_CONSTANTS),
            (cfg,        self._FIELDS_CFG),
            (timings,    self._FIELDS_TIMINGS),
            (pressurant, self._FIELDS_PRESSURANT),
            (oxidizer,   self._FIELDS_OXIDIZER),
            (fuel,       self._FIELDS_FUEL)
        ):
            for attr_name, (excel_key, default) in mapping.items():
                setattr(self, attr_name, _get_or_default(source, excel_key, default))
 
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

        # Dry mass
        self.m_dry += self.m_additions

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
        const:dict[str,float|bool|str],
        df_cfg:pd.DataFrame,
        df_timings:pd.DataFrame,
        df_pressurant:pd.DataFrame,
        df_oxidizer:pd.DataFrame,
        df_fuel:pd.DataFrame,
        row:int
        ) -> Input:
        """
        Idea: call this function with the ouput of `dfs_from_excel()` defined above,
            and the number of the simulation, 0-indexed.
            This makes it easier to iterate over all simulations.

        Note: `row` does not correspond to the row number from the excel file,
            but to the row number of the dataframe.
            This is the number of the corresponding simulation, 0-indexed.
        """
        cfg = df_cfg.iloc[row].to_dict()
        timings = df_timings.iloc[row].to_dict()
        pressurant = df_pressurant.iloc[row].to_dict()
        oxidizer = df_oxidizer.iloc[row].to_dict()
        fuel = df_fuel.iloc[row].to_dict()
        # Too lazy to typecheck, we trust the user 
        return cls(const,cfg,timings,pressurant,oxidizer,fuel)  # type: ignore
    
#--- THRUST_RESULTS DATACLASS ---
@dataclass
class Thrust_results:
    t_total:np.ndarray
    F:np.ndarray
    total_impulse:float
    slope_ramp_up:float
    slope_derating:float
    slope_shutdown:float

#--- LAUNCH_RESULTS DATACLASS ---
@dataclass
class Launch_results:
    idx_break:int
    t_break:float
    t_exit:float
    v_exit:float

#--- PROPELLANT_RESULTS DATACLASS ---
@dataclass
class Propellant_results:
    # Equivalent heights
    ## Tank
    h_eq:float
    ## Fuel
    h_fuel_free:float
    h_fuel_fixed:float
    h_fuel_total:float
    ## Ox
    h_ox_free:float
    h_ox_fixed:float
    h_ox_total:float

    # Equivalent volumes
    ## Tank
    V_tank_total:float
    ## Fuel
    V_fuel_free:float
    V_fuel_fixed:float
    V_fuel_total:float
    ## Oxidizer
    V_ox_free:float
    V_ox_fixed:float
    V_ox_total:float

    # Heights of interest
    ## Fixed mass (liquid remaining at bottom)
    z_fuel_fixed_COM:float
    z_ox_fixed_COM:float
    ## Free mass bottom position
    z_fuel_free_bottom:float
    z_ox_free_bottom:float
    ## Total mass
    z_fuel_total_COM:float
    z_ox_total_COM:float

    z_fuel_total_bottom:float
    z_ox_total_bottom:float

    # Mass depletion
    mass_lost_fuel_before_break:float
    mass_lost_ox_before_break:float

    # Propellant volumes
    ullage_fuel_m3:np.ndarray
    ullage_ox_m3:np.ndarray