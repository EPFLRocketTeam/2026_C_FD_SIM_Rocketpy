from excel_io import Input, Thrust_results, Launch_results, Propellant_results
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
import csv

def compute_thrust_curve(ipt:Input, plot:bool = False) -> Thrust_results:
    """Build the engine's thrust profile over time and compute total impulse.

    Returns:
        (t_total, F, total_impulse, slope_ramp_up, slope_derating, slope_shutdown)
        where t_total and F are numpy arrays representing the curve.
    """
    # --- Compute slopes for each linear segment ---
    slope_ramp_up = ipt.F_full_thrust / ipt.t_full_thrust
    slope_derating = (ipt.F_ramp_down - ipt.F_derating) / (ipt.t_ramp_down - ipt.t_derating)
    slope_shutdown = (ipt.F_shutdown - ipt.F_ramp_down) / (ipt.t_shutdown - ipt.t_ramp_down)

    # --- Build time vector and thrust profile ---
    t_total = np.linspace(0, ipt.t_shutdown, ipt.N_points)
    F = np.zeros_like(t_total)

    for i, t in enumerate(t_total):
        if t <= ipt.t_full_thrust:
            F[i] = slope_ramp_up * t
        elif t <= ipt.t_derating:
            F[i] = ipt.F_derating
        elif t <= ipt.t_ramp_down:
            F[i] = ipt.F_derating + slope_derating * (t - ipt.t_derating)
        else:
            F[i] = ipt.F_ramp_down + slope_shutdown * (t - ipt.t_ramp_down)

    # --- Compute total impulse (area under curve) ---
    total_impulse = float(np.trapezoid(F, t_total))

    # --- Plot thrust curve (only if requested) ---
    if plot:
        plt.figure(figsize=(8, 5))
        plt.plot(t_total, F, label='Thrust Curve (Nominal)', color='dodgerblue', linewidth=2)
        plt.title('Thrust Curve (Nominal)')
        plt.xlabel('Time [s]')
        plt.ylabel('Thrust [N]')
        plt.grid(True, which='both', linestyle='--', linewidth=0.5)
        plt.legend()
        plt.tight_layout()
        plt.show()

    return Thrust_results(t_total,F,total_impulse,slope_ramp_up,slope_derating,slope_shutdown)

def compute_hold_down_and_launch(
        ipt:Input,
        tr:Thrust_results,
        plot:bool = False
        ) -> Launch_results:
    # Variables used in formulas
    ## Forces
    m_wet = ipt.m_dry + ipt.m_ox_burn + ipt.m_ox_end + ipt.m_fuel_burn + ipt.m_fuel_end + ipt.m_n2_copv*2 # Already removed all losses before ignition
    W = m_wet * ipt.g

    ## Angles
    alpha_rad = np.deg2rad(ipt.alpha)
    beta_rad = np.deg2rad(ipt.beta)

    ## Time
    dt = np.mean(np.diff(tr.t_total))

    # 1. Compute reaction forces at each time step
    denominator = np.cos(beta_rad) - ipt.mu * np.sin(beta_rad)
    F_HD = (tr.F - W * (np.cos(alpha_rad) - ipt.mu * np.sin(alpha_rad))) / denominator
    F_rrb = (tr.F * np.sin(beta_rad) + W * np.sin(alpha_rad - beta_rad)) / denominator

    # 2. Identify when hold-down force exceeds the break threshold
    if ipt.F_HD_break > 0:
        mask_break = F_HD >= ipt.F_HD_break
        if np.any(mask_break):
            idx_break = int(np.argmax(mask_break))
            t_break = tr.t_total[idx_break]
        else:
            raise ValueError("Hold-down threshold not reached during the burn !")
    else:
        print("No hold-down mechanism !")
        idx_break = 0
        t_break = tr.t_total[idx_break]

    # 3. Launch vehicle kinematics after release
    ## Compute acceleration
    a_LV = (tr.F - m_wet * ipt.g * np.cos(alpha_rad)) / m_wet
    a_LV[a_LV < 0] = 0  # rocket can't accelerate backward along rail

    ## Integrate velocity and displacement over time (from t_break onwards)
    v = np.zeros_like(a_LV)
    s = np.zeros_like(a_LV)

    for i in range(idx_break + 1, len(tr.t_total)):
        v[i] = v[i-1] + a_LV[i-1] * dt
        s[i] = s[i-1] + v[i-1] * dt

    ## Find when rocket clears the rail
    mask_exit = s >= ipt.l_rail
    if np.any(mask_exit):
        idx_exit = np.argmax(mask_exit)
        t_exit = tr.t_total[idx_exit]
        v_exit = v[idx_exit]
    else:
        raise ValueError("Rocket did not clear the rail within thrust duration !")

    # 4. Plot results
    if plot:
        plt.figure(figsize=(9,6))

        plt.plot(tr.t_total, tr.F, label='Thrust $F_{eng}$', color='tab:orange', linewidth=2)
        plt.plot(tr.t_total, F_HD, label='Hold-down force $F_{HD}$', color='tab:red', linewidth=2)
        plt.plot(tr.t_total, F_rrb, label='Rail reaction $F_{rrb}$', color='tab:blue', linewidth=2)

        # Highlight key events
        plt.axvline(t_break, color='green', linestyle='--', label=f'Hold-down break: {t_break:.3f} s')
        plt.axvline(t_exit, color='purple', linestyle='--', label=f'Rail exit: {t_exit:.3f} s')

        plt.title('Thrust and Reaction Forces During Launch')
        plt.xlabel('Time [s]')
        plt.ylabel('Force [N]')
        plt.xlim(0, t_exit * 1.05)
        plt.legend()
        plt.grid(True)
        plt.tight_layout()
        plt.show()
    
    return Launch_results(idx_break,t_break,t_exit,v_exit)

def compute_propellant_masses(
        ipt:Input,
        tr:Thrust_results,
        lr:Launch_results,
        plot:bool = False
        ) -> Propellant_results:
    # Compute equivalent cylindrical height
    A_tank = np.pi * (ipt.r_int**2)
    h_eq = ipt.h_cyl #+ (4/3) * h_cap

    # Compute equivalent total tank volume
    V_tank_total = A_tank * h_eq

    # Compute fixed and free volumes for each propellant
    ## Fuel
    V_fuel_free = ipt.m_fuel_burn / ipt.rho_fuel
    V_fuel_fixed = ipt.m_fuel_end / ipt.rho_fuel
    V_fuel_total = ipt.m_fuel_total / ipt.rho_fuel

    ## Oxidizer
    V_ox_free = ipt.m_ox_burn / ipt.rho_ox
    V_ox_fixed = ipt.m_ox_end / ipt.rho_ox
    V_ox_total = ipt.m_ox_total / ipt.rho_ox

    # Compute equivalent heights
    h_fuel_free = V_fuel_free / A_tank
    h_fuel_fixed = V_fuel_fixed / A_tank
    h_fuel_total = V_fuel_total / A_tank

    h_ox_free = V_ox_free / A_tank
    h_ox_fixed = V_ox_fixed / A_tank
    h_ox_total = V_ox_total / A_tank

    # Heights of interest
    ## Fixed mass (liquid remaining at bottom)
    z_fuel_fixed_COM = h_fuel_fixed / 2
    z_ox_fixed_COM = h_ox_fixed / 2

    ## Free mass bottom position
    z_fuel_free_bottom = h_fuel_fixed
    z_ox_free_bottom = h_ox_fixed

    ## Total mass
    z_fuel_total_COM = h_fuel_total / 2
    z_ox_total_COM = h_ox_total / 2

    z_fuel_total_bottom = h_fuel_total
    z_ox_total_bottom = h_ox_total

    # --------------------- Mass Depletion Curves --------------------------------

    # Helper: compute mdot and remaining mass over the full time array
    def compute_full_depletion(free_mass, rho, t, F):
        """
        Compute mdot(t) and remaining mass mrem(t) for t starting at 0 across full burn.
        mdot proportional to F(t) and normalized so integral mdot dt = free_mass.
        Returns mdot, mrem, consumed (cumulative consumed mass).
        """
        integral_F = np.trapezoid(F, t)
        if integral_F <= 0:
            mdot = np.zeros_like(F)
        else:
            mdot = free_mass * (F / integral_F)
        dt = np.diff(t, prepend=t[0])  # first dt=0
        consumed = np.cumsum(mdot * dt)
        mrem = np.maximum(free_mass - consumed, 0.0)
        Vrem = mrem / rho # calulates remaining propellant volume 
        return mdot, mrem, consumed, Vrem

    # Compute for fuel and oxidizer
    mdot_fuel, mrem_fuel, consumed_fuel, Vrem_fuel = compute_full_depletion(ipt.m_fuel_burn, ipt.rho_fuel, tr.t_total, tr.F)
    mdot_ox,   mrem_ox,   consumed_ox, Vrem_ox   = compute_full_depletion(ipt.m_ox_burn, ipt.rho_ox, tr.t_total, tr.F)

    mass_lost_fuel_before_break = consumed_fuel[lr.idx_break] + ipt.m_fuel_delay
    mass_lost_ox_before_break   = consumed_ox[lr.idx_break] + ipt.m_ox_boil_off + ipt.m_ox_prechill + ipt.m_ox_delay

    # Compute total remaining mass (fixed + free)
    mrem_fuel_total = mrem_fuel + ipt.m_fuel_end # m_fuel_end has m_fuel_cutoff in it
    mrem_ox_total   = mrem_ox + ipt.m_ox_end

    # ------------------ Plotting ------------------
    if plot:
        fig, axes = plt.subplots(2, 1, figsize=(10, 9), sharex=True)
        plt.subplots_adjust(hspace=0.35)

        # Fuel subplot
        ax = axes[0]
        ax.plot(tr.t_total, mdot_fuel, label="Fuel mdot [kg/s]", color="tab:purple", linewidth=2)
        ax.set_ylabel("mdot [kg/s]", color="tab:purple")
        ax.tick_params(axis="y", labelcolor="tab:purple")
        ax.set_ylim(bottom=0)

        ax2 = ax.twinx()
        ax2.plot(tr.t_total, mrem_fuel_total, label="Fuel remaining [kg]", color="tab:green", linewidth=2)
        ax2.set_ylabel("Remaining mass [kg]", color="tab:green")
        ax2.tick_params(axis="y", labelcolor="tab:green")
        ax2.set_ylim(bottom=0)

        ax.axvline(lr.t_break, color="tab:orange", linestyle="--", linewidth=1.5, label="HD break")
        # annotate mass lost before break
        ax2.annotate(f"Lost before HD: {mass_lost_fuel_before_break:.3f} [kg]",
                    xy=(lr.t_break, mrem_fuel_total[lr.idx_break]/2),
                    xytext=(lr.t_break + 0.15 * (tr.t_total[-1]), mrem_fuel_total[lr.idx_break] - 0.5 * ipt.m_fuel_burn),
                    arrowprops=dict(arrowstyle="->", color="gray"))
        ax.set_title("Fuel depletion [entire burn]")
        ax.set_xlabel("Time [s]")

        # Combined legend
        lines, labels = ax.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax.legend(lines + lines2, labels + labels2, loc="upper right")

        # Oxidizer subplot
        ax = axes[1]
        ax.plot(tr.t_total, mdot_ox, label="Ox mdot [kg/s]", color="tab:purple", linewidth=2)
        ax.set_ylabel("mdot [kg/s]", color="tab:purple")
        ax.tick_params(axis="y", labelcolor="tab:purple")
        ax.set_ylim(bottom=0)

        ax2 = ax.twinx()
        ax2.plot(tr.t_total, mrem_ox_total, label="Ox remaining [kg]", color="tab:green", linewidth=2)
        ax2.set_ylabel("Remaining mass [kg]", color="tab:green")
        ax2.tick_params(axis="y", labelcolor="tab:green")
        ax2.set_ylim(bottom=0)

        ax.axvline(lr.t_break, color="tab:orange", linestyle="--", linewidth=1.5, label="HD break")
        ax2.annotate(f"Lost before HD: {mass_lost_ox_before_break:.3f} [kg]",
                    xy=(lr.t_break, mrem_ox_total[lr.idx_break]/2),
                    xytext=(lr.t_break + 0.15 * (tr.t_total[-1]), mrem_ox_total[lr.idx_break] - 0.5 * ipt.m_ox_burn),
                    arrowprops=dict(arrowstyle="->", color="gray"))
        ax.set_title("Oxidizer depletion [entire burn]")
        ax.set_xlabel("Time [s]")

        lines, labels = ax.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax.legend(lines + lines2, labels + labels2, loc="upper right")

        plt.xlim(0, tr.t_total[-1])
        plt.tight_layout()
        plt.show()

    # Fuel volumes (L)
    Vrem_fuel_L = Vrem_fuel * 1000.0
    V_fuel_fixed_m3 = V_fuel_fixed
    ullage_fuel_m3 = V_tank_total - V_fuel_fixed_m3 - Vrem_fuel
    ullage_fuel_L = np.maximum(ullage_fuel_m3 * 1000.0, 0.0)

    # Ox volumes (L)
    Vrem_ox_L = Vrem_ox * 1000.0
    V_ox_fixed_m3 = V_ox_fixed
    ullage_ox_m3 = V_tank_total - V_ox_fixed_m3 - Vrem_ox
    ullage_ox_L = np.maximum(ullage_ox_m3 * 1000.0, 0.0)

    # Volumes lost before break (L)
    vol_fuel_lost_before_break_L = (mass_lost_fuel_before_break / ipt.rho_fuel) * 1000.0
    vol_ox_lost_before_break_L   = (mass_lost_ox_before_break   / ipt.rho_ox)   * 1000.0

    # Create subplots (2 rows: fuel, oxidizer) - shared x axis
    if plot:
        fig, axes = plt.subplots(2, 1, figsize=(10, 9), sharex=True)
        plt.subplots_adjust(hspace=0.35)

        # --- Fuel subplot ---
        ax = axes[0]
        ax.plot(tr.t_total, Vrem_fuel_L, label="Remaining fuel volume [L]", color="tab:blue", linewidth=2)
        ax.plot(tr.t_total, ullage_fuel_L, label="Ullage volume [L]", color="tab:gray", linestyle="--", linewidth=2)
        ax.set_ylabel("Volume [L]")
        ax.set_ylim(bottom=0)
        ax.ticklabel_format(axis='y', style='plain')  # avoid scientific notation

        # vertical marker at HD break
        ax.axvline(lr.t_break, color="tab:orange", linestyle="--", linewidth=1.5, label="HD break")

        # annotate volume lost before break
        ax.annotate(f"Lost before HD: {vol_fuel_lost_before_break_L:.3f} [L]",
                    xy=(lr.t_break, Vrem_fuel_L[lr.idx_break]),
                    xytext=(lr.t_break + 0.05 * (tr.t_total[-1]), max(Vrem_fuel_L.max(), ullage_fuel_L.max()) * 0.6),
                    arrowprops=dict(arrowstyle="->", color="gray"))

        ax.set_title("Fuel remaining volume and ullage [entire burn]")
        ax.legend(loc="upper right")

        # --- Oxidizer subplot ---
        ax = axes[1]
        ax.plot(tr.t_total, Vrem_ox_L, label="Remaining oxidizer volume [L]", color="tab:blue", linewidth=2)
        ax.plot(tr.t_total, ullage_ox_L, label="Ullage volume [L]", color="tab:gray", linestyle="--", linewidth=2)
        ax.set_ylabel("Volume [L]")
        ax.set_ylim(bottom=0)
        ax.ticklabel_format(axis='y', style='plain')

        # vertical marker at HD break
        ax.axvline(lr.t_break, color="tab:orange", linestyle="--", linewidth=1.5, label="HD break")

        # annotate volume lost before break
        ax.annotate(f"Lost before HD: {vol_ox_lost_before_break_L:.3f} [L]",
                    xy=(lr.t_break, Vrem_ox_L[lr.idx_break]),
                    xytext=(lr.t_break + 0.05 * (tr.t_total[-1]), max(Vrem_ox_L.max(), ullage_ox_L.max()) * 0.6),
                    arrowprops=dict(arrowstyle="->", color="gray"))

        ax.set_title("Oxidizer remaining volume and ullage [entire burn]")
        ax.set_xlabel("Time [s]")
        ax.legend(loc="upper right")

        plt.xlim(0, tr.t_total[-1])
        plt.tight_layout()
        plt.show()

    return Propellant_results(
        h_eq, h_fuel_free, h_fuel_fixed, h_fuel_total,
        h_ox_free, h_ox_fixed, h_ox_total,
        V_tank_total, V_fuel_free,V_fuel_fixed,V_fuel_total,
        V_ox_free, V_ox_fixed, V_ox_total,
        z_fuel_fixed_COM, z_ox_fixed_COM, z_fuel_free_bottom,
        z_ox_free_bottom, z_fuel_total_COM, z_ox_total_COM,
        z_fuel_total_bottom, z_ox_total_bottom,
        mass_lost_fuel_before_break, mass_lost_ox_before_break,
        ullage_fuel_m3, ullage_ox_m3
        )

def create_eng_files(ipt:Input, tr:Thrust_results, lr:Launch_results, pr:Propellant_results):
    mask_after_break = tr.t_total >= lr.t_break
    t_flight = tr.t_total[mask_after_break] - lr.t_break  # reset time so that break = 0
    F_flight = tr.F[mask_after_break]
    F_flight[0] = 0

    #print(t_total)
    #print(t_total[mask_after_break])
    #print(t_flight)


    if ipt.savefiles:
        # Define output file name and header 
        eng_filename = f"B3_{ipt.Version}.eng"
        header_line = f"B3_{ipt.Version} 240 200 0 0.001 0.001 ERT"

        # Prepare thrust curve data 
        # Select only data after hold-down break (the rocket starts moving)
        mask_after_break = tr.t_total >= lr.t_break
        t_flight = tr.t_total[mask_after_break] - lr.t_break  # reset time so that break = 0
        F_flight = tr.F[mask_after_break]
        F_flight[0] = 0

        t_data = t_flight
        F_data = F_flight

        # Write the .eng file
        with open(eng_filename, "w") as f:
            # Header
            f.write(header_line + "\n")
            # Time–thrust data
            for t, tr.F in zip(t_data, F_data):
                f.write(f"{t:.4f} {tr.F:.2f}\n")
            # Empty line at the end
            f.write("\n")

        print(f".eng file successfully written: {eng_filename}")
        print(f"File contains {len(t_data)} thrust data points.")

        # ------------------ Write propellant .eng files starting at HD break ------------------

        small_dt = 0.001           # tiny initial time stamp in eng file [s]
        tiny_thrust_max = 0.001    # tiny N peak for these mass-only engines [N]

        if len(t_flight) < 2:
            raise RuntimeError("Not enough time points after hold-down break to build .eng files.")

        # helper to build propellant .eng
        def build_propellant_eng(
                name_label:str,
                free_mass_initial:float,
                mass_lost_before_break:float,
                h_free_m:float,
                t_ref:np.ndarray,
                F_ref:np.ndarray
                ) -> dict[str,str|float|np.ndarray]:
            """
            name_label : string label e.g. "LOX" or "FUEL"
            free_mass_initial : original free mass [kg] defined in sheet (m_*_total or m_ox_burn)
            mass_lost_before_break : mass already consumed before HD break [kg]
            h_free_m   : free height [m] to put in second header number (converted to mm)
            t_ref, F_ref : arrays starting at t=0 (time since HD break) and thrust shape [N]
            """
            # Remaining free mass to be consumed after HD break
            remaining_free_mass = float(free_mass_initial - mass_lost_before_break)
            if remaining_free_mass < 0:
                # numerical safety
                print(f"Warning: {name_label} remaining_free_mass negative ({remaining_free_mass:.6f}). Clamping to 0.")
                remaining_free_mass = 0.0

            # Create mass-flow profile ONLY for the after-break portion
            integral_F_after = np.trapezoid(F_ref, t_ref)
            if integral_F_after <= 0:
                mdot_after = np.zeros_like(F_ref)
            else:
                mdot_after = remaining_free_mass * (F_ref / integral_F_after)

            # Build tiny thrust shape scaled to the relative thrust shape (preserve timing)
            if np.max(F_ref) <= 0:
                scaled_thrust = np.zeros_like(F_ref)
            else:
                scaled_thrust = tiny_thrust_max * (F_ref / np.max(F_ref))

            # Assemble time & thrust arrays for .eng file:
            # (0, 0) required by OpenRocket
            # (small_dt, small_thrust_just_after_zero) to ensure it starts
            t_eng = t_flight
            # choose a small thrust at small_dt equal to scaled_thrust[0] if exists else small value
            F_eng_prop = scaled_thrust

            # Header formatting:
            # name includes Version
            name = f"{name_label}_{ipt.Version}"
            diameter_mm = 230
            length_mm = float(h_free_m) * 1000.0 if (h_free_m is not None) else 0.0
            # dry mass = wet mass = remaining_free_mass (as requested)
            header = f"{name} {diameter_mm:.0f} {length_mm:.1f} 0 {remaining_free_mass:.5f} {remaining_free_mass:.5f} ERT"

            # Write file directly in the current folder
            fname = f"{name}.eng"
            with open(fname, "w") as fh:
                fh.write(header + "\n")
                for tt, FF in zip(t_eng, F_eng_prop):
                    fh.write(f"{tt:.4f} {FF:.6f}\n")
                fh.write("\n")

            # return summary info
            return {
                "filename": fname,
                "remaining_free_mass": remaining_free_mass,
                "mass_lost_before_break": mass_lost_before_break,
                "t_last": t_ref[-1],
                "num_points": len(t_eng)
            }

        # Build LOX and FUEL .eng files
        lox_summary = build_propellant_eng("LOX", ipt.m_ox_burn, pr.mass_lost_ox_before_break, pr.h_ox_free, t_flight, F_flight)
        fuel_summary = build_propellant_eng("FUEL", ipt.m_fuel_burn, pr.mass_lost_fuel_before_break, pr.h_fuel_free, t_flight, F_flight)

        # Print summary
        print("\n=== .eng file generation summary ===")
        print("LOX:", lox_summary)
        print("FUEL:", fuel_summary)
        print(".eng files successfully written to the current directory.")

        # ------------------ Save Ullage Data to CSV Files ------------------

        # Prepare ullage data arrays (ensure consistent lengths)
        # Filenames (based on Version)
        fuel_csv_name = f"ethanol_ullage_data_{ipt.Version}.csv"
        ox_csv_name   = f"lox_ullage_data_{ipt.Version}.csv"

        # Helper function to write CSV
        def write_ullage_csv(filename, t, ullage):
            """
            Write time [s] and ullage volume [m^3] to CSV file.
            """
            with open(filename, mode='w', newline='') as file:
                writer = csv.writer(file)
                for ti, ui in zip(t, ullage):
                    writer.writerow([f"{ti:.6f}", f"{ui:.8f}"])
            print(f"CSV file written: {filename} ({len(t)} data points)")

        # Write both CSVs
        write_ullage_csv(fuel_csv_name, t_flight, pr.ullage_fuel_m3)
        write_ullage_csv(ox_csv_name,   t_flight, pr.ullage_ox_m3)

        # ------------------ Save COPV Mass vs Time Data to CSV ------------------

        # Define COPV mass depletion parameters
        m_copv_initial = ipt.m_n2_copv    # [kg] initial mass
        t_start = 0.0                     # [s]
        t_end = t_flight[-1]              # [s] total burn duration

        # Generate linearly decreasing mass array
        m_copv_vs_time = np.linspace(m_copv_initial, 0.0, len(t_flight))

        # Build filename based on Version
        copv_csv_name = f"copv_mass_vs_time_{ipt.Version}.csv"

        # Write CSV
        with open(copv_csv_name, mode='w', newline='') as file:
            writer = csv.writer(file)
            for ti, mi in zip(t_flight, m_copv_vs_time):
                writer.writerow([f"{ti:.6f}", f"{mi:.6f}"])

        print(f"CSV file written: {copv_csv_name} ({len(tr.t_total)} data points)")
