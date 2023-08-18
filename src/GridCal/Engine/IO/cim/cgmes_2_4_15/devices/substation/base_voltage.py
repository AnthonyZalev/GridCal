# GridCal
# Copyright (C) 2015 - 2023 Santiago Peñate Vera
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
from GridCal.Engine.IO.cim.cgmes_2_4_15.cim_enums import cgmesProfile
from GridCal.Engine.IO.cim.cgmes_2_4_15.devices.identified_object import IdentifiedObject
from GridCal.Engine.IO.base.units import UnitMultiplier, UnitSymbol


class BaseVoltage(IdentifiedObject):

    def __init__(self, rdfid, tpe="BaseVoltage"):
        IdentifiedObject.__init__(self, rdfid, tpe)

        self.nominalVoltage: float = 0.0

        self.register_property(name='nominalVoltage',
                               class_type=float,
                               multiplier=UnitMultiplier.k,
                               unit=UnitSymbol.V,
                               description="The power system resource's base voltage.",
                               profiles=[cgmesProfile.EQ, cgmesProfile.EQ_BD])

    def __str__(self):
        return self.tpe + ':' + self.rdfid + ':' + str(self.nominalVoltage) + ' kV'
