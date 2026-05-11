import math
from scipy.integrate import dblquad

class Bay:
    def __init__(self, nom, x, y, radius, length, mass, shape, width = 0):
        self.nom = nom
        self.x = x # [m] : minimal x position according to the chosen coordinate system
        self.y = y # [m] : minimal y position according to the chosen coordinate system
        self.radius = radius # [m] (or width for a triangular shape)
        self.length = length # [m]
        self.mass = mass # [kg]
        self.shape = shape  # 'cylindrical', 'conical', 'semi-cylindrical', 'triangular'
        self.width = width # [m] only for triangular shapes

        
    def center_masse(self) :
        # --- Compute the center of mass coordinates of the bay (x_cm, y_cm) ---
        if self.shape == 'cylindrical':
            return self.length/2, 0

        elif self.shape == 'semi-cylindrical':
            return self.length/2, 4 * self.radius / (3*math.pi)
        
        elif self.shape == 'conical':
            return self.length/4, 0
        
        elif self.shape == 'triangular':
            return self.length / 3, self.width /3
        
        else:
            raise ValueError("undefined shape")
    
    def moment_of_inertia(self):
        # --- Compute the moment of inertia of the bay (Ix, Iy, Iz) relative to the center of mass of the bay ---
        if self.shape == 'cylindrical':
            Ix = 1/2 * self.mass * self.radius**2
            Iy = Iz = 1/12 * self.mass * (3 * self.radius**2 + self.length**2)

        elif self.shape == 'semi-cylindrical':
            Ix = self.mass * self.radius**2 * (1/2 - 16/(9*math.pi**2))
            Iy = self.mass * (self.radius**2/4 + self.length**2/12)
            Iz = self.mass * self.radius**2 * (1/4 - 16/(9 * math.pi**2)) + self.mass * self.length**2/12
        
        elif self.shape == 'conical':
            Ix = 3/10 * self.mass * self.radius**2
            Iy = Iz = 3/80 * self.mass * (4*self.radius**2 + self.length**2)
        
        elif self.shape == 'triangular':
            Ix = self.mass * (self.radius**2 / 18 + self.width**2 / 12)
            Iy = self.mass * (self.length**2 / 18 + self.radius**2 / 18)
            Iz = self.mass * (self.length**2 / 18 + self.width**2 / 12)

        else:
            raise ValueError("undefined shape")
        
        return Ix, Iy, Iz