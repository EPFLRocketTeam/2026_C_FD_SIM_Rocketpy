import numpy as np
import os
import csv
from rocketpy import SolidMotor, Rocket, LiquidMotor, Motor, CylindricalTank, MassFlowRateBasedTank, Fluid, Function, MassBasedTank, UllageBasedTank

class RocketBuilder:
    # rocket dimensions
    BODY_RADIUS = 0.243/2          # m
    #NOSE_LENGTH = 1.003             # m
    NOSE_POWER = 0.5
    # FIN_COUNT = 4
    #FIN_TIP_CHORD = 0.161           # m
    #FIN_SWEEP_LENGTH = 0.539
    FIN_POSITION = 1.1315
    RAIL_BUTTONS = (0.46279, 0.4628)     # m
    #TAIL_TOP_RADIUS = 0.1215 # m
    #TAIL_BOTTOM_RADIUS = 0.070 # m
    #TAIL_LENGTH = 0.41755 # m
    TAIL_POSITION = 0.41755 # m
    
    # solid motor properties
    SOLID_MOTOR_DRY_MASS = 5.0          # kg
    SOLID_MOTOR_NOZZLE_RADIUS = 0.05    # m
    GRAIN_DENSITY = 1815          # kg/m^3
    GRAIN_OUTER_RADIUS = 0.075    # m
    GRAIN_INIT_INNER_RADIUS = 0.03 # m
    GRAIN_INIT_HEIGHT = 0.3       # m
    GRAIN_SEPARATION = 0.005      # m
    GRAIN_COUNT = 4

    # solid motor properties
    LIQUID_MOTOR_DRY_MASS = 1e-5         # kg
    LIQUID_NOZZLE_RADIUS = 0.04946         # m
    # cylindrical tank
    TANK_RADIUS = 0.115                  # m
    TANK_LENGTH = 0.3851                 # m (both)
    TANK_DISTANCE = 0.9                 # m distance oxi-fuel tanks
    PRESSURE_TANK_RADIUS = 0.0885
    PRESSURE_TANK_LENGTH = 0.570

    FUEL_DENSITY = 810.0          # kg/m^3 (ethanol)
    OXIDIZER_DENSITY = 1154.0     # kg/m^3 (LOX)
    PRESSURE_GAS_DENSITY = 600.0  # kg/m^3
    PRESSURE_GAS_DENSITY_LOX = 113.4262136487
    PRESSURE_GAS_DENSITY_FUEL = 68.9301721355

    FULL_THRUST_FORCE = 6500.0      # N
    RAMP_UP_TIME = 0.4              # s
    RAMP_DOWN_TIME = 0.2            # s

    G = 9.81
    THRUST = 6500
    ISP = 220
    FUEL_END_MASS = 0.405
    OX_END_MASS = 0.577
    PRESSURANT_MASS_INIT = 2.605

    TANK_POS_HEIGHT = 0.388
    FRACTION_FILM_COOLING = 0.0750
    BOIL_OFF_RATE = 0.001                # kg/s
    PRECHILL_RATE = 4.362                # kg/s
    IGNITION_RATE = 4.362                # kg/s
    IGNITION_DELAY = -0.050              # s
    CUTOFF_TIME = 0.025                  # s
    PRECHILL_TIME = 0.200                # s
    HOLD_TIME = 300                      # s
    ALPHA = 6.0                          # degrees
    BETA = 6.0                           # degrees
    RAIL_LENGTH = 11.65                       # m
    MU = 0.5
    F_HD_BREAK = 3300.0                  # N
    DRY_MASS_DEFAULT = 108               # kg

    def __init__(self, params: dict):
        """
        Expected keys in params:
            dry_mass               : rocket dry mass (without motor) [kg]
            fin_span               : fin span [m]
            fin_root_chord         : fin root chord [m]
            propellant_mass        : total propellant mass (unused if using tank masses)
            burn_time              : burn time [s]
            motor_type             : 'liquid' (only liquid supported here)
            body_length            : total body length [m]
            cg_without_motor       : CG without motor from nose tip [m]
            initial_fuel_mass      : initial fuel mass [kg] (default 8.82)
            initial_oxidizer_mass  : initial oxidizer mass [kg] (default 12.66)
            thrust_source          : optional thrust curve (callable or .eng file path)
        """
        self.params = params
        self.rocket = None
        self.motor = None
        
        self.dry_mass = params.get('dry_mass', 108)
        self.fin_span = params.get('fin_span', 0.3)
        self.fin_root_chord = params.get('fin_root_chord', 0.671) 
        self.fin_tip_chord = params.get('fin_tip_chord', 0.161)
        self.fin_sweep_length = params.get('fin_sweep_length', 0.539)
        self.fin_count = params.get('fin_count', 4)
        self.propellant_mass = params.get('propellant_mass', 8.115)
        self.burn_time = params.get('burn_time', 6.1604)
        self.motor_type = params.get('motor_type', 'solid')

        self.nose_length = params.get('nose_length', 1.003)
        self.tail_length = params.get('tail_length', 0.41755)
        self.tail_top_radius = params.get('tail_top_radius', 0.1215)
        self.tail_bottom_radius = params.get('tail_bottom_radius', 0.070)
        self.version = params.get('version', 'CH')
        
        self.body_length = params.get('body_length', 5.81755)
        self.cg_without_motor = params.get('cg_without_motor', 2.59)
        self.fuel_mass = params.get('fuel_mass', 8.82)        # kg
        self.oxidizer_mass = params.get('initial_oxidizer_mass', 12.66) # kg
        self.thrust_source = params.get('thrust_source', None)

        self.total_impulse = self.params.get('total_impulse', 40500)  # Ns
        self.m_ox_burn = self.params.get('oxidizer_mass', 12.66)   # kg
        self.m_fuel_burn = self.params.get('fuel_mass', 8.82)      # kg
        self.m_press_initial = self.params.get('pressurant_mass_per_tank', 2.605)

        self.reefed_mass = params.get('reefed_mass', 1.0)       # kg (est.)
        self.unreefed_mass = params.get('unreefed_mass', 1.5)   # kg (est.)
        self.parachute_position = params.get('parachute_position', self.body_length - 0.5)
        
    def build_solid_motor(self) -> SolidMotor:
        total_impulse = self.propellant_mass * 2000
        thrust = total_impulse / self.burn_time
        
        motor = SolidMotor(
            thrust_source=lambda t: thrust,
            dry_mass=self.SOLID_MOTOR_DRY_MASS,
            dry_inertia=(0.1, 0.1, 0.01),
            nozzle_radius=self.SOLID_MOTOR_NOZZLE_RADIUS,
            grain_number=self.GRAIN_COUNT,
            grain_density=self.GRAIN_DENSITY,
            grain_outer_radius=self.GRAIN_OUTER_RADIUS,
            grain_initial_inner_radius=self.GRAIN_INIT_INNER_RADIUS,
            grain_initial_height=self.GRAIN_INIT_HEIGHT,
            grain_separation=self.GRAIN_SEPARATION,
            grains_center_of_mass_position=0.5,
            center_of_dry_mass_position=0.5,
            nozzle_position=0,
            burn_time=self.burn_time,
            coordinate_system_orientation="nozzle_to_combustion_chamber",
        )
        return motor
    
    def build_liquid_motor(self) -> LiquidMotor:
        of_ratio = self.m_ox_burn / self.m_fuel_burn
        g = self.G

        total_mass_flow = self.THRUST / (self.ISP * g)
        mdot_fuel_total = total_mass_flow / (1 + of_ratio)
        mdot_film = mdot_fuel_total * self.FRACTION_FILM_COOLING
        mdot_fuel_burn = mdot_fuel_total + mdot_film
        mdot_ox_burn = total_mass_flow / (1 + 1 / of_ratio)

        burn_time = (self.m_fuel_burn + self.m_ox_burn) * g * self.ISP / self.THRUST

        m_fuel_cutoff = mdot_fuel_burn * self.CUTOFF_TIME
        m_fuel_end = self.FUEL_END_MASS + m_fuel_cutoff
        m_ox_end = self.OX_END_MASS

        m_ox_boil = self.BOIL_OFF_RATE * self.HOLD_TIME
        m_ox_prechill = self.PRECHILL_RATE * self.PRECHILL_TIME
        m_ox_ignition = self.IGNITION_RATE * abs(self.IGNITION_DELAY)

        N = 500
        t_full = np.linspace(0, burn_time, N)
        F_full = np.zeros_like(t_full)
        for i, t in enumerate(t_full):
            if t <= self.RAMP_UP_TIME:
                F_full[i] = self.THRUST * t / self.RAMP_UP_TIME
            elif t <= burn_time - self.RAMP_DOWN_TIME:
                F_full[i] = self.THRUST
            else:
                F_full[i] = self.THRUST * (burn_time - t) / self.RAMP_DOWN_TIME

        imp_full = np.trapezoid(F_full, t_full)

        # ---- Hold‑down analysis ----
        m_wet_hd = self.dry_mass + self.m_ox_burn + m_ox_end + self.m_fuel_burn + m_fuel_end + 2 * self.PRESSURANT_MASS_INIT
        W = m_wet_hd * g

        alpha_rad = np.deg2rad(self.ALPHA)
        beta_rad = np.deg2rad(self.BETA)
        denominator = np.cos(beta_rad) - self.MU * np.sin(beta_rad)

        F_HD = (F_full - W * (np.cos(alpha_rad) - self.MU * np.sin(alpha_rad))) / denominator
        mask_break = F_HD >= self.F_HD_BREAK
        if np.any(mask_break):
            idx_break = np.argmax(mask_break)
            t_break = t_full[idx_break]
        else:
            t_break = 0.0
            idx_break = 0

        dt_full = np.gradient(t_full)
        consumed_fuel_full = np.cumsum((self.m_fuel_burn * F_full / imp_full) * dt_full)
        m_fuel_before_break = consumed_fuel_full[idx_break]

        consumed_ox_full = np.cumsum((self.m_ox_burn * F_full / imp_full) * dt_full)
        m_ox_before_break_burn = consumed_ox_full[idx_break]
        m_ox_before_break_total = m_ox_before_break_burn + m_ox_boil + m_ox_prechill + m_ox_ignition

        m_fuel_remaining = self.m_fuel_burn - m_fuel_before_break
        m_ox_remaining = self.m_ox_burn - m_ox_before_break_burn

        mask_post = t_full >= t_break
        t_flight = t_full[mask_post] - t_break
        F_post = F_full[mask_post]
        F_post[0] = 0.0   

        imp_post = np.trapezoid(F_post, t_flight)
        if imp_post <= 0:
            raise RuntimeError("Zero impulse after hold‑down break – check parameters.")

        mdot_fuel_post = m_fuel_remaining * F_post / imp_post
        mdot_ox_post = m_ox_remaining * F_post / imp_post

        dt_post = np.gradient(t_flight)
        rem_fuel = m_fuel_remaining - np.cumsum(mdot_fuel_post * dt_post)
        rem_ox   = m_ox_remaining - np.cumsum(mdot_ox_post * dt_post)
        rem_fuel = np.maximum(rem_fuel, 0.0)
        rem_ox   = np.maximum(rem_ox, 0.0)

        V_tank = np.pi * self.TANK_RADIUS ** 2 * self.TANK_LENGTH
        V_fuel_free = rem_fuel / self.FUEL_DENSITY
        V_ox_free   = rem_ox / self.OXIDIZER_DENSITY
        V_fuel_fixed = m_fuel_end / self.FUEL_DENSITY
        V_ox_fixed = m_ox_end / self.OXIDIZER_DENSITY

        ullage_fuel = np.maximum(V_tank - V_fuel_fixed - V_fuel_free, 0.0)
        ullage_ox   = np.maximum(V_tank - V_ox_fixed   - V_ox_free, 0.0)

        eng_filename = f"B3_{self.version}.eng"
        with open(eng_filename, "w") as f:
            f.write(f"B3_{self.version} 240 200 0 0.001 0.001 ERT\n")
            for tt, ff in zip(t_flight, F_post):
                f.write(f"{tt:.4f} {ff:.2f}\n")
            f.write("\n")

        fuel_csv = f"ethanol_ullage_data_{self.version}.csv"
        with open(fuel_csv, "w", newline="") as f:
            writer = csv.writer(f)
            for tt, uu in zip(t_flight, ullage_fuel):
                writer.writerow([f"{tt:.6f}", f"{uu:.8f}"])

        ox_csv = f"lox_ullage_data_{self.version}.csv"
        with open(ox_csv, "w", newline="") as f:
            writer = csv.writer(f)
            for tt, uu in zip(t_flight, ullage_ox):
                writer.writerow([f"{tt:.6f}", f"{uu:.8f}"])

        lox_fluid = Fluid(name="LOX", density=self.OXIDIZER_DENSITY)
        ethanol_fluid = Fluid(name="Ethanol", density=self.FUEL_DENSITY)
        press_gas_lox = Fluid(name="N2_cold", density=self.PRESSURE_GAS_DENSITY_LOX)
        press_gas_fuel = Fluid(name="N2_warm", density=self.PRESSURE_GAS_DENSITY_FUEL)
        press_gas = Fluid(name="N2_press", density=600.0)

        tank_geom = CylindricalTank(self.TANK_RADIUS, self.TANK_LENGTH, spherical_caps=False)
        press_tank_geom = CylindricalTank(self.PRESSURE_TANK_RADIUS, self.PRESSURE_TANK_LENGTH, spherical_caps=False)

        fuel_ullage_func = Function(
            fuel_csv,
            extrapolation="zero",
            inputs="Time (s)",
            outputs="Ullage Volume (m³)",
        )
        ox_ullage_func = Function(
            ox_csv,
            extrapolation="zero",
            inputs="Time (s)",
            outputs="Ullage Volume (m³)",
        )

        lox_tank = UllageBasedTank(
            name="LOX Tank",
            flux_time=burn_time - t_break,
            geometry=tank_geom,
            gas=press_gas_lox,
            liquid=lox_fluid,
            ullage=ox_ullage_func,
        )
        ethanol_tank = UllageBasedTank(
            name="Ethanol Tank",
            flux_time=burn_time - t_break,
            geometry=tank_geom,
            gas=press_gas_fuel,
            liquid=ethanol_fluid,
            ullage=fuel_ullage_func,
        )

        def linear_mass(t):
            return max(0.0, self.PRESSURANT_MASS_INIT * (1 - t / burn_time))

        pressure_tank_1 = MassBasedTank(
            name="Pressure Tank 1",
            geometry=press_tank_geom,
            liquid_mass=0.0,
            gas_mass=linear_mass,
            flux_time=burn_time,
            gas=press_gas,
            liquid=press_gas,
        )
        pressure_tank_2 = MassBasedTank(
            name="Pressure Tank 2",
            geometry=press_tank_geom,
            liquid_mass=0.0,
            gas_mass=linear_mass,
            flux_time=burn_time,
            gas=press_gas,
            liquid=press_gas,
        )

        # ---- Assemble motor ----
        motor = LiquidMotor(
            thrust_source=eng_filename,
            dry_mass=self.LIQUID_MOTOR_DRY_MASS,
            dry_inertia=(1e-5, 1e-5, 1e-5),
            nozzle_radius=self.LIQUID_NOZZLE_RADIUS,
            center_of_dry_mass_position=1e-5,
            nozzle_position=0,
            burn_time=burn_time - t_break,
            reshape_thrust_curve=False,
            interpolation_method="linear",
            coordinate_system_orientation="nozzle_to_combustion_chamber",
        )

        base = 0.41755 + 0.756                # tail + coupler
        pos_lox = base + self.TANK_POS_HEIGHT / 2
        pos_p1  = base + self.TANK_POS_HEIGHT + self.TANK_DISTANCE - self.PRESSURE_TANK_LENGTH / 2
        pos_eth = base + self.TANK_POS_HEIGHT + self.TANK_DISTANCE + self.TANK_POS_HEIGHT / 2
        pos_p2  = base + self.TANK_POS_HEIGHT + self.TANK_DISTANCE + self.TANK_POS_HEIGHT + self.TANK_DISTANCE - self.PRESSURE_TANK_LENGTH / 2

        motor.add_tank(lox_tank, position=pos_lox)
        motor.add_tank(pressure_tank_1, position=pos_p1)
        motor.add_tank(ethanol_tank, position=pos_eth)
        motor.add_tank(pressure_tank_2, position=pos_p2)

        return motor
    
    def build_motor(self)->Motor:
        if self.motor_type == 'solid':
            self.motor = self.build_solid_motor()
            return self.motor
        elif self.motor_type == 'liquid':
            self.motor = self.build_liquid_motor()
            return self.motor
        else:
            raise ValueError(f"Unknown motor_type: {self.motor_type}")

    def build(self) -> Rocket:
        if(self.motor is None):
            self.motor = self.build_motor()

        rocket = Rocket(
            radius=self.BODY_RADIUS,
            mass=self.dry_mass,
            inertia=(131.535, 131.5725, 0.7669, 0.0067, 0.0041, -0.2543),
            power_off_drag=0.380,
            power_on_drag=0.380,
            center_of_mass_without_motor=self.cg_without_motor,
            #center_of_mass_without_motor=1.95,
            coordinate_system_orientation="tail_to_nose",
        )
        
        rocket.add_motor(self.motor, position=0)
        
        rocket.add_nose(
            length=self.nose_length,
            kind="powerseries",
            power=self.NOSE_POWER,
            position=self.body_length
        )
        
        rocket.add_trapezoidal_fins(
            n=int(self.fin_count),
            span=self.fin_span,
            root_chord=self.fin_root_chord,
            tip_chord=self.fin_tip_chord,
            sweep_length=self.fin_sweep_length,
            position=self.FIN_POSITION
        )

        rocket.add_tail(
            top_radius=self.tail_top_radius, # m
            bottom_radius=self.tail_bottom_radius, # m
            length=self.tail_length, # m
            position=self.TAIL_POSITION # m
        )

        rocket.add_parachute(
            name="reefed",
            cd_s=1.6,
            trigger="apogee",  # ejection at apogee
            sampling_rate=100, # Hz
            lag=7, # s
            noise=(0, 0, 0)
        )
        rocket.add_parachute(
            name="unreefed",
            cd_s=14.06,
            trigger=400,      # ejection 400m AGL
            sampling_rate=100,
            lag=0,
            noise=(0, 0, 0)
        )

        rocket.set_rail_buttons(self.RAIL_BUTTONS[0], self.RAIL_BUTTONS[1])
        self.rocket = rocket
        return rocket
    
    def show(self):
        if(self.rocket is None):
            self.build().draw()
        else:
            self.rocket.draw()

if __name__ == "__main__":
    from rocketpy import Flight, Environment
    import datetime
    params = {
        'motor_type': 'liquid',
        'dry_mass': 108.0,
        'fin_span': 0.196,
        'fin_root_chord': 0.712,
        'fin_tip_chord': 0.196,
        'fin_sweep_length': 0.467,
        'fin_count': 5.0,
        'fuel_mass': 8.456,
        'oxidizer_mass': 12.507,
        'nose_length': 1.010,
        'tail_length': 0.400,
        'tail_top_radius': 0.139,
        'tail_bottom_radius': 0.090,
    }
    
    builder = RocketBuilder(params)
    rocket = builder.build()
    
    print("Rocket successfully built!")
    print(f"Static margin: {rocket.static_margin(0):.2f} m")
    
    builder.show()

    # now = datetime.datetime.now(datetime.timezone.utc)
    # env = Environment(latitude=38.9627778, longitude=-8.96277777, elevation=160, date=(now.year, now.month, now.day, now.hour))
    # env.set_atmospheric_model(type="forecast", file="GFS")
    past_date = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=7)
    env = Environment(latitude=47.027868, longitude=6.901897, elevation=500, date=(past_date.year, past_date.month, past_date.day, past_date.hour))
    env.set_atmospheric_model(type="forecast", file="GFS")
    # env = Environment(latitude=38.9627778, longitude=-8.96277777, elevation=160)
    # env.set_atmospheric_model(type="standard_atmosphere")
    # env.info()

    flight = Flight(
        rocket=rocket,
        environment=env,
        rail_length=11.65,
        inclination=85.0,
        heading=144,
        terminate_on_apogee=True,
        max_time=120
    )
    flight.plots.trajectory_3d()