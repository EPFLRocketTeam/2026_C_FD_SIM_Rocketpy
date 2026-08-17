"""
simulator.py

Script de simulation FH2/EuRoC — fusionne les versions "constant thrust" et
"peak thrust" en un seul fichier. Le modèle de courbe de poussée et les
sorties souhaitées se choisissent directement dans l'Excel (feuilles
Propellant / Parameters), plus besoin de deux notebooks séparés.

Usage : lancer ce script tel quel (ou copier les sections dans des cellules
Jupyter, elles sont découpées par des commentaires "# ---" comme dans les
notebooks d'origine). Le fichier Excel pointé par FILE doit déjà exister et
être nommé "{version}_SIM.xlsx" pour correspondre à ce que write_to_file va
chercher à mettre à jour.
"""

# ============================================================
# Imports
# ============================================================
import sys, os
sys.path.append(os.path.join(os.getcwd(), '..', 'Excel'))

import csv
import math
import numpy as np
import matplotlib.pyplot as plt

from class_bay        import Bay
from class_structure  import read_structure
from class_propellant import read_propellant
from class_parameters import read_parameters

from rocketpy import (
    Environment, LiquidMotor, Rocket, Flight, Fluid,
    CylindricalTank, UllageBasedTank, MassBasedTank, Function,
)

# ============================================================
# Input Values
# ============================================================
# Se placer dans le dossier de ce script, peu importe d'où il est lancé.
# Résout d'un coup TOUS les chemins relatifs utilisés plus bas (lecture de
# l'Excel, écriture des .eng/.csv/.png, mise à jour de "{version}_SIM.xlsx").
# (En notebook Jupyter, __file__ n'existe pas : on garde alors le dossier
# courant du kernel, qui est déjà correct dans l'usage normal.)
try:
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
except NameError:
    pass

# Dossier de données : déduit automatiquement du fichier Excel indiqué
# ci-dessous (FILE). Change juste FILE pour chaque nouvelle run — le
# dossier qui le contient devient le dossier où tout est écrit
# (.eng, .csv, .png, "{version}_SIM.xlsx"). Le template TEMPLATE_SIM.xlsx
# lui-même reste au niveau du code, jamais modifié.
#
# Exemple : crée un dossier "v1" contenant une copie du template (par ex.
# renommée "v1.xlsx"), puis mets FILE = "v1/v1.xlsx" ci-dessous.
FILE = "Fins/Fins.xlsx"  # <-- à adapter : chemin vers TON fichier de travail

DATA_DIR = os.path.dirname(os.path.abspath(FILE)) or "."
os.makedirs(DATA_DIR, exist_ok=True)

struct = read_structure(FILE)
prop   = read_propellant(FILE)
params = read_parameters(FILE)

# Structure
mode                     = struct.mode
l_center_of_mass         = struct.l_center_of_mass
m_dry_measured           = struct.m_dry_measured
r_rocket                 = struct.r_rocket
drag_coeff_rocket        = struct.drag_coeff_rocket
top_r_bt                 = struct.top_r_bt
bottom_r_bt              = struct.bottom_r_bt
l_bt                     = struct.l_bt
m_bt                     = struct.m_bt
r_nozzle                 = struct.r_nozzle
l_ebay                   = struct.l_ebay
m_ebay                   = struct.m_ebay
pos_lox                  = struct.pos_lox
l_lox                    = struct.l_lox
m_lox                    = struct.m_lox
pos_aerocover            = struct.pos_aerocover
m_aerocover              = struct.m_aerocover
l_aerocover              = struct.l_aerocover
r_aerocover              = struct.r_aerocover
pos_copv_mbay            = struct.pos_copv_mbay
l_pbay1                  = struct.l_pbay1
m_pbay1                  = struct.m_pbay1
pos_eth                  = struct.pos_eth
l_eth                    = struct.l_eth
m_eth                    = struct.m_eth
pos_copv_pbay            = struct.pos_copv_pbay
l_pbay2                  = struct.l_pbay2
m_pbay2                  = struct.m_pbay2
l_avbay                  = struct.l_avbay
m_avbay                  = struct.m_avbay
l_rebay                  = struct.l_rebay
m_rebay                  = struct.m_rebay
drag_coeff_para_reefed   = struct.drag_coeff_para_reefed
drag_coeff_para_unreefed = struct.drag_coeff_para_unreefed
trig_alt_para            = struct.trig_alt_para
l_nosecone               = struct.l_nosecone
m_nosecone               = struct.m_nosecone
r_int                    = struct.r_int
tank_spherical_caps      = struct.tank_spherical_caps
tank_volume              = struct.tank_volume
r_int_copv               = struct.r_int_copv
copv_spherical_caps      = struct.copv_spherical_caps
copv_volume              = struct.copv_volume
n_fins                   = struct.n_fins
env_fins                 = struct.env_fins
rc_fins                  = struct.rc_fins
tc_fins                  = struct.tc_fins
pos_fins                 = struct.pos_fins
cangle_fins              = struct.cangle_fins
sweep_l_fins             = struct.sweep_l_fins
m_fins                   = struct.m_fins
pos_sup_rb               = struct.pos_sup_rb
pos_inf_rb               = struct.pos_inf_rb

# Propellant
of_ratio                          = prop.of_ratio
isp                               = prop.isp
thrust                            = prop.thrust
total_impulse                     = prop.total_impulse
thrust_curve_mode                 = prop.thrust_curve_mode
derated_thrust_in                 = prop.derated_thrust  # 0 = non spécifié -> défaut 85% du pic
lox_boil_off_mass_flow_rate       = prop.lox_boil_off
lox_prechill_mass_flow_rate       = prop.lox_prechill
lox_ignition_mass_flow_rate       = prop.lox_ignition
lox_ramp_up_mass_flow_rate        = prop.lox_ramp_up
lox_ramp_down_mass_flow_rate      = prop.lox_ramp_down
lox_cutoff_mass_flow_rate         = prop.lox_cutoff
eth_ignition_mass_flow_rate       = prop.eth_ignition
eth_ramp_up_mass_flow_rate        = prop.eth_ramp_up
eth_ramp_down_mass_flow_rate      = prop.eth_ramp_down
eth_cutoff_mass_flow_rate         = prop.eth_cutoff
eth_frac_cooling                  = prop.eth_frac_cooling
m_eth_unused                      = prop.m_eth_unused
m_eth_density                     = prop.m_eth_density
m_lox_unused                      = prop.m_lox_unused
m_lox_density                     = prop.m_lox_density
m_n2                              = prop.m_n2
hold_time                         = prop.hold_time
prechill_time                     = prop.prechill_time
ignition_delay                    = prop.ignition_delay
ramp_up_time                      = prop.ramp_up_time
cutoff_time                       = prop.cutoff_time
ramp_down_time                    = prop.ramp_down_time
f_shutdown                        = prop.f_shutdown
f_hold_down                       = prop.f_hold_down

# Parameters
version           = params.version.strip()
save_files        = params.save_files
n_points          = params.n_points
write_to_file     = params.write_to_file
output_general      = params.output_general
output_euler_angles   = params.output_euler_angles
output_stability      = params.output_stability
output_trajectory     = params.output_trajectory
output_velocity       = params.output_velocity
output_acceleration   = params.output_acceleration
output_thrust_curve   = params.output_thrust_curve
annee             = params.annee
mois              = params.mois
jour              = params.jour
heure             = params.heure
minute            = params.minute
latitude          = params.latitude
longitude         = params.longitude
elevation         = params.elevation
alpha_rail        = params.alpha_rail
beta_rail         = params.beta_rail
l_rail            = params.l_rail
coeff_fr_rail     = params.coeff_fr_rail
inclination_rail  = params.inclination_rail
heading_rail      = params.heading_rail
g = 9.80665

# ============================================================
# Rocket
# ============================================================
Boattail        = Bay("Boattail",          0,                                             0,         r_rocket,    l_bt,          m_bt,              "cylindrical")
EngineBay       = Bay("EngineBay",         Boattail.length,                               0,         r_rocket,    l_ebay,        m_ebay+m_fins,            "tank")
LOx             = Bay("LOx",               EngineBay.z + EngineBay.length,                0,         r_rocket,    l_lox,         m_lox,             "tank")
Aerocover       = Bay("Aerocover",         pos_aerocover,                                 r_rocket,  r_aerocover, l_aerocover,   m_aerocover,       "semi-cylindrical")
PressurantBay1  = Bay("PressurantBay1",    LOx.z + LOx.length,                            0,         r_rocket,    l_pbay1,       m_pbay1,           "cylindrical")
ETH             = Bay("ETH",               PressurantBay1.z + PressurantBay1.length,      0,         r_rocket,    l_eth,         m_eth,             "tank")
PressurantBay2  = Bay("PressurantBay2",    ETH.z + ETH.length,                            0,         r_rocket,    l_pbay2,       m_pbay2,           "cylindrical")
AVBay           = Bay("AVBay",             PressurantBay2.z + PressurantBay2.length,      0,         r_rocket,    l_avbay,       m_avbay,           "cylindrical")
RecoveryBay     = Bay("RecoveryBay",       AVBay.z + AVBay.length,                        0,         r_rocket,    l_rebay,       m_rebay,           "cylindrical")
Nosecone        = Bay("Nosecone",          RecoveryBay.z + RecoveryBay.length,            0,         r_rocket,    l_nosecone,    m_nosecone,        "conical")

rocket = [Boattail, EngineBay, LOx, Aerocover, PressurantBay1, ETH, PressurantBay2, AVBay, RecoveryBay, Nosecone]


# ============================================================
# CoM et moment d'inertie
# ============================================================
if mode == 0:
    m_dry = sum(bay.mass for bay in rocket)

    z_cm = 0
    y_cm = 0

    for bay in rocket:
        z_local, y_local = bay.center_masse()
        z_cm += bay.mass * (bay.z + z_local)
        y_cm += bay.mass * (bay.y + y_local)

    z_cm /= m_dry
    y_cm /= m_dry

    Ix = 0
    Iy = 0
    Iz = 0

    for bay in rocket:
        z_local, y_local = bay.center_masse()
        z_bay_cm = bay.z + z_local
        y_bay_cm = bay.y + y_local
        dz = z_bay_cm - z_cm
        dy = y_bay_cm - y_cm
        dx = 0  # suppose symmetry

        Ix_local, Iy_local, Iz_local = bay.moment_of_inertia()

        Ix += Ix_local + bay.mass * (dy**2 + dz**2)
        Iy += Iy_local + bay.mass * (dx**2 + dz**2)
        Iz += Iz_local + bay.mass * (dx**2 + dy**2)
elif mode == 1:
    m_dry = m_dry_measured + sum(bay.mass for bay in rocket)
    
    z_cm = l_center_of_mass * m_dry_measured
    y_cm = 0

    for bay in rocket:
        z_local, y_local = bay.center_masse()
        # print(bay.nom, bay.mass)
        z_cm += bay.mass * (bay.z + z_local)
        y_cm += bay.mass * (bay.y + y_local)

    z_cm /= m_dry
    y_cm /= m_dry

    # z_cm -= 0.1

    # Hardcoded the model (EuRoC_1)
    Ix = 242.7543433720102
    Iy = 242.71214558814867
    Iz = 0.9012818783579469

    # for bay in rocket:
    #     z_local, y_local = bay.center_masse()
    #     z_bay_cm = bay.z + z_local
    #     y_bay_cm = bay.y + y_local
    #     dz = z_bay_cm - z_cm
    #     dy = y_bay_cm - y_cm
    #     dx = 0  # suppose symmetry

    #     Ix_local, Iy_local, Iz_local = bay.moment_of_inertia()

    #     Ix += Ix_local + bay.mass * (dy**2 + dz**2)
    #     Iy += Iy_local + bay.mass * (dx**2 + dz**2)
    #     Iz += Iz_local + bay.mass * (dx**2 + dy**2)
else:
    m_dry = 0
    Ix = 0
    Iy = 0
    Iz = 0
    raise ValueError(
        "Mode has to be 0 or 1."
        "Setting dry mass and inertia to 0."
    )

# print(m_dry, Ix, Iy, Iz, z_cm, y_cm)

# ============================================================
# Propulsion reference quantities
# ============================================================

F_full_thrust = float(thrust)
F_shutdown = float(f_shutdown)

if F_full_thrust <= 0:
    raise ValueError("thrust must be strictly positive.")

if total_impulse <= 0:
    raise ValueError("total_impulse must be strictly positive.")

if isp <= 0:
    raise ValueError("isp must be strictly positive.")

if of_ratio <= 0:
    raise ValueError("of_ratio must be strictly positive.")

if F_shutdown < 0:
    raise ValueError("f_shutdown cannot be negative.")

if (
    ramp_up_time < 0
    or ramp_down_time < 0
    or cutoff_time < 0
):
    raise ValueError(
        "Engine phase durations must be non-negative."
    )


# ------------------------------------------------------------
# Core flow at full nominal thrust
# ------------------------------------------------------------

# This flow corresponds to the quoted CORE Isp.
engine_mass_flow_rate = (
    F_full_thrust
    / (isp * g)
)

# Main-injector fuel flow
eth_mass_flow_rate = (
    engine_mass_flow_rate
    / (1.0 + of_ratio)
)

# Main-injector LOX flow
lox_burn_mass_flow_rate = (
    engine_mass_flow_rate
    - eth_mass_flow_rate
)

# Film cooling is additional ethanol and is not contained in
# the core Isp.
film_cooling_mass_flow_rate = (
    eth_mass_flow_rate
    * eth_frac_cooling
)

eth_burn_mass_flow_rate = (
    eth_mass_flow_rate
    + film_cooling_mass_flow_rate
)

# Equivalent rectangle thrust curve burn time
equivalent_burn_time = (
    total_impulse
    / F_full_thrust
)


# ============================================================
# Thrust curve timing
# ============================================================

# Ramp-up is modeled as linear:
#
#        0 N -> F_full_thrust
#
impulse_ramp_up = (
    0.5
    * F_full_thrust
    * ramp_up_time
)

# Cutoff is modeled as:
#
#        F_shutdown -> 0 N
#
# If F_shutdown = 0, this phase contributes zero impulse even
# though propellant may still be expelled.
impulse_cutoff = (
    0.5
    * F_shutdown
    * cutoff_time
)

t_rampup_end = ramp_up_time


# ============================================================
# CONSTANT THRUST MODE
# ============================================================

if thrust_curve_mode == "constant":

    F_derating = F_full_thrust
    F_ramp_down = F_full_thrust

    if F_shutdown > F_ramp_down:
        raise ValueError(
            "f_shutdown cannot exceed thrust at the start "
            "of ramp-down."
        )

    # Linear ramp-down:
    #
    # F_full_thrust -> F_shutdown
    #
    impulse_ramp_down = (
        0.5
        * (F_ramp_down + F_shutdown)
        * ramp_down_time
    )

    # Solve the flat duration needed to reach total_impulse.
    flat_duration = (
        total_impulse
        - impulse_ramp_up
        - impulse_ramp_down
        - impulse_cutoff
    ) / F_full_thrust

    if flat_duration < 0:
        raise ValueError(
            "Cannot match total_impulse with the requested "
            "ramp-up, ramp-down and cutoff phases. "
            "The non-flat phases already consume too much impulse."
        )

    t_full_thrust = t_rampup_end

    t_ramp_down = (
        t_full_thrust
        + flat_duration
    )

    t_shutdown = (
        t_ramp_down
        + ramp_down_time
    )

    t_cutoff_end = (
        t_shutdown
        + cutoff_time
    )

    # Physical elapsed duration of the main-combustion phase.
    main_phase_duration = flat_duration

    # Main-phase impulse only:
    # excludes ramp-up, ramp-down and cutoff.
    main_impulse_total = (
        F_full_thrust
        * flat_duration
    )

    def main_impulse_elapsed(t):
        """
        Thrust impulse accumulated during the main-combustion
        phase only.
        """

        t = np.asarray(
            t,
            dtype=float,
        )

        dt_main = np.clip(
            t - t_rampup_end,
            0.0,
            flat_duration,
        )

        return (
            F_full_thrust
            * dt_main
        )

    def evaluate_thrust(t):
        """
        Full physical thrust curve from beginning of ramp-up
        through end of cutoff.
        """

        t = np.asarray(
            t,
            dtype=float,
        )

        F_out = np.zeros_like(t)

        # Ramp-up
        if ramp_up_time > 0:

            mask = (
                (t >= 0.0)
                & (t <= t_rampup_end)
            )

            F_out[mask] = (
                F_full_thrust
                * t[mask]
                / ramp_up_time
            )

        else:

            F_out[t >= 0.0] = (
                F_full_thrust
            )

        # Constant main burn
        mask = (
            (t > t_rampup_end)
            & (t <= t_ramp_down)
        )

        F_out[mask] = (
            F_full_thrust
        )

        # Ramp-down
        if ramp_down_time > 0:

            mask = (
                (t > t_ramp_down)
                & (t <= t_shutdown)
            )

            u = (
                (t[mask] - t_ramp_down)
                / ramp_down_time
            )

            F_out[mask] = (
                F_ramp_down
                + (
                    F_shutdown
                    - F_ramp_down
                )
                * u
            )

        # Cutoff
        if cutoff_time > 0:

            mask = (
                (t > t_shutdown)
                & (t <= t_cutoff_end)
            )

            u = (
                (t[mask] - t_shutdown)
                / cutoff_time
            )

            F_out[mask] = (
                F_shutdown
                * (1.0 - u)
            )

        return np.maximum(
            F_out,
            0.0,
        )


# ============================================================
# PEAKED / DERATED MODE
# ============================================================

elif thrust_curve_mode == "peaked":

    peak_duration_factor = 1.5

    F_derating = (
        derated_thrust_in
        if derated_thrust_in > 0
        else 0.85 * F_full_thrust
    )

    if (
        F_derating <= 0
        or F_derating > F_full_thrust
    ):
        raise ValueError(
            "derated thrust must be > 0 and <= nominal thrust."
        )

    if F_shutdown > F_derating:
        raise ValueError(
            "f_shutdown cannot exceed the derated thrust "
            "at the start of ramp-down."
        )


    # Duration of full-thrust -> derated transition
    t_peak_transition = (
        (peak_duration_factor - 1.0)
        * ramp_up_time
    )

    t_derate_end = (
        t_rampup_end
        + t_peak_transition
    )


    impulse_transition = (
        0.5
        * (
            F_full_thrust
            + F_derating
        )
        * t_peak_transition
    )


    impulse_ramp_down = (
        0.5
        * (
            F_derating
            + F_shutdown
        )
        * ramp_down_time
    )


    # Solve actual derated plateau duration.
    t_const = (
        total_impulse
        - impulse_ramp_up
        - impulse_transition
        - impulse_ramp_down
        - impulse_cutoff
    ) / F_derating

    if t_const < 0:
        raise ValueError(
            "Cannot match total_impulse with the requested "
            "peak, derating, ramp-down and cutoff phases."
        )


    t_full_thrust = (
        t_rampup_end
    )

    t_ramp_down = (
        t_derate_end
        + t_const
    )

    t_shutdown = (
        t_ramp_down
        + ramp_down_time
    )

    t_cutoff_end = (
        t_shutdown
        + cutoff_time
    )


    main_phase_duration = (
        t_peak_transition
        + t_const
    )


    main_impulse_total = (
        impulse_transition
        + F_derating * t_const
    )


    def main_impulse_elapsed(t):
        """
        Main-phase impulse accumulated after ramp-up and before
        ramp-down.

        During this phase, main propellant flow scales with thrust.
        """

        t = np.asarray(
            t,
            dtype=float,
        )

        u = np.clip(
            t - t_rampup_end,
            0.0,
            main_phase_duration,
        )


        if t_peak_transition > 0:

            u_transition = np.minimum(
                u,
                t_peak_transition,
            )

            # Integral of the linearly derating thrust.
            I_transition_partial = (
                F_full_thrust
                * u_transition
                + 0.5
                * (
                    F_derating
                    - F_full_thrust
                )
                / t_peak_transition
                * u_transition**2
            )

            return np.where(
                u <= t_peak_transition,

                I_transition_partial,

                impulse_transition
                + F_derating
                * (
                    u
                    - t_peak_transition
                ),
            )


        return (
            F_derating
            * u
        )


    def evaluate_thrust(t):
        """
        Full peaked/derated physical thrust curve.
        """

        t = np.asarray(
            t,
            dtype=float,
        )

        F_out = np.zeros_like(t)


        # Ramp-up
        if ramp_up_time > 0:

            mask = (
                (t >= 0.0)
                & (t <= t_rampup_end)
            )

            F_out[mask] = (
                F_full_thrust
                * t[mask]
                / ramp_up_time
            )

        else:

            F_out[t >= 0.0] = (
                F_full_thrust
            )


        # Peak -> derated transition
        if t_peak_transition > 0:

            mask = (
                (t > t_rampup_end)
                & (t <= t_derate_end)
            )

            u = (
                (t[mask] - t_rampup_end)
                / t_peak_transition
            )

            F_out[mask] = (
                F_full_thrust
                + (
                    F_derating
                    - F_full_thrust
                )
                * u
            )


        # Derated plateau
        mask = (
            (t > t_derate_end)
            & (t <= t_ramp_down)
        )

        F_out[mask] = (
            F_derating
        )


        # Ramp-down
        if ramp_down_time > 0:

            mask = (
                (t > t_ramp_down)
                & (t <= t_shutdown)
            )

            u = (
                (t[mask] - t_ramp_down)
                / ramp_down_time
            )

            F_out[mask] = (
                F_derating
                + (
                    F_shutdown
                    - F_derating
                )
                * u
            )


        # Cutoff
        if cutoff_time > 0:

            mask = (
                (t > t_shutdown)
                & (t <= t_cutoff_end)
            )

            u = (
                (t[mask] - t_shutdown)
                / cutoff_time
            )

            F_out[mask] = (
                F_shutdown
                * (1.0 - u)
            )


        return np.maximum(
            F_out,
            0.0,
        )

else:
    raise ValueError(
        f"Unknown thrust_curve_mode: "
        f"{thrust_curve_mode!r} "
        "(expected 'constant' or 'peaked')."
    )


# ============================================================
# Master propulsion time vector + thrust curve
# ============================================================

if int(n_points) < 2:
    raise ValueError(
        "n_points must be >= 2."
    )

t_base = np.linspace(
    0.0,
    t_cutoff_end,
    int(n_points),
)

phase_times = [
    0.0,
    t_rampup_end,
    t_ramp_down,
    t_shutdown,
    t_cutoff_end,
]

if thrust_curve_mode == "peaked":
    phase_times.append(t_derate_end)

t_total = np.unique(
    np.concatenate(
        [
            t_base,
            np.asarray(phase_times, dtype=float),
        ]
    )
)

t_total.sort()

F = evaluate_thrust(t_total)

F_eng = F

# Numerical verification only
# The phase timing above is solved analytically to hit total_impulse
computed_impulse = np.trapezoid(
    F_eng,
    t_total,
)

if not np.isclose(
    computed_impulse,
    total_impulse,
    rtol=1e-4,
    atol=1.0,
):
    raise RuntimeError(
        "Generated thrust curve impulse does not match "
        f"target: {computed_impulse:.2f} vs "
        f"{total_impulse:.2f} N.s"
    )

print(
    "\n========== THRUST CURVE =========="
)

print(
    f"Mode: {thrust_curve_mode}"
)

print(
    f"Equivalent rectangular burn time : "
    f"{equivalent_burn_time:.4f} s"
)

print(
    f"Main physical phase duration      : "
    f"{main_phase_duration:.4f} s"
)

print(
    f"End of thrust ramp-down           : "
    f"{t_shutdown:.4f} s"
)

print(
    f"End of cutoff / propellant flow   : "
    f"{t_cutoff_end:.4f} s"
)

print(
    f"Integrated impulse                : "
    f"{computed_impulse:.2f} N.s "
    f"(target {total_impulse:.2f} N.s)"
)

print(
    "==================================\n"
)

# This is the main combustion phase (no longer the full burn duration)
# burn_time = (
#     main_impulse_total
#     / F_full_thrust
# )


# ============================================================
# Propellant phase masses
# ============================================================

# ------------------------------------------------------------
# PRE-t=0 losses
# ------------------------------------------------------------

# TODO: use sign of ignition_delay to determine 0 flow rate for either lox or eth
m_fuel_ignition = (
    eth_ignition_mass_flow_rate
    * abs(ignition_delay)
)

m_ox_boil_off = (
    lox_boil_off_mass_flow_rate
    * hold_time
)

m_ox_prechill = (
    lox_prechill_mass_flow_rate
    * prechill_time
)

m_ox_ignition = (
    lox_ignition_mass_flow_rate
    * abs(ignition_delay)
)

# ------------------------------------------------------------
# POST-t=0 expendable propellant
# ------------------------------------------------------------

m_fuel_rampup = (
    eth_ramp_up_mass_flow_rate
    * ramp_up_time
)

m_ox_rampup = (
    lox_ramp_up_mass_flow_rate
    * ramp_up_time
)

# Main combustion propellant.
#
# Since core Isp is tied to thrust, the main-flow mass is tied
# to the actual main-phase impulse.
#
# This automatically handles the derated region in peaked mode.
m_fuel_burn = (
    eth_burn_mass_flow_rate
    * main_impulse_total
    / F_full_thrust
)

m_ox_burn = (
    lox_burn_mass_flow_rate
    * main_impulse_total
    / F_full_thrust
)

m_fuel_rampdown = (
    eth_ramp_down_mass_flow_rate
    * ramp_down_time
)

m_ox_rampdown = (
    lox_ramp_down_mass_flow_rate
    * ramp_down_time
)

# TODO: use sign of cutoff_time to determine 0 flow rate for either lox or eth
m_fuel_cutoff = (
    eth_cutoff_mass_flow_rate
    * cutoff_time
)

m_ox_cutoff = (
    lox_cutoff_mass_flow_rate
    * cutoff_time
)

m_fuel_unused = m_eth_unused

m_ox_unused = m_lox_unused

# All liquid that leaves after t=0.
free_fuel = (
    m_fuel_rampup
    + m_fuel_burn
    + m_fuel_rampdown
    + m_fuel_cutoff
)

free_ox = (
    m_ox_rampup
    + m_ox_burn
    + m_ox_rampdown
    + m_ox_cutoff
)

# Total amount loaded before pre-start losses.
m_fuel_total = (
    m_fuel_ignition
    + free_fuel
    + m_fuel_unused
)

m_ox_total = (
    m_ox_boil_off
    + m_ox_prechill
    + m_ox_ignition
    + free_ox
    + m_ox_unused
)

# Two identical COPVs
m_n2_copv = m_n2


m_wet = (
    m_dry
    + m_fuel_total
    + m_ox_total
    + 2.0 * m_n2_copv
)


nominal_total_impulse = total_impulse


# ============================================================
# Exact propellant depletion
# ============================================================

def compute_propellant_depletion(
    t,
    rampup_mdot,
    burn_mdot_full,
    rampdown_mdot,
    cutoff_mdot,
):
    """
    Exact cumulative depletion from t = 0.

    rampup_mdot, rampdown_mdot and cutoff_mdot are phase-average
    mass-flow rates supplied by the user.

    During the main-combustion phase, flow scales with thrust so
    that the core Isp / O-F model remains consistent.
    """

    t = np.asarray(
        t,
        dtype=float,
    )

    # Ramp-up elapsed time
    dt_rampup = np.clip(
        t,
        0.0,
        ramp_up_time,
    )

    # Ramp-down elapsed time
    dt_rampdown = np.clip(
        t - t_ramp_down,
        0.0,
        ramp_down_time,
    )

    # Cutoff elapsed time
    dt_cutoff = np.clip(
        t - t_shutdown,
        0.0,
        cutoff_time,
    )

    # Main-combustion impulse elapsed
    main_impulse = main_impulse_elapsed(t)

    consumed = (
        rampup_mdot
        * dt_rampup
        + (
            burn_mdot_full
            / F_full_thrust
            * main_impulse
        )
        + rampdown_mdot
        * dt_rampdown
        + cutoff_mdot
        * dt_cutoff
    )

    free_mass = (
        rampup_mdot
        * ramp_up_time
        + (
            burn_mdot_full
            / F_full_thrust
            * main_impulse_total
        )
        + rampdown_mdot
        * ramp_down_time
        + cutoff_mdot
        * cutoff_time
    )

    mrem = np.maximum(
        free_mass - consumed,
        0.0,
    )

    return consumed, mrem, free_mass

# Fuel
(
    consumed_fuel,
    mrem_fuel,
    free_fuel_check,
) = compute_propellant_depletion(
    t=t_total,
    rampup_mdot=eth_ramp_up_mass_flow_rate,
    burn_mdot_full=eth_burn_mass_flow_rate,
    rampdown_mdot=eth_ramp_down_mass_flow_rate,
    cutoff_mdot=eth_cutoff_mass_flow_rate,
)

# LOX
(
    consumed_ox,
    mrem_ox,
    free_ox_check,
) = compute_propellant_depletion(
    t=t_total,
    rampup_mdot=lox_ramp_up_mass_flow_rate,
    burn_mdot_full=lox_burn_mass_flow_rate,
    rampdown_mdot=lox_ramp_down_mass_flow_rate,
    cutoff_mdot=lox_cutoff_mass_flow_rate,
)


# ============================================================
# Pointwise mass flow rate arrays
# ============================================================

# These are mainly useful for diagnostics / plotting.
# The cumulative consumption above is analytic and therefore does
# not suffer from phase-boundary integration error.

mdot_fuel = np.zeros_like(t_total)

mdot_ox = np.zeros_like(t_total)


# Ramp-up
mask = (
    (t_total >= 0.0)
    & (t_total < t_rampup_end)
)

mdot_fuel[mask] = eth_ramp_up_mass_flow_rate

mdot_ox[mask] = lox_ramp_up_mass_flow_rate


# Main combustion
mask = (
    (t_total >= t_rampup_end)
    & (t_total < t_ramp_down)
)

mdot_scale = np.zeros_like(t_total)

mdot_scale[mask] = (
    F_eng[mask]
    / F_full_thrust
)

mdot_fuel[mask] = (
    eth_burn_mass_flow_rate
    * mdot_scale[mask]
)

mdot_ox[mask] = (
    lox_burn_mass_flow_rate
    * mdot_scale[mask]
)


# Ramp-down
mask = (
    (t_total >= t_ramp_down)
    & (t_total < t_shutdown)
)

mdot_fuel[mask] = eth_ramp_down_mass_flow_rate

mdot_ox[mask] = lox_ramp_down_mass_flow_rate


# Cutoff
mask = (
    (t_total >= t_shutdown)
    & (t_total <= t_cutoff_end)
)

mdot_fuel[mask] = eth_cutoff_mass_flow_rate

mdot_ox[mask] = lox_cutoff_mass_flow_rate


# Remaining liquid volume
Vrem_fuel = (
    mrem_fuel
    / m_eth_density
)

Vrem_ox = (
    mrem_ox
    / m_lox_density
)


# ============================================================
# Tank quantities
# ============================================================

A_tank = (
    np.pi
    * r_int**2
)

V_tank_total = (
    tank_volume
)


V_fuel_free = (
    free_fuel
    / m_eth_density
)

V_fuel_fixed = (
    m_fuel_unused
    / m_eth_density
)


V_ox_free = (
    free_ox
    / m_lox_density
)

V_ox_fixed = (
    m_ox_unused
    / m_lox_density
)


h_fuel_free = (
    V_fuel_free
    / A_tank
)

h_ox_free = (
    V_ox_free
    / A_tank
)


# ============================================================
# Vehicle mass from t = 0 onward
# ============================================================

mass_lost_fuel_before_t0 = (
    m_fuel_ignition
)

mass_lost_ox_before_t0 = (
    m_ox_boil_off
    + m_ox_prechill
    + m_ox_ignition
)

m_wet_t0 = (
    m_wet
    - mass_lost_fuel_before_t0
    - mass_lost_ox_before_t0
)

m_vehicle = (
    m_wet_t0
    - consumed_fuel
    - consumed_ox
)


# ============================================================
# Hold-down and rail exit
# ============================================================

alpha = np.deg2rad(alpha_rail)

beta = np.deg2rad(beta_rail)

t_array = t_total

denominator = (
    np.cos(beta)
    - coeff_fr_rail
    * np.sin(beta)
)


if np.isclose(denominator, 0.0):
    raise ValueError(
        "Hold-down force denominator is approximately zero."
    )

W = m_vehicle * g

F_HD = (
    F_eng
    - W
    * (
        np.cos(alpha)
        - coeff_fr_rail
        * np.sin(alpha)
    )
) / denominator

F_rrb = (
    F_eng
    * np.sin(beta)
    + W
    * np.sin(alpha - beta)
) / denominator


# ------------------------------------------------------------
# Hold-down release
# ------------------------------------------------------------

# TODO: refine idx_break with interpolation 
if f_hold_down > 0:
    mask_break = F_HD >= f_hold_down

    if np.any(mask_break):
        idx_break = int(np.argmax(mask_break))
        t_break = t_array[idx_break]

    else:
        raise ValueError(
            "Hold-down threshold not reached during propulsion."
        )

else:
    idx_break = 0
    t_break = t_array[0]


# ============================================================
# Propellant lost before hold-down release
# ============================================================

mass_lost_fuel_before_break = (
    mass_lost_fuel_before_t0
    + consumed_fuel[idx_break]
)


mass_lost_ox_before_break = (
    mass_lost_ox_before_t0
    + consumed_ox[idx_break]
)


# ============================================================
# Rail motion
# ============================================================

# a_LV = (
#     F_eng
#     - m_vehicle
#     * g
#     * np.cos(alpha)
# ) / m_vehicle


# a_LV[a_LV < 0.0] = 0.0


# v = np.zeros_like(a_LV)

# s = np.zeros_like(a_LV)


# for i in range(idx_break + 1, len(t_array)):
#     dt_i = (
#         t_array[i]
#         - t_array[i - 1]
#     )

#     v[i] = (
#         v[i - 1]
#         + a_LV[i - 1]
#         * dt_i
#     )

#     s[i] = (
#         s[i - 1]
#         + v[i - 1]
#         * dt_i
#     )


# mask_exit = s >= l_rail


# if np.any(mask_exit):
#     idx_exit = int(np.argmax(mask_exit))
# else:
#     raise ValueError(
#         "Rocket did not clear the rail within the propulsion timeline."
#     )


# ============================================================
# Consistency checks
# ============================================================

if not np.isclose(
    free_fuel,
    free_fuel_check,
    rtol=1e-10,
    atol=1e-10,
):
    raise RuntimeError(
        "Fuel depletion is inconsistent."
    )


if not np.isclose(
    free_ox,
    free_ox_check,
    rtol=1e-10,
    atol=1e-10,
):
    raise RuntimeError(
        "LOX depletion is inconsistent."
    )


if not np.isclose(
    consumed_fuel[-1],
    free_fuel,
    rtol=1e-10,
    atol=1e-10,
):
    raise RuntimeError(
        "Fuel is not fully depleted by end of cutoff."
    )


if not np.isclose(
    consumed_ox[-1],
    free_ox,
    rtol=1e-10,
    atol=1e-10,
):
    raise RuntimeError(
        "LOX is not fully depleted by end of cutoff."
    )


print(
    "\n========== PROPELLANT =========="
)

print(
    f"Fuel total loaded       : "
    f"{m_fuel_total:.4f} kg"
)

print(
    f"LOX total loaded        : "
    f"{m_ox_total:.4f} kg"
)

print(
    f"Wet mass after filling  : "
    f"{m_wet:.4f} kg"
)

print(
    f"Vehicle mass at t=0     : "
    f"{m_wet_t0:.4f} kg"
)

print(
    f"Hold-down release       : "
    f"{t_break:.4f} s"
)

print(
    f"Vehicle mass at release : "
    f"{m_vehicle[idx_break]:.4f} kg"
)

print(
    f"Fuel lost before release: "
    f"{mass_lost_fuel_before_break:.4f} kg"
)

print(
    f"LOX lost before release : "
    f"{mass_lost_ox_before_break:.4f} kg"
)

print(
    "================================\n"
)



# ============================================================
# Ullage
# ============================================================

raw_ullage_fuel_m3 = (
    V_tank_total
    - V_fuel_fixed
    - Vrem_fuel
)

raw_ullage_lox_m3 = (
    V_tank_total
    - V_ox_fixed
    - Vrem_ox
)


tol_ullage = 1e-9


if np.any(
    raw_ullage_fuel_m3
    < -tol_ullage
):
    raise ValueError(
        "Fuel tank is overfilled in the depletion model."
    )

if np.any(
    raw_ullage_lox_m3
    < -tol_ullage
):
    raise ValueError(
        "LOX tank is overfilled in the depletion model."
    )


ullage_fuel_m3 = np.maximum(
    raw_ullage_fuel_m3,
    0.0,
)

ullage_lox_m3 = np.maximum(
    raw_ullage_lox_m3,
    0.0,
)

L_PER_M3 = 1000.0

def ullage_from_liquid_volume(
    V_tank,
    V_liquid,
    name="Tank",
):

    V_ullage = V_tank - V_liquid

    if V_ullage < -tol_ullage:
        raise ValueError(
            f"{name} is overfilled by "
            f"{-V_ullage * L_PER_M3:.3f} L "
            f"(liquid={V_liquid * L_PER_M3:.3f} L, "
            f"tank={V_tank * L_PER_M3:.3f} L)"
        )

    V_ullage = max(
        V_ullage,
        0.0,
    )

    ullage_L = V_ullage * L_PER_M3

    ullage_pct = (
        100.0
        * V_ullage
        / V_tank
    )

    return V_ullage, ullage_L, ullage_pct


# ------------------------------------------------------------
# Immediately after filling
# ------------------------------------------------------------

V_fuel_filled = (
    m_fuel_total
    / m_eth_density
)


V_lox_filled = (
    m_ox_total
    / m_lox_density
)


(
    _,
    ullage_fuel_fill_L,
    ullage_fuel_fill_pct,
) = ullage_from_liquid_volume(
    V_tank_total,
    V_fuel_filled,
    "Fuel tank after filling",
)


(
    _,
    ullage_lox_fill_L,
    ullage_lox_fill_pct,
) = ullage_from_liquid_volume(
    V_tank_total,
    V_lox_filled,
    "LOX tank after filling",
)


# ------------------------------------------------------------
# t = 0: after pre-start losses, before ramp-up
# ------------------------------------------------------------

V_fuel_t0 = (
    V_fuel_fixed
    + V_fuel_free
)


V_lox_t0 = (
    V_ox_fixed
    + V_ox_free
)


(
    _,
    ullage_fuel_t0_L,
    ullage_fuel_t0_pct,
) = ullage_from_liquid_volume(
    V_tank_total,
    V_fuel_t0,
    "Fuel tank at t=0",
)


(
    _,
    ullage_lox_t0_L,
    ullage_lox_t0_pct,
) = ullage_from_liquid_volume(
    V_tank_total,
    V_lox_t0,
    "LOX tank at t=0",
)


# ------------------------------------------------------------
# Hold-down release
# ------------------------------------------------------------

V_fuel_release = (
    V_fuel_fixed
    + Vrem_fuel[idx_break]
)


V_lox_release = (
    V_ox_fixed
    + Vrem_ox[idx_break]
)


(
    _,
    ullage_fuel_release_L,
    ullage_fuel_release_pct,
) = ullage_from_liquid_volume(
    V_tank_total,
    V_fuel_release,
    "Fuel tank at hold-down release",
)


(
    _,
    ullage_lox_release_L,
    ullage_lox_release_pct,
) = ullage_from_liquid_volume(
    V_tank_total,
    V_lox_release,
    "LOX tank at hold-down release",
)


print("\n================ ULLAGE =================")

print("Immediately after filling:")

print(
    f"  Fuel : "
    f"{ullage_fuel_fill_L:.2f} L "
    f"({ullage_fuel_fill_pct:.2f} %)"
)

print(
    f"  LOX  : "
    f"{ullage_lox_fill_L:.2f} L "
    f"({ullage_lox_fill_pct:.2f} %)"
)


print("\nAt t=0 (start of ramp-up):")

print(
    f"  Fuel : "
    f"{ullage_fuel_t0_L:.2f} L "
    f"({ullage_fuel_t0_pct:.2f} %)"
)

print(
    f"  LOX  : "
    f"{ullage_lox_t0_L:.2f} L "
    f"({ullage_lox_t0_pct:.2f} %)"
)


print(
    f"\nAt hold-down release "
    f"(t={t_break:.3f} s):"
)

print(
    f"  Fuel : "
    f"{ullage_fuel_release_L:.2f} L "
    f"({ullage_fuel_release_pct:.2f} %)"
)

print(
    f"  LOX  : "
    f"{ullage_lox_release_L:.2f} L "
    f"({ullage_lox_release_pct:.2f} %)"
)

print("=========================================\n")


# ============================================================
# RocketPy flight-time thrust and ullage files
# ============================================================

mask_after_break = t_total >= t_break


# RocketPy motor time zero = hold-down release.
t_flight = t_total[mask_after_break] - t_break


F_flight = F_eng[mask_after_break].copy()


if len(t_flight) < 2:
    raise RuntimeError(
        "Not enough time points after hold-down release."
    )


# ============================================================
# Thrust curve plot
# Full propulsion curve + portion actually fed to RocketPy
# ============================================================

# ------------------------------------------------------------
# Construct exact pre-release curve
# ------------------------------------------------------------

F_break = float(
    np.interp(
        t_break,
        t_total,
        F_eng,
    )
)

mask_before_break = (
    t_total < t_break
)

t_hold_down = np.concatenate(
    (
        t_total[mask_before_break],
        [t_break],
    )
)

F_hold_down = np.concatenate(
    (
        F_eng[mask_before_break],
        [F_break],
    )
)


# ------------------------------------------------------------
# RocketPy curve on the original engine-time axis
# ------------------------------------------------------------

# t_flight has t = 0 at hold-down release.
# Shift it back to the master engine clock for this plot.
t_rocketpy_plot = t_flight + t_break


# ------------------------------------------------------------
# Impulse split
# ------------------------------------------------------------

impulse_hold_down = np.trapezoid(
    F_hold_down,
    t_hold_down,
)

impulse_rocketpy = np.trapezoid(
    F_flight,
    t_flight,
)

impulse_fraction_lost = (
    100.0
    * impulse_hold_down
    / nominal_total_impulse
)


# ------------------------------------------------------------
# Plot
# ------------------------------------------------------------

fig, ax = plt.subplots(
    figsize=(9, 5.5)
)


# Thrust lost before release
ax.plot(
    t_hold_down,
    F_hold_down,
    color="red",
    linewidth=2.2,
    label="Thrust during hold-down",
)


# Shaded area showing lost impulse
ax.fill_between(
    t_hold_down,
    0.0,
    F_hold_down,
    color="red",
    alpha=0.12,
)


# Actual thrust curve passed to RocketPy
ax.plot(
    t_rocketpy_plot,
    F_flight,
    color="dodgerblue",
    linewidth=2.2,
    label="Thrust fed to RocketPy",
)


# Hold-down release marker
ax.axvline(
    t_break,
    color="black",
    linestyle="--",
    linewidth=1.2,
    label=f"Hold-down release: {t_break:.3f} s",
)


ax.set_title(
    f"Thrust Curve — {thrust_curve_mode.capitalize()} Mode"
)

ax.set_xlabel(
    "Time from start of ramp-up [s]"
)

ax.set_ylabel(
    "Thrust [N]"
)

ax.grid(
    True,
    which="both",
    linestyle="--",
    linewidth=0.5,
    alpha=0.6,
)


# ------------------------------------------------------------
# Impulse information
# ------------------------------------------------------------

textstr = (
    f"Nominal impulse: {nominal_total_impulse:.1f} N·s\n"
    f"Hold-down impulse: {impulse_hold_down:.1f} N·s "
    f"({impulse_fraction_lost:.2f}%)\n"
    f"RocketPy impulse: {impulse_rocketpy:.1f} N·s"
)

ax.text(
    0.98,
    0.96,
    textstr,
    transform=ax.transAxes,
    horizontalalignment="right",
    verticalalignment="top",
    bbox=dict(
        boxstyle="round",
        facecolor="white",
        alpha=0.85,
    ),
)

ax.scatter(
    [t_break],
    [F_break],
    color="black",
    zorder=5,
)

ax.annotate(
    "Release",
    xy=(t_break, F_break),
    xytext=(20, 20),
    textcoords="offset points",
    arrowprops=dict(
        arrowstyle="->",
    ),
)


ax.legend(
    loc="best"
)

fig.tight_layout()


if (write_to_file and output_thrust_curve):
    fig.savefig(
        os.path.join(
            DATA_DIR,
            f"{version}_thrust_curve.png",
        ),
        dpi=150,
        bbox_inches="tight",
    )

    plt.show()

else:

    plt.close(fig)


# ------------------------------------------------------------
# Main thrust .eng file
# ------------------------------------------------------------

eng_filename = os.path.join(
    DATA_DIR,
    f"B3_{version}.eng",
)

header_line = f"B3_{version} 240 200 0 0.001 0.001 ERT"

with open(eng_filename, "w") as f:
    f.write(header_line + "\n")

    for (t_value, F_value) in zip(t_flight, F_flight):
        # RocketPy/RASP .eng import rejects a 0 s / 0 N point.
        # Normally release happens at positive thrust anyway.
        if (np.isclose(
                t_value,
                0.0,
            )
            and np.isclose(
                F_value,
                0.0,
            )
        ):
            continue

        f.write(f"{t_value:.6f} {F_value:.3f}\n")

    f.write("\n")

B3_eng_path = eng_filename


# ------------------------------------------------------------
# Ullage CSVs
# ------------------------------------------------------------

ullage_fuel_flight_m3 = ullage_fuel_m3[mask_after_break]

ullage_lox_flight_m3 = ullage_lox_m3[mask_after_break]

def write_ullage_csv(
    filename,
    t,
    ullage,
):

    if len(t) != len(ullage):
        raise ValueError(
            f"Time and ullage arrays have different "
            f"lengths for {filename}."
        )

    with open(filename, mode="w", newline="") as file:

        writer = csv.writer(file)

        for ti, ui in zip(t, ullage):
            writer.writerow(
                [
                    f"{ti:.6f}",
                    f"{ui:.8f}",
                ]
            )

ethanol_csv_path = os.path.join(
    DATA_DIR,
    f"ethanol_ullage_data_{version}.csv",
)

lox_csv_path = os.path.join(
    DATA_DIR,
    f"lox_ullage_data_{version}.csv",
)


write_ullage_csv(
    ethanol_csv_path,
    t_flight,
    ullage_fuel_flight_m3,
)

write_ullage_csv(
    lox_csv_path,
    t_flight,
    ullage_lox_flight_m3,
)


# This includes the cutoff phase.
t_end = t_flight[-1] # Full burn duration after hold-down break


# ============================================================
# Pressurant N2
# ============================================================

# TODO: look into https://coolprop.org/fluid_properties/fluids/Nitrogen.html
rho_n2_lox_tank = (
    6000000.0 * 0.028
    / (8.314 * 178.15)
)

rho_n2_ethanol_tank = (
    6000000.0 * 0.028
    / (8.314 * 293.15)
)


# N2 present in the propellant tank ullages during flight
m_n2_lox_ullage = (
    rho_n2_lox_tank
    * ullage_lox_flight_m3
)

m_n2_ethanol_ullage = (
    rho_n2_ethanol_tank
    * ullage_fuel_flight_m3
)


# ============================================================
# COPV
# ============================================================

m_copv_initial = m_n2_copv

m_copv_lox_vs_time = (
    m_n2_copv
    - m_n2_lox_ullage
)

m_copv_eth_vs_time = (
    m_n2_copv
    - m_n2_ethanol_ullage
)


if np.any(m_copv_lox_vs_time < 0.0):
    required = np.max(m_n2_lox_ullage)

    raise ValueError(
        "LOX COPV does not contain enough N2 to maintain "
        "the assumed 6 MPa ullage condition. "
        f"Required: {required:.4f} kg, "
        f"available: {m_n2_copv:.4f} kg."
    )


if np.any(m_copv_eth_vs_time < 0.0):
    required = np.max(m_n2_ethanol_ullage)

    raise ValueError(
        "Fuel COPV does not contain enough N2 to maintain "
        "the assumed 6 MPa ullage condition. "
        f"Required: {required:.4f} kg, "
        f"available: {m_n2_copv:.4f} kg."
    )


copv_lox_csv_path = os.path.join(
    DATA_DIR,
    f"copv_lox_mass_vs_time_{version}.csv",
)

copv_eth_csv_path = os.path.join(
    DATA_DIR,
    f"copv_eth_mass_vs_time_{version}.csv",
)

with open(copv_lox_csv_path, mode="w", newline="") as file:
    writer = csv.writer(file)

    for ti, mi in zip(t_flight, m_copv_lox_vs_time):
        writer.writerow(
            [
                f"{ti:.6f}",
                f"{mi:.6f}",
            ]
        )

with open(copv_eth_csv_path, mode="w", newline="") as file:
    writer = csv.writer(file)

    for ti, mi in zip(t_flight, m_copv_eth_vs_time):
        writer.writerow(
            [
                f"{ti:.6f}",
                f"{mi:.6f}",
            ]
        )

# ============================================================
# Environment
# ============================================================
env = Environment(latitude=latitude, longitude=longitude, elevation=elevation)
env.set_date(date=(annee, mois, jour, heure, minute))
env.set_atmospheric_model(type="Windy", file="ECMWF")
# env.set_atmospheric_model(type="standard_atmosphere")
# env.set_atmospheric_model( # +90° crosswind
#     type="custom_atmosphere",
#     wind_u=-6.472,
#     wind_v=-4.702
# )
# env.set_atmospheric_model( # -90° crosswind
#     type="custom_atmosphere",
#     wind_u=6.472,
#     wind_v=4.702
# )

# ============================================================
# Ullage Functions
# ============================================================
lox_tank_ullage = Function(
    lox_csv_path, 
    interpolation="linear", 
    extrapolation="constant", 
    inputs="Time (s)", 
    outputs="Ullage Volume (m^3)"
)
ethanol_tank_ullage = Function(
    ethanol_csv_path, 
    interpolation="linear", 
    extrapolation="constant", 
    inputs="Time (s)", 
    outputs="Ullage Volume (m^3)"
)


# ============================================================
# Fluids
# ============================================================
lox = Fluid(name="Lox", density=m_lox_density)
ethanol = Fluid(name="Ethanol", density=m_eth_density)
pressurizing_gas_lox = Fluid(name="N2", density=6000000*0.028/(8.314*178.15))
pressurizing_gas_ethanol = Fluid(name="N2", density=6000000*0.028/(8.314*293.15))
pressurizing_gas = Fluid(name="N2", density=600)


# ============================================================
# Tanks — hauteur dérivée du volume + rayon + choix de calottes
# ============================================================

def compute_tank_height(volume: float, radius: float, spherical_caps: bool) -> float:
    """
    Calcule le paramètre 'height' à passer à rocketpy.CylindricalTank pour
    obtenir un volume interne total donné.

    Cas calottes plates (spherical_caps=False) — cylindre pur :
        V = π r² H
        => H = V / (π r²)
        (height passé à RocketPy = H, directement la hauteur cylindrique)

    Cas calottes sphériques (spherical_caps=True) :
        Les deux calottes hémisphériques (rayon r) forment ensemble le
        volume d'une sphère complète :
            V_calottes = (4/3) π r³
        Le volume total est celui du cylindre central + les deux calottes :
            V = π r² H_cyl + (4/3) π r³
            => H_cyl = (V - (4/3) π r³) / (π r²)

        RocketPy attend en paramètre 'height' la hauteur TOTALE du réservoir
        (partie cylindrique + les deux calottes ; chaque calotte a une
        hauteur = r, donc height = H_cyl + 2r) — passer height=H_total avec
        spherical_caps=True réduit automatiquement la portion cylindrique à
        H_total - 2r en interne, côté RocketPy.
            height = H_cyl + 2r
    """
    if radius <= 0:
        raise ValueError("Tank radius must be positive.")

    if not spherical_caps:
        return volume / (math.pi * radius**2)

    cap_volume = (4.0 / 3.0) * math.pi * radius**3
    if volume <= cap_volume:
        raise ValueError(
            f"Tank volume ({volume:.5f} m³) is smaller than the volume of the "
            f"two spherical caps alone ({cap_volume:.5f} m³) for radius={radius} m. "
            "Increase the tank volume or reduce the radius."
        )
    h_cyl = (volume - cap_volume) / (math.pi * radius**2)
    return h_cyl + 2 * radius

tank_height = compute_tank_height(tank_volume, r_int, tank_spherical_caps)
tank_geometry_lox = CylindricalTank(r_int, tank_height, spherical_caps=tank_spherical_caps)
tank_geometry_ethanol = CylindricalTank(r_int, tank_height, spherical_caps=tank_spherical_caps)

lox_tank = UllageBasedTank(
    name="LOX Tank", 
    flux_time=t_end, 
    geometry=tank_geometry_lox,
    gas=pressurizing_gas_lox, 
    liquid=lox, 
    ullage=lox_tank_ullage,
)
#print("Tank volume (recalculé par RocketPy):", tank_geometry_lox.volume())

ethanol_tank = UllageBasedTank(
    name="Ethanol Tank", 
    flux_time=t_end, 
    geometry=tank_geometry_ethanol,
    gas=pressurizing_gas_ethanol, 
    liquid=ethanol, 
    ullage=ethanol_tank_ullage,
)

copv_height = compute_tank_height(copv_volume, r_int_copv, copv_spherical_caps)
pressure_tank_geometry = CylindricalTank(r_int_copv, copv_height, spherical_caps=copv_spherical_caps)

copv_lox_mass = Function(
    copv_lox_csv_path,
    interpolation="linear",
    extrapolation="constant",
)

copv_eth_mass = Function(
    copv_eth_csv_path,
    interpolation="linear",
    extrapolation="constant",
)

pressure_tank_lox = MassBasedTank(
    name="LOX Pressure Tank",
    geometry=pressure_tank_geometry,
    liquid_mass=0,
    flux_time=t_end,
    gas_mass=copv_lox_mass,
    gas=pressurizing_gas,
    liquid=pressurizing_gas,
)

pressure_tank_eth = MassBasedTank(
    name="Ethanol Pressure Tank",
    geometry=pressure_tank_geometry,
    liquid_mass=0,
    flux_time=t_end,
    gas_mass=copv_eth_mass,
    gas=pressurizing_gas,
    liquid=pressurizing_gas,
)

# print(f"Tank height: {tank_height} m")
# print(f"Copv height: {copv_height} m")


# ============================================================
# Motor
# ============================================================
B3 = LiquidMotor(
    thrust_source=B3_eng_path,
    dry_mass=1e-5,
    dry_inertia=(1e-5, 1e-5, 1e-5),
    nozzle_radius=r_nozzle,
    center_of_dry_mass_position=1e-5,
    nozzle_position=0,
    burn_time=t_end,
    reshape_thrust_curve=False,
    interpolation_method="linear",
    coordinate_system_orientation="nozzle_to_combustion_chamber",
    reference_pressure=101325,
)

B3.add_tank(lox_tank, position=pos_lox)
B3.add_tank(pressure_tank_lox, position=pos_copv_mbay)
B3.add_tank(ethanol_tank, position=pos_eth)
B3.add_tank(pressure_tank_eth, position=pos_copv_pbay)

expected_fluid_mass_release = (
    m_vehicle[idx_break]
    - m_dry
)

rocketpy_fluid_mass_release = (
    B3.propellant_mass(0)
)

mass_error = (
    rocketpy_fluid_mass_release
    - expected_fluid_mass_release
)


print("\n========== ROCKETPY MOTOR MASS CHECK ==========")

print(
    f"Expected fluid mass at release : "
    f"{expected_fluid_mass_release:.8f} kg"
)

print(
    f"RocketPy fluid mass at release : "
    f"{rocketpy_fluid_mass_release:.8f} kg"
)

print(
    f"Mass bookkeeping error         : "
    f"{mass_error:+.8f} kg"
)

print("================================================\n")


if not np.isclose(
    rocketpy_fluid_mass_release,
    expected_fluid_mass_release,
    atol=1e-4,
    rtol=1e-6,
):
    raise RuntimeError(
        "RocketPy fluid inventory does not match "
        "wrapper fluid inventory at hold-down release."
    )


# ============================================================
# Rocket
# ============================================================
firehorn2 = Rocket(
    radius=r_rocket,
    mass=m_dry,
    inertia=(Ix, Iy, Iz),
    power_off_drag=drag_coeff_rocket,
    power_on_drag=drag_coeff_rocket,
    center_of_mass_without_motor=z_cm,
    coordinate_system_orientation="tail_to_nose",
)

firehorn2.add_cm_eccentricity(x=0, y=y_cm)
firehorn2.add_motor(motor=B3, position=0)

firehorn2.set_rail_buttons(
    lower_button_position=pos_inf_rb,
    upper_button_position=pos_sup_rb,
)

firehorn2.add_nose(
    length=l_nosecone, kind="powerseries", power=0.5,
    position=Nosecone.z + l_nosecone,
)

firehorn2.add_trapezoidal_fins(
    n=int(n_fins),
    span=env_fins,
    root_chord=rc_fins,
    position=pos_fins,
    cant_angle=int(cangle_fins),
    tip_chord=tc_fins,
    sweep_length=sweep_l_fins,
)

firehorn2.add_tail(
    top_radius=top_r_bt,
    bottom_radius=bottom_r_bt,
    length=l_bt,
    position=Boattail.length,
)

firehorn2.add_parachute(
    name="reefed", cd_s=drag_coeff_para_reefed,
    trigger="apogee", sampling_rate=100, lag=7, noise=(0, 0, 0),
)

firehorn2.add_parachute(
    name="unreefed", cd_s=drag_coeff_para_unreefed,
    trigger=trig_alt_para, sampling_rate=100, lag=0, noise=(0, 0, 0),
)

firehorn2.draw()


# ============================================================
# Flight
# ============================================================
flight = Flight(
    rocket=firehorn2,
    rail_length=l_rail,
    environment=env,
    inclination=inclination_rail,
    heading=heading_rail,
)


# ============================================================
# Nettoyage des fichiers intermédiaires (.eng / .csv) si save_files=False
# Ils ne sont plus nécessaires une fois le Flight construit : RocketPy les
# a déjà lus en mémoire au moment de créer le moteur/les réservoirs.
# ============================================================
if not save_files:
    intermediate_files = [
        eng_filename,
        os.path.join(DATA_DIR, f"LOX_{version}.eng"),
        os.path.join(DATA_DIR, f"FUEL_{version}.eng"),
        ethanol_csv_path,
        lox_csv_path,
        copv_lox_csv_path,
        copv_eth_csv_path
    ]
    for _f in intermediate_files:
        try:
            os.remove(_f)
        except FileNotFoundError:
            pass
    print(f"save_files=False : fichiers intermédiaires supprimés ({len(intermediate_files)} fichiers).")


# ============================================================
# Outputs — pilotés par les cases output_* de l'Excel (feuille Parameters)
# ============================================================
print(f"Impulse (nominale, hold-down inclus): {nominal_total_impulse} [Ns]")
print(f"Burn time: {t_cutoff_end:.3f} [s]")
print(f"Dry mass: {m_dry:.2f} [kg]")
print(f"Wet mass: {m_wet:.2f} [kg]")
print(f"Apogee (AGL): {flight.altitude(flight.apogee_time):.1f} [m]")
print(f"Out of rail time: {(t_break + flight.out_of_rail_time):.3f} [s]")
print(f"Burn out time: {(t_break + flight.rocket.motor.burn_out_time):.3f} [s]")
print(f"Time to apogee: {(t_break + flight.apogee_time):.3f} [s]")
print(f"Disreef time: {(t_break + flight.parachute_events[1][0] + flight.parachute_events[1][1].lag):.3f} [s]")
print(f"Time of impact: {(t_break + flight.t_final):.3f} [s]")
print(f"Max Mach: {flight.max_mach_number:.3f} [-]")
print(f"Max velocity: {flight.max_speed:.2f} [m/s]")
print(f"Max acceleration: {flight.max_acceleration:.2f} [m/s^2]")
print(f"Out of rail velocity: {flight.out_of_rail_velocity:.2f} [m/s]")
print(f"Rail departure angle of attack: {flight.angle_of_attack(flight.out_of_rail_time):.3f} [°]")

flight.stability_margin.plot()
flight.prints.stability_margin()
print("Rail exit velocity:",
      flight.out_of_rail_velocity)
print("Rail exit stability:",
      flight.out_of_rail_stability_margin)
print("Max Q:",
      flight.max_dynamic_pressure)
print("Max Q time:",
      t_break + flight.max_dynamic_pressure_time)

tq = flight.max_dynamic_pressure_time
print("AoA at max-Q:",
      flight.angle_of_attack(tq))
print("SM at max-Q:",
      flight.stability_margin(tq))
flight.angle_of_attack.plot()
flight.dynamic_pressure.plot()


if write_to_file:
    # --- Résultats généraux -> feuille 'Simulation' de l'Excel ---
    if output_general:
        import importlib
        import output_into_excel
        importlib.reload(output_into_excel)
        from output_into_excel import write_flight_outputs_vertical

        write_flight_outputs_vertical(
            flight=flight,
            version=version,
            directory=DATA_DIR,
            dry_mass=m_dry,
            wet_mass=m_wet,
            nominal_total_impulse=nominal_total_impulse,
        )

    # --- Graphes -> PNG ---
    t_plot = np.linspace(0.01, flight.t_final * 0.999, n_points)

    if output_euler_angles:
        phi = np.array([flight.phi(t) for t in t_plot])
        theta = np.array([flight.theta(t) for t in t_plot])
        psi = np.array([flight.psi(t) for t in t_plot])
        plt.figure(figsize=(9, 5))
        plt.plot(t_plot, phi, label="φ — Spin")
        plt.plot(t_plot, theta, label="θ — Nutation")
        plt.plot(t_plot, psi, label="ψ — Precession")
        plt.xlabel("Time (s)"); plt.ylabel("Angle (°)"); plt.title("Euler Angles")
        plt.legend(); plt.grid(True, alpha=0.3)
        plt.savefig(os.path.join(DATA_DIR, f"euler_angles_{version}.png"), dpi=150, bbox_inches="tight")
        plt.show()

    if output_stability:
        margin = np.array([
            flight.stability_margin(t)
            for t in t_plot
        ])
        plt.figure(figsize=(9, 5))
        plt.plot(t_plot, margin, color="firebrick")
        plt.axhline(0, color="black", linewidth=0.8, linestyle="--")
        plt.xlabel("Time (s)"); plt.ylabel("Static margin (calibers)"); plt.title("Stability Margin vs Time")
        plt.grid(True, alpha=0.3)
        plt.savefig(os.path.join(DATA_DIR, f"stability_margin_{version}.png"), dpi=150, bbox_inches="tight")
        plt.show()

    if output_trajectory:
        altitude = np.array([flight.altitude(t) for t in t_plot])
        plt.figure(figsize=(9, 5))
        plt.plot(t_plot, altitude, color="steelblue")
        plt.xlabel("Time (s)"); plt.ylabel("Altitude AGL (m)"); plt.title("Altitude vs Time")
        plt.grid(True, alpha=0.3)
        plt.savefig(os.path.join(DATA_DIR, f"trajectory_{version}.png"), dpi=150, bbox_inches="tight")
        plt.show()

    if output_velocity:
        speed = np.array([flight.speed(t) for t in t_plot])
        plt.figure(figsize=(9, 5))
        plt.plot(t_plot, speed, color="darkorange")
        plt.xlabel("Time (s)"); plt.ylabel("Speed (m/s)"); plt.title("Speed vs Time")
        plt.grid(True, alpha=0.3)
        plt.savefig(os.path.join(DATA_DIR, f"velocity_{version}.png"), dpi=150, bbox_inches="tight")
        plt.show()

    if output_acceleration:
        accel = np.array([flight.acceleration(t) for t in t_plot])
        plt.figure(figsize=(9, 5))
        plt.plot(t_plot, accel, color="seagreen")
        plt.xlabel("Time (s)"); plt.ylabel("Acceleration (m/s²)"); plt.title("Acceleration vs Time")
        plt.grid(True, alpha=0.3)
        plt.savefig(os.path.join(DATA_DIR, f"acceleration_{version}.png"), dpi=150, bbox_inches="tight")
        plt.show()

    # output_thrust_curve est déjà sauvegardé plus haut (au moment du tracé de la courbe)
else:
    print("write_to_file=False : aucun fichier de sortie écrit.")
