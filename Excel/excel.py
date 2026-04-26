from dataclasses import dataclass
import numpy as np

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

    def __init__(
            self,
            cfg:dict[str,float],
            bgt_timings:dict[str,float],
            bgt_pressurant:dict[str,float],
            bgt_oxidizer:dict[str,float],
            bgt_fuel:dict[str,float]
        ) -> None:
        """
        Parameters:
        - cfg:             Config Configurations table
        - bgt_timings:     Budget Timings table
        - bgt_pressurant:  Budget Pressurant table
        - bgt_oxidizer:    Budget Oxidizer table
        - bgt_fuel:        Budget Fuel table
        - 
        Default values are taken from Firehorn 1.
        """
        # Constants
        ## General
        self.Version = "CH"
        self.savefiles = True
        self.N_points = 1000
        self.run_environment = True
        self.write_to_file = False
        self.out_filename = "output_CH.csv"
        
        ## Propellant tanks geometry
        self.r_int = 0.115
        self.h_cyl = 0.3851008075
        self.h_cap = 0.05

        ## Hold-down
        ### Geometry
        self.alpha = 6
        self.beta = 6
        self.l_rail = 11.65
        ### Other
        self.g = 9.81
        self.F_HD_break = 3300
        self.mu = 0.5
        self.m_additions = 0

        # Values read from excel
        ## configurations
        self.m_dry = cfg.get("Dry mass [kg]",84.4)
        if np.isnan(self.m_dry):
            self.m_dry = 84.4
        self.Thrust = cfg.get("Nominal Thrust [N]",6308)
        if np.isnan(self.Thrust):
            self.Thrust = 6308
        self.ISP = cfg.get("ISP [s]",198)
        if np.isnan(self.ISP):
            self.ISP = 198
        self.OF_ratio = cfg.get("core O/F [-]",1.463)
        if np.isnan(self.OF_ratio):
            self.OF_ratio = 1.463
        self.ramp_up_time = cfg.get("Ramp up time [s]",0.361)
        if np.isnan(self.ramp_up_time):
            self.ramp_up_time = 0.361
        self.ramp_down_time = cfg.get("Ramp down time [s]",0.2)
        if np.isnan(self.ramp_down_time):
            self.ramp_down_time = 0.2
        self.Total_impulse = cfg.get("Total impulse [Ns]",36167)
        if np.isnan(self.Total_impulse):
            self.Total_impulse = 36167
        self.hold_time = cfg.get("Hold",300)
        if np.isnan(self.hold_time):
            self.hold_time = 300
        
        ## budget timings
        self.prechill_time = bgt_timings.get("prechill_time",0.2)
        if np.isnan(self.prechill_time):
            self.prechill_time = 0.2
        self.ignition_delay = bgt_timings.get("ignition_delay",-0.05)
        if np.isnan(self.ignition_delay):
            self.ignition_delay = -0.05
        self.cutoff_time = bgt_timings.get("cutoff_time",0.025)
        if np.isnan(self.cutoff_time):
            self.cutoff_time = 0.025

        ## budget pressurant
        self.m_n2_copv = bgt_pressurant.get("m_n2_copv",2.605)
        if np.isnan(self.m_n2_copv):
            self.m_n2_copv = 2.605

        ## budget oxidizer
        self.rho_ox = bgt_oxidizer.get("rho_ox",1154)
        if np.isnan(self.rho_ox):
            self.rho_ox = 1154
        self.mass_flow_rate_lox_boil_off = bgt_oxidizer.get("m_ox_boil_off",0.001)
        if np.isnan(self.mass_flow_rate_lox_boil_off):
            self.mass_flow_rate_lox_boil_off = 0.001
        self.mass_flow_rate_lox_ignition = bgt_oxidizer.get("m_ox_ignition",4.313)
        if np.isnan(self.mass_flow_rate_lox_ignition):
            self.mass_flow_rate_lox_ignition = 4.313
        self.mass_flow_rate_lox_prechill = bgt_oxidizer.get("m_ox_prechill",4.313)
        if np.isnan(self.mass_flow_rate_lox_prechill):
            self.mass_flow_rate_lox_prechill = 4.313
        self.mass_flow_rate_lox_burn = bgt_oxidizer.get("m_ox_burn",1.879)
        if np.isnan(self.mass_flow_rate_lox_burn):
            self.mass_flow_rate_lox_burn = 1.879
        self.m_ox_end = bgt_oxidizer.get("m_ox_end",2.67)
        if np.isnan(self.m_ox_end):
            self.m_ox_end = 2.67
        
        ## budget fuel
        self.rho_fuel = bgt_fuel.get("rho_fuel",810)
        if np.isnan(self.rho_fuel):
            self.rho_fuel = 810
        self.fraction_film_cooling = bgt_fuel.get("frac_film_cooling",0.0733)
        if np.isnan(self.fraction_film_cooling):
            self.fraction_film_cooling = 0.0733
        self.mass_flow_rate_ethanol_ignition = bgt_fuel.get("m_fuel_ignition",0)
        if np.isnan(self.mass_flow_rate_ethanol_ignition):
            self.mass_flow_rate_ethanol_ignition = 0
        self.m_fuel_delay = bgt_fuel.get("m_fuel_delay",0)
        if np.isnan(self.m_fuel_delay):
            self.m_fuel_delay = 0
        self.m_fuel_end = bgt_fuel.get("m_fuel_end",0.527)
        if np.isnan(self.m_fuel_end):
            self.m_fuel_end = 0.527

        # Computed values
        ## Propellant masses
        ### General
        self.mass_flow_rate = self.Thrust / (self.ISP * self.g)
        self.burn_time = self.Total_impulse / self.Thrust
        self.propellant_mass = self.mass_flow_rate * self.burn_time
        ### Fuel (ethanol) mass flow rates
        self.mass_flow_rate_ethanol = self.mass_flow_rate / (1 + self.OF_ratio)
        self.mass_flow_rate_film_cooling = self.mass_flow_rate_ethanol * self.fraction_film_cooling
        self.mass_flow_rate_ethanol_burn = self.mass_flow_rate_ethanol + self.mass_flow_rate_film_cooling
        ### Oxidizer (lox) mass flow rates
        self.mass_flow_rate_lox_burn = self.mass_flow_rate / (1 + 1/self.OF_ratio)
        ### Fuel (ethanol) masses
        self.m_fuel_cutoff = self.mass_flow_rate_ethanol_burn * self.cutoff_time
        self.m_fuel_burn = self.mass_flow_rate_ethanol_burn * self.burn_time
        self.m_fuel_end += self.m_fuel_cutoff
        self.m_fuel_total = self.m_fuel_delay + self.m_fuel_burn + self.m_fuel_end
        ### Oxidizer (lox) masses
        self.m_ox_boil_off = self.mass_flow_rate_lox_boil_off * self.hold_time
        self.m_ox_prechill = self.mass_flow_rate_lox_prechill * self.prechill_time
        self.m_ox_delay = self.mass_flow_rate_lox_ignition * abs(self.ignition_delay)
        self.m_ox_burn = self.mass_flow_rate_lox_burn * self.burn_time
        self.m_ox_total = self.m_ox_boil_off + self.m_ox_prechill + self.m_ox_delay + self.m_ox_burn + self.m_ox_end
        ### Wet mass
        self.wet_mass = self.m_dry + self.m_fuel_total + self.m_ox_total + 2*self.m_n2_copv

        ## Thrust curve
        ### Force
        self.F_full_thrust = self.Thrust
        self.F_derating = self.Thrust
        self.F_ramp_down = self.Thrust
        self.F_shutdown = 0
        ### Timings
        self.t_full_thrust = self.ramp_up_time
        self.t_ramp_down = self.burn_time
        self.t_derating = self.t_ramp_down - 0.001
        self.t_shutdown = self.t_ramp_down + self.ramp_down_time
