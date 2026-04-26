import functions as fct
import pandas as pd

file = "2026_C_SE_PROPELLANT_BUDGET_CDR.xlsx"
sheet = "Simulations"
df = fct.read_prop_budget_cdr(file,sheet)

n_sims = df.shape[0]

for i in range(2,n_sims):
    input = 