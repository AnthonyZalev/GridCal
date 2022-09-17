# GridCal
# Copyright (C) 2022 Santiago Peñate Vera
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
import numpy as np
import numba as nb

from GridCal.Engine.basic_structures import Logger
from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.Core.snapshot_pf_data import compile_snapshot_circuit, SnapshotData
from GridCal.Engine.Simulations.PowerFlow.NumericalMethods import helm_coefficients_AY


def calc_V_outage(branch_data, Ybus, Yseries, V0, S0, Ysh0, pq, pv, sl, pqpv):
    """
    Calculate the voltage due to outages in a non-linear manner with HELM.
    Use directly V from HELM, do not go for Pade, may need more time for not much benefit

    :param branch_data: branch data for all branches to disconnect
    :param Ybus: original admittance matrix
    :param Yseries: admittance matrix with only series branches
    :param V0: initial voltage array
    :param S0: vector of powers
    :param Ysh0: array of shunt admittances
    :param pq: set of PQ buses
    :param pv: set of PV buses
    :param sl: set of slack buses
    :param pqpv: set of PQ + PV buses
    :return: matrix of voltages after the outages
    """

    nbus = Ybus.shape[0]
    nbr = len(branch_data)
    V_cont = np.zeros((nbus, nbr))

    for i in range(nbr):

        AY = build_AY_outage()

        U, X, Q, V, iter_ =  helm_coefficients_AY(Ybus, Yseries, V0, S0, Ysh0, AY, pq, pv, sl, pqpv, tolerance=1e-6, max_coeff=10)

        V_cont[:, i] = V

    return V_cont


def calc_ptdf_from_V(V_cont, Y, Pini):

    nbus = V_cont.shape[0]

    Pbus = np.real(V_cont * np.conj(Y * V_cont))

    Pinim = np.zeros_like(Pbus)
    ir = range(nbus)
    Pinim[ir, :] = Pini

    ptdf = (Pbus - Pinim) / Pinim

    return ptdf


def calc_lodf_from_V(V_cont, Yf, Cf, Pini):

    nbr = V_cont.shape[1]

    Vf = Cf * V_cont
    Pf = np.real(Vf * np.conj(Yf * V_cont))

    Pinim = np.zeros_like(Pf)
    ir = range(nbr)
    Pinim[ir, :] = Pini

    lodf = (Pf - Pinim) / Pinim

    return lodf


@nb.njit(cache=True)
def make_otdf(ptdf, lodf, j):
    """
    Outage sensitivity of the branches when transferring power from the bus j to the slack
        LODF: outage transfer distribution factors
    :param ptdf: power transfer distribution factors matrix (n-branch, n-bus)
    :param lodf: line outage distribution factors matrix (n-branch, n-branch)
    :param j: index of the bus injection
    :return: LODF matrix (n-branch, n-branch)
    """
    nk = ptdf.shape[0]
    nl = nk
    otdf = np.empty((nk, nl))

    for k in range(nk):
        for l in range(nl):
            otdf[k, l] = ptdf[k, j] + lodf[k, l] * ptdf[l, j]

    return otdf


@nb.njit(parallel=True)
def make_otdf_max(ptdf, lodf):
    """
    Maximum Outage sensitivity of the branches when transferring power from any bus to the slack
        LODF: outage transfer distribution factors
    :param ptdf: power transfer distribution factors matrix (n-branch, n-bus)
    :param lodf: line outage distribution factors matrix (n-branch, n-branch)
    :return: LODF matrix (n-branch, n-branch)
    """
    nj = ptdf.shape[1]
    nk = ptdf.shape[0]
    nl = nk
    otdf = np.zeros((nk, nl))

    if nj < 500:
        for j in range(nj):
            for k in range(nk):
                for l in range(nl):
                    val = ptdf[k, j] + lodf[k, l] * ptdf[l, j]
                    if abs(val) > abs(otdf[k, l]):
                        otdf[k, l] = val
    else:
        for j in nb.prange(nj):
            for k in range(nk):
                for l in range(nl):
                    val = ptdf[k, j] + lodf[k, l] * ptdf[l, j]
                    if abs(val) > abs(otdf[k, l]):
                        otdf[k, l] = val
    return otdf


@nb.njit(cache=True)
def make_contingency_flows(lodf, flows):
    """
    Make contingency Sf matrix
    :param lodf: line outage distribution factors
    :param flows: base Sf in MW
    :return: outage Sf for every line after each contingency (n-branch, n-branch[outage])
    """
    nbr = lodf.shape[0]
    omw = np.zeros((nbr, nbr))

    for m in range(nbr):
        for c in range(nbr):
            if m != c:
                omw[m, c] = flows[m] + lodf[m, c] * flows[c]

    return omw


@nb.njit(cache=True)
def make_transfer_limits(ptdf, flows, rates):
    """
    Compute the maximum transfer limits of each branch in normal operation
    :param ptdf: power transfer distribution factors matrix (n-branch, n-bus)
    :param flows: base Sf in MW
    :param rates: array of branch rates
    :return: Max transfer limits vector  (n-branch)
    """
    nbr = ptdf.shape[0]
    nbus = ptdf.shape[1]
    tmc = np.zeros(nbr)

    for m in range(nbr):
        for i in range(nbus):

            if ptdf[m, i] != 0.0:
                val = (rates[m] - flows[m]) / ptdf[m, i]  # I want it with sign

                # update the transference value
                if abs(val) > abs(tmc[m]):
                    tmc[m] = val

    return tmc


@nb.njit(parallel=True)
def make_contingency_transfer_limits(otdf_max, lodf, flows, rates):
    """
    Compute the maximum transfer limits after contingency of each branch
    :param otdf_max: Maximum Outage sensitivity of the branches when transferring power
                     from any bus to the slack  (n-branch, n-branch)
    :param omw: contingency Sf matrix (n-branch, n-branch)
    :param rates: array of branch rates
    :return: Max transfer limits matrix  (n-branch, n-branch)
    """
    nbr = otdf_max.shape[0]
    tmc = np.zeros((nbr, nbr))

    if nbr < 500:
        for m in range(nbr):
            for c in range(nbr):
                if m != c:
                    if otdf_max[m, c] != 0.0:
                        omw = flows[m] + lodf[m, c] * flows[c]  # compute the contingency flow
                        tmc[m, c] = (rates[m] - omw) / otdf_max[m, c]  # i want it with sign
    else:
        for m in nb.prange(nbr):
            for c in range(nbr):
                if m != c:
                    if otdf_max[m, c] != 0.0:
                        omw = flows[m] + lodf[m, c] * flows[c]  # compute the contingency flow
                        tmc[m, c] = (rates[m] - omw) / otdf_max[m, c]  # i want it with sign

    return tmc


def make_worst_contingency_transfer_limits(tmc):

    nbr = tmc.shape[0]
    wtmc = np.zeros((nbr, 2))

    wtmc[:, 0] = tmc.max(axis=1)
    wtmc[:, 1] = tmc.min(axis=1)

    return wtmc


class NonLinearAnalysis:

    def __init__(self, grid: MultiCircuit, distributed_slack=True, correct_values=True):
        """

        :param grid:
        :param distributed_slack:
        """

        self.grid = grid

        self.distributed_slack = distributed_slack

        self.correct_values = correct_values

        self.numerical_circuit: SnapshotData = None

        self.PTDF = None

        self.LODF = None

        self.__OTDF = None

        self.V_cont = None

        self.logger = Logger()

    def run(self):
        """
        Run the PTDF and LODF
        """
        self.numerical_circuit = compile_snapshot_circuit(self.grid)
        islands = self.numerical_circuit.split_into_islands()
        n_br = self.numerical_circuit.nbr
        n_bus = self.numerical_circuit.nbus
        self.PTDF = np.zeros((n_br, n_bus))
        self.LODF = np.zeros((n_br, n_br))
        self.V_cont = np.zeros((n_bus, n_br))

        # compute the PTDF and LODF per islands
        if len(islands) > 0:
            for n_island, island in enumerate(islands):

                # no slacks will make it impossible to compute the PTDF analytically
                if len(island.vd) == 1:
                    if len(island.pqpv) > 0:

def calc_V_outage(branch_data, Ybus, Yseries, V0, S0, Ysh0, pq, pv, sl, pqpv):
                        V_cont = calc_V_outage(island.branch_data, 
                                               island.Ybus,
                                               island.Yseries,
                                               island.Vbus,
                                               island.Sbus,
                                               island.Yshunt,
                                               island.pq,
                                               island.pv,
                                               island.vd,
                                               island.pqpv)  # call HELM with AY

                        ptdf_island = calc_ptdf_from_V(V_cont, )
                        lodf_island = calc_lodf_from_V(V_cont, )

                        # assign objects to the full matrix
                        self.V_cont[np.ix_(island.original_bus_idx, island.original_branch_idx)] = V_cont
                        self.PTDF[np.ix_(island.original_branch_idx, island.original_bus_idx)] = ptdf_island
                        self.LODF[np.ix_(island.original_branch_idx, island.original_branch_idx)] = lodf_island

                    else:
                        self.logger.add_error('No PQ or PV nodes', 'Island {}'.format(n_island))
                elif len(island.vd) == 0:
                    self.logger.add_warning('No slack bus', 'Island {}'.format(n_island))
                else:
                    self.logger.add_error('More than one slack bus', 'Island {}'.format(n_island))
        else:

            # there is only 1 island, use island[0]
            self.V_cont = calc_V_outage(island[0].something, )  # call HELM with AY
            self.PTDF = calc_ptdf_from_V(V_cont, )
            self.LODF = calc_lodf_from_V(V_cont, )

    @property
    def OTDF(self):
        """
        Maximum Outage sensitivity of the branches when transferring power from any bus to the slack
        LODF: outage transfer distribution factors
        :return: Maximum LODF matrix (n-branch, n-branch)
        """
        if self.__OTDF is None:  # lazy-evaluation
            self.__OTDF = make_otdf_max(self.PTDF, self.LODF)

        return self.__OTDF

    def get_transfer_limits(self, flows):
        """
        compute the normal transfer limits
        :param flows: base Sf in MW
        :return: Max transfer limits vector (n-branch)
        """
        return make_transfer_limits(self.PTDF, flows, self.numerical_circuit.Rates)

    def get_contingency_transfer_limits(self, flows):
        """
        Compute the contingency transfer limits
        :param flows: base Sf in MW
        :return: Max transfer limits matrix (n-branch, n-branch)
        """
        return make_contingency_transfer_limits(self.OTDF, self.LODF, flows, self.numerical_circuit.Rates)

    def get_flows(self, Sbus):
        """
        Compute the time series branch Sf using the PTDF
        :param Sbus: Power injections time series array
        :return: branch active power Sf time series
        """

        # option 2: call the power directly
        Pbr = np.dot(self.PTDF, Sbus.real) * self.grid.Sbase

        return Pbr

    def get_flows_time_series(self, Sbus):
        """
        Compute the time series branch Sf using the PTDF
        :param Sbus: Power injections time series array
        :return: branch active power Sf time series
        """

        # option 2: call the power directly
        Pbr = np.dot(self.PTDF, Sbus.real).T * self.grid.Sbase

        return Pbr
