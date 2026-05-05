from scipy.optimize import brentq
import numpy as np

a = 1.2178 # Jm^3/mol^2
b = 8.407e-5 # m^3/mol
R = 8.314 # J/(mol K)
M = 0.04607 # kg/mol

def van_der_waals(v, T, P):
    return v**3 - (b + R*T/P) * v**2 + a/P * v - a*b/P

T = 20 + 273.15  # K
P = 60e5          # Pa (1e5 Pa = 1 bar)

# find the zero
v = brentq(van_der_waals, b*1.01, 1.0, args=(T, P))

rho = M / v
print(f"v   = {v:.4e} m³/mol")
print(f"rho = {rho:.1f} kg/m³")