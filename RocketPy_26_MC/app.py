"""
app.py

Streamlit interface for the FH2/EuRoC flight simulator.

Run with:
    streamlit run app.py

Structure:
- Home screen: choose "Simulation normale" (a single flight) or
  "Analyse Monte Carlo" (many perturbed flights to estimate dispersion).
- Simulation normale: sidebar (model selection, advanced mode, run button),
  Structure / Propellant / Parameters tabs with forms auto-generated from
  the dataclasses, then metrics + plots once the simulation has run.
- Analyse Monte Carlo: same baseline configuration tabs, plus a panel to
  pick which parameters to randomize, the ± range and step, and the number
  of runs. Produces a 3D trajectory overlay and a 2D impact-point scatter
  relative to the launch pad.

Requires (on top of the single-sim dependencies): plotly (for the 3D and
impact plots in Monte Carlo mode) — `pip install plotly`.
"""
from __future__ import annotations

import dataclasses
import math
import os
from pathlib import Path

import numpy as np
import pandas as pd
import pydeck as pdk
import streamlit as st

try:
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

from class_structure import Structure, read_structure
from class_propellant import Propellant, read_propellant
from class_parameters import Parameters, read_parameters
from simulator import run_simulation

st.set_page_config(
    page_title="ERT Flight Simulator",
    layout="wide",
    page_icon="logo_ert_sim_bebas.png",
)

st.markdown(
    """
    <style>
    button[data-testid="stNumberInputStepUp"],
    button[data-testid="stNumberInputStepDown"] {
        display: none;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

col_title, col_logo = st.columns([5, 1.5])
with col_title:
    st.title("ERT Flight Simulator")
    st.caption("Developed by FD team, spring 2026")
with col_logo:
    st.image("logo_ert_sim_bebas.png", width=300)


def fmt(value: float, sig: int = 4) -> str:
    """Format a number with a reasonable number of significant digits
    (avoids ugly values like 37.00000) while keeping large numbers readable."""
    if value is None or (isinstance(value, float) and (math.isnan(value) or math.isinf(value))):
        return "-"
    if value == 0:
        return "0"
    digits = sig - int(math.floor(math.log10(abs(value)))) - 1
    rounded = round(value, max(digits, 0))
    if abs(rounded) >= 1000:
        return f"{rounded:,.0f}".replace(",", " ")
    if rounded == int(rounded):
        return f"{int(rounded)}"
    return f"{rounded:g}"

# ----------------------------------------------------------------------
# 1. Available models (path to the default-values Excel file)
# ----------------------------------------------------------------------
MODELS = {
    "FH2": "DEFAULT.xlsx",
}

# Parameters considered "essential" -> visible even in simple mode.
# The rest only appears when "Advanced mode" is checked.
ESSENTIAL_FIELDS = {
    "Structure": {"mode", "trig_alt_para", "tank_spherical_caps", "tank_volume", "r_int"},
    "Propellant": {"of_ratio", "isp", "thrust", "total_impulse", "f_hold_down"},
    "Parameters": {"version", "save_files", "write_to_file", "latitude", "longitude", "elevation", "inclination_rail", "heading_rail"},
}

# Parameters fields that exist for schema parity with the base simulation
# code but are not used by PRISM's own export flow (which is driven by the
# sidebar/export checkboxes further down) — always hidden from the form.
PARAMETERS_HIDDEN_FIELDS = {
    "output_general", "output_euler_angles", "output_stability",
    "output_trajectory", "output_velocity", "output_acceleration", "output_thrust_curve",
}

LAUNCH_SITES = {
    "EuRoC (Portugal)": {"latitude": 39.390150, "longitude": -8.289145, "elevation": 130.0},
    "Payerne (Switzerland)": {"latitude": 46.8432, "longitude": 6.9151, "elevation": 447.0},
    "EPFL (Switzerland)": {"latitude": 46.5191, "longitude": 6.5668, "elevation": 397.0},
    "Sion (Switzerland)": {"latitude": 46.2196, "longitude": 7.3267, "elevation": 482.0},
}


@st.cache_data
def load_defaults(excel_path: str, _mtime: float):
    structure = read_structure(excel_path)
    propellant = read_propellant(excel_path)
    parameters = read_parameters(excel_path)
    return structure, propellant, parameters


# ----------------------------------------------------------------------
# Parameter descriptions (shown as tooltips on hover)
# ----------------------------------------------------------------------
PARAM_HELP = {
    # --- Structure ---
    "mode_CoM": "0 = compute dry mass/CoM from the bays below. 1 = use a measured dry mass + CoM (m_dry_measured, l_center_of_mass) with the bays as additional masses only — inertia is then a fixed measured value, not recomputed.",
    "mode_Inertia": "0 = compute inertia from the bays below. 1 = use a measured dry mass + CoM (m_dry_measured, l_center_of_mass) with the bays as additional masses only — inertia is then a fixed measured value, not recomputed.",
    "l_center_of_mass": "Measured center-of-mass axial position (mode 1 only) [mm or same unit as bay positions]",
    "m_dry_measured": "Measured dry mass of the reference vehicle (mode 1 only) [kg]",
    "r_rocket": "Rocket body outer radius [m]",
    "drag_coeff_rocket": "Rocket drag coefficient (Cd), dimensionless",
    "top_r_bt": "Boattail top radius [m]",
    "bottom_r_bt": "Boattail bottom radius [m]",
    "l_bt": "Boattail length [m]",
    "m_bt": "Boattail mass [kg]",
    "r_nozzle": "Engine nozzle exit radius [m]",
    "l_ebay": "Engine bay length [m]",
    "m_ebay": "Engine bay mass [kg]",
    "pos_lox": "LOX tank fluid axial position fed to RocketPy [m] (independent from the bay chain, used for motor CG modeling)",
    "l_lox": "LOX tank bay length [m]",
    "m_lox": "LOX tank bay mass [kg]",
    "pos_aerocover": "Aerocover axial position from the boattail base [m]",
    "m_aerocover": "Aerocover mass [kg]",
    "l_aerocover": "Aerocover length [m]",
    "r_aerocover": "Aerocover width/radius [m]",
    "pos_copv_mbay": "LOX-side COPV (pressurant tank) fluid axial position fed to RocketPy [m]",
    "l_pbay1": "Pressurant bay 1 length [m]",
    "m_pbay1": "Pressurant bay 1 mass [kg]",
    "pos_eth": "Ethanol tank fluid axial position fed to RocketPy [m] (independent from the bay chain, used for motor CG modeling)",
    "l_eth": "Ethanol tank bay length [m]",
    "m_eth": "Ethanol tank bay mass [kg]",
    "pos_copv_pbay": "Ethanol-side COPV (pressurant tank) fluid axial position fed to RocketPy [m]",
    "l_pbay2": "Pressurant bay 2 length [m]",
    "m_pbay2": "Pressurant bay 2 mass [kg]",
    "l_avbay": "Avionics bay length [m]",
    "m_avbay": "Avionics bay mass [kg]",
    "l_rebay": "Recovery bay length [m]",
    "m_rebay": "Recovery bay mass [kg]",
    "drag_coeff_para_reefed": "Reefed main parachute Cd·S (drag coefficient × area) [m²]",
    "drag_coeff_para_unreefed": "Fully open main parachute Cd·S (drag coefficient × area) [m²]",
    "trig_alt_para": "Altitude AGL at which the main parachute fully opens [m]",
    "l_nosecone": "Nose cone length [m]",
    "m_nosecone": "Nose cone mass [kg]",
    "r_int": "Propellant tank internal radius [m]",
    "tank_spherical_caps": "Whether the LOX/Ethanol tanks have hemispherical end caps (True) or flat caps (False)",
    "tank_volume": "LOX/Ethanol tank internal volume [m³] — the cylindrical height is derived automatically from this and the radius",
    "h_cap": "Propellant tank end-cap height [m]",
    "r_int_copv": "COPV (pressurant tank) internal radius [m]",
    "copv_spherical_caps": "Whether the COPV has hemispherical end caps (True) or flat caps (False)",
    "copv_volume": "COPV internal volume [m³] — the cylindrical height is derived automatically from this and the radius",
    "n_fins": "Number of fins",
    "env_fins": "Fin span [m]",
    "rc_fins": "Fin root chord [m]",
    "tc_fins": "Fin tip chord [m]",
    "pos_fins": "Fin axial position [m]",
    "cangle_fins": "Fin cant angle [deg]",
    "sweep_l_fins": "Fin sweep length [m]",
    "m_fins": "Total fins mass [kg] (bundled into the engine bay mass for CoM/inertia)",
    "pos_sup_rb": "Upper rail button axial position [m]",
    "pos_inf_rb": "Lower rail button axial position [m]",
    # --- Propellant ---
    "of_ratio": "Oxidizer-to-fuel mass ratio (O/F)",
    "isp": "Specific impulse [s]",
    "thrust": "Nominal (steady-state / peak) thrust [N]",
    "total_impulse": "Total impulse delivered over the burn [N·s]",
    "lox_boil_off": "LOX boil-off mass flow rate during hold-down [kg/s]",
    "lox_prechill": "LOX mass flow rate during tank prechill [kg/s]",
    "lox_ignition": "LOX mass flow rate during the ignition delay [kg/s]",
    "lox_ramp_up": "LOX mass flow rate during thrust ramp-up [kg/s]",
    "lox_ramp_down": "LOX mass flow rate during thrust ramp-down [kg/s]",
    "lox_cutoff": "LOX mass flow rate during the final cutoff phase [kg/s]",
    "eth_ignition": "Ethanol mass flow rate during the ignition delay [kg/s]",
    "eth_ramp_up": "Ethanol mass flow rate during thrust ramp-up [kg/s]",
    "eth_ramp_down": "Ethanol mass flow rate during thrust ramp-down [kg/s]",
    "eth_cutoff": "Ethanol mass flow rate during the final cutoff phase [kg/s]",
    "eth_frac_cooling": "Fraction of ethanol flow diverted to film cooling",
    "m_eth_unused": "Ethanol mass left unused (trapped) at burnout [kg]",
    "m_eth_density": "Ethanol density [kg/m³]",
    "m_lox_unused": "LOX mass left unused (trapped) at burnout [kg]",
    "m_lox_density": "LOX density [kg/m³]",
    "m_n2": "Nitrogen pressurant mass per COPV [kg]",
    "hold_time": "Hold-down duration before ignition [s]",
    "prechill_time": "LOX line/tank prechill duration [s]",
    "ignition_delay": "Delay between valve opening and ignition [s]",
    "ramp_up_time": "Thrust ramp-up duration at start of burn [s]",
    "cutoff_time": "Final cutoff duration, from f_shutdown down to zero thrust [s]",
    "ramp_down_time": "Thrust ramp-down duration, down to f_shutdown [s]",
    "f_shutdown": "Thrust level at the start of the final cutoff phase [N]",
    "f_hold_down": "Force threshold at which the hold-down mechanism releases [N]",
    # --- Parameters ---
    "version": "Simulation/version identifier, used to name output files",
    "save_files": "Whether to write .eng / .csv intermediate files to disk",
    "n_points": "Number of time samples used across the simulation",
    "write_to_file": "Whether to write the results back into the Excel file",
    "annee": "Launch year",
    "mois": "Launch month",
    "jour": "Launch day",
    "heure": "Launch hour (UTC)",
    "minute": "Launch minute (UTC)",
    "latitude": "Launch site latitude [deg]",
    "longitude": "Launch site longitude [deg]",
    "elevation": "Launch site ground elevation [m]",
    "alpha_rail": "Hold-down angle alpha, between thrust line and rail [deg]",
    "beta_rail": "Hold-down angle beta, of the hold-down mechanism [deg]",
    "l_rail": "Launch rail length [m]",
    "coeff_fr_rail": "Friction coefficient between the rocket and the rail",
    "inclination_rail": "Launch rail inclination from horizontal [deg]",
    "heading_rail": "Launch rail heading from north [deg]",
}


def render_dataclass_form(obj, prefix: str, advanced: bool, essential_keys: set[str], exclude_fields: set[str] = frozenset()):
    """
    Generates a form from a dataclass's fields.
    Returns a dict {field: new_value} to apply with dataclasses.replace().
    """
    updated = {}
    field_list = [
        f for f in dataclasses.fields(obj)
        if f.name not in exclude_fields and (advanced or f.name in essential_keys)
    ]

    cols = st.columns(2)
    for i, f in enumerate(field_list):
        value = getattr(obj, f.name)
        widget_key = f"{prefix}_{f.name}"
        help_text = PARAM_HELP.get(f.name)
        with cols[i % 2]:
            if isinstance(value, bool):
                updated[f.name] = st.checkbox(f.name, value=value, key=widget_key, help=help_text)
            elif isinstance(value, int):
                updated[f.name] = st.number_input(f.name, value=value, step=1, key=widget_key, help=help_text)
            elif isinstance(value, float):
                updated[f.name] = st.number_input(f.name, value=value, format="%.4g", key=widget_key, help=help_text)
            elif isinstance(value, str):
                updated[f.name] = st.text_input(f.name, value=value, key=widget_key, help=help_text)
            else:
                st.write(f"{f.name}: {value}")
                updated[f.name] = value

    if not advanced:
        total_visible_candidates = len([f for f in dataclasses.fields(obj) if f.name not in exclude_fields])
        n_hidden = total_visible_candidates - len(field_list)
        if n_hidden > 0:
            st.caption(f"{n_hidden} advanced parameter(s) hidden — check \u00ab Advanced mode \u00bb to see them.")

    return updated


# ========================================================================
# Home screen — choose Simulation normale vs. Analyse Monte Carlo
# ========================================================================
if "app_mode" not in st.session_state:
    st.session_state["app_mode"] = None

if st.session_state["app_mode"] is None:
    st.markdown(
        """
        <style>
        .home-card {
            border: 1px solid rgba(128,128,128,0.3);
            border-radius: 14px;
            padding: 1.8rem 1.6rem 1.4rem 1.6rem;
            height: 210px;
            text-align: center;
            display: flex;
            flex-direction: column;
            justify-content: center;
            transition: box-shadow 0.15s ease, transform 0.15s ease;
        }
        .home-card:hover {
            box-shadow: 0 4px 18px rgba(0,0,0,0.12);
            transform: translateY(-2px);
        }
        .home-card .home-icon { font-size: 2.6rem; margin-bottom: 0.3rem; }
        .home-card .home-title { font-size: 1.25rem; font-weight: 700; margin-bottom: 0.5rem; }
        .home-card .home-desc { font-size: 0.92rem; color: rgba(128,128,128,0.95); line-height: 1.4; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        "<h2 style='text-align:center; margin-bottom:0.2rem;'>Que veux-tu faire ?</h2>"
        "<p style='text-align:center; color:rgba(128,128,128,0.9); margin-bottom:2rem;'>"
        "Choisis un mode pour commencer.</p>",
        unsafe_allow_html=True,
    )

    col_a, col_gap, col_b = st.columns([10, 1, 10])
    with col_a:
        st.markdown(
            """
            <div class="home-card">
                <div class="home-icon">🚀</div>
                <div class="home-title">Simulation normale</div>
                <div class="home-desc">Un seul vol, avec les paramètres que tu choisis.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.write("")
        if st.button("Lancer une simulation normale", type="primary", width="stretch"):
            st.session_state["app_mode"] = "single"
            st.rerun()
    with col_b:
        st.markdown(
            """
            <div class="home-card">
                <div class="home-icon">🎲</div>
                <div class="home-title">Analyse Monte Carlo</div>
                <div class="home-desc">Fait varier plusieurs paramètres (poussée, Isp, masse,
                ailerons, vent, angle de rampe...) aléatoirement sur de nombreux tirs pour
                estimer la dispersion : apogée, point d'impact, etc.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.write("")
        if st.button("Lancer une analyse Monte Carlo", width="stretch"):
            st.session_state["app_mode"] = "monte_carlo"
            st.rerun()
    st.stop()

with st.sidebar:
    if st.button("← Retour à l'accueil"):
        st.session_state["app_mode"] = None
        st.rerun()
    st.divider()
    st.subheader("Configuration")
    model_name = st.selectbox("Model", list(MODELS.keys()))

excel_path = MODELS[model_name]
if not Path(excel_path).exists():
    st.error(
        f"Excel file not found: {excel_path}. "
        "Place it in the same folder as app.py (or update MODELS)."
    )
    st.stop()

default_structure, default_propellant, default_parameters = load_defaults(
    excel_path, os.path.getmtime(excel_path)
)


# ========================================================================
# Mode : Simulation normale
# ========================================================================
def render_single_sim(default_structure, default_propellant, default_parameters):
    with st.sidebar:
        advanced = st.checkbox("Advanced mode", value=False)
        run_clicked = st.button("Run simulation", type="primary")

    tab_structure, tab_propellant, tab_parameters = st.tabs(
        ["Structure", "Propellant", "Parameters"]
    )

    with tab_structure:
        structure_vals = render_dataclass_form(
            default_structure, "struct", advanced, ESSENTIAL_FIELDS["Structure"]
        )

    with tab_propellant:
        thrust_curve_mode = st.radio(
            "Thrust curve model",
            options=["constant", "peaked"],
            index=0 if default_propellant.thrust_curve_mode != "peaked" else 1,
            format_func=lambda m: "Constant thrust" if m == "constant" else "Peak then derate",
            horizontal=True,
            key="thrust_curve_mode",
            help=(
                "Constant thrust: flat thrust profile during the burn (simple model), "
                "set with a single value ('thrust' below). "
                "Peak then derate: thrust peaks shortly after ignition ('thrust' below "
                "is used as the peak) then settles to a lower steady value ('derated "
                "thrust') before shutdown. Total impulse is kept consistent with "
                "'total_impulse' either way."
            ),
        )

        derated_thrust_val = 0.0
        if thrust_curve_mode == "peaked":
            derated_thrust_val = st.number_input(
                "Derated thrust (after peak) [N]",
                value=float(default_propellant.derated_thrust or default_propellant.thrust * 0.85),
                format="%.4g",
                key="prop_derated_thrust",
                help="Steady thrust the engine settles to after the initial peak, before shutdown. 0 = default to 85% of the peak.",
            )

        propellant_vals = render_dataclass_form(
            default_propellant, "prop", advanced, ESSENTIAL_FIELDS["Propellant"],
            exclude_fields={"thrust_curve_mode", "derated_thrust", "m_lox_density", "m_eth_density"},
        )
        propellant_vals["thrust_curve_mode"] = thrust_curve_mode
        propellant_vals["derated_thrust"] = derated_thrust_val

    with tab_parameters:
        site_options = ["Custom"] + list(LAUNCH_SITES.keys())
        site_choice = st.selectbox("Launch site preset", site_options, key="site_preset")

        if site_choice != "Custom" and st.session_state.get("_prev_site_preset") != site_choice:
            site = LAUNCH_SITES[site_choice]
            st.session_state["params_latitude"] = site["latitude"]
            st.session_state["params_longitude"] = site["longitude"]
            st.session_state["params_elevation"] = site["elevation"]
        st.session_state["_prev_site_preset"] = site_choice

        version_val = st.text_input(
            "version", value=default_parameters.version, key="params_version",
            help=PARAM_HELP.get("version"),
        )

        col_save, col_write = st.columns(2)
        with col_save:
            save_files_val = st.checkbox(
                "save_files", value=default_parameters.save_files, key="params_save_files",
                help=PARAM_HELP.get("save_files"),
            )
        with col_write:
            write_to_file_val = st.checkbox(
                "write_to_file", value=default_parameters.write_to_file, key="params_write_to_file",
                help=PARAM_HELP.get("write_to_file"),
            )

        if write_to_file_val:
            st.markdown("**What to export once the simulation finishes:**")
            st.caption("CSV files")
            col_c1, col_c2, col_c3, col_c4 = st.columns(4)
            with col_c1:
                st.checkbox("General results", value=False, key="exp_general")
            with col_c2:
                st.checkbox("Structure", value=False, key="exp_struct")
            with col_c3:
                st.checkbox("Propellant", value=False, key="exp_prop")
            with col_c4:
                st.checkbox("Parameters", value=False, key="exp_params")

            st.caption("Graphs (PNG)")
            from output_plots import PLOT_REGISTRY
            plot_keys = list(PLOT_REGISTRY.keys())
            plot_cols = st.columns(len(plot_keys))
            for col, key in zip(plot_cols, plot_keys):
                label, _ = PLOT_REGISTRY[key]
                with col:
                    st.checkbox(label, value=(key in ("euler_angles", "stability_margin")), key=f"exp_plot_{key}")

        parameters_vals = render_dataclass_form(
            default_parameters, "params", advanced, ESSENTIAL_FIELDS["Parameters"],
            exclude_fields={"version", "save_files", "write_to_file"} | PARAMETERS_HIDDEN_FIELDS,
        )
        parameters_vals["version"] = version_val
        parameters_vals["save_files"] = save_files_val
        parameters_vals["write_to_file"] = write_to_file_val

    # --------------------------------------------------------------
    # Running the simulation
    # --------------------------------------------------------------
    if run_clicked:
        structure = dataclasses.replace(default_structure, **structure_vals)
        propellant = dataclasses.replace(default_propellant, **propellant_vals)
        parameters = dataclasses.replace(default_parameters, **parameters_vals)

        with st.spinner("Simulation running (RocketPy)..."):
            try:
                result = run_simulation(
                    structure, propellant, parameters,
                    work_dir="sim_output",
                )
                st.session_state["result"] = result
                st.session_state["result_error"] = None
                st.session_state["last_structure"] = structure
                st.session_state["last_propellant"] = propellant
                st.session_state["last_parameters"] = parameters
            except Exception as e:  # noqa: BLE001
                st.session_state["result"] = None
                st.session_state["result_error"] = str(e)
                result = None

        st.session_state["exported_csv_paths"] = []
        st.session_state["export_error"] = None
        if result and parameters.write_to_file:
            try:
                from output_results import write_dataclass_csv, write_flight_outputs_csv
                from output_plots import PLOT_REGISTRY

                version = parameters.version.strip()
                directory = result.get("output_folder") or f"sim_output/{version}"
                exported = []
                if st.session_state.get("exp_general", False):
                    exported.append(str(write_flight_outputs_csv(
                        result["flight"], version, directory,
                        dry_mass=result.get("dry_mass"), wet_mass=result.get("wet_mass"),
                        nominal_total_impulse=result.get("nominal_total_impulse"),
                    )))
                if st.session_state.get("exp_struct"):
                    exported.append(str(write_dataclass_csv(structure, "Structure", directory)))
                if st.session_state.get("exp_prop"):
                    exported.append(str(write_dataclass_csv(propellant, "Propellant", directory)))
                if st.session_state.get("exp_params"):
                    exported.append(str(write_dataclass_csv(parameters, "Parameters", directory)))
                for key in PLOT_REGISTRY:
                    if st.session_state.get(f"exp_plot_{key}"):
                        _, plot_fn = PLOT_REGISTRY[key]
                        exported.append(str(plot_fn(result, directory)))
                st.session_state["exported_csv_paths"] = exported
            except Exception as e:  # noqa: BLE001
                st.session_state["export_error"] = str(e)

    if st.session_state.get("result_error"):
        st.error(f"Simulation failed: {st.session_state['result_error']}")

    if st.session_state.get("export_error"):
        st.error(f"Export failed: {st.session_state['export_error']}")

    result = st.session_state.get("result")

    # --------------------------------------------------------------
    # Results
    # --------------------------------------------------------------
    if result:
        st.subheader("Results")

        if result.get("rocket_drawing") and Path(result["rocket_drawing"]).exists():
            st.image(result["rocket_drawing"], caption="Rocket model (generated by RocketPy)", width=500)

        st.caption(f"Atmospheric model used: {result.get('atmospheric_model', 'unknown')}")

        if result.get("output_folder"):
            st.success(f"Intermediate files saved to: `{result['output_folder']}`")
        else:
            st.caption("Intermediate files were not saved (save_files is off).")

        if st.session_state.get("exported_csv_paths"):
            csv_list = "\n".join(f"- `{p}`" for p in st.session_state["exported_csv_paths"])
            st.info(f"Exported files:\n{csv_list}")

        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Dry mass", f"{fmt(result['dry_mass'])} kg")
        col2.metric("Wet mass", f"{fmt(result['wet_mass'])} kg")
        col3.metric("Rail exit stability", f"{fmt(result['out_of_rail_stability_margin'], 3)} cal")
        col4.metric("Rail exit velocity", f"{fmt(result['out_of_rail_velocity'])} m/s")
        col5.metric("Max Mach", f"{fmt(result['max_mach'], 3)}")

        col6, col7, col8, col9, col10 = st.columns(5)
        col6.metric("Apogee (AGL)", f"{fmt(result['apogee_agl'])} m")
        col7.metric("Horizontal distance", f"{fmt(result['map']['impact_distance'])} m")

        graph_traj, graph_vel, graph_acc, graph_margin, graph_thrust = st.tabs(
            ["Trajectory", "Velocity", "Acceleration", "Stability", "Thrust"]
        )

        with graph_traj:
            df_traj = pd.DataFrame({
                "time": result["trajectory"]["time"],
                "Altitude (m)": result["trajectory"]["altitude"],
            })
            st.line_chart(df_traj, x="time", y="Altitude (m)")

            st.caption("Ground track: liftoff → impact")
            map_data = result["map"]

            path_coords = [
                [lon, lat, alt]
                for lat, lon, alt in zip(map_data["latitude"], map_data["longitude"], map_data["altitude"])
            ]

            path_layer = pdk.Layer(
                "PathLayer",
                data=[{"path": path_coords}],
                get_path="path",
                get_width=4,
                width_min_pixels=2,
                get_color=[255, 99, 71],
                pickable=True,
            )

            points_data = [
                {
                    "position": [map_data["launch_longitude"], map_data["launch_latitude"], 0],
                    "label": "Liftoff",
                    "color": [0, 170, 60],
                    "radius": 25,
                },
                {
                    "position": [map_data["impact_longitude"], map_data["impact_latitude"], 0],
                    "label": f"Impact — {fmt(map_data['impact_distance'])} m from launch",
                    "color": [220, 40, 40],
                    "radius": 25,
                },
            ]

            for event in map_data.get("parachute_events", []):
                points_data.append({
                    "position": [event["longitude"], event["latitude"], event["altitude"]],
                    "label": f"{event['name']} deployed — {fmt(event['altitude'])} m AGL, t={fmt(event['time'])} s",
                    "color": [40, 120, 220],
                    "radius": 60,
                })

            point_layer = pdk.Layer(
                "ScatterplotLayer",
                data=points_data,
                get_position="position",
                get_fill_color="color",
                get_radius="radius",
                radius_min_pixels=6,
                pickable=True,
            )

            view_state = pdk.ViewState(
                latitude=map_data["launch_latitude"],
                longitude=map_data["launch_longitude"],
                zoom=13,
                pitch=45,
            )

            st.pydeck_chart(pdk.Deck(
                layers=[path_layer, point_layer],
                initial_view_state=view_state,
                tooltip={"text": "{label}"},
            ))

        with graph_vel:
            df_vel = pd.DataFrame({
                "time": result["velocity"]["time"],
                "Speed (m/s)": result["velocity"]["speed"],
            })
            st.line_chart(df_vel, x="time", y="Speed (m/s)")

        with graph_acc:
            df_acc = pd.DataFrame({
                "time": result["acceleration"]["time"],
                "Acceleration (m/s2)": result["acceleration"]["accel"],
            })
            st.line_chart(df_acc, x="time", y="Acceleration (m/s2)")

        with graph_margin:
            df_margin = pd.DataFrame({
                "time": result["static_margin"]["time"],
                "Static margin (calibers)": result["static_margin"]["margin"],
            })
            st.line_chart(df_margin, x="time", y="Static margin (calibers)")
            st.caption("Static margin in calibers — should stay positive for a stable rocket.")

        with graph_thrust:
            df_thrust = pd.DataFrame({
                "time": result["thrust_curve"]["time"],
                "Thrust (N)": result["thrust_curve"]["thrust"],
            })
            st.line_chart(df_thrust, x="time", y="Thrust (N)")

        st.info(
            "PDF export: not wired up yet — next step once the results "
            "display has been validated."
        )
    else:
        st.caption("Configure the parameters then click « Run simulation ».")


# ========================================================================
# Mode : Analyse Monte Carlo
# ========================================================================

# Parameters that can be randomized, and how each one is applied to the
# baseline Structure/Propellant/Parameters. "special" entries are handled
# explicitly in apply_mc_perturbation() below since they don't map to a
# single dataclass field.
MC_VARIABLES = {
    "thrust": {
        "label": "Thrust",
        "help": "Nominal/peak engine thrust — motor-to-motor performance variation.",
    },
    "isp": {
        "label": "Isp",
        "help": "Specific impulse — motor-to-motor performance variation.",
    },
    "dry_mass": {
        "label": "Dry mass",
        "help": "Scales every bay mass together — build/manufacturing mass uncertainty.",
    },
    "fins": {
        "label": "Fin geometry",
        "help": "Scales fin span, root/tip chord and sweep length together — manufacturing tolerance on fin size.",
    },
    "drag": {
        "label": "Drag coefficient (Cd)",
        "help": "Rocket power-on/power-off drag coefficient — aerodynamic model uncertainty.",
    },
    "rail_angle": {
        "label": "Rail launch angle",
        "help": "Rail inclination from horizontal — pointing / tip-off uncertainty.",
    },
    "chute_alt": {
        "label": "Parachute trigger altitude",
        "help": "Altitude AGL at which the main parachute fully opens (trig_alt_para) — deployment sensor/logic uncertainty.",
    },
    "wind": {
        "label": "Wind (gusts)",
        "help": (
            "Wind speed/direction sampled independently at several altitude layers "
            "(0–6000 m AGL) around the base speed below, direction randomized "
            "0–360° per layer — approximates gusts as the rocket climbs through them."
        ),
    },
}

_MC_STRUCT_MASS_FIELDS = [
    "m_bt", "m_ebay", "m_lox", "m_aerocover", "m_pbay1",
    "m_eth", "m_pbay2", "m_avbay", "m_rebay", "m_nosecone", "m_fins",
]
_MC_STRUCT_FIN_FIELDS = ["env_fins", "rc_fins", "tc_fins", "sweep_l_fins"]

# Altitude layers (m AGL) at which wind speed/direction are sampled to build
# a gusty vertical wind profile — RocketPy interpolates linearly between them.
WIND_GUST_ALTITUDES = [0, 300, 800, 1500, 2500, 4000, 6000]

# Sensible default (± range %, step %) per variable — thrust/Isp typically
# vary much less run-to-run than e.g. drag or wind.
DEFAULT_MC_RANGES = {
    "thrust": (5.0, 1.0),
    "isp": (3.0, 0.5),
    "dry_mass": (3.0, 0.5),
    "fins": (5.0, 1.0),
    "drag": (10.0, 2.0),
    "rail_angle": (10.0, 2.0),
    "chute_alt": (10.0, 2.0),
    "wind": (20.0, 5.0),
}


def _mc_sample_pct(rng, grid) -> float:
    """Pick one relative offset (in %, e.g. -6.0) from the discrete grid."""
    return float(rng.choice(grid))


def sample_wind_profile(wind_base_speed, gusty, grid, rng):
    """Builds a (altitude_m, speed_m/s, direction_deg) profile.
    If gusty=False, returns a flat, non-random profile (constant speed,
    direction 0°) — used as the deterministic reference/baseline wind so
    it stays comparable across runs. If gusty=True, each altitude layer
    gets its own speed (sampled from `grid`, same ± range/step as the
    other Monte Carlo variables) and its own random direction (0–360°),
    simulating gusts that change as the rocket climbs."""
    profile = []
    for alt in WIND_GUST_ALTITUDES:
        if gusty:
            f = _mc_sample_pct(rng, grid) / 100.0
            speed = max(wind_base_speed * (1 + f), 0.0)
            direction = float(rng.uniform(0, 360))
        else:
            speed = wind_base_speed
            direction = 0.0
        profile.append((float(alt), speed, direction))
    return profile


def apply_mc_perturbation(base_structure, base_propellant, base_parameters, selected, grids, wind_base_speed, rng):
    """Returns (structure, propellant, parameters, wind_profile, offsets)
    for one Monte Carlo draw. `grids` is a dict {var_key: grid_array} giving
    each selected parameter its own ± range/step grid. `offsets` records
    what was actually sampled, for the detail table."""
    structure = base_structure
    propellant = base_propellant
    parameters = base_parameters
    offsets: dict[str, float] = {}

    if "thrust" in selected:
        f = _mc_sample_pct(rng, grids["thrust"]) / 100.0
        propellant = dataclasses.replace(propellant, thrust=propellant.thrust * (1 + f))
        offsets["thrust [%]"] = f * 100

    if "isp" in selected:
        f = _mc_sample_pct(rng, grids["isp"]) / 100.0
        propellant = dataclasses.replace(propellant, isp=propellant.isp * (1 + f))
        offsets["isp [%]"] = f * 100

    if "dry_mass" in selected:
        f = _mc_sample_pct(rng, grids["dry_mass"]) / 100.0
        updates = {name: getattr(structure, name) * (1 + f) for name in _MC_STRUCT_MASS_FIELDS}
        structure = dataclasses.replace(structure, **updates)
        offsets["dry_mass [%]"] = f * 100

    if "fins" in selected:
        f = _mc_sample_pct(rng, grids["fins"]) / 100.0
        updates = {name: getattr(structure, name) * (1 + f) for name in _MC_STRUCT_FIN_FIELDS}
        structure = dataclasses.replace(structure, **updates)
        offsets["fins [%]"] = f * 100

    if "drag" in selected:
        f = _mc_sample_pct(rng, grids["drag"]) / 100.0
        structure = dataclasses.replace(structure, drag_coeff_rocket=structure.drag_coeff_rocket * (1 + f))
        offsets["drag [%]"] = f * 100

    if "rail_angle" in selected:
        f = _mc_sample_pct(rng, grids["rail_angle"]) / 100.0
        parameters = dataclasses.replace(parameters, inclination_rail=parameters.inclination_rail * (1 + f))
        offsets["rail_angle [%]"] = f * 100

    if "chute_alt" in selected:
        f = _mc_sample_pct(rng, grids["chute_alt"]) / 100.0
        structure = dataclasses.replace(structure, trig_alt_para=structure.trig_alt_para * (1 + f))
        offsets["chute_alt [%]"] = f * 100

    wind_profile = sample_wind_profile(wind_base_speed, "wind" in selected, grids.get("wind"), rng)
    if "wind" in selected:
        speeds = [s for _, s, _ in wind_profile]
        offsets["wind_min [m/s]"] = min(speeds)
        offsets["wind_max [m/s]"] = max(speeds)

    return structure, propellant, parameters, wind_profile, offsets


def render_monte_carlo(default_structure, default_propellant, default_parameters):
    if not PLOTLY_AVAILABLE:
        st.error(
            "Le mode Analyse Monte Carlo nécessite le paquet `plotly` "
            "(pour les tracés 3D et le plan d'impact), qui n'est pas installé.\n\n"
            "Installe-le puis relance l'app :\n```bash\npip install plotly\n```"
        )
        st.stop()

    st.subheader("Configuration de base (nominale)")
    st.caption(
        "Ces valeurs servent de point de départ ; l'analyse Monte Carlo fait "
        "varier autour d'elles les paramètres cochés ci-dessous."
    )

    advanced = st.checkbox("Advanced mode", value=False, key="mc_advanced")

    tab_structure, tab_propellant, tab_parameters = st.tabs(
        ["Structure", "Propellant", "Parameters"]
    )
    with tab_structure:
        structure_vals = render_dataclass_form(
            default_structure, "mcs", advanced, ESSENTIAL_FIELDS["Structure"]
        )
    with tab_propellant:
        propellant_vals = render_dataclass_form(
            default_propellant, "mcp", advanced, ESSENTIAL_FIELDS["Propellant"],
            exclude_fields={"thrust_curve_mode", "derated_thrust", "m_lox_density", "m_eth_density"},
        )
        propellant_vals["thrust_curve_mode"] = default_propellant.thrust_curve_mode
        propellant_vals["derated_thrust"] = default_propellant.derated_thrust
    with tab_parameters:
        site_options = ["Custom"] + list(LAUNCH_SITES.keys())
        mc_site_choice = st.selectbox("Launch site preset", site_options, key="mc_site_preset")

        if mc_site_choice != "Custom" and st.session_state.get("_mc_prev_site_preset") != mc_site_choice:
            site = LAUNCH_SITES[mc_site_choice]
            st.session_state["mcpar_latitude"] = site["latitude"]
            st.session_state["mcpar_longitude"] = site["longitude"]
            st.session_state["mcpar_elevation"] = site["elevation"]
        st.session_state["_mc_prev_site_preset"] = mc_site_choice

        parameters_vals = render_dataclass_form(
            default_parameters, "mcpar", advanced, ESSENTIAL_FIELDS["Parameters"],
            exclude_fields={"version", "save_files", "write_to_file"} | PARAMETERS_HIDDEN_FIELDS,
        )
        parameters_vals["version"] = default_parameters.version
        parameters_vals["save_files"] = False
        parameters_vals["write_to_file"] = False

    base_structure = dataclasses.replace(default_structure, **structure_vals)
    base_propellant = dataclasses.replace(default_propellant, **propellant_vals)
    base_parameters = dataclasses.replace(default_parameters, **parameters_vals)

    st.divider()
    st.subheader("Paramètres à faire varier")

    selected = set()
    mc_cols = st.columns(3)
    for i, (key, info) in enumerate(MC_VARIABLES.items()):
        with mc_cols[i % 3]:
            if st.checkbox(info["label"], value=False, key=f"mc_var_{key}", help=info["help"]):
                selected.add(key)

    wind_base_speed = st.number_input(
        "Vitesse de vent de base [m/s]",
        min_value=0.0, value=5.0, step=0.5,
        key="mc_wind_base_speed",
        help=(
            "Vent de référence pour tous les tirs Monte Carlo (évite un appel "
            "météo réel par tir). Si « Wind (gusts) » est coché ci-dessus, la "
            "vitesse est en plus tirée aléatoirement autour de cette valeur à "
            "chaque palier d'altitude, avec une direction randomisée sur 360°."
        ),
    )

    st.divider()
    st.subheader("Étendue de variation")
    st.caption(
        "Chaque paramètre coché a sa propre plage ± % et son propre pas — "
        "le thrust et l'Isp, par exemple, ne varient généralement pas du même ordre de grandeur."
    )

    ranges: dict[str, tuple[float, float]] = {}
    if selected:
        for key in MC_VARIABLES:
            if key not in selected:
                continue
            default_range, default_step = DEFAULT_MC_RANGES[key]
            col_label, col_r, col_s = st.columns([2, 1, 1])
            with col_label:
                st.markdown(f"**{MC_VARIABLES[key]['label']}**")
            with col_r:
                r = st.number_input(
                    "± range (%)", min_value=0.1, max_value=100.0,
                    value=default_range, step=0.5, key=f"mc_range_{key}",
                )
            with col_s:
                s = st.number_input(
                    "Pas (%)", min_value=0.1, max_value=50.0,
                    value=default_step, step=0.1, key=f"mc_step_{key}",
                )
            ranges[key] = (r, s)
    else:
        st.caption("Coche au moins un paramètre ci-dessus pour régler sa plage.")

    n_runs = st.number_input(
        "Nombre de simulations", min_value=5, max_value=500, value=30, step=5,
    )

    run_mc_clicked = st.button("Lancer l'analyse Monte Carlo", type="primary", disabled=(len(selected) == 0))
    if len(selected) == 0:
        st.caption("Coche au moins un paramètre à faire varier pour lancer l'analyse.")

    if run_mc_clicked:
        grids: dict[str, np.ndarray] = {}
        for key, (range_pct, step_pct) in ranges.items():
            grid = np.arange(-range_pct, range_pct + step_pct / 2, step_pct)
            grids[key] = grid if len(grid) > 0 else np.array([0.0])
        rng = np.random.default_rng()

        runs = []
        n_failed = 0
        progress = st.progress(0.0, text="Simulations Monte Carlo en cours...")
        for i in range(int(n_runs)):
            struct_i, prop_i, params_i, wind_profile_i, offsets = apply_mc_perturbation(
                base_structure, base_propellant, base_parameters, selected, grids, wind_base_speed, rng,
            )
            try:
                res = run_simulation(
                    struct_i, prop_i, params_i,
                    work_dir="mc_output", draw_rocket=False,
                    wind_profile=wind_profile_i,
                )
                # Vitesse de vent AU SOL (première couche du profil, alt=0),
                # utilisée pour colorer la trajectoire — pas le max sur tout
                # le profil, qui dépasserait presque toujours le seuil vu le
                # nombre de couches d'altitude tirées indépendamment.
                ground_wind_i = wind_profile_i[0][1]
                runs.append({"offsets": offsets, "wind_speed": ground_wind_i, "result": res})
            except Exception:  # noqa: BLE001
                n_failed += 1
            progress.progress((i + 1) / int(n_runs), text=f"Simulations Monte Carlo en cours... ({i + 1}/{int(n_runs)})")
        progress.empty()

        baseline_result = None
        try:
            # Le nominal doit utiliser exactement le même modèle de vent que
            # le lot Monte Carlo — vent plat, non-aléatoire (gusty=False) —
            # pour rester comparable, que "Wind" soit coché ou non. Sinon le
            # nominal irait chercher la météo réelle (Windy/GFS), incohérente
            # avec le vent utilisé par tous les tirs MC.
            baseline_wind_profile = sample_wind_profile(wind_base_speed, False, None, rng)
            baseline_result = run_simulation(
                base_structure, base_propellant, base_parameters,
                work_dir="mc_output", draw_rocket=False,
                wind_profile=baseline_wind_profile,
            )
        except Exception:  # noqa: BLE001
            pass

        st.session_state["mc_runs"] = runs
        st.session_state["mc_baseline"] = baseline_result
        st.session_state["mc_failed"] = n_failed

    runs = st.session_state.get("mc_runs")
    baseline_result = st.session_state.get("mc_baseline")

    if runs:
        st.divider()
        st.subheader("Résultats")

        n_failed = st.session_state.get("mc_failed", 0)
        status = f"{len(runs)} simulations réussies"
        if n_failed:
            status += f", {n_failed} échouées (paramètres tirés incohérents — hold-down non atteint, etc.)"
        st.success(status)

        apogees = np.array([r["result"]["apogee_agl"] for r in runs])
        distances = np.array([r["result"]["map"]["impact_distance"] for r in runs])

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Apogée moyenne", f"{fmt(apogees.mean())} m")
        col2.metric("Écart-type apogée", f"{fmt(apogees.std())} m")
        col3.metric("Distance d'impact moyenne", f"{fmt(distances.mean())} m")
        col4.metric("Écart-type distance d'impact", f"{fmt(distances.std())} m")

        with st.expander("Critères de tir nominal", expanded=False):
            col_c1, col_c2, col_c3, col_c4 = st.columns(4)
            with col_c1:
                crit_wind_max = st.number_input(
                    "Vent au sol < [m/s]", min_value=0.0, value=8.0, step=0.5, key="mc_crit_wind",
                )
            with col_c2:
                crit_rail_vel_min = st.number_input(
                    "Vitesse sortie rail ≥ [m/s]", min_value=0.0, value=30.0, step=1.0, key="mc_crit_railvel",
                )
            with col_c3:
                crit_stability_min = st.number_input(
                    "Stabilité sortie rail > [cal]", min_value=0.0, value=3.0, step=0.5, key="mc_crit_stability",
                )
            with col_c4:
                crit_apogee_min = st.number_input(
                    "Apogée ≥ [m]", min_value=0.0, value=3000.0, step=50.0, key="mc_crit_apogee",
                )

        n_ok = 0
        for r in runs:
            res = r["result"]
            wind_ok = r.get("wind_speed") is not None and r["wind_speed"] < crit_wind_max
            vel_ok = res["out_of_rail_velocity"] >= crit_rail_vel_min
            stab_ok = res["out_of_rail_stability_margin"] > crit_stability_min
            apogee_ok = res["apogee_agl"] >= crit_apogee_min
            if wind_ok and vel_ok and stab_ok and apogee_ok:
                n_ok += 1
        pct_ok = 100.0 * n_ok / len(runs)
        st.metric(
            "Tirs respectant tous les critères",
            f"{pct_ok:.1f}%",
            help=(
                f"{n_ok}/{len(runs)} tirs avec vent au sol < {crit_wind_max:.1f} m/s, "
                f"vitesse sortie rail ≥ {crit_rail_vel_min:.1f} m/s, "
                f"stabilité sortie rail > {crit_stability_min:.1f} cal "
                f"et apogée ≥ {crit_apogee_min:.0f} m."
            ),
        )

        tab_3d, tab_impact = st.tabs(["Trajectoires 3D (carte)", "Points d'impact"])

        with tab_3d:
            wind_threshold = st.number_input(
                "Seuil de vent mis en évidence [m/s]",
                min_value=0.0, value=8.0, step=0.5,
                key="mc_wind_threshold",
                help="Les trajectoires dont le vent tiré AU SOL (altitude 0) dépasse ce seuil sont tracées en orange.",
            )

            def _run_tooltip_props(run_id, result):
                return {
                    "run_id": str(run_id),
                    "stability_str": f"{fmt(result['out_of_rail_stability_margin'], 3)} cal",
                    "velocity_str": f"{fmt(result['out_of_rail_velocity'])} m/s",
                    "apogee_str": f"{fmt(result['apogee_agl'])} m",
                }

            low_wind_paths, high_wind_paths = [], []
            for i, r in enumerate(runs):
                m = r["result"]["map"]
                path = [[lon, lat, alt] for lat, lon, alt in zip(m["latitude"], m["longitude"], m["altitude"])]
                entry = {"path": path, **_run_tooltip_props(i + 1, r["result"])}
                if r.get("wind_speed") is not None and r["wind_speed"] > wind_threshold:
                    high_wind_paths.append(entry)
                else:
                    low_wind_paths.append(entry)

            layers = []
            if low_wind_paths:
                layers.append(pdk.Layer(
                    "PathLayer", data=low_wind_paths, get_path="path",
                    get_color=[70, 130, 180, 160], get_width=3, width_min_pixels=1.5,
                    pickable=True, auto_highlight=True,
                ))
            if high_wind_paths:
                layers.append(pdk.Layer(
                    "PathLayer", data=high_wind_paths, get_path="path",
                    get_color=[255, 140, 0, 200], get_width=3, width_min_pixels=1.5,
                    pickable=True, auto_highlight=True,
                ))

            launch_lat = runs[0]["result"]["map"]["launch_latitude"]
            launch_lon = runs[0]["result"]["map"]["launch_longitude"]

            if baseline_result:
                bm = baseline_result["map"]
                nominal_path = [[lon, lat, alt] for lat, lon, alt in zip(bm["latitude"], bm["longitude"], bm["altitude"])]
                nominal_entry = {"path": nominal_path, **_run_tooltip_props("Nominal", baseline_result)}
                layers.append(pdk.Layer(
                    "PathLayer", data=[nominal_entry], get_path="path",
                    get_color=[220, 20, 60, 230], get_width=6, width_min_pixels=3,
                    pickable=True, auto_highlight=True,
                ))

            layers.append(pdk.Layer(
                "ScatterplotLayer",
                data=[{"position": [launch_lon, launch_lat, 0]}],
                get_position="position", get_fill_color=[0, 170, 60], get_radius=25,
                radius_min_pixels=6,
            ))

            view_state = pdk.ViewState(latitude=launch_lat, longitude=launch_lon, zoom=12.5, pitch=55)
            st.pydeck_chart(pdk.Deck(
                layers=layers,
                initial_view_state=view_state,
                tooltip={
                    "html": (
                        "<b>Tir {run_id}</b><br/>"
                        "Stabilité sortie rail: {stability_str}<br/>"
                        "Vitesse sortie rail: {velocity_str}<br/>"
                        "Apogée: {apogee_str}"
                    ),
                    "style": {"backgroundColor": "rgba(30,30,30,0.9)", "color": "white"},
                },
            ))
            st.caption("Survole une trajectoire pour voir sa stabilité/vitesse en sortie de rail et son apogée.")
            st.caption(
                f"{len(runs)} trajectoires sur fond de carte réelle — orange = vent au sol > {wind_threshold:.1f} m/s "
                f"({len(high_wind_paths)} tirs), bleu = vent au sol ≤ {wind_threshold:.1f} m/s ({len(low_wind_paths)} tirs), "
                "rouge = trajectoire nominale."
            )
            st.caption(
                "⚠️ Le vent simulé est un profil de rafales par palier d'altitude (pas de vraie météo) "
                "— voir la vitesse de vent de base et le réglage « Wind (gusts) » ci-dessus."
            )

        with tab_impact:
            impact_x = [r["result"]["map"]["impact_x"] for r in runs]
            impact_y = [r["result"]["map"]["impact_y"] for r in runs]
            is_high_wind = [
                (r.get("wind_speed") is not None and r["wind_speed"] > wind_threshold) for r in runs
            ]

            fig2d = go.Figure()
            low_x = [x for x, hw in zip(impact_x, is_high_wind) if not hw]
            low_y = [y for y, hw in zip(impact_y, is_high_wind) if not hw]
            high_x = [x for x, hw in zip(impact_x, is_high_wind) if hw]
            high_y = [y for y, hw in zip(impact_y, is_high_wind) if hw]
            fig2d.add_trace(go.Scatter(
                x=low_x, y=low_y, mode="markers",
                marker=dict(size=8, color="steelblue", opacity=0.6),
                name=f"Wind ≤ {wind_threshold:.1f} m/s",
            ))
            fig2d.add_trace(go.Scatter(
                x=high_x, y=high_y, mode="markers",
                marker=dict(size=8, color="darkorange", opacity=0.8),
                name=f"Wind > {wind_threshold:.1f} m/s",
            ))
            fig2d.add_trace(go.Scatter(
                x=[0], y=[0], mode="markers",
                marker=dict(size=16, color="black", symbol="triangle-up"),
                name="Launch pad",
            ))
            if baseline_result:
                fig2d.add_trace(go.Scatter(
                    x=[baseline_result["map"]["impact_x"]], y=[baseline_result["map"]["impact_y"]],
                    mode="markers",
                    marker=dict(size=13, color="crimson", symbol="x"),
                    name="Nominal impact",
                ))
            fig2d.update_layout(
                xaxis_title="East (m)",
                yaxis_title="North (m)",
                yaxis=dict(scaleanchor="x", scaleratio=1),
                height=600,
            )
            st.plotly_chart(fig2d, width="stretch")
            st.caption("Position des points d'impact par rapport au pas de tir (0, 0).")

        with st.expander("Détail des tirages"):
            rows = []
            for i, r in enumerate(runs):
                res = r["result"]
                row = {
                    "run": i + 1,
                    "apogee [m]": res["apogee_agl"],
                    "stability_rail_exit [cal]": res["out_of_rail_stability_margin"],
                    "velocity_rail_exit [m/s]": res["out_of_rail_velocity"],
                }
                row.update(r["offsets"])
                row["wind_speed [m/s]"] = r.get("wind_speed")
                row["impact_distance [m]"] = res["map"]["impact_distance"]
                rows.append(row)
            st.dataframe(pd.DataFrame(rows), width="stretch")
    else:
        st.caption("Configure les paramètres puis clique sur « Lancer l'analyse Monte Carlo ».")


# ========================================================================
# Dispatch
# ========================================================================
if st.session_state["app_mode"] == "single":
    render_single_sim(default_structure, default_propellant, default_parameters)
else:
    render_monte_carlo(default_structure, default_propellant, default_parameters)
