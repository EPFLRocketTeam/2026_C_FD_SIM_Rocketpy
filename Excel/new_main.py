import excel_io as xl
import functions as fct
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# Declare excel file-related stuff
xl_file = "2026_prop_budget.xlsx"
nsims = 44
blocks = {
    "cfg":        xl._BlockSpec(sheet="Config", cols="B:M", header_row=1,   first_data_row=3),
    "timings":    xl._BlockSpec(sheet="Budget", cols="B:I", header_row=2,   first_data_row=5),
    "pressurant": xl._BlockSpec(sheet="Budget", cols="B:F", header_row=55,  first_data_row=58),
    "oxidizer":   xl._BlockSpec(sheet="Budget", cols="B:V", header_row=108, first_data_row=111),
    "fuel":       xl._BlockSpec(sheet="Budget", cols="B:V", header_row=161, first_data_row=164)
}

# Simulation constants (constant throughout all simulations)
constants:dict[str,float|bool|str] = {
    # General
    "Version":                  "CH",
    "savefiles":                False,
    "number of points":         1000,
    "run environment":          True,
    "write to file":            False,
    "output file":              "output_CH.csv",

    # Propellant tank geometry
    "interior radius":          0.115,
    "cylinder height":          0.3851008075,
    "cap height":               0.05,

    # Hold-down geometry
    "alpha":                    6,
    "beta":                     6,
    "rail length":              11.65,

    # Hold-down other
    "g":                        9.81,
    "hold-down break force":    3300,
    "button-rail friction":     0.5,
    "mass additions":           0,
}

# Read the excel into dataframes
dfs = xl.dfs_from_excel(
    file=xl_file,
    nsims=nsims,
    blocks=blocks
)

# Iterate through the simulations
for i in range(nsims):
    name = dfs[0].index[i]
    input = xl.Input.from_dfs(constants,*dfs,i)
    tr = fct.compute_thrust_curve(input)
    lr = fct.compute_hold_down_and_launch(input,tr)
    pr = fct.compute_propellant_masses(input,tr,lr)
    if input.savefiles:
        fct.create_eng_files

