from __future__ import annotations
from dataclasses import dataclass, fields
import pandas as pd

def dfs_from_excel(
    file:str,
    nsims:int,
    config_cols:str = "B:G",
    timings_cols:str = "B:H",
    pressurant_cols:str = "B:C",
    oxidizer_cols:str = "B:G",
    fuel_cols:str = "B:G"
) -> tuple[pd.DataFrame,pd.DataFrame,pd.DataFrame,pd.DataFrame,pd.DataFrame]:
    config = pd.read_excel(
        file,
        sheet_name="Config",
        skiprows=[0],
        header=0,
        index_col=0,
        usecols=config_cols,
        nrows=nsims+1
    )
    timings = pd.read_excel(
        file,
        sheet_name="Timings",
        skiprows=[0],
        header=0,
        index_col=0,
        usecols=timings_cols,
        nrows=nsims+1
    )
    pressurant = pd.read_excel(
        file,
        sheet_name="Pressurant",
        skiprows=[0],
        header=0,
        index_col=0,
        usecols=pressurant_cols,
        nrows=nsims+1
    )
    oxidizer = pd.read_excel(
        file,
        sheet_name="Oxidizer",
        skiprows=[0],
        header=0,
        index_col=0,
        usecols=oxidizer_cols,
        nrows=nsims+1
    )
    fuel = pd.read_excel(
        file,
        sheet_name="Fuel",
        skiprows=[0],
        header=0,
        index_col=0,
        usecols=fuel_cols,
        nrows=nsims+1
    )
    
    return config, timings, pressurant, oxidizer, fuel

@dataclass
class Input:
    # General
    m_dry: float                            # [kg], launch vehicle dry mass (weighted 84.4 w. 3U)

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

    _DICT_CONFIG = {
        "m_dry":          ("m_dry", 84.4),              # Dry mass [kg]
        "Thrust":         ("Thrust", 6308),             # Nominal Thrust [N]  (header in sheet is misspelled "Thurst")
        "ISP":            ("ISP", 198),                 # ISP [s]
        "OF_ratio":       ("OF_ratio", 1.463),          # core O/F [-]
        "Total_impulse":  ("Total_impulse", 36167),     # Total impulse [Ns]
    }

    _DICT_TIMINGS = {
        "hold_time":       ("hold_time", 300),          # Hold / duration
        "prechill_time":   ("prechill_time", 0.2),      # Prechill / duration
        "ignition_delay":  ("ignition_delay", -0.05),   # Ignition / ignition_delay
        "ramp_up_time":    ("ramp_up_time", 0.361),     # Ramp up time [s]
        "cutoff_time":     ("cutoff_time", 0.025),      # Cutoff / delay
        "ramp_down_time":  ("ramp_down_time", 0.171),   # Ramp down time [s]
    }

    _DICT_PRESSURANT = {
        "m_n2_copv": ("m_n2_copv", 2.605),        # Mass [kg] / m_n2_copv
    }


    _DICT_OXIDIZER = {
        "rho_ox":                       ("rho_ox", 1154),           # ρ_ox
        "mass_flow_rate_lox_boil_off":  ("mf_ox_boil-off", 0.001),  # ṁ_ox_boil-off
        "mass_flow_rate_lox_ignition":  ("mf_ox_ignition", 4.313),  # ṁ_ox_ignition
        "mass_flow_rate_lox_prechill":  ("mf_ox_prechill", 4.313),  # ṁ_ox_prechill
        "m_ox_end":                     ("m_ox_end", 2.67),         # m_ox_end
    }

    _DICT_FUEL = {
        "rho_fuel":                         ("rho_fuel", 810),              # ρ_fuel
        "fraction_film_cooling":            ("frac_film_cooling", 0.0733),  # frac_film_cooling
        "mass_flow_rate_ethanol_ignition":  ("mf_fuel_ignition", 0),        # ṁ_fuel_ignition
        "m_fuel_delay":                     ("m_fuel_delay", 0),            # m_fuel_delay
        "m_fuel_end":                       ("m_fuel_end", 0.527),          # m_fuel_end
    }

# --- __init__ helper ---

    def _compute_derived(self, g:float, m_additions:float) -> None:
        """Compute values derived from the raw inputs."""
        # General mass flow / burn time
        self.mass_flow_rate = self.Thrust / (self.ISP * g)
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
        self.m_dry += m_additions

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

# --- __init__ ---

    def __init__(
            self,
            config:pd.DataFrame,
            timings:pd.DataFrame,
            pressurant:pd.DataFrame,
            oxidizer:pd.DataFrame,
            fuel:pd.DataFrame,
            row:int,                 # 1-indexed (row 0 is the default (Firehorn 1))
            g:float = 9.81,          # gravity
            m_additions:float = 0    # mass additions [kg]
        ):
        # initialize input according to provided arguments
        for table, dict in (
            (config.iloc[row], self._DICT_CONFIG),
            (timings.iloc[row], self._DICT_TIMINGS),
            (pressurant.iloc[row], self._DICT_PRESSURANT),
            (oxidizer.iloc[row], self._DICT_OXIDIZER),
            (fuel.iloc[row], self._DICT_FUEL)
        ):
            for attr_name, (table_name, default) in dict.items():
                value = table[table_name]
                if pd.isna(value):
                    value = default
                setattr(self, attr_name, value)

        # compute other values from input
        self._compute_derived(g, m_additions)

# --- useful ---
    
    def display(self) -> None:
        for field in fields(self):
            field_name = field.name
            field_value = getattr(self, field_name)
            print(f"{field_name}: {field_value}")
        return
