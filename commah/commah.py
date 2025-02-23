#!/usr/bin/env ipython
# -*- coding: utf-8 -*-

"""Routine for creating Mass Accretion Histories and NFW profiles."""

from __future__ import absolute_import, division, print_function

import scipy
import numpy as np
import cosmolopy as cp
import commah.cosmology_list as cg

__author__ = 'Camila Correa and Alan Duffy'
__email__ = 'mail@alanrduffy.com'

def _izip(*iterables):
    # zip('ABCD', 'xy') --> Ax By
    sentinel = object()
    iterators = [iter(it) for it in iterables]
    while iterators:
        result = []
        for it in iterators:
            elem = next(it, sentinel)
            if elem is sentinel:
                return
            result.append(elem)
        yield tuple(result)

def _checkinput(zi, Mi, z=False, verbose=None):
    """ Check and convert any input scalar or array to numpy array """
    # How many halo redshifts provided?
    zi = np.array(zi, ndmin=1, dtype=float)

    # How many halo masses provided?
    Mi = np.array(Mi, ndmin=1, dtype=float)

    # Check the input sizes for zi and Mi make sense, if not then exit unless
    # one axis is length one, then replicate values to the size of the other
    if (zi.size > 1) and (Mi.size > 1):
        if(zi.size != Mi.size):
            print("Error ambiguous request")
            print("Need individual redshifts for all haloes provided ")
            print("Or have all haloes at same redshift ")
            return(-1)
    elif (zi.size == 1) and (Mi.size > 1):
        if verbose:
            print("Assume zi is the same for all Mi halo masses provided")
        # Replicate redshift for all halo masses
        zi = np.ones_like(Mi)*zi[0]
    elif (Mi.size == 1) and (zi.size > 1):
        if verbose:
            print("Assume Mi halo masses are the same for all zi provided")
        # Replicate redshift for all halo masses
        Mi = np.ones_like(zi)*Mi[0]
    else:
        if verbose:
            print("A single Mi and zi provided")

    # Very simple test for size / type of incoming array
    # just in case numpy / list given
    if z is False:
        # Didn't pass anything, set zi = z
        lenzout = 1
    else:
        # If something was passed, convert to 1D NumPy array
        z = np.array(z, ndmin=1, dtype=float)
        lenzout = z.size

    return(zi, Mi, z, zi.size, Mi.size, lenzout)


def getcosmo(cosmology):
    """ Find cosmological parameters for named cosmo in cosmology.py list """

    defaultcosmologies = {'dragons': cg.DRAGONS(), 'wmap1': cg.WMAP1_Mill(),
                          'wmap3': cg.WMAP3_ML(), 'wmap5': cg.WMAP5_mean(),
                          'wmap7': cg.WMAP7_ML(), 'wmap9': cg.WMAP9_ML(),
                          'wmap1_lss': cg.WMAP1_2dF_mean(),
                          'wmap3_mean': cg.WMAP3_mean(),
                          'wmap5_ml': cg.WMAP5_ML(),
                          'wmap5_lss': cg.WMAP5_BAO_SN_mean(),
                          'wmap7_lss': cg.WMAP7_BAO_H0_mean(),
                          'planck13': cg.Planck_2013(),
                          'planck15': cg.Planck_2015()}

    if isinstance(cosmology, dict):
        # User providing their own variables
        cosmo = cosmology
        if 'A_scaling' not in cosmology.keys():
            A_scaling = getAscaling(cosmology, newcosmo=True)
            cosmo.update({'A_scaling': A_scaling})

        # Add extra variables by hand that cosmolopy requires
        # note that they aren't used (set to zero)
        for paramnames in cg.WMAP5_mean().keys():
            if paramnames not in cosmology.keys():
                cosmo.update({paramnames: 0})
    elif cosmology.lower() in defaultcosmologies.keys():
        # Load by name of cosmology instead
        cosmo = defaultcosmologies[cosmology.lower()]
        A_scaling = getAscaling(cosmology)
        cosmo.update({'A_scaling': A_scaling})
    else:
        print("You haven't passed a dict of cosmological parameters ")
        print("OR a recognised cosmology, you gave %s" % (cosmology))
    # No idea why this has to be done by hand but should be O_k = 0
    cosmo = cp.distance.set_omega_k_0(cosmo)

    # Adding baryonic effects option, cosmolopy asks for it
    if cosmo['omega_b_0']>0:
        cosmo.update({'baryonic_effects': True})
    else:
        cosmo.update({'baryonic_effects': False})
    # Use the cosmology as **cosmo passed to cosmolopy routines
    return(cosmo)


def _getcosmoheader(cosmo):
    """ Output the cosmology to a string for writing to file """

    cosmoheader = ("# Cosmology (flat) Om:{0:.3f}, Ol:{1:.3f}, h:{2:.2f}, "
                   "sigma8:{3:.3f}, ns:{4:.2f}".format(
                       cosmo['omega_M_0'], cosmo['omega_lambda_0'], cosmo['h'],
                       cosmo['sigma_8'], cosmo['n']))

    return(cosmoheader)


def cduffy(z, M, vir='200crit', relaxed=True):
    """ NFW conc from Duffy 08 Table 1 for halo mass and redshift"""

    if(vir == '200crit'):
        if relaxed:
            params = [6.71, -0.091, -0.44]
        else:
            params = [5.71, -0.084, -0.47]
    elif(vir == 'tophat'):
        if relaxed:
            params = [9.23, -0.090, -0.69]
        else:
            params = [7.85, -0.081, -0.71]
    elif(vir == '200mean'):
        if relaxed:
            params = [11.93, -0.090, -0.99]
        else:
            params = [10.14, -0.081, -1.01]
    else:
        print("Didn't recognise the halo boundary definition provided %s"
              % (vir))

    return(params[0] * ((M/(2e12/0.72))**params[1]) * ((1+z)**params[2]))


def _delta_sigma(**cosmo):
    """ Perturb best-fit constant of proportionality Ascaling for
        rho_crit - rho_2 relation for unknown cosmology (Correa et al 2015c)

    Parameters
    ----------
    cosmo : dict
        Dictionary of cosmological parameters, similar in format to:
        {'N_nu': 0,'Y_He': 0.24, 'h': 0.702, 'n': 0.963,'omega_M_0': 0.275,
         'omega_b_0': 0.0458,'omega_lambda_0': 0.725,'omega_n_0': 0.0,
         'sigma_8': 0.816, 't_0': 13.76, 'tau': 0.088,'z_reion': 10.6}

    Returns
    -------
    float
        The perturbed 'A' relation between rho_2 and rho_crit for the cosmology

    Raises
    ------

    """

    M8_cosmo = cp.perturbation.radius_to_mass(8, **cosmo)
    perturbed_A = (0.796/cosmo['sigma_8']) * \
                  (M8_cosmo/2.5e14)**((cosmo['n']-0.963)/6)
    return(perturbed_A)


def getAscaling(cosmology, newcosmo=None):
    """ Returns the normalisation constant between
        Rho_-2 and Rho_mean(z_formation) for a given cosmology

    Parameters
    ----------
    cosmology : str or dict
        Can be named cosmology, default WMAP7 (aka DRAGONS), or
        DRAGONS, WMAP1, WMAP3, WMAP5, WMAP7, WMAP9, Planck13, Planck15
        or dictionary similar in format to:
        {'N_nu': 0,'Y_He': 0.24, 'h': 0.702, 'n': 0.963,'omega_M_0': 0.275,
         'omega_b_0': 0.0458,'omega_lambda_0': 0.725,'omega_n_0': 0.0,
         'sigma_8': 0.816, 't_0': 13.76, 'tau': 0.088,'z_reion': 10.6}
    newcosmo : str, optional
        If cosmology is not from predefined list have to perturbation
        A_scaling variable. Defaults to None.

    Returns
    -------
    float
        The scaled 'A' relation between rho_2 and rho_crit for the cosmology

    """
    # Values from Correa 15c
    defaultcosmologies = {'dragons': 887, 'wmap1': 853, 'wmap3': 850,
                          'wmap5': 887, 'wmap7': 887, 'wmap9': 950,
                          'wmap1_lss': 853, 'wmap3_mean': 850,
                          'wmap5_ml': 887, 'wmap5_lss': 887,
                          'wmap7_lss': 887,
                          'planck13': 880, 'planck15': 880}

    if newcosmo:
        # Scale from default WMAP5 cosmology using Correa et al 14b eqn C1
        A_scaling = defaultcosmologies['wmap5'] * _delta_sigma(**cosmology)
    else:
        if cosmology.lower() in defaultcosmologies.keys():
            A_scaling = defaultcosmologies[cosmology.lower()]
        else:
            print("Error, don't recognise your cosmology for A_scaling ")
            print("You provided %s" % (cosmology))

    return(A_scaling)


def _int_growth(z, **cosmo):
    """ Returns integral of the linear growth factor from z=200 to z=z """

    zmax = 200

    if hasattr(z, "__len__"):
        for zval in z:
            assert(zval < zmax)
    else:
        assert(z < zmax)

    y, yerr = scipy.integrate.quad(
        lambda z: (1 + z)/(cosmo['omega_M_0']*(1 + z)**3 +
                           cosmo['omega_lambda_0'])**(1.5),
        z, zmax)

    return(y)


def _deriv_growth(z, **cosmo):
    """ Returns derivative of the linear growth factor at z
        for a given cosmology **cosmo """

    inv_h = (cosmo['omega_M_0']*(1 + z)**3 + cosmo['omega_lambda_0'])**(-0.5)
    fz = (1 + z) * inv_h**3

    deriv_g = growthfactor(z, norm=True, **cosmo)*(inv_h**2) *\
        1.5 * cosmo['omega_M_0'] * (1 + z)**2 -\
        fz * growthfactor(z, norm=True, **cosmo)/_int_growth(z, **cosmo)

    return(deriv_g)


def growthfactor(z, norm=True, **cosmo):
    """ Returns linear growth factor at a given redshift, normalised to z=0
        by default, for a given cosmology

    Parameters
    ----------

    z : float or numpy array
        The redshift at which the growth factor should be calculated
    norm : boolean, optional
        If true then normalise the growth factor to z=0 case defaults True
    cosmo : dict
        Dictionary of cosmological parameters, similar in format to:
        {'N_nu': 0,'Y_He': 0.24, 'h': 0.702, 'n': 0.963,'omega_M_0': 0.275,
         'omega_b_0': 0.0458,'omega_lambda_0': 0.725,'omega_n_0': 0.0,
         'sigma_8': 0.816, 't_0': 13.76, 'tau': 0.088,'z_reion': 10.6}

    Returns
    -------
    float or numpy array
        The growth factor at a range of redshifts 'z'

    Raises
    ------

    """
    H = np.sqrt(cosmo['omega_M_0'] * (1 + z)**3 +
                cosmo['omega_lambda_0'])
    growthval = H * _int_growth(z, **cosmo)
    if norm:
        growthval /= _int_growth(0, **cosmo)

    return(growthval)


def _minimize_c(c, z=0, a_tilde=1, b_tilde=-1,
                Ascaling=900, omega_M_0=0.25, omega_lambda_0=0.75):
    """ Trial function to solve 2 eqns (17 and 18) from Correa et al. (2015c)
        for 1 unknown, i.e. concentration, returned by a minimisation call """

    # Fn 1 (LHS of Eqn 18)

    Y1 = np.log(2) - 0.5
    Yc = np.log(1+c) - c/(1+c)
    f1 = Y1/Yc

    # Fn 2 (RHS of Eqn 18)

    # Eqn 14 - Define the mean inner density
    rho_2 = 200 * c**3 * Y1 / Yc

    # Eqn 17 rearranged to solve for Formation Redshift
    # essentially when universe had rho_2 density
    zf = (((1 + z)**3 + omega_lambda_0/omega_M_0) *
          (rho_2/Ascaling) - omega_lambda_0/omega_M_0)**(1/3) - 1

    # RHS of Eqn 19
    f2 = ((1 + zf - z)**a_tilde) * np.exp((zf - z) * b_tilde)

    # LHS - RHS should be zero for the correct concentration
    return(f1-f2)


def formationz(c, z, Ascaling=900, omega_M_0=0.25, omega_lambda_0=0.75):
    """ Rearrange eqn 18 from Correa et al (2015c) to return
        formation redshift for a concentration at a given redshift

    Parameters
    ----------
    c : float / numpy array
        Concentration of halo
    z : float / numpy array
        Redshift of halo with concentration c
    Ascaling : float
        Cosmological dependent scaling between densities, use function
        getAscaling('WMAP5') if unsure. Default is 900.
    omega_M_0 : float
        Mass density of the universe. Default is 0.25
    omega_lambda_0 : float
        Dark Energy density of the universe. Default is 0.75

    Returns
    -------
    zf : float / numpy array
        Formation redshift for halo of concentration 'c' at redshift 'z'

    """
    Y1 = np.log(2) - 0.5
    Yc = np.log(1+c) - c/(1+c)
    rho_2 = 200*(c**3)*Y1/Yc

    zf = (((1+z)**3 + omega_lambda_0/omega_M_0) *
          (rho_2/Ascaling) - omega_lambda_0/omega_M_0)**(1/3) - 1

    return(zf)


def calc_ab(zi, Mi, **cosmo):
    """ Calculate growth rate indices a_tilde and b_tilde

    Parameters
    ----------
    zi : float
        Redshift
    Mi : float
        Halo mass at redshift 'zi'
    cosmo : dict
        Dictionary of cosmological parameters, similar in format to:
        {'N_nu': 0,'Y_He': 0.24, 'h': 0.702, 'n': 0.963,'omega_M_0': 0.275,
         'omega_b_0': 0.0458,'omega_lambda_0': 0.725,'omega_n_0': 0.0,
         'sigma_8': 0.816, 't_0': 13.76, 'tau': 0.088,'z_reion': 10.6}

    Returns
    -------
    (a_tilde, b_tilde) : float
    """

    # When zi = 0, the a_tilde becomes alpha and b_tilde becomes beta

    # Eqn 23 of Correa et al 2015a (analytically solve from Eqn 16 and 17)
    # Arbitray formation redshift, z_-2 in COM is more physically motivated
    zf = -0.0064 * (np.log10(Mi))**2 + 0.0237 * (np.log10(Mi)) + 1.8837

    # Eqn 22 of Correa et al 2015a
    q = 4.137 * zf**(-0.9476)

    # Radius of a mass Mi
    R_Mass = cp.perturbation.mass_to_radius(Mi, **cosmo)  # [Mpc]
    # Radius of a mass Mi/q
    Rq_Mass = cp.perturbation.mass_to_radius(Mi/q, **cosmo)  # [Mpc]

    # Mass variance 'sigma' evaluate at z=0 to a good approximation
    sig, err_sig = cp.perturbation.sigma_r(R_Mass, 0, **cosmo)  # [Mpc]
    sigq, err_sigq = cp.perturbation.sigma_r(Rq_Mass, 0, **cosmo)  # [Mpc]

    f = (sigq**2 - sig**2)**(-0.5)

    # Eqn 9 and 10 from Correa et al 2015c
    # (generalised to zi from Correa et al 2015a's z=0 special case)
    # a_tilde is power law growth rate
    a_tilde = (np.sqrt(2/np.pi) * 1.686 * _deriv_growth(zi, **cosmo) /
               growthfactor(zi, norm=True, **cosmo)**2 + 1)*f
    # b_tilde is exponential growth rate
    b_tilde = -f

    return(a_tilde, b_tilde)


def acc_rate(z, zi, Mi, **cosmo):
    """ Calculate accretion rate and mass history of a halo at any
        redshift 'z' with mass 'Mi' at a lower redshift 'z'

    Parameters
    ----------
    z : float
        Redshift to solve acc_rate / mass history. Note zi<z
    zi : float
        Redshift
    Mi : float
        Halo mass at redshift 'zi'
    cosmo : dict
        Dictionary of cosmological parameters, similar in format to:
        {'N_nu': 0,'Y_He': 0.24, 'h': 0.702, 'n': 0.963,'omega_M_0': 0.275,
         'omega_b_0': 0.0458,'omega_lambda_0': 0.725,'omega_n_0': 0.0,
         'sigma_8': 0.816, 't_0': 13.76, 'tau': 0.088,'z_reion': 10.6}

    Returns
    -------
    (dMdt, Mz) : float
        Accretion rate [Msol/yr], halo mass [Msol] at redshift 'z'

    """
    # Find parameters a_tilde and b_tilde for initial redshift
    # use Eqn 9 and 10 of Correa et al. (2015c)
    a_tilde, b_tilde = calc_ab(zi, Mi, **cosmo)

    # Halo mass at z, in Msol
    # use Eqn 8 in Correa et al. (2015c)
    Mz = Mi * ((1 + z - zi)**a_tilde) * (np.exp(b_tilde * (z - zi)))

    # Accretion rate at z, Msol yr^-1
    # use Eqn 11 from Correa et al. (2015c)
    dMdt = 71.6 * (Mz/1e12) * (cosmo['h']/0.7) *\
        (-a_tilde / (1 + z - zi) - b_tilde) * (1 + z) *\
        np.sqrt(cosmo['omega_M_0']*(1 + z)**3+cosmo['omega_lambda_0'])

    return(dMdt, Mz)


def MAH(z, zi, Mi, **cosmo):
    """ Calculate mass accretion history by looping function acc_rate
        over redshift steps 'z' for halo of mass 'Mi' at redshift 'zi'

    Parameters
    ----------
    z : float / numpy array
        Redshift to output MAH over. Note zi<z always
    zi : float
        Redshift
    Mi : float
        Halo mass at redshift 'zi'
    cosmo : dict
        Dictionary of cosmological parameters, similar in format to:
        {'N_nu': 0,'Y_He': 0.24, 'h': 0.702, 'n': 0.963,'omega_M_0': 0.275,
         'omega_b_0': 0.0458,'omega_lambda_0': 0.725,'omega_n_0': 0.0,
         'sigma_8': 0.816, 't_0': 13.76, 'tau': 0.088,'z_reion': 10.6}

    Returns
    -------
    (dMdt, Mz) : float / numpy arrays of equivalent size to 'z'
        Accretion rate [Msol/yr], halo mass [Msol] at redshift 'z'

    """

    # Ensure that z is a 1D NumPy array
    z = np.array(z, ndmin=1, dtype=float)

    # Create a full array
    dMdt_array = np.empty_like(z)
    Mz_array = np.empty_like(z)

    for i_ind, zval in enumerate(z):
        # Solve the accretion rate and halo mass at each redshift step
        dMdt, Mz = acc_rate(zval, zi, Mi, **cosmo)

        dMdt_array[i_ind] = dMdt
        Mz_array[i_ind] = Mz

    return(dMdt_array, Mz_array)


def COM(z, M, **cosmo):
    """ Calculate concentration for halo of mass 'M' at redshift 'z'

    Parameters
    ----------
    z : float / numpy array
        Redshift to find concentration of halo
    M : float / numpy array
        Halo mass at redshift 'z'. Must be same size as 'z'
    cosmo : dict
        Dictionary of cosmological parameters, similar in format to:
        {'N_nu': 0,'Y_He': 0.24, 'h': 0.702, 'n': 0.963,'omega_M_0': 0.275,
         'omega_b_0': 0.0458,'omega_lambda_0': 0.725,'omega_n_0': 0.0,
         'sigma_8': 0.816, 't_0': 13.76, 'tau': 0.088,'z_reion': 10.6}

    Returns
    -------
    (c_array, sig_array, nu_array, zf_array) : float / numpy arrays
        of equivalent size to 'z' and 'M'. Variables are
        Concentration, Mass Variance 'sigma' this corresponds too,
        the dimnesionless fluctuation this represents and formation redshift

    """
    # Check that z and M are arrays
    z = np.array(z, ndmin=1, dtype=float)
    M = np.array(M, ndmin=1, dtype=float)

    # Create array
    c_array = np.empty_like(z)
    sig_array = np.empty_like(z)
    nu_array = np.empty_like(z)
    zf_array = np.empty_like(z)

    for i_ind, (zval, Mval) in enumerate(_izip(z, M)):
        # Evaluate the indices at each redshift and mass combination
        # that you want a concentration for, different to MAH which
        # uses one a_tilde and b_tilde at the starting redshift only
        a_tilde, b_tilde = calc_ab(zval, Mval, **cosmo)

        # Minimize equation to solve for 1 unknown, 'c'
        c = scipy.optimize.brentq(_minimize_c, 2, 1000,
                                  args=(zval, a_tilde, b_tilde,
                                        cosmo['A_scaling'], cosmo['omega_M_0'],
                                        cosmo['omega_lambda_0']))

        if np.isclose(c, 0):
            print("Error solving for concentration with given redshift and "
                  "(probably) too small a mass")
            c = -1
            sig = -1
            nu = -1
            zf = -1
        else:
            # Calculate formation redshift for this concentration,
            # redshift at which the scale radius = virial radius: z_-2
            zf = formationz(c, zval, Ascaling=cosmo['A_scaling'],
                            omega_M_0=cosmo['omega_M_0'],
                            omega_lambda_0=cosmo['omega_lambda_0'])

            R_Mass = cp.perturbation.mass_to_radius(Mval, **cosmo)

            sig, err_sig = cp.perturbation.sigma_r(R_Mass, 0, **cosmo)
            nu = 1.686/(sig*growthfactor(zval, norm=True, **cosmo))

        c_array[i_ind] = c
        sig_array[i_ind] = sig
        nu_array[i_ind] = nu
        zf_array[i_ind] = zf

    return(c_array, sig_array, nu_array, zf_array)


def run(cosmology, zi=0, Mi=1e12, z=False, com=True, mah=True,
        filename=None, verbose=None, retcosmo=None):
    """ Run commah code on halo of mass 'Mi' at redshift 'zi' with
        accretion and profile history at higher redshifts 'z'
        This is based on Correa et al. (2015a,b,c)

    Parameters
    ----------
    cosmology : str or dict
        Can be named cosmology, default WMAP7 (aka DRAGONS), or
        DRAGONS, WMAP1, WMAP3, WMAP5, WMAP7, WMAP9, Planck13, Planck15
        or dictionary similar in format to:
        {'N_nu': 0,'Y_He': 0.24, 'h': 0.702, 'n': 0.963,'omega_M_0': 0.275,
         'omega_b_0': 0.0458,'omega_lambda_0': 0.725,'omega_n_0': 0.0,
         'sigma_8': 0.816, 't_0': 13.76, 'tau': 0.088,'z_reion': 10.6}

    zi : float / numpy array, optional
        Redshift at which halo has mass 'Mi'. If float then all
        halo masses 'Mi' are assumed to be at this redshift.
        If array but Mi is float, then this halo mass is used across
        all starting redshifts. If both Mi and zi are arrays then they
        have to be the same size for one - to - one correspondence between
        halo mass and the redshift at which it has that mass. Default is 0.
    Mi : float / numpy array, optional
        Halo mass 'Mi' at a redshift 'zi'. If float then all redshifts 'zi'
        are solved for this halo mass. If array but zi is float, then this
        redshift is applied to all halo masses. If both Mi and zi are
        arrays then they have to be the same size for one - to - one
        correspondence between halo mass and the redshift at which it
        has that mass. Default is 1e12 Msol.
    z : float / numpy array, optional
        Redshift to solve commah code at. Must have zi<z else these steps
        are skipped. Default is False, meaning commah is solved at z=zi

    com : bool, optional
        If true then solve for concentration-mass,
        default is True.
    mah : bool, optional
        If true then solve for accretion rate and halo mass history,
        default is True.
    filename : bool / str, optional
        If str is passed this is used as a filename for output of commah
    verbose : bool, optional
        If true then give comments, default is None.
    retcosmo : bool, optional
        Return cosmological parameters used as a dict if retcosmo = True,
        default is None.

    Returns
    -------
    dataset : structured dataset
        dataset contains structured columns of size
        (size(Mi) > size(z)) by size(z)

        If mah = True and com = False then columns are
        ('zi',float),('Mi',float),('z',float),('dMdt',float),('Mz',float)
        where 'zi' is the starting redshift, 'Mi' is halo mass at zi
        'z' is output redshift (NB z>zi), 'dMdt' is accretion rate [Msol/yr]
        and 'Mz' is the halo mass at 'z' for a halo which was 'Mi' massive
        at starting redshift 'zi'

        If mah = False and com = True then columns are
        ('zi',float),('Mi',float),('z',float),('c',float),('sig',float),('nu',float),('zf',float)
        where 'zi' is the starting redshift, 'Mi' is halo mass at zi
        'z' is output redshift (NB z>zi), 'c' is NFW concentration of halo
        at the redshift 'z', 'sig' is the mass variance 'sigma',
        'nu' is the dimensionless fluctuation for halo mass 'Mi' at 'zi',
        'zf' is the formation redshift for a halo of mass 'Mi' at redshift 'zi'

        If mah = True and com = True then columns are:
        ('zi',float),('Mi',float),('z',float),('dMdt',float),('Mz',float),
        ('c',float),('sig',float),('nu',float),('zf',float)

    file : structured dataset with name 'filename' if passed

    Raises
    ------
    Output -1
        If com = False and mah = False as user has to select something.
    Output -1
        If 'zi' and 'Mi' are arrays of unequal size. Impossible to match
        corresponding masses and redshifts of output.

    Examples
    --------
    Examples should be written in doctest format, and should illustrate how
    to use the function.

    >>> import examples
    >>> examples.runcommands() #  A series of ways to query structured dataset
    >>> examples.plotcommands() #  Examples to plot data

    """

    # Check user choices...
    if not com and not mah:
        print("User has to choose com=True and / or mah=True ")
        return(-1)

    # Convert arrays / lists to np.array
    # and inflate redshift / mass axis
    # to match each other for later loop
    results = _checkinput(zi, Mi, z=z, verbose=verbose)

    # Return if results is -1
    if(results == -1):
        return(-1)
    # If not, unpack the returned iterable
    else:
        zi, Mi, z, lenz, lenm, lenzout = results
    # At this point we will have lenm objects to iterate over

    # Get the cosmological parameters for the given cosmology
    cosmo = getcosmo(cosmology)

    # Create  output file if desired
    if filename:
        print("Output to file %r" % (filename))
        fout = open(filename, 'w')

    # Create the structured dataset
    try:
        if mah and com:
            if verbose:
                print("Output requested is zi, Mi, z, dMdt, Mz, c, sig, nu, "
                      "zf")
            if filename:
                fout.write(_getcosmoheader(cosmo)+'\n')
                fout.write("# Initial z - Initial Halo  - Output z - "
                           " Accretion -  Final Halo  - concentration - "
                           "    Mass   -    Peak    -  Formation z "+'\n')
                fout.write("#           -     mass      -          -"
                           "    rate    -     mass     -               - "
                           " Variance  -   Height   -              "+'\n')
                fout.write("#           -    (M200)     -          - "
                           "  (dM/dt)  -    (M200)    -               - "
                           "  (sigma)  -    (nu)    -              "+'\n')
                fout.write("#           -    [Msol]     -          - "
                           " [Msol/yr] -    [Msol]    -               - "
                           "           -            -              "+'\n')
            dataset = np.zeros((lenm, lenzout), dtype=[('zi', float),
                               ('Mi', float), ('z', float), ('dMdt', float),
                               ('Mz', float), ('c', float), ('sig', float),
                               ('nu', float), ('zf', float)])
        elif mah:
            if verbose:
                print("Output requested is zi, Mi, z, dMdt, Mz")
            if filename:
                fout.write(_getcosmoheader(cosmo)+'\n')
                fout.write("# Initial z - Initial Halo  - Output z -"
                           "   Accretion - Final Halo "+'\n')
                fout.write("#           -     mass      -          -"
                           "     rate    -   mass     "+'\n')
                fout.write("#           -    (M200)     -          -"
                           "    (dm/dt)  -  (M200)    "+'\n')
                fout.write("#           -    [Msol]     -          -"
                           "   [Msol/yr] -  [Msol]    "+'\n')
            dataset = np.zeros((lenm, lenzout), dtype=[('zi', float),
                               ('Mi', float), ('z', float),
                               ('dMdt', float), ('Mz', float)])
        else:
            if verbose:
                print("Output requested is zi, Mi, z, c, sig, nu, zf")
            if filename:
                fout.write(_getcosmoheader(cosmo)+'\n')
                fout.write("# Initial z - Initial Halo  - Output z - "
                           " concentration - "
                           "  Mass    -    Peak    -  Formation z "+'\n')
                fout.write("#           -     mass      -          -"
                           "                -"
                           " Variance  -   Height   -              "+'\n')
                fout.write("#           -   (M200)      -          - "
                           "               - "
                           " (sigma)  -    (nu)    -              "+'\n')
                fout.write("#           -   [Msol]      -          - "
                           "               - "
                           "          -            -            "+'\n')
            dataset = np.zeros((lenm, lenzout), dtype=[('zi', float),
                               ('Mi', float), ('z', float), ('c', float),
                               ('sig', float), ('nu', float), ('zf', float)])

        # Now loop over the combination of initial redshift and halo mamss
        for i_ind, (zval, Mval) in enumerate(_izip(zi, Mi)):
            if verbose:
                print("Output Halo of Mass Mi=%s at zi=%s" % (Mval, zval))
            # For a given halo mass Mi at redshift zi need to know
            # output redshifts 'z'
            # Check that all requested redshifts are greater than
            # input redshift, except if z is False, in which case
            # only solve z at zi, i.e. remove a loop
            if z is False:
                ztemp = np.array(zval, ndmin=1, dtype=float)
            else:
                ztemp = np.array(z[z >= zval], dtype=float)

            # Loop over the output redshifts
            if ztemp.size:
                # Return accretion rates and halo mass progenitors at
                # redshifts 'z' for object of mass Mi at zi
                dMdt, Mz = MAH(ztemp, zval, Mval, **cosmo)
                if mah and com:
                    # More expensive to return concentrations
                    c, sig, nu, zf = COM(ztemp, Mz, **cosmo)
                    # Save all arrays
                    for j_ind, j_val in enumerate(ztemp):
                        dataset[i_ind, j_ind] =\
                            (zval, Mval, ztemp[j_ind], dMdt[j_ind], Mz[j_ind],
                             c[j_ind], sig[j_ind], nu[j_ind], zf[j_ind])
                        if filename:
                            fout.write(
                                "{}, {}, {}, {}, {}, {}, {}, {}, {} \n".format(
                                    zval, Mval, ztemp[j_ind], dMdt[j_ind],
                                    Mz[j_ind], c[j_ind], sig[j_ind], nu[j_ind],
                                    zf[j_ind]))
                elif mah:
                    # Save only MAH arrays
                    for j_ind, j_val in enumerate(ztemp):
                        dataset[i_ind, j_ind] =\
                            (zval, Mval, ztemp[j_ind], dMdt[j_ind], Mz[j_ind])
                        if filename:
                            fout.write("{}, {}, {}, {}, {} \n".format(
                                zval, Mval, ztemp[j_ind], dMdt[j_ind],
                                Mz[j_ind]))
                else:
                    # Output only COM arrays
                    c, sig, nu, zf = COM(ztemp, Mz, **cosmo)
                    # For any halo mass Mi at redshift zi
                    # solve for c, sig, nu and zf
                    for j_ind, j_val in enumerate(ztemp):
                        dataset[i_ind, j_ind] =\
                            (zval, Mval, ztemp[j_ind], c[j_ind], sig[j_ind],
                             nu[j_ind], zf[j_ind])
                        if filename:
                            fout.write("{}, {}, {}, {}, {}, {}, {} \n".format(
                                zval, Mval, ztemp[j_ind], c[j_ind], sig[j_ind],
                                nu[j_ind], zf[j_ind]))

    # Make sure to close the file if it was opened
    finally:
        fout.close() if filename else None

    if retcosmo:
        return(dataset, cosmo)
    else:
        return(dataset)
