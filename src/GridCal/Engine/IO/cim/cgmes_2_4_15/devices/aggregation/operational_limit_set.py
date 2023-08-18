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
import GridCal.Engine.IO.cim.cgmes_2_4_15.devices.terminal
from GridCal.Engine.IO.base.units import UnitMultiplier, UnitSymbol


class OperationalLimitSet(IdentifiedObject):

    def __init__(self, rdfid, tpe):
        IdentifiedObject.__init__(self, rdfid, tpe)

        self.Terminal: GridCal.Engine.IO.cim.cgmes_2_4_15.devices.terminal.Terminal | None = None
        self.Equipment: IdentifiedObject | None = None

        self.register_property(name='Terminal',
                               class_type=GridCal.Engine.IO.cim.cgmes_2_4_15.devices.terminal.Terminal,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="",
                               profiles=[cgmesProfile.EQ])

        self.register_property(name='Equipment',
                               class_type=IdentifiedObject,
                               multiplier=UnitMultiplier.none,
                               unit=UnitSymbol.none,
                               description="The equipment to which the limit set applies.",
                               profiles=[cgmesProfile.EQ])
