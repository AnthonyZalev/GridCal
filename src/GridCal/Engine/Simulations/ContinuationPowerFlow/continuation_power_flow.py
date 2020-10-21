# This file is a python port of the routines included in MATPOWER to perform continuation power flow.
# The license is the same BSD-style that is provided in LICENSE_MATPOWER

import numpy as np
from numpy import angle, exp, r_, linalg, Inf, dot, zeros, conj
from scipy.sparse import hstack, vstack
from scipy.sparse.linalg import spsolve
from enum import Enum
from GridCal.Engine.basic_structures import ReactivePowerControlMode, Logger
from GridCal.Engine.Simulations.PowerFlow.power_flow_worker import control_q_direct, compile_types
from GridCal.Engine.Simulations.PowerFlow.high_speed_jacobian import _create_J_with_numba
# from GridCal.Engine.Simulations.PowerFlow.jacobian_based_power_flow import Jacobian


class VCStopAt(Enum):
    Nose = 'Nose'
    Full = 'Full curve'


class VCParametrization(Enum):
    Natural = 'Natural'
    ArcLength = 'Arc Length'
    PseudoArcLength = 'Pseudo Arc Length'


def cpf_p(parametrization: VCParametrization, step, z, V, lam, V_prev, lamprv, pv, pq, pvpq):
    """
    Computes the value of the Current Parametrization Function
    :param parametrization: Value of  option (1: Natural, 2:Arc-length, 3: pseudo arc-length)
    :param step: continuation step size
    :param z: normalized tangent prediction vector from previous step
    :param V: complex bus voltage vector at current solution
    :param lam: scalar lambda value at current solution
    :param V_prev: complex bus voltage vector at previous solution
    :param lamprv: scalar lambda value at previous solution
    :param pv: vector of indices of PV buses
    :param pq: vector of indices of PQ buses
    :param pvpq: vector of indices of PQ and PV buses
    :return: value of the parametrization function at the current point
    """

    """
    #CPF_P Computes the value of the CPF parametrization function.
    #
    #   P = CPF_P(parametrization, STEP, Z, V, LAM, VPRV, LAMPRV, PV, PQ)
    #
    #   Computes the value of the parametrization function at the current
    #   solution point.
    #
    #   Inputs:
    #       parametrization : Value of cpf.parametrization option
    #       STEP : continuation step size
    #       Z : normalized tangent prediction vector from previous step
    #       V : complex bus voltage vector at current solution
    #       LAM : scalar lambda value at current solution
    #       VPRV : complex bus voltage vector at previous solution
    #       LAMPRV : scalar lambda value at previous solution
    #       PV : vector of indices of PV buses
    #       PQ : vector of indices of PQ buses
    #
    #   Outputs:
    #       P : value of the parametrization function at the current point
    #
    #   See also CPF_PREDICTOR, CPF_CORRECTOR.

    #   MATPOWER
    #   Copyright (c) 1996-2015 by Power System Engineering Research Center (PSERC)
    #   by Shrirang Abhyankar, Argonne National Laboratory
    #   and Ray Zimmerman, PSERC Cornell
    #
    #   $Id: cpf_p.m 2644 2015-03-11 19:34:22Z ray $
    #
    #   This file is part of MATPOWER.
    #   Covered by the 3-clause BSD License (see LICENSE file for details).
    #   See http://www.pserc.cornell.edu/matpower/ for more info.

    ## evaluate P(x0, lambda0)
    """
    if parametrization == VCParametrization.Natural:        # natural
        if lam >= lamprv:
            P = lam - lamprv - step
        else:
            P = lamprv - lam - step

    elif parametrization == VCParametrization.ArcLength:    # arc length
        Va = angle(V)
        Vm = np.abs(V)
        Va_prev = angle(V_prev)
        Vm_prev = np.abs(V_prev)
        a = r_[Va[pvpq], Vm[pq], lam]
        b = r_[Va_prev[pvpq], Vm_prev[pq], lamprv]
        P = np.sum(np.power(a - b, 2)) - np.power(step, 2)

    elif parametrization == VCParametrization.PseudoArcLength:    # pseudo arc length
        nb = len(V)
        Va = angle(V)
        Vm = np.abs(V)
        Va_prev = angle(V_prev)
        Vm_prev = np.abs(V_prev)
        a = z[r_[pv, pq, nb + pq, 2 * nb]]
        b = r_[Va[pvpq], Vm[pq], lam]
        c = r_[Va_prev[pvpq], Vm_prev[pq], lamprv]
        P = dot(a, b - c) - step
    else:
        # natural
        if lam >= lamprv:
            P = lam - lamprv - step
        else:
            P = lamprv - lam - step

    return P


def cpf_p_jac(parametrization: VCParametrization, z, V, lam, Vprv, lamprv, pv, pq, pvpq):
    """
    Computes partial derivatives of Current Parametrization Function (CPF).
    :param parametrization:
    :param z: normalized tangent prediction vector from previous step
    :param V: complex bus voltage vector at current solution
    :param lam: scalar lambda value at current solution
    :param Vprv: complex bus voltage vector at previous solution
    :param lamprv: scalar lambda value at previous solution
    :param pv: vector of indices of PV buses
    :param pq: vector of indices of PQ buses
    :param pvpq: vector of indices of PQ and PV buses
    :return:  partial of parametrization function w.r.t. voltages
              partial of parametrization function w.r.t. lambda
    """

    """
    #CPF_P_JAC Computes partial derivatives of CPF parametrization function.
    #
    #   [DP_DV, DP_DLAM ] = CPF_P_JAC(parametrization, Z, V, LAM, ...
    #                                                   VPRV, LAMPRV, PV, PQ)
    #
    #   Computes the partial derivatives of the continuation power flow
    #   parametrization function w.r.t. bus voltages and the continuation
    #   parameter lambda.
    #
    #   Inputs:
    #       parametrization : Value of cpf.parametrization option.
    #       Z : normalized tangent prediction vector from previous step
    #       V : complex bus voltage vector at current solution
    #       LAM : scalar lambda value at current solution
    #       VPRV : complex bus voltage vector at previous solution
    #       LAMPRV : scalar lambda value at previous solution
    #       PV : vector of indices of PV buses
    #       PQ : vector of indices of PQ buses
    #
    #   Outputs:
    #       DP_DV : partial of parametrization function w.r.t. voltages
    #       DP_DLAM : partial of parametrization function w.r.t. lambda
    #
    #   See also CPF_PREDICTOR, CPF_CORRECTOR.

    #   MATPOWER
    #   Copyright (c) 1996-2015 by Power System Engineering Research Center (PSERC)
    #   by Shrirang Abhyankar, Argonne National Laboratory
    #   and Ray Zimmerman, PSERC Cornell
    #
    #   $Id: cpf_p_jac.m 2644 2015-03-11 19:34:22Z ray $
    #
    #   This file is part of MATPOWER.
    #   Covered by the 3-clause BSD License (see LICENSE file for details).
    #   See http://www.pserc.cornell.edu/matpower/ for more info.
    """

    if parametrization == VCParametrization.Natural:   # natural
        npv = len(pv)
        npq = len(pq)
        dP_dV = zeros(npv + 2 * npq)
        if lam >= lamprv:
            dP_dlam = 1.0
        else:
            dP_dlam = -1.0

    elif parametrization == VCParametrization.ArcLength:  # arc length
        Va = angle(V)
        Vm = np.abs(V)
        Vaprv = angle(Vprv)
        Vmprv = np.abs(Vprv)
        dP_dV = 2.0 * (r_[Va[pvpq], Vm[pq]] - r_[Vaprv[pvpq], Vmprv[pq]])

        if lam == lamprv:   # first step
            dP_dlam = 1.0   # avoid singular Jacobian that would result from [dP_dV, dP_dlam] = 0
        else:
            dP_dlam = 2.0 * (lam - lamprv)

    elif parametrization == VCParametrization.PseudoArcLength:  # pseudo arc length
        nb = len(V)
        dP_dV = z[r_[pv, pq, nb + pq]]
        dP_dlam = z[2 * nb]

    else:
        # pseudo arc length for any other case
        nb = len(V)
        dP_dV = z[r_[pv, pq, nb + pq]]
        dP_dlam = z[2 * nb]

    return dP_dV, dP_dlam


def corrector(Ybus, Ibus, Sbus, V0, pv, pq, lam0, Sxfr, Vprv, lamprv, z, step, parametrization, tol, max_it,
              pvpq_lookup, verbose):
    """
    Solves the corrector step of a continuation power flow using a full Newton method
    with selected parametrization scheme.

    solves for bus voltages and lambda given the full system admittance
    matrix (for all buses), the complex bus power injection vector (for
    all buses), the initial vector of complex bus voltages, and column
    vectors with the lists of bus indices for the swing bus, PV buses, and
    PQ buses, respectively. The bus voltage vector contains the set point
    for generator (including ref bus) buses, and the reference angle of the
    swing bus, as well as an initial guess for remaining magnitudes and
    angles.

     Uses default options if this parameter is not given. Returns the
     final complex voltages, a flag which indicates whether it converged or not,
     the number of iterations performed, and the final lambda.

    :param Ybus: Admittance matrix (CSC sparse)
    :param Ibus: Bus current injections
    :param Sbus: Bus power injections
    :param V0:  Bus initial voltages
    :param pv: list of pv nodes
    :param pq: list of pq nodes
    :param lam0: initial value of lambda (loading parameter)
    :param Sxfr: [delP+j*delQ] transfer/loading vector for all buses
    :param Vprv: final complex V corrector solution from previous continuation step
    :param lamprv: final lambda corrector solution from previous continuation step
    :param z: normalized predictor for all buses
    :param step: continuation step size
    :param parametrization:
    :param tol:
    :param max_it:
    :param verbose:
    :return: V, CONVERGED, I, LAM
    """

    """
    # CPF_CORRECTOR  Solves the corrector step of a continuation power flow using a
    #   full Newton method with selected parametrization scheme.
    #   [V, CONVERGED, I, LAM] = CPF_CORRECTOR(YBUS, SBUS, V0, REF, PV, PQ, ...
    #                 LAM0, SXFR, VPRV, LPRV, Z, STEP, parametrization, MPOPT)
    #   solves for bus voltages and lambda given the full system admittance
    #   matrix (for all buses), the complex bus power injection vector (for
    #   all buses), the initial vector of complex bus voltages, and column
    #   vectors with the lists of bus indices for the swing bus, PV buses, and
    #   PQ buses, respectively. The bus voltage vector contains the set point
    #   for generator (including ref bus) buses, and the reference angle of the
    #   swing bus, as well as an initial guess for remaining magnitudes and
    #   angles. MPOPT is a MATPOWER options struct which can be used to
    #   set the termination tolerance, maximum number of iterations, and
    #   output options (see MPOPTION for details). Uses default options if
    #   this parameter is not given. Returns the final complex voltages, a
    #   flag which indicates whether it converged or not, the number
    #   of iterations performed, and the final lambda.
    #
    #   The extra continuation inputs are LAM0 (initial predicted lambda),
    #   SXFR ([delP+j*delQ] transfer/loading vector for all buses), VPRV
    #   (final complex V corrector solution from previous continuation step),
    #   LAMPRV (final lambda corrector solution from previous continuation step),
    #   Z (normalized predictor for all buses), and STEP (continuation step size).
    #   The extra continuation output is LAM (final corrector lambda).
    #
    #   See also RUNCPF.
    
    #   MATPOWER
    #   Copyright (c) 1996-2015 by Power System Engineering Research Center (PSERC)
    #   by Ray Zimmerman, PSERC Cornell,
    #   Shrirang Abhyankar, Argonne National Laboratory,
    #   and Alexander Flueck, IIT
    #
    #   Modified by Alexander J. Flueck, Illinois Institute of Technology
    #   2001.02.22 - corrector.m (ver 1.0) based on newtonpf.m (MATPOWER 2.0)
    #
    #   Modified by Shrirang Abhyankar, Argonne National Laboratory
    #   (Updated to be compatible with MATPOWER version 4.1)
    #
    #   $Id: cpf_corrector.m 2644 2015-03-11 19:34:22Z ray $
    #
    #   This file is part of MATPOWER.
    #   Covered by the 3-clause BSD License (see LICENSE file for details).
    #   See http://www.pserc.cornell.edu/matpower/ for more info.
    """

    # initialize
    converged = False
    i = 0
    V = V0
    Va = angle(V)
    Vm = np.abs(V)
    lam = lam0             # set lam to initial lam0
    
    # set up indexing for updating V
    npv = len(pv)
    npq = len(pq)
    pvpq = r_[pv, pq]
    nj = npv + npq * 2

    # j1:j2 - V angle of pv and pq buses
    j1 = 0
    j2 = npv + npq
    # j2:j3 - V mag of pq buses
    j3 = j2 + npq

    # evaluate F(x0, lam0), including Sxfr transfer/loading
    Scalc = V * np.conj(Ybus * V)
    mismatch = Scalc - Sbus - lam * Sxfr
    # F = r_[mismatch[pvpq].real, mismatch[pq].imag]
    
    # evaluate P(x0, lambda0)
    P = cpf_p(parametrization, step, z, V, lam, Vprv, lamprv, pv, pq, pvpq)
    
    # augment F(x,lambda) with P(x,lambda)
    F = r_[mismatch[pvpq].real, mismatch[pq].imag, P]
    
    # check tolerance
    normF = linalg.norm(F, Inf)

    if normF < tol:
        converged = True
        if verbose:
            print('\nConverged!\n')

    # do Newton iterations
    while not converged and i < max_it:

        # update iteration counter
        i += 1
        
        # evaluate Jacobian
        # J = Jacobian(Ybus, V, Ibus, pq, pvpq)
        J = _create_J_with_numba(Ybus, V, pvpq, pq, pvpq_lookup, npv, npq)
    
        dF_dlam = -r_[Sxfr[pvpq].real, Sxfr[pq].imag]

        dP_dV, dP_dlam = cpf_p_jac(parametrization, z, V, lam, Vprv, lamprv, pv, pq, pvpq)
    
        # augment J with real/imag - Sxfr and z^T
        '''
        J = [   J   dF_dlam 
              dP_dV dP_dlam ]
        '''
        J = vstack([hstack([J, dF_dlam.reshape(nj, 1)]),
                    hstack([dP_dV, dP_dlam])], format="csc")
    
        # compute update step
        dx = -spsolve(J, F)
    
        # update voltage
        if npv:
            Va[pvpq] += dx[j1:j2]
        if npq:
            Vm[pq] += dx[j2:j3]

        # update lambda
        lam += dx[j3]

        # update Vm and Va again in case we wrapped around with a negative Vm
        V = Vm * exp(1j * Va)
        Vm = np.abs(V)
        Va = angle(V)

        # evaluate F(x, lam)
        Scalc = V * conj(Ybus * V)
        mismatch = Scalc - Sbus - lam * Sxfr

        # evaluate P(x, lambda)
        P = cpf_p(parametrization, step, z, V, lam, Vprv, lamprv, pv, pq, pvpq)
    
        # compose the mismatch vector
        F = r_[mismatch[pv].real,
               mismatch[pq].real,
               mismatch[pq].imag,
               P]
    
        # check for convergence
        normF = linalg.norm(F, Inf)

        if verbose:
            print('\n#3d        #10.3e', i, normF)
        
        if normF < tol:
            converged = True
            if verbose:
                print('\nNewton''s method corrector converged in ', i, ' iterations.\n')

    if verbose:
        if not converged:
            print('\nNewton method corrector did not converge in  ', i, ' iterations.\n')

    return V, converged, i, lam, normF, Scalc


def predictor(V, Ibus, lam, Ybus, Sxfr, pv, pq, step, z, Vprv, lamprv,
              parametrization: VCParametrization, pvpq_lookup):
    """
    Computes a prediction (approximation) to the next solution of the
    continuation power flow using a normalized tangent predictor.
    :param V: complex bus voltage vector at current solution
    :param Ibus:
    :param lam: scalar lambda value at current solution
    :param Ybus: complex bus admittance matrix
    :param Sxfr: complex vector of scheduled transfers (difference between bus injections in base and target cases)
    :param pv: vector of indices of PV buses
    :param pq: vector of indices of PQ buses
    :param step: continuation step length
    :param z: normalized tangent prediction vector from previous step
    :param Vprv: complex bus voltage vector at previous solution
    :param lamprv: scalar lambda value at previous solution
    :param parametrization: Value of cpf parametrization option.
    :return: V0 : predicted complex bus voltage vector
             LAM0 : predicted lambda continuation parameter
             Z : the normalized tangent prediction vector
    """

    """    
    %   MATPOWER
    %   Copyright (c) 1996-2015 by Power System Engineering Research Center (PSERC)
    %   by Shrirang Abhyankar, Argonne National Laboratory
    %   and Ray Zimmerman, PSERC Cornell
    %
    %   $Id: cpf_predictor.m 2644 2015-03-11 19:34:22Z ray $
    %
    %   This file is part of MATPOWER.
    %   Covered by the 3-clause BSD License (see LICENSE file for details).
    %   See http://www.pserc.cornell.edu/matpower/ for more info.
    """

    # sizes
    nb = len(V)
    npv = len(pv)
    npq = len(pq)
    pvpq = r_[pv, pq]
    nj = npv+npq*2

    # compute Jacobian for the power flow equations
    # J = Jacobian(Ybus, V, Ibus, pq, pvpq)
    J = _create_J_with_numba(Ybus, V, pvpq, pq, pvpq_lookup, npv, npq)

    dF_dlam = -r_[Sxfr[pvpq].real, Sxfr[pq].imag]

    dP_dV, dP_dlam = cpf_p_jac(parametrization, z, V, lam, Vprv, lamprv, pv, pq, pvpq)
    
    # linear operator for computing the tangent predictor
    '''
    J2 = [   J   dF_dlam
           dP_dV dP_dlam ]
    '''
    J2 = vstack([hstack([J,     dF_dlam.reshape(nj, 1)]),
                 hstack([dP_dV, dP_dlam])], format="csc")

    Va_prev = np.angle(V)
    Vm_prev = np.abs(V)
    
    # compute normalized tangent predictor
    s = np.zeros(npv + 2 * npq + 1)

    # increase in the direction of lambda
    s[npv + 2 * npq] = 1

    # tangent vector
    z[r_[pvpq, nb + pq, 2 * nb]] = spsolve(J2, s)

    # normalize_string tangent predictor  (dividing by the euclidean norm)
    z /= linalg.norm(z)
    
    Va0 = Va_prev
    Vm0 = Vm_prev
    # lam0 = lam
    
    # prediction for next step
    Va0[pvpq] = Va_prev[pvpq] + step * z[pvpq]
    Vm0[pq] = Vm_prev[pq] + step * z[pq + nb]
    lam0 = lam + step * z[2 * nb]
    V0 = Vm0 * exp(1j * Va0)
        
    return V0, lam0, z


def continuation_nr(Ybus, Ibus_base, Ibus_target, Sbus_base, Sbus_target, V, pv, pq, step,
                    approximation_order: VCParametrization,
                    adapt_step, step_min, step_max, error_tol=1e-3, tol=1e-6, max_it=20,
                    stop_at=VCStopAt.Nose,
                    controlQ=ReactivePowerControlMode.NoControl,
                    Qmax_bus=None, Qmin_bus=None, original_bus_types=None,
                    verbose=False, call_back_fx=None, logger=Logger()):
    """
    Runs a full AC continuation power flow using a normalized tangent
    predictor and selected approximation_order scheme.
    :param Ybus: Admittance matrix
    :param Ibus_base:
    :param Ibus_target:
    :param Sbus_base: Power array of the base solvable case
    :param Sbus_target: Power array of the case to be solved
    :param V: Voltage array of the base solved case
    :param pv: Array of pv indices
    :param pq: Array of pq indices
    :param step: Adaptation step
    :param approximation_order: order of the approximation {Natural, Arc, Pseudo arc}
    :param adapt_step: use adaptive step size?
    :param step_min: minimum step size
    :param step_max: maximum step size
    :param error_tol: Error tolerance
    :param tol: Solutions tolerance
    :param max_it: Maximum iterations
    :param stop_at:  Value of Lambda to stop at. It can be a number or {'NOSE', 'FULL'}
    :param verbose: Display additional intermediate information?
    :param call_back_fx: Function to call on every iteration passing the lambda parameter
    :return: Voltage_series: List of all the voltage solutions from the base to the target
             Lambda_series: Lambda values used in the continuation


    Ported from MATPOWER
        Copyright (c) 1996-2015 by Power System Engineering Research Center (PSERC)
        by Ray Zimmerman, PSERC Cornell,
        Shrirang Abhyankar, Argonne National Laboratory,
        and Alexander Flueck, IIT

        $Id: runcpf.m 2644 2015-03-11 19:34:22Z ray $

        This file is part of MATPOWER.
        Covered by the 3-clause BSD License (see LICENSE file for details).
        See http://www.pserc.cornell.edu/matpower/ for more info.
    """

    ########################################
    # INITIALIZATION
    ########################################

    # scheduled transfer
    Sxfr = Sbus_target - Sbus_base
    nb = len(Sbus_base)
    lam = 0
    lam_prev = lam   # lam at previous step
    V_prev = V       # V at previous step
    continuation = True
    cont_steps = 0
    normF = 0
    success = False
    pvpq = r_[pv, pq]
    bus_types = original_bus_types.copy()

    z = zeros(2 * nb + 1)
    z[2 * nb] = 1.0

    # generate lookup pvpq -> index pvpq (used in createJ)
    pvpq_lookup = np.zeros(np.max(Ybus.indices) + 1, dtype=int)
    pvpq_lookup[pvpq] = np.arange(len(pvpq))

    # result arrays
    voltage_series = list()
    lambda_series = list()

    # Simulation
    while continuation:
        cont_steps += 1

        # prediction for next step
        V0, lam0, z = predictor(V=V,
                                Ibus=Ibus_base,
                                lam=lam,
                                Ybus=Ybus,
                                Sxfr=Sxfr,
                                pv=pv,
                                pq=pq,
                                step=step,
                                z=z,
                                Vprv=V_prev,
                                lamprv=lam_prev,
                                parametrization=approximation_order,
                                pvpq_lookup=pvpq_lookup)

        # save previous voltage, lambda before updating
        V_prev = V.copy()
        lam_prev = lam

        # correction
        V, success, i, lam, normF, Scalc = corrector(Ybus=Ybus,
                                                     Ibus=Ibus_base,
                                                     Sbus=Sbus_base,
                                                     V0=V0,
                                                     pv=pv,
                                                     pq=pq,
                                                     lam0=lam0,
                                                     Sxfr=Sxfr,
                                                     Vprv=V_prev,
                                                     lamprv=lam_prev,
                                                     z=z,
                                                     step=step,
                                                     parametrization=approximation_order,
                                                     tol=tol,
                                                     max_it=max_it,
                                                     pvpq_lookup=pvpq_lookup,
                                                     verbose=verbose)

        # store series values
        voltage_series.append(V)
        lambda_series.append(lam)

        if success:

            if verbose:
                print('Step: ', cont_steps, ' Lambda prev: ', lam_prev, ' Lambda: ', lam)
                print(V)

            # Check controls
            if controlQ == ReactivePowerControlMode.Direct:
                V, \
                Qnew, \
                types_new, \
                any_q_control_issue = control_q_direct(V=V,
                                                       Vset=np.abs(V),
                                                       Q=Scalc.imag,
                                                       Qmax=Qmax_bus,
                                                       Qmin=Qmin_bus,
                                                       types=bus_types,
                                                       original_types=original_bus_types,
                                                       verbose=verbose)
            else:
                # did not check Q limits
                any_q_control_issue = False
                types_new = bus_types
                Qnew = Scalc.imag

            # Check the actions of the Q-control
            if any_q_control_issue:
                bus_types = types_new
                Sbus = Scalc.real + 1j * Qnew
                vd, pq, pv, pqpv = compile_types(Sbus, types_new, logger)
            else:
                if verbose:
                    print('Q controls Ok')

            if stop_at == VCStopAt.Full:
                if abs(lam) < 1e-8:
                    # traced the full continuation curve
                    if verbose:
                        print('\nTraced full continuation curve in ', cont_steps, ' continuation steps\n')
                    continuation = False

                elif (lam < lam_prev) and (lam - step < 0):
                    # next step will overshoot

                    # modify step-size
                    step = lam

                    # change to natural parametrization
                    approximation_order = VCParametrization.Natural

                    # disable step-adaptivity
                    adapt_step = 0
            elif stop_at == VCStopAt.Nose:

                if lam < lam_prev:
                    # reached the nose point
                    if verbose:
                        print('\nReached steady state loading limit in ', cont_steps, ' continuation steps\n')
                    continuation = False
            else:
                raise Exception('Stop point ' + stop_at + ' not recognised.')

            if adapt_step and continuation:

                # Adapt step size
                fx = r_[angle(V[pq]), np.abs(V[pvpq]), lam] - r_[angle(V0[pq]), np.abs(V0[pvpq]), lam0]
                cpf_error = linalg.norm(fx, Inf)

                if cpf_error == 0:
                    cpf_error = 1e-20

                if cpf_error < error_tol:
                    # Increase step size
                    step = step * error_tol / cpf_error
                    if step > step_max:
                        step = step_max

                else:
                    # Decrease step size
                    step = step * error_tol / cpf_error
                    if step < step_min:
                        step = step_min

            # call callback function
            if call_back_fx is not None:
                call_back_fx(lam)

        else:

            continuation = False

            if verbose:
                print('step ', cont_steps, ' : lambda = ', lam, ', corrector did not converge in ', i, ' iterations\n')

    return voltage_series, lambda_series, normF, success


if __name__ == '__main__':

    from GridCal.Engine import *

    # fname = os.path.join('..', '..', '..', '..', 'Grids_and_profiles', 'grids', 'IEEE 30 Bus with storage.xlsx')
    fname = os.path.join('..', '..', '..', '..', 'Grids_and_profiles', 'grids', 'lynn5buspv.xlsx')

    print('Reading...')
    main_circuit = FileOpen(fname).open()
    pf_options = PowerFlowOptions(SolverType.NR, verbose=False,
                                  initialize_with_existing_solution=False,
                                  multi_core=False, dispatch_storage=True,
                                  control_q=ReactivePowerControlMode.NoControl,
                                  control_p=True)

    ####################################################################################################################
    # PowerFlowDriver
    ####################################################################################################################
    print('\n\n')
    power_flow = PowerFlowDriver(main_circuit, pf_options)
    power_flow.run()

    print('\n\n', main_circuit.name)
    print('\t|V|:', abs(power_flow.results.voltage))
    print('\t|Sbranch|:', abs(power_flow.results.Sbranch))
    print('\t|loading|:', abs(power_flow.results.loading) * 100)
    print('\tReport')
    print(power_flow.results.get_report_dataframe())

    ####################################################################################################################
    # Voltage collapse
    ####################################################################################################################
    vc_options = ContinuationPowerFlowOptions(step=0.001,
                                              approximation_order=VCParametrization.ArcLength,
                                              adapt_step=True,
                                              step_min=0.00001,
                                              step_max=0.2,
                                              error_tol=1e-3,
                                              tol=1e-6,
                                              max_it=20,
                                              stop_at=VCStopAt.Full,
                                              verbose=False)

    # just for this test
    numeric_circuit = main_circuit.compile_snapshot()
    numeric_inputs = numeric_circuit.compute(ignore_single_node_islands=pf_options.ignore_single_node_islands)
    Sbase = zeros(len(main_circuit.buses), dtype=complex)
    Vbase = zeros(len(main_circuit.buses), dtype=complex)
    for c in numeric_inputs:
        Sbase[c.original_bus_idx] = c.Sbus
        Vbase[c.original_bus_idx] = c.Vbus

    unitary_vector = -1 + 2 * np.random.random(len(main_circuit.buses))

    # unitary_vector = random.random(len(grid.buses))
    vc_inputs = ContinuationPowerFlowInput(Sbase=Sbase,
                                           Vbase=Vbase,
                                           Starget=Sbase * (1 + unitary_vector))
    vc = ContinuationPowerFlow(circuit=main_circuit, options=vc_options, inputs=vc_inputs, pf_options=pf_options)
    vc.run()
    df = vc.results.plot()

    print(df)

    plt.show()
