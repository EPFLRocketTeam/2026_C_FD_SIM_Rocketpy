"""
simulator.py

Refactorisation de simulator.ipynb (version courbe de poussée à 4 phases,
débits massiques LOX/éthanol distincts par phase, double suivi N2 des COPV
LOX/éthanol) en une fonction unique réutilisable :
run_simulation(structure, propellant, parameters, work_dir="."). 

La logique physique (bays, moment d'inertie, courbe de poussée, hold-down,
déplétion, fichiers .eng/.csv, construction RocketPy, Flight) suit le
notebook de référence. Seule la structure change : tout est encapsulé pour
pouvoir être appelé depuis une app Streamlit (ou n'importe quel autre
script) sans dépendre de l'exécution cellule par cellule.

thrust_curve_mode et derated_thrust sont maintenant des champs du dataclass
Propellant (plus besoin de les passer séparément à run_simulation).
"""
from __future__ import annotations

import csv
import math
import os
import shutil
import tempfile
from pathlib import Path

import numpy as np

from class_bay import Bay
from class_structure import Structure
from class_propellant import Propellant
from class_parameters import Parameters

G = 9.80665


def compute_tank_height(volume: float, radius: float, spherical_caps: bool) -> float:
    """
    Calcule le paramètre 'height' à passer à rocketpy.CylindricalTank pour
    obtenir un volume interne total donné.

    Cas calottes plates (spherical_caps=False) — cylindre pur :
        V = π r² H  =>  H = V / (π r²)

    Cas calottes sphériques (spherical_caps=True) :
        V = π r² H_cyl + (4/3) π r³  =>  H_cyl = (V - (4/3) π r³) / (π r²)
        RocketPy attend la hauteur TOTALE (cylindre + 2 calottes de hauteur r) :
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


def _autocrop_whitespace(image_path: Path, padding: int = 15) -> None:
    """Recadre automatiquement les marges blanches/vides autour du dessin
    RocketPy sauvegardé, avec une petite marge de respiration."""
    from PIL import Image, ImageChops

    im = Image.open(image_path).convert("RGB")
    bg = Image.new("RGB", im.size, im.getpixel((0, 0)))
    diff = ImageChops.difference(im, bg)
    bbox = diff.getbbox()
    if bbox:
        left, top, right, bottom = bbox
        left = max(left - padding, 0)
        top = max(top - padding, 0)
        right = min(right + padding, im.width)
        bottom = min(bottom + padding, im.height)
        im.crop((left, top, right, bottom)).save(image_path)


def run_simulation(
    struct: Structure,
    prop: Propellant,
    params: Parameters,
    work_dir: str | Path = ".",
    draw_rocket: bool = True,
    wind_speed_override: float | None = None,
    wind_direction_override_deg: float | None = None,
    wind_profile: list[tuple[float, float, float]] | None = None,
) -> dict:
    """
    Exécute la simulation complète FH2 et retourne un dict de résultats.

    Paramètres
    ----------
    struct, prop, params : instances de Structure / Propellant / Parameters
        (chargées depuis l'Excel ou modifiées via l'interface Streamlit).
        prop.thrust_curve_mode ("constant" ou "peaked") et
        prop.derated_thrust pilotent le modèle de courbe de poussée.
    work_dir : dossier où écrire les fichiers intermédiaires (.eng, .csv)
    draw_rocket : si False, saute le rendu RocketPy de la fusée (utile pour
        aller vite quand on lance beaucoup de simulations, p. ex. Monte Carlo).
    wind_profile : si fourni, liste de (altitude_m, vitesse_m/s, direction_deg)
        — vent variable par palier d'altitude (rafales : vitesse/direction
        différentes à chaque palier, interpolées linéairement entre paliers
        par RocketPy). Prioritaire sur wind_speed_override s'il est fourni.
    wind_speed_override, wind_direction_override_deg : si fournis (tous les
        deux non-None) et qu'aucun wind_profile n'est donné, utilise un vent
        uniforme constant (m/s, degrés — 0° = vers l'est, sens trigonométrique)
        au lieu d'aller chercher la météo réelle (Windy/GFS). Utile pour un
        balayage Monte Carlo contrôlé et pour éviter un appel réseau par run.

    Retour : dict — voir la fin de la fonction pour la liste des clés.
    """
    from rocketpy import (
        Environment,
        LiquidMotor,
        Rocket,
        Flight,
        Fluid,
        CylindricalTank,
        UllageBasedTank,
        MassBasedTank,
        Function,
    )

    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    version = params.version.strip()
    version_dir = work_dir / version
    version_dir.mkdir(parents=True, exist_ok=True)

    thrust_curve_mode = prop.thrust_curve_mode
    derated_thrust_in = prop.derated_thrust  # 0 = non spécifié -> défaut 85% du pic

    # ------------------------------------------------------------------
    # 1. Rocket (bays) + centre de masse + moments d'inertie
    # ------------------------------------------------------------------
    Boattail = Bay("Boattail", 0, 0, struct.r_rocket, struct.l_bt, struct.m_bt, "cylindrical")
    EngineBay = Bay(
        "EngineBay", Boattail.length, 0, struct.r_rocket, struct.l_ebay,
        struct.m_ebay + struct.m_fins, "tank",
    )
    LOx = Bay("LOx", EngineBay.z + EngineBay.length, 0, struct.r_rocket, struct.l_lox, struct.m_lox, "tank")
    Aerocover = Bay(
        "Aerocover", struct.pos_aerocover, struct.r_rocket,
        struct.r_aerocover, struct.l_aerocover, struct.m_aerocover, "semi-cylindrical",
    )
    PressurantBay1 = Bay(
        "PressurantBay1", LOx.z + LOx.length, 0,
        struct.r_rocket, struct.l_pbay1, struct.m_pbay1, "cylindrical",
    )
    ETH = Bay(
        "ETH", PressurantBay1.z + PressurantBay1.length, 0,
        struct.r_rocket, struct.l_eth, struct.m_eth, "tank",
    )
    PressurantBay2 = Bay(
        "PressurantBay2", ETH.z + ETH.length, 0,
        struct.r_rocket, struct.l_pbay2, struct.m_pbay2, "cylindrical",
    )
    AVBay = Bay(
        "AVBay", PressurantBay2.z + PressurantBay2.length, 0,
        struct.r_rocket, struct.l_avbay, struct.m_avbay, "cylindrical",
    )
    RecoveryBay = Bay(
        "RecoveryBay", AVBay.z + AVBay.length, 0,
        struct.r_rocket, struct.l_rebay, struct.m_rebay, "cylindrical",
    )
    Nosecone = Bay(
        "Nosecone", RecoveryBay.z + RecoveryBay.length, 0,
        struct.r_rocket, struct.l_nosecone, struct.m_nosecone, "conical",
    )

    rocket_bays = [
        Boattail, EngineBay, LOx, Aerocover, PressurantBay1,
        ETH, PressurantBay2, AVBay, RecoveryBay, Nosecone,
    ]

    if struct.mode == 0:
        m_dry = sum(bay.mass for bay in rocket_bays)

        z_cm = 0.0
        y_cm = 0.0
        for bay in rocket_bays:
            z_local, y_local = bay.center_masse()
            z_cm += bay.mass * (bay.z + z_local)
            y_cm += bay.mass * (bay.y + y_local)
        z_cm /= m_dry
        y_cm /= m_dry

        Ix = Iy = Iz = 0.0
        for bay in rocket_bays:
            z_local, y_local = bay.center_masse()
            z_bay_cm = bay.z + z_local
            y_bay_cm = bay.y + y_local
            dz = z_bay_cm - z_cm
            dy = y_bay_cm - y_cm
            dx = 0.0  # symétrie supposée

            Ix_local, Iy_local, Iz_local = bay.moment_of_inertia()
            Ix += Ix_local + bay.mass * (dy**2 + dz**2)
            Iy += Iy_local + bay.mass * (dx**2 + dz**2)
            Iz += Iz_local + bay.mass * (dx**2 + dy**2)

    elif struct.mode == 1:
        # Mode "masse mesurée" : m_dry_measured + l_center_of_mass viennent
        # d'une pesée/mesure réelle ; les bays ne servent qu'aux masses
        # additionnelles (avionique, etc.). ATTENTION : les moments
        # d'inertie ci-dessous sont ceux mesurés/estimés pour un modèle
        # de référence précis (EuRoC_1) — ils ne sont PAS recalculés à
        # partir des bays et doivent être mis à jour manuellement si la
        # configuration change.
        m_dry = struct.m_dry_measured + sum(bay.mass for bay in rocket_bays)

        z_cm = struct.l_center_of_mass * struct.m_dry_measured
        y_cm = 0.0
        for bay in rocket_bays:
            z_local, y_local = bay.center_masse()
            z_cm += bay.mass * (bay.z + z_local)
            y_cm += bay.mass * (bay.y + y_local)
        z_cm /= m_dry
        y_cm /= m_dry

        Ix = 242.7543433720102
        Iy = 242.71214558814867
        Iz = 0.9012818783579469

    else:
        raise ValueError("struct.mode has to be 0 or 1.")

    # ------------------------------------------------------------------
    # 2. Grandeurs de propulsion de référence
    # ------------------------------------------------------------------
    F_full_thrust = float(prop.thrust)
    F_shutdown = float(prop.f_shutdown)

    if F_full_thrust <= 0:
        raise ValueError("thrust must be strictly positive.")
    if prop.total_impulse <= 0:
        raise ValueError("total_impulse must be strictly positive.")
    if prop.isp <= 0:
        raise ValueError("isp must be strictly positive.")
    if prop.of_ratio <= 0:
        raise ValueError("of_ratio must be strictly positive.")
    if F_shutdown < 0:
        raise ValueError("f_shutdown cannot be negative.")
    if prop.ramp_up_time < 0 or prop.ramp_down_time < 0 or prop.cutoff_time < 0:
        raise ValueError("Engine phase durations must be non-negative.")

    # Débit au régime nominal (Isp coeur)
    engine_mass_flow_rate = F_full_thrust / (prop.isp * G)
    eth_mass_flow_rate = engine_mass_flow_rate / (1.0 + prop.of_ratio)
    lox_burn_mass_flow_rate = engine_mass_flow_rate - eth_mass_flow_rate
    film_cooling_mass_flow_rate = eth_mass_flow_rate * prop.eth_frac_cooling
    eth_burn_mass_flow_rate = eth_mass_flow_rate + film_cooling_mass_flow_rate

    equivalent_burn_time = prop.total_impulse / F_full_thrust

    # ------------------------------------------------------------------
    # 3. Timing de la courbe de poussée
    # ------------------------------------------------------------------
    impulse_ramp_up = 0.5 * F_full_thrust * prop.ramp_up_time
    impulse_cutoff = 0.5 * F_shutdown * prop.cutoff_time
    t_rampup_end = prop.ramp_up_time

    if thrust_curve_mode == "constant":
        F_derating = F_full_thrust
        F_ramp_down = F_full_thrust

        if F_shutdown > F_ramp_down:
            raise ValueError("f_shutdown cannot exceed thrust at the start of ramp-down.")

        impulse_ramp_down = 0.5 * (F_ramp_down + F_shutdown) * prop.ramp_down_time
        flat_duration = (
            prop.total_impulse - impulse_ramp_up - impulse_ramp_down - impulse_cutoff
        ) / F_full_thrust
        if flat_duration < 0:
            raise ValueError(
                "Cannot match total_impulse with the requested ramp-up, "
                "ramp-down and cutoff phases. The non-flat phases already "
                "consume too much impulse."
            )

        t_full_thrust = t_rampup_end
        t_ramp_down = t_full_thrust + flat_duration
        t_shutdown = t_ramp_down + prop.ramp_down_time
        t_cutoff_end = t_shutdown + prop.cutoff_time
        t_derate_end = None  # inutilisé en mode constant

        main_phase_duration = flat_duration
        main_impulse_total = F_full_thrust * flat_duration

        def main_impulse_elapsed(t):
            t = np.asarray(t, dtype=float)
            dt_main = np.clip(t - t_rampup_end, 0.0, flat_duration)
            return F_full_thrust * dt_main

        def evaluate_thrust(t):
            t = np.asarray(t, dtype=float)
            F_out = np.zeros_like(t)

            if prop.ramp_up_time > 0:
                mask = (t >= 0.0) & (t <= t_rampup_end)
                F_out[mask] = F_full_thrust * t[mask] / prop.ramp_up_time
            else:
                F_out[t >= 0.0] = F_full_thrust

            mask = (t > t_rampup_end) & (t <= t_ramp_down)
            F_out[mask] = F_full_thrust

            if prop.ramp_down_time > 0:
                mask = (t > t_ramp_down) & (t <= t_shutdown)
                u = (t[mask] - t_ramp_down) / prop.ramp_down_time
                F_out[mask] = F_ramp_down + (F_shutdown - F_ramp_down) * u

            if prop.cutoff_time > 0:
                mask = (t > t_shutdown) & (t <= t_cutoff_end)
                u = (t[mask] - t_shutdown) / prop.cutoff_time
                F_out[mask] = F_shutdown * (1.0 - u)

            return np.maximum(F_out, 0.0)

    elif thrust_curve_mode == "peaked":
        peak_duration_factor = 1.5

        F_derating = derated_thrust_in if derated_thrust_in > 0 else 0.85 * F_full_thrust
        if F_derating <= 0 or F_derating > F_full_thrust:
            raise ValueError("derated thrust must be > 0 and <= nominal thrust.")
        if F_shutdown > F_derating:
            raise ValueError("f_shutdown cannot exceed the derated thrust at the start of ramp-down.")

        t_peak_transition = (peak_duration_factor - 1.0) * prop.ramp_up_time
        t_derate_end = t_rampup_end + t_peak_transition

        impulse_transition = 0.5 * (F_full_thrust + F_derating) * t_peak_transition
        impulse_ramp_down = 0.5 * (F_derating + F_shutdown) * prop.ramp_down_time

        t_const = (
            prop.total_impulse - impulse_ramp_up - impulse_transition
            - impulse_ramp_down - impulse_cutoff
        ) / F_derating
        if t_const < 0:
            raise ValueError(
                "Cannot match total_impulse with the requested peak, "
                "derating, ramp-down and cutoff phases."
            )

        t_full_thrust = t_rampup_end
        t_ramp_down = t_derate_end + t_const
        t_shutdown = t_ramp_down + prop.ramp_down_time
        t_cutoff_end = t_shutdown + prop.cutoff_time

        main_phase_duration = t_peak_transition + t_const
        main_impulse_total = impulse_transition + F_derating * t_const

        def main_impulse_elapsed(t):
            t = np.asarray(t, dtype=float)
            u = np.clip(t - t_rampup_end, 0.0, main_phase_duration)

            if t_peak_transition > 0:
                u_transition = np.minimum(u, t_peak_transition)
                I_transition_partial = (
                    F_full_thrust * u_transition
                    + 0.5 * (F_derating - F_full_thrust) / t_peak_transition * u_transition**2
                )
                return np.where(
                    u <= t_peak_transition,
                    I_transition_partial,
                    impulse_transition + F_derating * (u - t_peak_transition),
                )
            return F_derating * u

        def evaluate_thrust(t):
            t = np.asarray(t, dtype=float)
            F_out = np.zeros_like(t)

            if prop.ramp_up_time > 0:
                mask = (t >= 0.0) & (t <= t_rampup_end)
                F_out[mask] = F_full_thrust * t[mask] / prop.ramp_up_time
            else:
                F_out[t >= 0.0] = F_full_thrust

            if t_peak_transition > 0:
                mask = (t > t_rampup_end) & (t <= t_derate_end)
                u = (t[mask] - t_rampup_end) / t_peak_transition
                F_out[mask] = F_full_thrust + (F_derating - F_full_thrust) * u

            mask = (t > t_derate_end) & (t <= t_ramp_down)
            F_out[mask] = F_derating

            if prop.ramp_down_time > 0:
                mask = (t > t_ramp_down) & (t <= t_shutdown)
                u = (t[mask] - t_ramp_down) / prop.ramp_down_time
                F_out[mask] = F_derating + (F_shutdown - F_derating) * u

            if prop.cutoff_time > 0:
                mask = (t > t_shutdown) & (t <= t_cutoff_end)
                u = (t[mask] - t_shutdown) / prop.cutoff_time
                F_out[mask] = F_shutdown * (1.0 - u)

            return np.maximum(F_out, 0.0)

    else:
        raise ValueError(f"Unknown thrust_curve_mode: {thrust_curve_mode!r} (expected 'constant' or 'peaked').")

    # ------------------------------------------------------------------
    # 4. Vecteur temps maître + courbe de poussée
    # ------------------------------------------------------------------
    if int(params.n_points) < 2:
        raise ValueError("n_points must be >= 2.")

    t_base = np.linspace(0.0, t_cutoff_end, int(params.n_points))
    phase_times = [0.0, t_rampup_end, t_ramp_down, t_shutdown, t_cutoff_end]
    if thrust_curve_mode == "peaked":
        phase_times.append(t_derate_end)

    t_total = np.unique(np.concatenate([t_base, np.asarray(phase_times, dtype=float)]))
    t_total.sort()

    F_eng = evaluate_thrust(t_total)

    computed_impulse = np.trapezoid(F_eng, t_total)
    if not np.isclose(computed_impulse, prop.total_impulse, rtol=1e-4, atol=1.0):
        raise RuntimeError(
            f"Generated thrust curve impulse does not match target: "
            f"{computed_impulse:.2f} vs {prop.total_impulse:.2f} N.s"
        )

    # ------------------------------------------------------------------
    # 5. Masses de propergol par phase
    # ------------------------------------------------------------------
    # Pertes avant t=0
    m_fuel_ignition = prop.eth_ignition * abs(prop.ignition_delay)
    m_ox_boil_off = prop.lox_boil_off * prop.hold_time
    m_ox_prechill = prop.lox_prechill * prop.prechill_time
    m_ox_ignition = prop.lox_ignition * abs(prop.ignition_delay)

    # Propergol consommable après t=0
    m_fuel_rampup = prop.eth_ramp_up * prop.ramp_up_time
    m_ox_rampup = prop.lox_ramp_up * prop.ramp_up_time

    m_fuel_burn = eth_burn_mass_flow_rate * main_impulse_total / F_full_thrust
    m_ox_burn = lox_burn_mass_flow_rate * main_impulse_total / F_full_thrust

    m_fuel_rampdown = prop.eth_ramp_down * prop.ramp_down_time
    m_ox_rampdown = prop.lox_ramp_down * prop.ramp_down_time

    m_fuel_cutoff = prop.eth_cutoff * prop.cutoff_time
    m_ox_cutoff = prop.lox_cutoff * prop.cutoff_time

    m_fuel_unused = prop.m_eth_unused
    m_ox_unused = prop.m_lox_unused

    free_fuel = m_fuel_rampup + m_fuel_burn + m_fuel_rampdown + m_fuel_cutoff
    free_ox = m_ox_rampup + m_ox_burn + m_ox_rampdown + m_ox_cutoff

    m_fuel_total = m_fuel_ignition + free_fuel + m_fuel_unused
    m_ox_total = m_ox_boil_off + m_ox_prechill + m_ox_ignition + free_ox + m_ox_unused

    m_n2_copv = prop.m_n2
    m_wet = m_dry + m_fuel_total + m_ox_total + 2.0 * m_n2_copv
    nominal_total_impulse = prop.total_impulse

    # ------------------------------------------------------------------
    # 6. Déplétion exacte du propergol
    # ------------------------------------------------------------------
    def compute_propellant_depletion(t, rampup_mdot, burn_mdot_full, rampdown_mdot, cutoff_mdot):
        t = np.asarray(t, dtype=float)
        dt_rampup = np.clip(t, 0.0, prop.ramp_up_time)
        dt_rampdown = np.clip(t - t_ramp_down, 0.0, prop.ramp_down_time)
        dt_cutoff = np.clip(t - t_shutdown, 0.0, prop.cutoff_time)
        main_impulse = main_impulse_elapsed(t)

        consumed = (
            rampup_mdot * dt_rampup
            + (burn_mdot_full / F_full_thrust * main_impulse)
            + rampdown_mdot * dt_rampdown
            + cutoff_mdot * dt_cutoff
        )
        free_mass = (
            rampup_mdot * prop.ramp_up_time
            + (burn_mdot_full / F_full_thrust * main_impulse_total)
            + rampdown_mdot * prop.ramp_down_time
            + cutoff_mdot * prop.cutoff_time
        )
        mrem = np.maximum(free_mass - consumed, 0.0)
        return consumed, mrem, free_mass

    consumed_fuel, mrem_fuel, free_fuel_check = compute_propellant_depletion(
        t_total, prop.eth_ramp_up, eth_burn_mass_flow_rate, prop.eth_ramp_down, prop.eth_cutoff,
    )
    consumed_ox, mrem_ox, free_ox_check = compute_propellant_depletion(
        t_total, prop.lox_ramp_up, lox_burn_mass_flow_rate, prop.lox_ramp_down, prop.lox_cutoff,
    )

    Vrem_fuel = mrem_fuel / prop.m_eth_density
    Vrem_ox = mrem_ox / prop.m_lox_density

    # ------------------------------------------------------------------
    # 7. Masse véhicule à partir de t=0
    # ------------------------------------------------------------------
    mass_lost_fuel_before_t0 = m_fuel_ignition
    mass_lost_ox_before_t0 = m_ox_boil_off + m_ox_prechill + m_ox_ignition
    m_wet_t0 = m_wet - mass_lost_fuel_before_t0 - mass_lost_ox_before_t0
    m_vehicle = m_wet_t0 - consumed_fuel - consumed_ox

    # ------------------------------------------------------------------
    # 8. Hold-down et rupture (release)
    # ------------------------------------------------------------------
    alpha = np.deg2rad(params.alpha_rail)
    beta = np.deg2rad(params.beta_rail)
    t_array = t_total

    denominator = np.cos(beta) - params.coeff_fr_rail * np.sin(beta)
    if np.isclose(denominator, 0.0):
        raise ValueError("Hold-down force denominator is approximately zero.")

    W = m_vehicle * G
    F_HD = (F_eng - W * (np.cos(alpha) - params.coeff_fr_rail * np.sin(alpha))) / denominator

    if prop.f_hold_down > 0:
        mask_break = F_HD >= prop.f_hold_down
        if np.any(mask_break):
            idx_break = int(np.argmax(mask_break))
            t_break = t_array[idx_break]
        else:
            raise ValueError("Hold-down threshold not reached during propulsion.")
    else:
        idx_break = 0
        t_break = t_array[0]

    # ------------------------------------------------------------------
    # 9. Vérifications de cohérence
    # ------------------------------------------------------------------
    if not np.isclose(free_fuel, free_fuel_check, rtol=1e-10, atol=1e-10):
        raise RuntimeError("Fuel depletion is inconsistent.")
    if not np.isclose(free_ox, free_ox_check, rtol=1e-10, atol=1e-10):
        raise RuntimeError("LOX depletion is inconsistent.")
    if not np.isclose(consumed_fuel[-1], free_fuel, rtol=1e-10, atol=1e-10):
        raise RuntimeError("Fuel is not fully depleted by end of cutoff.")
    if not np.isclose(consumed_ox[-1], free_ox, rtol=1e-10, atol=1e-10):
        raise RuntimeError("LOX is not fully depleted by end of cutoff.")

    # ------------------------------------------------------------------
    # 10. Ullage
    # ------------------------------------------------------------------
    A_tank = np.pi * (struct.r_int**2)
    V_tank_total = struct.tank_volume
    V_fuel_fixed = m_fuel_unused / prop.m_eth_density
    V_ox_fixed = m_ox_unused / prop.m_lox_density

    raw_ullage_fuel_m3 = V_tank_total - V_fuel_fixed - Vrem_fuel
    raw_ullage_lox_m3 = V_tank_total - V_ox_fixed - Vrem_ox

    tol_ullage = 1e-9
    if np.any(raw_ullage_fuel_m3 < -tol_ullage):
        raise ValueError("Fuel tank is overfilled in the depletion model.")
    if np.any(raw_ullage_lox_m3 < -tol_ullage):
        raise ValueError("LOX tank is overfilled in the depletion model.")

    ullage_fuel_m3 = np.maximum(raw_ullage_fuel_m3, 0.0)
    ullage_lox_m3 = np.maximum(raw_ullage_lox_m3, 0.0)

    # ------------------------------------------------------------------
    # 11. Fichiers .eng / .csv pour RocketPy (référentiel temps : release)
    # ------------------------------------------------------------------
    mask_after_break = t_total >= t_break
    t_flight = t_total[mask_after_break] - t_break
    F_flight = F_eng[mask_after_break].copy()

    if len(t_flight) < 2:
        raise RuntimeError("Not enough time points after hold-down release.")

    eng_filename = version_dir / f"B3_{version}.eng"
    header_line = f"B3_{version} 240 200 0 0.001 0.001 ERT"
    with open(eng_filename, "w") as f:
        f.write(header_line + "\n")
        for t_value, F_value in zip(t_flight, F_flight):
            # RocketPy/RASP .eng import rejects a 0 s / 0 N point.
            if np.isclose(t_value, 0.0) and np.isclose(F_value, 0.0):
                continue
            f.write(f"{t_value:.6f} {F_value:.3f}\n")
        f.write("\n")
    B3_eng_path = eng_filename

    def write_ullage_csv(filename, t, ullage):
        with open(filename, mode="w", newline="") as file:
            writer = csv.writer(file)
            for ti, ui in zip(t, ullage):
                writer.writerow([f"{ti:.6f}", f"{ui:.8f}"])

    ullage_fuel_flight_m3 = ullage_fuel_m3[mask_after_break]
    ullage_lox_flight_m3 = ullage_lox_m3[mask_after_break]

    ethanol_csv_path = version_dir / f"ethanol_ullage_data_{version}.csv"
    lox_csv_path = version_dir / f"lox_ullage_data_{version}.csv"
    write_ullage_csv(ethanol_csv_path, t_flight, ullage_fuel_flight_m3)
    write_ullage_csv(lox_csv_path, t_flight, ullage_lox_flight_m3)

    t_end = t_flight[-1]  # inclut la phase de cutoff

    # ------------------------------------------------------------------
    # 12. Pressurant N2 — suivi séparé COPV LOX / COPV éthanol
    # ------------------------------------------------------------------
    rho_n2_lox_tank = 6_000_000.0 * 0.028 / (8.314 * 178.15)
    rho_n2_ethanol_tank = 6_000_000.0 * 0.028 / (8.314 * 293.15)

    m_n2_lox_ullage = rho_n2_lox_tank * ullage_lox_flight_m3
    m_n2_ethanol_ullage = rho_n2_ethanol_tank * ullage_fuel_flight_m3

    m_copv_lox_vs_time = m_n2_copv - m_n2_lox_ullage
    m_copv_eth_vs_time = m_n2_copv - m_n2_ethanol_ullage

    if np.any(m_copv_lox_vs_time < 0.0):
        required = np.max(m_n2_lox_ullage)
        raise ValueError(
            "LOX COPV does not contain enough N2 to maintain the assumed "
            f"6 MPa ullage condition. Required: {required:.4f} kg, "
            f"available: {m_n2_copv:.4f} kg."
        )
    if np.any(m_copv_eth_vs_time < 0.0):
        required = np.max(m_n2_ethanol_ullage)
        raise ValueError(
            "Fuel COPV does not contain enough N2 to maintain the assumed "
            f"6 MPa ullage condition. Required: {required:.4f} kg, "
            f"available: {m_n2_copv:.4f} kg."
        )

    copv_lox_csv_path = version_dir / f"copv_lox_mass_vs_time_{version}.csv"
    copv_eth_csv_path = version_dir / f"copv_eth_mass_vs_time_{version}.csv"
    with open(copv_lox_csv_path, mode="w", newline="") as file:
        writer = csv.writer(file)
        for ti, mi in zip(t_flight, m_copv_lox_vs_time):
            writer.writerow([f"{ti:.6f}", f"{mi:.6f}"])
    with open(copv_eth_csv_path, mode="w", newline="") as file:
        writer = csv.writer(file)
        for ti, mi in zip(t_flight, m_copv_eth_vs_time):
            writer.writerow([f"{ti:.6f}", f"{mi:.6f}"])

    # ------------------------------------------------------------------
    # 13. RocketPy : Environment, Motor, Rocket, Flight
    # ------------------------------------------------------------------
    env = Environment(latitude=params.latitude, longitude=params.longitude, elevation=params.elevation)
    env.set_date(date=(params.annee, params.mois, params.jour, params.heure, params.minute))

    if wind_profile is not None and len(wind_profile) > 0:
        wind_u_pairs = []
        wind_v_pairs = []
        for alt, speed, direction_deg in wind_profile:
            theta = math.radians(direction_deg)
            wind_u_pairs.append((alt, speed * math.cos(theta)))
            wind_v_pairs.append((alt, speed * math.sin(theta)))
        speeds = [s for _, s, _ in wind_profile]
        atmospheric_model_used = (
            f"Custom gusty wind profile ({len(wind_profile)} layers, "
            f"{min(speeds):.1f}–{max(speeds):.1f} m/s)"
        )
        env.set_atmospheric_model(type="custom_atmosphere", wind_u=wind_u_pairs, wind_v=wind_v_pairs)
    elif wind_speed_override is not None and wind_direction_override_deg is not None:
        theta = math.radians(wind_direction_override_deg)
        wind_u = wind_speed_override * math.cos(theta)
        wind_v = wind_speed_override * math.sin(theta)
        atmospheric_model_used = (
            f"Custom uniform wind ({wind_speed_override:.1f} m/s, "
            f"{wind_direction_override_deg:.0f}°)"
        )
        env.set_atmospheric_model(type="custom_atmosphere", wind_u=wind_u, wind_v=wind_v)
    else:
        atmospheric_model_used = "ECMWF (Windy)"
        try:
            env.set_atmospheric_model(type="Windy", file="ECMWF")
        except Exception:
            try:
                atmospheric_model_used = "GFS (forecast)"
                env.set_atmospheric_model(type="Forecast", file="GFS")
            except Exception:
                atmospheric_model_used = "Standard atmosphere (no real wind data)"
                env.set_atmospheric_model(type="standard_atmosphere")

    lox_tank_ullage = Function(
        str(lox_csv_path), interpolation="linear", extrapolation="constant",
        inputs="Time (s)", outputs="Ullage Volume (m^3)",
    )
    ethanol_tank_ullage = Function(
        str(ethanol_csv_path), interpolation="linear", extrapolation="constant",
        inputs="Time (s)", outputs="Ullage Volume (m^3)",
    )

    lox = Fluid(name="Lox", density=prop.m_lox_density)
    ethanol = Fluid(name="Ethanol", density=prop.m_eth_density)
    pressurizing_gas_lox = Fluid(name="N2", density=rho_n2_lox_tank)
    pressurizing_gas_ethanol = Fluid(name="N2", density=rho_n2_ethanol_tank)
    pressurizing_gas = Fluid(name="N2", density=600)

    tank_height = compute_tank_height(struct.tank_volume, struct.r_int, struct.tank_spherical_caps)
    tank_geometry_lox = CylindricalTank(struct.r_int, tank_height, spherical_caps=struct.tank_spherical_caps)
    tank_geometry_ethanol = CylindricalTank(struct.r_int, tank_height, spherical_caps=struct.tank_spherical_caps)

    lox_tank = UllageBasedTank(
        name="LOX Tank", flux_time=t_end, geometry=tank_geometry_lox,
        gas=pressurizing_gas_lox, liquid=lox, ullage=lox_tank_ullage,
    )
    ethanol_tank = UllageBasedTank(
        name="Ethanol Tank", flux_time=t_end, geometry=tank_geometry_ethanol,
        gas=pressurizing_gas_ethanol, liquid=ethanol, ullage=ethanol_tank_ullage,
    )

    copv_height = compute_tank_height(struct.copv_volume, struct.r_int_copv, struct.copv_spherical_caps)
    pressure_tank_geometry = CylindricalTank(struct.r_int_copv, copv_height, spherical_caps=struct.copv_spherical_caps)

    copv_lox_mass = Function(str(copv_lox_csv_path), interpolation="linear", extrapolation="constant")
    copv_eth_mass = Function(str(copv_eth_csv_path), interpolation="linear", extrapolation="constant")

    pressure_tank_lox = MassBasedTank(
        name="LOX Pressure Tank", geometry=pressure_tank_geometry, liquid_mass=0,
        flux_time=t_end, gas_mass=copv_lox_mass, gas=pressurizing_gas, liquid=pressurizing_gas,
    )
    pressure_tank_eth = MassBasedTank(
        name="Ethanol Pressure Tank", geometry=pressure_tank_geometry, liquid_mass=0,
        flux_time=t_end, gas_mass=copv_eth_mass, gas=pressurizing_gas, liquid=pressurizing_gas,
    )

    B3 = LiquidMotor(
        thrust_source=str(B3_eng_path),
        dry_mass=1e-5,
        dry_inertia=(1e-5, 1e-5, 1e-5),
        nozzle_radius=struct.r_nozzle,
        center_of_dry_mass_position=1e-5,
        nozzle_position=0,
        burn_time=t_end,
        reshape_thrust_curve=False,
        interpolation_method="linear",
        coordinate_system_orientation="nozzle_to_combustion_chamber",
        reference_pressure=101325,
    )

    B3.add_tank(lox_tank, position=struct.pos_lox)
    B3.add_tank(pressure_tank_lox, position=struct.pos_copv_mbay)
    B3.add_tank(ethanol_tank, position=struct.pos_eth)
    B3.add_tank(pressure_tank_eth, position=struct.pos_copv_pbay)

    expected_fluid_mass_release = m_vehicle[idx_break] - m_dry
    rocketpy_fluid_mass_release = B3.propellant_mass(0)
    if not np.isclose(rocketpy_fluid_mass_release, expected_fluid_mass_release, atol=1e-4, rtol=1e-6):
        raise RuntimeError(
            "RocketPy fluid inventory does not match wrapper fluid inventory "
            "at hold-down release."
        )

    firehorn2 = Rocket(
        radius=struct.r_rocket,
        mass=m_dry,
        inertia=(Ix, Iy, Iz),
        power_off_drag=struct.drag_coeff_rocket,
        power_on_drag=struct.drag_coeff_rocket,
        center_of_mass_without_motor=z_cm,
        coordinate_system_orientation="tail_to_nose",
    )
    firehorn2.add_cm_eccentricity(x=0, y=y_cm)
    firehorn2.add_motor(motor=B3, position=0)

    firehorn2.set_rail_buttons(
        lower_button_position=struct.pos_inf_rb,
        upper_button_position=struct.pos_sup_rb,
    )
    firehorn2.add_nose(
        length=struct.l_nosecone, kind="powerseries", power=0.5,
        position=Nosecone.z + struct.l_nosecone,
    )
    firehorn2.add_trapezoidal_fins(
        n=int(struct.n_fins),
        span=struct.env_fins,
        root_chord=struct.rc_fins,
        position=struct.pos_fins,
        cant_angle=int(struct.cangle_fins),
        tip_chord=struct.tc_fins,
        sweep_length=struct.sweep_l_fins,
    )
    firehorn2.add_tail(
        top_radius=struct.top_r_bt,
        bottom_radius=struct.bottom_r_bt,
        length=struct.l_bt,
        position=Boattail.length,
    )
    firehorn2.add_parachute(
        name="reefed", cd_s=struct.drag_coeff_para_reefed,
        trigger="apogee", sampling_rate=100, lag=7, noise=(0, 0, 0),
    )
    firehorn2.add_parachute(
        name="unreefed", cd_s=struct.drag_coeff_para_unreefed,
        trigger=struct.trig_alt_para, sampling_rate=100, lag=0, noise=(0, 0, 0),
    )

    rocket_drawing_path = None
    if draw_rocket:
        rocket_drawing_path = Path(tempfile.mkdtemp()) / "rocket_drawing.png"
        firehorn2.draw(filename=str(rocket_drawing_path))
        _autocrop_whitespace(rocket_drawing_path)

    flight = Flight(
        rocket=firehorn2,
        rail_length=params.l_rail,
        environment=env,
        inclination=params.inclination_rail,
        heading=params.heading_rail,
    )

    # ------------------------------------------------------------------
    # 14. Résultats
    # ------------------------------------------------------------------
    t_plot = np.linspace(0.01, flight.t_final * 0.999, params.n_points)
    altitude = np.array([flight.altitude(t) for t in t_plot])
    speed = np.array([flight.speed(t) for t in t_plot])
    acceleration = np.array([flight.acceleration(t) for t in t_plot])
    static_margin = np.array([flight.static_margin(t) for t in t_plot])
    latitude = np.array([flight.latitude(t) for t in t_plot])
    longitude = np.array([flight.longitude(t) for t in t_plot])
    # Coordonnées locales par rapport au pas de tir (x = est, y = nord, en
    # mètres) — utiles pour les tracés 3D / vue en plan (indépendantes de la
    # projection lat/long).
    local_x = np.array([flight.x(t) for t in t_plot])
    local_y = np.array([flight.y(t) for t in t_plot])
    phi = np.array([flight.phi(t) for t in t_plot])
    theta = np.array([flight.theta(t) for t in t_plot])
    psi = np.array([flight.psi(t) for t in t_plot])

    impact_latitude = float(flight.latitude(flight.t_final))
    impact_longitude = float(flight.longitude(flight.t_final))
    impact_distance = float(np.sqrt(flight.x_impact**2 + flight.y_impact**2))

    parachute_events = []
    for trigger_time, parachute in flight.parachute_events:
        open_time = trigger_time + parachute.lag
        parachute_events.append({
            "name": parachute.name.title(),
            "time": float(open_time),
            "altitude": float(flight.altitude(open_time)),
            "latitude": float(flight.latitude(open_time)),
            "longitude": float(flight.longitude(open_time)),
        })

    # ------------------------------------------------------------------
    # 15. save_files : nettoyage si désactivé
    # ------------------------------------------------------------------
    output_folder = None
    if params.save_files:
        output_folder = str(version_dir)
    else:
        shutil.rmtree(version_dir, ignore_errors=True)

    return {
        "flight": flight,
        "rocket_drawing": str(rocket_drawing_path) if rocket_drawing_path else None,
        "atmospheric_model": atmospheric_model_used,
        "output_folder": output_folder,
        "apogee_agl": float(flight.altitude(flight.apogee_time)),
        "apogee_asl": float(flight.apogee),
        "max_speed": float(flight.max_speed),
        "max_acceleration": float(flight.max_acceleration),
        "max_mach": float(flight.max_mach_number),
        "time_to_apogee": float(flight.apogee_time),
        "out_of_rail_velocity": float(flight.out_of_rail_velocity),
        "out_of_rail_time": float(flight.out_of_rail_time),
        "out_of_rail_stability_margin": float(flight.out_of_rail_stability_margin),
        "dry_mass": float(m_dry),
        "wet_mass": float(m_wet),
        "nominal_total_impulse": float(nominal_total_impulse),
        "trajectory": {"time": t_plot, "altitude": altitude, "x": local_x, "y": local_y},
        "velocity": {"time": t_plot, "speed": speed},
        "acceleration": {"time": t_plot, "accel": acceleration},
        "static_margin": {"time": t_plot, "margin": static_margin},
        "euler_angles": {"time": t_plot, "phi": phi, "theta": theta, "psi": psi},
        "thrust_curve": {"time": t_total, "thrust": F_eng},
        "map": {
            "latitude": latitude,
            "longitude": longitude,
            "altitude": altitude,
            "launch_latitude": float(params.latitude),
            "launch_longitude": float(params.longitude),
            "impact_latitude": impact_latitude,
            "impact_longitude": impact_longitude,
            "impact_x": float(flight.x_impact),
            "impact_y": float(flight.y_impact),
            "impact_distance": impact_distance,
            "parachute_events": parachute_events,
        },
    }
