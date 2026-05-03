import numpy as np
from rocketpy import SolidMotor, Rocket, LiquidMotor, Motor, CylindricalTank, MassFlowRateBasedTank, Fluid, Function, MassBasedTank, UllageBasedTank

class RocketBuilder:
    # rocket dimensions
    BODY_RADIUS = 0.243/2          # m
    NOSE_LENGTH = 1.003             # m
    NOSE_POWER = 0.5
    FIN_COUNT = 4
    FIN_TIP_CHORD = 0.161           # m
    FIN_SWEEP_LENGTH = 0.539
    FIN_POSITION = 1.1315
    RAIL_BUTTONS = (0.46279, 0.4628)     # m
    TAIL_TOP_RADIUS = 0.1215 # m
    TAIL_BOTTOM_RADIUS = 0.070 # m
    TAIL_LENGTH = 0.41755 # m
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
    TANK_DISTANCE = 0.1                 # m distance oxi-fuel tanks
    PRESSURE_TANK_RADIUS = 0.0885
    PRESSURE_TANK_LENGTH = 0.570

    FUEL_DENSITY = 810.0          # kg/m^3 (ethanol)
    OXIDIZER_DENSITY = 1154.0     # kg/m^3 (LOX)
    PRESSURE_GAS_DENSITY = 600.0  # kg/m^3

    FULL_THRUST_FORCE = 6500.0      # N
    RAMP_UP_TIME = 0.4              # s
    RAMP_DOWN_TIME = 0.2            # s

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
        self.propellant_mass = params.get('propellant_mass', 8.115)
        self.burn_time = params.get('burn_time', 6.1604)
        self.motor_type = params.get('motor_type', 'solid')
        
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
        

        self.burn_time = self.total_impulse / self.FULL_THRUST_FORCE  # s

        def thrust_func(t):
            if t <= 0:
                return 0.0
            if t <= self.RAMP_UP_TIME:
                return self.FULL_THRUST_FORCE * (t / self.RAMP_UP_TIME)
            elif t <= self.burn_time - self.RAMP_DOWN_TIME:
                return self.FULL_THRUST_FORCE
            elif t <= self.burn_time:
                frac = (self.burn_time - t) / self.RAMP_DOWN_TIME
                return self.FULL_THRUST_FORCE * frac
            else:
                return 0.0

        tank_geometry = CylindricalTank(radius=self.TANK_RADIUS, height=self.TANK_LENGTH, spherical_caps=False)
        press_tank_geom = CylindricalTank(radius=self.PRESSURE_TANK_RADIUS, height=self.PRESSURE_TANK_LENGTH, spherical_caps=False)

        lox = Fluid(name="LOX", density=self.OXIDIZER_DENSITY)          # kg/m³
        ethanol = Fluid(name="Ethanol", density=self.FUEL_DENSITY)   # kg/m³
        pressurizing_gas = Fluid(name="N2", density=self.PRESSURE_GAS_DENSITY)  # placeholder

        eps = 1e-9
        ox_outflow = (self.m_ox_burn / self.burn_time) * (1 - eps)
        fuel_outflow = (self.m_fuel_burn / self.burn_time) * (1 - eps)

        lox_tank = MassFlowRateBasedTank(
            name="LOX Tank",
            geometry=tank_geometry,
            flux_time=self.burn_time,
            initial_liquid_mass=self.m_ox_burn,
            initial_gas_mass=0.1,
            liquid_mass_flow_rate_in=0.0,
            liquid_mass_flow_rate_out=ox_outflow,
            gas_mass_flow_rate_in=0.0,
            gas_mass_flow_rate_out=0.0,
            liquid=lox,
            gas=pressurizing_gas,
        )

        ethanol_tank = MassFlowRateBasedTank(
            name="Ethanol Tank",
            geometry=tank_geometry,
            flux_time=self.burn_time,
            initial_liquid_mass=self.m_fuel_burn,
            initial_gas_mass=0.1,
            liquid_mass_flow_rate_in=0.0,
            liquid_mass_flow_rate_out=fuel_outflow,
            gas_mass_flow_rate_in=0.0,
            gas_mass_flow_rate_out=0.0,
            liquid=ethanol,
            gas=pressurizing_gas,
        )

        def linear_mass(t):
            return max(0.0, self.m_press_initial * (1 - t / self.burn_time))

        pressure_tank_1 = MassBasedTank(
            name="Pressure Tank 1",
            geometry=press_tank_geom,
            liquid_mass=0.0,
            gas_mass=linear_mass,
            flux_time=self.burn_time,
            gas=pressurizing_gas,
            liquid=pressurizing_gas,
        )

        pressure_tank_2 = MassBasedTank(
            name="Pressure Tank 2",
            geometry=press_tank_geom,
            liquid_mass=0.0,
            gas_mass=linear_mass,
            flux_time=self.burn_time,
            gas=pressurizing_gas,
            liquid=pressurizing_gas,
        )

        motor = LiquidMotor(
            thrust_source=thrust_func,
            dry_mass=self.LIQUID_MOTOR_DRY_MASS,
            dry_inertia=(1e-5,1e-5,1e-5),
            nozzle_radius=self.LIQUID_NOZZLE_RADIUS,
            center_of_dry_mass_position=1e-5,
            nozzle_position=0,
            burn_time=self.burn_time,
            coordinate_system_orientation="nozzle_to_combustion_chamber",
        )

        motor.add_tank(lox_tank, position=0.41755 + 0.756 + 0.388/2)
        motor.add_tank(pressure_tank_1, position=0.41755 + 0.756 + 0.388 + 0.900 - 0.570/2)
        motor.add_tank(ethanol_tank, position=0.41755 + 0.756 + 0.388 + 0.900 + 0.388/2)
        motor.add_tank(pressure_tank_2, position=0.41755 + 0.756 + 0.388 + 0.900 + 0.388 + 0.900 - 0.570/2)
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
            inertia=(131.535, 131.5725, 0.7669, 0.0067, 0.0041, -0.2543), # From SolidWorks
            power_off_drag=0.380, # From RASAero (0,380)
            power_on_drag=0.380, # From RASAero
            center_of_mass_without_motor=self.cg_without_motor, # from OpenRocket, Payload de 3 kg dans nosecone
            #center_of_mass_without_motor=1.95, # from OpenRocket, Payload de 1 kg dans nosecone
            coordinate_system_orientation="tail_to_nose",
        )
        
        rocket.add_motor(self.motor, position=0)
        
        rocket.add_nose(
            length=self.NOSE_LENGTH,
            kind="powerseries",
            power=self.NOSE_POWER,
            position=self.body_length
        )
        
        rocket.add_trapezoidal_fins(
            n=self.FIN_COUNT,
            span=self.fin_span,
            root_chord=self.fin_root_chord,
            tip_chord=self.FIN_TIP_CHORD,
            sweep_length=self.FIN_SWEEP_LENGTH,
            position=self.FIN_POSITION
        )

        rocket.add_tail(
            top_radius=self.TAIL_TOP_RADIUS, # m
            bottom_radius=self.TAIL_BOTTOM_RADIUS, # m
            length=self.TAIL_LENGTH, # m
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