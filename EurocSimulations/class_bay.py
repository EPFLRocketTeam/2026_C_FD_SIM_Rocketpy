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

        
    def center_masse_bay(self) :
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
    