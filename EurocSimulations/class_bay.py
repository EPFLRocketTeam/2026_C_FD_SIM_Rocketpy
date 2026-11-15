import math
from scipy.integrate import dblquad

class Bay:
    def __init__(self, nom, z, y, radius, length, mass, shape, width = 0, inner_radius = 0):
        self.nom = nom
        self.z = z # [m] : minimal x position according to the chosen coordinate system
        self.y = y # [m] : minimal y position according to the chosen coordinate system
        self.radius = radius # [m] (or width for a triangular shape)
        self.length = length # [m]
        self.mass = mass # [kg]
        self.shape = shape  # 'cylindrical', 'conical', 'semi-cylindrical', 'triangular', 'tank' (holed cylinder and two disks to close it)
        self.width = width # [m] only for triangular shapes

    def center_masse(self) :
        # --- Compute the center of mass coordinates of the bay (z_cm, y_cm) ---
        if self.shape == 'cylindrical':
            return self.length/2, 0
        
        elif self.shape == 'tank':
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

            Iz = 1/2 * self.mass * self.radius**2
            Ix = Iy = 1/12 * self.mass * (3 * self.radius**2 + self.length**2)

        elif self.shape == 'tank':
            # repartition of the mass (consider uniform material)
            # knowing that the lateral surface (cylinder) = 2 pi radius length
            #              the disk surface = pi radius**2
            #              the total surface = 2 pi radius (length + radius)

            mass_cylinder = self.mass * self.length / (self.length + self.radius)
            mass_disk = (self.mass * self.radius / (self.length + self.radius)) / 2

            # contribution of the holed cylinder
            Iz_cylinder = mass_cylinder * self.radius**2
            Ix_cylinder = Iy_cylinder = 1/12 * mass_cylinder * (6 * self.radius**2 + self.length**2)

            # contribution of the disks closing the cylinder
            Iz_disk = 1/2 * mass_disk * self.radius**2
            Ix_disk = Iy_disk = 1/4 * mass_disk * self.radius **2

            # add contribution and use Huygens-Steiner
            Iz = Iz_cylinder + 2*Iz_disk
            Ix = Iy = 2 * Ix_disk + Ix_cylinder + 1/2 * mass_disk * self.length**2

        elif self.shape == 'semi-cylindrical':
            Iz = self.mass * self.radius**2 * (1/2 - 16/(9*math.pi**2))
            Ix = self.mass * (self.radius**2/4 + self.length**2/12)
            Iy = self.mass * self.radius**2 * (1/4 - 16/(9 * math.pi**2)) + self.mass * self.length**2/12
        
        elif self.shape == 'conical':
            Iz = 3/10 * self.mass * self.radius**2
            Ix = Iy = 3/20 * self.mass * (self.radius**2/4 + self.length**2)
        
        elif self.shape == 'triangular':
            Iz = self.mass * (self.radius**2 / 18 + self.width**2 / 12)
            Ix = self.mass * (self.length**2 / 18 + self.radius**2 / 18)
            Iy = self.mass * (self.length**2 / 18 + self.width**2 / 12)

        else:
            raise ValueError("undefined shape")
        
        return Ix, Iy, Iz
