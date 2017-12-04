import bspline as bs

class ZSurfaceIO(JsonData):
    def __init__(self, config={}):
        self.u_knots = [int]
        self.v_knots = [int]
        self.u_degree = 2
        self.v_degree = 2
        self.rational = False
        self.poles = [ [ [float] ] ]
        self.quad = [[float]]
        self.z_transform = [float]
        super().__init__(config)


def bs_zsurface_read(z_surface_io):
    io = z_surface_io
    u_basis = bs.SplineBasis(io.u_degree, io.u_knots)
    v_basis = bs.SplineBasis(io.v_degree, io.v_knots)

    z_surf = bs.Surface( (u_basis, v_basis), io.poles, io.rational)
    surf = bs.Z_Surface(io.quad, z_surf)
    if io.z_transform is not None:
        surf.transform(None, io.z_transform)

def bs_zsurface_write(z_surf):

    config = dict(
        u_degree = z_surf.u_basis.degree,
        u_knots = z_surf.u_basis.knots,
        v_degree = z_surf.v_basis.degree,
        v_knots = z_surf.v_basis.knots,
        rational = z_surf.z_surface.rational,
        poles = z_surf.z_surface.poles,
        quad = z_surf.quad,
        z_transform = z_surf.get_z_transform()  #TODO
    )
    return ZSurfaceIO(config)
