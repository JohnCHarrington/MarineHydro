""" Solve potential flow problems using vortex panels

This module holds routines to determine the potential flow and
separation point around bodies of any shape or number using
vortex panels and laminar boundary layer theory.

Classes:
    Panel, PanelArray

Methods:
    panelize, concatenate
    make_polygon, make_ellipse, make_circle, make_jukowski

Imports:
    numpy, pyplot from matplotlib, march & sep from BoundaryLayer
"""

import numpy
from matplotlib import pyplot
from BoundaryLayer import march,sep

### Fundamentals

class Panel(object):
    """Vortex panel class

    Attributes:
    xc,yc -- the x and y location of the panel center
    S     -- the half-width of the panel
    sx,sy -- the x and y component of the tangent unit vector
    gamma -- the panel vortex strength
    """

    def __init__(self, x0, y0, x1, y1, gamma=0):
        """Initialize a panel between two points

        Inputs:
        x0,y0 -- the x and y location of the starting point
        x1,y1 -- the x and y location of the ending point
        gamma -- the panel vortex strength; defaults to zero

        Outputs:
        A Panel object.

        Examples:
        p_1 = vp.Panel(-1,0,1,0)    # make panel on x-axis with gamma=0
        p_2 = vp.Panel(0,-1,0,1,4)  # make panel on y-axis with gamma=4
        """
        self.x = (x0,x1); self.y = (y0,y1)              # copy end-points
        self.gamma = gamma; self._gamma = (gamma,gamma) # copy gamma
        self.xc = 0.5*(x0+x1); self.yc = 0.5*(y0+y1)    # panel center
        dx = x1-self.xc; dy = y1-self.yc
        self.S = numpy.sqrt(dx**2+dy**2)                # half-width
        self.sx = dx/self.S; self.sy = dy/self.S        # tangent

    def velocity(self, x, y):
        """Compute the velocity induced by the panel

        Inputs:
        x,y   -- the x and y location of the desired velocity

        Outputs:
        u,v   -- the x and y components of the velocity

        Examples:
        p_2 = vp.Panel(0,-1,0,1,4)        # make panel on y-axis with gamma=4
        u,v = p_2.velocity(-1,0)          # get induced velocity on x-axis
        """
        if self._gamma[1]-self._gamma[0]: # non-constant gamma
            u0,v0,u1,v1 = self._linear(x,y)
            return (self._gamma[0]*u0+self._gamma[1]*u1,
                    self._gamma[0]*v0+self._gamma[1]*v1)
        else:
            u,v = self._constant(x,y)     # constant gamma
            return self.gamma*u,self.gamma*v

    def plot(self, style='k'):
        """Plot the vortex panel as a line segment

        Inputs:
        style -- a string defining the matplotlib style

        Examples:
        my_panel = vp.Panel(0,-1,0,1)  # creates panel on y-axis
        my_panel.plot()                # plot the panel
        """
        return pyplot.plot(self.x, self.y, style, lw=2)

    def _constant(self, x, y):
        "Constant panel induced velocity"
        lr, dt, _, _ = self._transform_xy(x, y)
        return self._rotate_uv(-dt*0.5/numpy.pi, -lr*0.5/numpy.pi)

    def _linear(self, x, y):
        "Linear panel induced velocity"
        lr, dt, xp, yp = self._transform_xy(x, y)
        g, h, c = (yp*lr+xp*dt)/self.S, (xp*lr-yp*dt)/self.S+2, 0.25/numpy.pi
        return (self._rotate_uv(c*( g-dt), c*( h-lr))
               +self._rotate_uv(c*(-g-dt), c*(-h-lr)))

    def _transform_xy(self, x, y):
        "transform from global to panel coordinates"
        xt = x-self.xc; yt = y-self.yc # shift x,y
        xp = xt*self.sx+yt*self.sy     # rotate x
        yp = yt*self.sx-xt*self.sy     # rotate y
        lr = 0.5*numpy.log(((xp-self.S)**2+yp**2)/((xp+self.S)**2+yp**2))
        dt = numpy.arctan2(yp,xp-self.S)-numpy.arctan2(yp,xp+self.S)
        return lr, dt, xp, yp

    def _rotate_uv(self, up, vp):
        "rotate velocity back to global coordinates"
        u = up*self.sx-vp*self.sy    # reverse rotate u prime
        v = vp*self.sx+up*self.sy    # reverse rotate v prime
        return u, v


class PanelArray(object):
    """Array of vortex panels

    Attributes:
    panels -- the numpy array of panels
    alpha  -- the flow angle of attack
    """

    def __init__(self, panels):
        """Initialize a PanelArray

        Inputs:
        panels -- a numpy array of panels

        Outputs:
        A PanelArray object.
        """
        self.panels = panels # copy the panels
        self.alpha = 0       # default alpha
        n = len(panels)
        self.bodies = [(0,n)]        # range for a body
        self.left = [n-1]+list(range(n-1)) # index to the left

    ### Flow solver

    def solve_gamma(self,alpha=0,kutta=[]):
        """ Set the vortex strength on a PanelArray to enforce the no slip and
        kutta conditions.

        Notes:
        Solves for the normalized gamma by using a unit magnitude background
        flow, |U|=1.

        Inputs:
        alpha   -- angle of attack relative to x-axis; must be a scalar; default 0
        kutta   -- panel indices (a list of tuples) on which to enforce the kutta
                    condition; defaults to empty list

        Outputs:
        gamma of the PanelArray is updated.

        Examples:
        foil = vp.make_jukowski(N=32)                    # make a Panel array
        foil.solve_gamma(alpha=0.1, kutta=[(0,-1)])      # solve for gamma
        foil.plot_flow()                                 # plot the flow
        """

        self._set_alpha(alpha)                # set alpha
        A,b = self._construct_A_b()           # construct linear system
        for i in kutta:                       # loop through index pairs
            A[i[0]:i[1],i] += 1                  # apply kutta condition
        gamma = numpy.linalg.solve(A, b)      # solve for gamma
        for i,p_i in enumerate(self.panels):  # loop through panels
            p_i.gamma = gamma[i]                 # update center gamma
            p_i._gamma = (gamma[i],gamma[i])     # update end-point gammas

    def solve_gamma_kutta(self,alpha=0):
        "special case of solve_gamma with kutta=[(0,-1)]"
        return self.solve_gamma(alpha,kutta=[(0,-1)])

    def solve_gamma_O2(self,alpha=0,kutta=[]):
        "special case of solve_gamma for linearly varying panels"
        self._set_alpha(alpha)                   # set alpha
        A,b = self._construct_A_b_O2()           # construct linear system
        if kutta:
            for j,i in kutta:
                A[i,:] = 0; A[i,i] = 1; b[i] = 0
        else:
            S = self.get_array('S')
            for s,e in self.bodies:
                A[s,:] = 0; b[s] = 0
                A[s,s:e] += S[s:e]
                A[s,self.left[s:e]] += S[s:e]
        gamma = numpy.linalg.solve(A, b)         # solve for gamma!
        for i,p_i in enumerate(self.panels):     # loop through panels
            p_i._gamma = (gamma[self.left[i]],gamma[i])      # update end-point gammas
            p_i.gamma = 0.5*sum(p_i._gamma)         # update center gamma

    def _set_alpha(self,alpha):
        "Set angle of attack, but it must be a scalar"
        if(isinstance(alpha, (set, list, tuple, numpy.ndarray))):
            raise TypeError('Only accepts scalar alpha')
        self.alpha = alpha

    def _construct_A_b(self):
        "construct the linear system to enforce no-slip on every panel"

        # get arrays
        xc,yc,sx,sy = self.get_array('xc','yc','sx','sy')

        # construct the matrix
        A = numpy.empty((len(xc), len(xc)))      # empty matrix
        for j, p_j in enumerate(self.panels):    # loop over panels
            u,v = p_j._constant(xc,yc)             # f_j at all panel centers
            A[:,j] = u*sx+v*sy                     # tangential component
        numpy.fill_diagonal(A,0.5)               # fill diagonal with 1/2

        # construct the RHS
        b = -numpy.cos(self.alpha)*sx-numpy.sin(self.alpha)*sy
        return A, b

    def _construct_A_b_O2(self):
        "construct the linear system to enforce no-pen on every panel"

        # get arrays
        xc,yc,sx,sy = self.get_array('xc','yc','sx','sy')

        # construct the matrix
        A = numpy.zeros((len(xc), len(xc)))      # empty matrix
        for j, p_j in enumerate(self.panels):    # loop over panels
            u0,v0,u1,v1 = p_j._linear(xc,yc)        # f_j at all panel centers
            A[:,self.left[j]] += -u0*sy+v0*sx       # -S end influence
            A[:,j] += -u1*sy+v1*sx                  # +S end influence

        # construct the RHS
        b = numpy.cos(self.alpha)*sy-numpy.sin(self.alpha)*sx
        return A, b


    ### Visualize

    def plot_flow(self,size=2,vmax=None):
        """ Plot the flow induced by the PanelArray and background flow

        Notes:
        Uses unit magnitude background flow, |U|=1.

        Inputs:
        size   -- size of the domain; corners are at (-size,-size) and (size,size)
        vmax   -- maximum contour level; defaults to the field max

        Outputs:
        pyplot of the flow vectors, velocity magnitude contours, and the panels.

        Examples:
        circle = vp.make_circle(N=32)      # make a Panel array
        circle.solve_gamma(alpha=0.1)      # solve for Panel strengths
        circle.plot_flow()                 # plot the flow
        """
        # define the grid
        line = numpy.linspace(-size, size, 128)  # computes a 1D-array
        x, y = numpy.meshgrid(line, line)        # generates a mesh grid

        # get the velocity from the free stream and panels
        u, v = self._flow_velocity(x, y)

        # plot it
        pyplot.figure(figsize=(9,7))                # set size
        pyplot.xlabel('x', fontsize=14)             # label x
        pyplot.ylabel('y', fontsize=14, rotation=0) # label y

        # plot contours
        m = numpy.sqrt(u**2+v**2)
        velocity = pyplot.contourf(x, y, m, vmin=0, vmax=vmax)
        cbar = pyplot.colorbar(velocity)
        cbar.set_label('Velocity magnitude', fontsize=14);

        # plot vector field
        pyplot.quiver(x[::4,::4], y[::4,::4],
                      u[::4,::4], v[::4,::4])
        # plot panels
        self.plot();

    def plot(self, style='k'):
        """Plot the PanelArray panels

        Inputs:
        style -- a string defining the matplotlib style

        Examples:
        circle = vp.make_circle(N=32) # make a circle PanelArray
        circle.plot(style='o-')       # plot the geometry
        """
        for p in self.panels: p.plot(style)

    def _flow_velocity(self,x,y):
        "get the velocity induced by panels and unit velocity at angle `alpha`"
        # get the uniform velocity ( make it the same size & shape as x )
        u = numpy.cos(self.alpha)*numpy.ones_like(x)
        v = numpy.sin(self.alpha)*numpy.ones_like(x)

        # add the velocity contribution from each panel
        for p_j in self.panels:
            u_j, v_j = p_j.velocity(x, y)
            u, v = u+u_j, v+v_j

        return u, v


    ## Panel array operations

    def get_array(self,key,*args):
        """ Generate numpy arrays of panel attributes

        Notes:
        Use help(Panel) to see available attributes

        Inputs:
        key (,*args) -- one or more names of the desired attributes

        Outputs:
        key_vals     -- numpy arrays filled with the named attributes

        Examples:
        circle = vp.make_circle(N=32)           # make a PanelArray
        xc,yc = circle.get_array('xc','yc')     # get arrays of the panel centers
        """
        if not args:
            return numpy.array([getattr(p,key) for p in self.panels])
        else:
            return [self.get_array(k) for k in (key,)+args]

    def distance(self):
        """ Find the cumulative distance of along the PanelArray

        Notes:
        s[0] = S[0], s[1] = 2*S[0]+S[1], s[2] = 2*S[0]+2*S[1]+S[2], ...

        Examples:
        foil = vp.make_jukowski(N=64)       # define the geometry
        s = foil.distance()                 # get the panel path distance
        """
        S = self.get_array('S')
        return numpy.cumsum(2*S)-S


    ### Boundary layers
    def split(self):
        """Split PanelArray into two boundary layer sections

        Outputs:
        top     -- PanelArray defining the top BL
        bottom  -- PanelArray defining the bottom BL

        Examples:
        foil = vp.make_jukowski(N=64)        #1. Define the geometry
        foil.solve_gamma_kutta(alpha=0.1)    #2. Solve for the potential flow
        foil_top,foil_bot = foil.split()     #3. Split the boundary layers
        """
        # split based on flow direction
        top = [p for p in self.panels if p.gamma<=0]
        bot = [p for p in self.panels if p.gamma>=0]
        return PanelArray(top),PanelArray(bot[::-1])

    def march(self,nu,thwaites=False):
        """ March along a set of BL panels

        Inputs:
        nu       -- kinematic viscosity
        thwaites -- Thwaites approximate method flag (default=False)

        Outputs:
        delta2 -- array momentum thicknesses at panel centers
        lam    -- array of shape function values at panel centers
        iSep   -- array index of separation point

        Examples:
        nu = 1e-5
        circle = vp.make_circle(N=64)     #1. make the geometry
        circle.solve_gamma()              #2. solve the pflow
        top,bottom = circle.split()       #3. split the panels
        delta2,lam,iSep = top.march(nu)   #4. march along the BL
        """
        s = self.distance()                   # distance
        u_e = abs(self.get_array('gamma'))    # velocity
        return march(s,u_e,nu,thwaites)       # march

    def sep_point(self):
        """ Predict separation point on a set of BL panels

        Outputs:
        x_s,y_s -- location of the boundary layer separation point

        Examples:
        foil = vp.make_jukowski(N=64)       #1. make the geometry
        foil.solve_gamma_kutta(alpha=0.1)   #2. solve the pflow
        top,bottom = foil.split()           #3. split the panels
        x_top,y_top = top.sep_point()       #4. find separation point
        """
        _,_,iSep = self.march(1)    # nu doesn't matter
        x,y = self.get_array('xc','yc')
        return sep(x,iSep),sep(y,iSep)

### Geometries

def panelize(x,y):
    """Create a PanelArray from a set of points

    Inputs:
    x,y    -- the x and y location of the panel end points

    Outputs:
    A PanelArray object
    """
    if len(x)<2:                                # check input lengths
        raise ValueError("point arrays must have len>1")
    if len(x)!=len(y):                          # check input lengths
        raise ValueError("x and y must be same length")

    panels = [Panel(x[i], y[i], x[i+1], y[i+1]) for i in range(len(x)-1)]
    return PanelArray(panels)

def make_polygon(N,sides):
    """ Make a polygonal PanelArray

    Inputs:
    N     -- number of panels to use
    sides -- number of sides in the polygon

    Outputs:
    A PanelArray object; see help(PanelArray)

    Examples:
    triangle = vp.make_polygon(N=33,sides=3)  # make a triangular Panel array
    triangle.plot()                           # plot the geometry
    """
    # define the end-points
    theta = numpy.linspace(0, -2*numpy.pi, N+1)          # equally spaced theta
    r = numpy.cos(numpy.pi/sides)/numpy.cos(             # r(theta)
            theta % (2.*numpy.pi/sides)-numpy.pi/sides)
    x,y = r*numpy.cos(theta), r*numpy.sin(theta)         # get the coordinates
    return panelize(x,y)

def make_ellipse(N, t_c, xcen=0, ycen=0):
    """ Make an elliptical PanelArray; defaults to circle

    Inputs:
    N         -- number of panels to use
    t_c       -- thickness/chord of the ellipse
    xcen,ycen -- location of the ellipse center; defaults to origin

    Outputs:
    A PanelArray object; see help(PanelArray)

    Examples:
    ellipse = vp.make_ellipse(N=32,t_c=0.5) # make a 1:2 elliptical Panel array
    ellipse.plot()                          # plot the geometry
    """
    theta = numpy.linspace(0, -2*numpy.pi, N+1)
    x,y = numpy.cos(theta)+xcen, numpy.sin(theta)*t_c+ycen
    return panelize(x,y)

def make_circle(N, xcen=0, ycen=0):
    "Make circle as special case of make_ellipse"
    return make_ellipse(N, t_c=1, xcen=xcen, ycen=ycen)

def make_jukowski(N, dx=0.18, dtheta=0, dr=0):
    """Make a foil-shaped PanelArray using the Jukowski mapping

    Note:
    Foil-shapes are obtained adjusting a circle and then mapping

    Inputs:
    N         -- number of panels to use
    dx        -- negative extent beyond x = -1
    dtheta    -- angle of rotation around (1,0)
    dr        -- radius extent beyond r = 1

    Outputs:
    A PanelArray object; see help(PanelArray)

    Examples:
    foil = vp.make_jukowski(N=64)    # make a symmetric foil Panel array
    foil.plot()                      # plot the geometry
    """
    # define the circle
    theta = numpy.linspace(0, -2*numpy.pi, N+1)
    r = (1+dx)/numpy.cos(dtheta)+dr
    x,y = r*numpy.cos(theta)-(r-1-dr), r*numpy.sin(theta)

    #rotate around (1,0)
    ds,dc = numpy.sin(dtheta),numpy.cos(dtheta)
    x2,y2 =  dc*(x-1)+ds*y+1, -ds*(x-1)+dc*y
    r2 = x2**2+y2**2

    # apply jukowski mapping
    x3,y3 = x2*(1+1./r2)/2, y2*(1-1./r2)/2
    return panelize(x3,y3)

def concatenate(a,b,*args):
    """Concatenate PanelArray bodies

    Inputs:
    a,b (,*args)    -- two or more PanelArray bodies

    Outputs:
    A PanelArray object
    """
    if not args:
        na = len(a.panels)
        c = PanelArray(a.panels+b.panels)
        c.bodies = a.bodies+[(s+na,e+na) for s,e in b.bodies]
        c.left = a.left+[l+na for l in b.left]
    else:
        c = concatenate(concatenate(a,b),*args)
    return c
