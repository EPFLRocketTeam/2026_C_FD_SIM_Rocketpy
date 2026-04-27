import math
from scipy.integrate import dblquad

class Bay:
    def __init__(self, nom, x, y, radius, length, mass, shape):
        self.nom = nom
        self.x = x # [mm] : minimal x position according to the chosen coordinate system
        self.y = y # [mm] : minimal y position according to the chosen coordinate system
        self.radius = radius # [mm]
        self.length = length # [mm]
        self.mass = mass # [g]
        self.shape = shape  # 'cylindrical', 'conical', 'semi-cylindrical'
    
    def volume(self):
        # --- Compute the volume of the bay ---
        if self.shape == 'cylindrical':
            return math.pi * self.radius**2 * self.length
        
        elif self.shape == 'conical':
            return math.pi * self.radius**2 * self.length / 3
        
        elif self.shape == 'semi-cylindrical':
            return math.pi * self.radius**2 * self.length / 2
        
    def _radius_max(self, xi):
        # --- Tool for integration : gives the radius of the bay at position xi ---
        if self.shape == "conical":
            return self.radius * (1 - xi / self.length)
        return self.radius  

    def center_masse_bay(self) :
        # --- Compute the center of mass coordinates of the bay ---
        rho = self.mass / self.volume()

        def integrand_x(r, xi):
            R = self._radius_max(xi)
            if R <= 0:
                return 0.0
            ang = math.pi if self.shape == "semi-cylindrical" else 2 * math.pi
            return (self.x + xi) * r * ang

        int_x, _ = dblquad(
            integrand_x,
            0, self.length,
            0, lambda xi: self._radius_max(xi),
        )
        x_cm = rho * int_x / self.mass

        if self.shape == "semi-cylindrical":
            ang_int_y = 2.0

            def integrand_y_semi(r, xi):
                R = self._radius_max(xi)
                if R <= 0:
                    return 0.0
                return (self.y * math.pi + r * ang_int_y) * r

            int_y, _ = dblquad(
                integrand_y_semi,
                0, self.length,
                0, lambda xi: self._radius_max(xi),
            )
            y_cm = rho * int_y / self.mass
        else:
            y_cm = self.y

        return x_cm, y_cm
    