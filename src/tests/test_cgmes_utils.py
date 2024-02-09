import pytest
from GridCalEngine.IO.cim.cgmes.cgmes_utils import get_windings_number, get_windings, get_voltages, get_rate, \
    get_voltage_power_transformer_end, get_pu_values_power_transformer_end, get_voltage_ac_line_segment, \
    get_pu_values_ac_line_segment, get_rate_ac_line_segment, get_voltage_terminal, get_topological_nodes_bus_bar, \
    get_topological_node_bus_bar, get_topological_nodes_dipole
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.ac_line_segment import ACLineSegment
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.base_voltage import BaseVoltage
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.busbar_section import BusbarSection
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.identified_object import IdentifiedObject
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.power_transformer import PowerTransformer
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.power_transformer_end import PowerTransformerEnd
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.terminal import Terminal
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.topological_node import TopologicalNode

from src.GridCalEngine.IO.cim.cgmes.cgmes_utils import get_pu_values_power_transformer


def test_get_windings_number_no_windings_returns_zero():
    # Create a PowerTransformer instance with no references to PowerTransformerEnd
    power_transformer = PowerTransformer("a", "b")
    assert get_windings_number(power_transformer) == 0


def test_get_windings_number_multiple_winding_returns_correct_amount():
    # Create a PowerTransformer instance with one reference to PowerTransformerEnd
    power_transformer = PowerTransformer("a", "b")
    power_transformer.references_to_me["PowerTransformerEnd"] = [1, 2, 3]
    assert get_windings_number(power_transformer) == 3


def test_get_windings_no_windings_returns_no_element():
    # Create a PowerTransformer instance with no references to PowerTransformerEnd
    power_transformer = PowerTransformer("a", "b")
    assert len(get_windings(power_transformer)) == 0


def test_get_windings_add_windings_returns_correct_element():
    # Create a PowerTransformer instance with no references to PowerTransformerEnd
    power_transformer = PowerTransformer("a", "b")
    power_transformer.references_to_me["PowerTransformerEnd"] = [1]
    assert get_windings(power_transformer)[0] == 1


def test_get_pu_values_power_transformer_no_power_transformer():
    with pytest.raises(AttributeError) as excinfo:
        get_pu_values_power_transformer(None, 100.0)
        assert str(excinfo.value).index('NoneType') != -1
        assert str(excinfo.value).index('references_to_me') != -1


def test_get_pu_values_power_transformer_no_winding():
    power_transformer = PowerTransformer()
    power_transformer.references_to_me["PowerTransformerEnd"] = []
    (R, X, G, B, R0, X0, G0, B0) = get_pu_values_power_transformer(power_transformer, 100.0)
    assert R == 0
    assert X == 0
    assert G == 0
    assert B == 0
    assert R0 == 0
    assert X0 == 0
    assert G0 == 0
    assert B0 == 0


def test_get_pu_values_power_transformer_two_windings():
    power_transformer = PowerTransformer()

    power_transformer_end = PowerTransformerEnd()
    power_transformer_end.ratedS = 1
    power_transformer_end.ratedU = 2

    power_transformer_end.r = 1
    power_transformer_end.x = 1
    power_transformer_end.g = 1
    power_transformer_end.b = 1
    power_transformer_end.r0 = 1
    power_transformer_end.x0 = 1
    power_transformer_end.g0 = 1
    power_transformer_end.b0 = 1

    power_transformer.references_to_me["PowerTransformerEnd"] = [power_transformer_end, power_transformer_end]
    (R, X, G, B, R0, X0, G0, B0) = get_pu_values_power_transformer(power_transformer, 100.0)
    assert R == 50
    assert X == 50
    assert G == 800
    assert B == 800
    assert R0 == 50
    assert X0 == 50
    assert G0 == 800
    assert B0 == 800


def test_get_voltages_():
    power_transformer = PowerTransformer()
    power_transformer_end = PowerTransformerEnd()
    power_transformer_end.ratedU = 1
    power_transformer.references_to_me["PowerTransformerEnd"] = [power_transformer_end, power_transformer_end]
    result = get_voltages(power_transformer)
    assert [1, 1] == result


def test_get_rate():
    power_transformer = PowerTransformer()
    power_transformer_end = PowerTransformerEnd()
    power_transformer_end.ratedS = 2
    power_transformer.references_to_me["PowerTransformerEnd"] = [power_transformer_end]
    result = get_rate(power_transformer)
    assert 2 == result


@pytest.fixture
def transformer_end_with_ratedU():
    pte = PowerTransformerEnd()
    pte.ratedU = 110
    pte.BaseVoltage = None
    return pte


@pytest.fixture
def transformer_end_with_BaseVoltage():
    pte = PowerTransformerEnd()
    pte.ratedU = 0
    pte.BaseVoltage = BaseVoltage()
    pte.BaseVoltage.nominalVoltage = 220
    return pte


@pytest.fixture
def transformer_end_without_voltage():
    pte = PowerTransformerEnd()
    pte.ratedU = 0
    pte.BaseVoltage = None
    return pte


def test_get_voltage_power_transformer_end_has_ratedU_value_returns_value(transformer_end_with_ratedU):
    assert get_voltage_power_transformer_end(transformer_end_with_ratedU) == 110


def test_get_voltage_power_transformer_end_has_BaseVoltage_value_returns_value(transformer_end_with_BaseVoltage):
    assert get_voltage_power_transformer_end(transformer_end_with_BaseVoltage) == 220


def test_get_voltage_power_transformer_end_has_no_voltage_returns_None(transformer_end_without_voltage):
    assert get_voltage_power_transformer_end(transformer_end_without_voltage) == None


def test_get_pu_values_power_transformer_end_no_ratedS_and_ratedU_returns_Zero():
    pte = PowerTransformerEnd()
    (R, X, G, B, R0, X0, G0, B0) = get_pu_values_power_transformer_end(pte)
    assert R == 0
    assert X == 0
    assert G == 0
    assert B == 0
    assert R0 == 0
    assert X0 == 0
    assert G0 == 0
    assert B0 == 0


def test_get_voltage_ac_line_segment_basevoltage_exists_returns_nominal_voltage():
    acl = ACLineSegment()
    acl.BaseVoltage = BaseVoltage()
    acl.BaseVoltage.nominalVoltage = 220
    assert get_voltage_ac_line_segment(acl, None) == 220


def test_get_voltage_ac_line_segment_basevoltage_None_Terminal_None_returns_None():
    acl = ACLineSegment()
    assert get_voltage_ac_line_segment(acl, None) == None


def test_get_voltage_ac_line_segment_basevoltage_None_Terminal_not_None_returns_first_elements_voltage():
    acl = ACLineSegment()
    t = Terminal()
    t.TopologicalNode = TopologicalNode()
    t.TopologicalNode.BaseVoltage = BaseVoltage()
    t.TopologicalNode.BaseVoltage.nominalVoltage = 220
    acl.references_to_me["Terminal"] = [t]
    assert get_voltage_ac_line_segment(acl, None) == 220


def test_get_voltage_ac_line_segment_basevoltage_None_Terminal_length_0_returns_None():
    acl = ACLineSegment()
    t = Terminal()
    t.TopologicalNode = TopologicalNode()
    t.TopologicalNode.BaseVoltage = BaseVoltage()
    t.TopologicalNode.BaseVoltage.nominalVoltage = 220
    acl.references_to_me["Terminal"] = []
    assert get_voltage_ac_line_segment(acl, None) == None


def test_get_pu_values_ac_line_segment_BaseVoltage_is_None_returns_zero():
    acls = ACLineSegment()
    (R, X, G, B, R0, X0, G0, B0) = get_pu_values_ac_line_segment(acls, None)
    assert R == 0
    assert X == 0
    assert G == 0
    assert B == 0
    assert R0 == 0
    assert X0 == 0
    assert G0 == 0
    assert B0 == 0


def test_get_pu_values_ac_line_segment_BaseVoltage_is_filled_returns_correct_values():
    acls = ACLineSegment()
    acls.BaseVoltage = BaseVoltage()
    acls.BaseVoltage.nominalVoltage = 10
    acls.r = 100
    acls.x = 100
    acls.gch = 100
    acls.bch = 100
    acls.r0 = 100
    acls.x0 = 100
    acls.gch0 = 100
    acls.bch0 = 100

    (R, X, G, B, R0, X0, G0, B0) = get_pu_values_ac_line_segment(acls, None)
    assert R == 100
    assert X == 100
    assert G == 100
    assert B == 100
    assert R0 == 100
    assert X0 == 100
    assert G0 == 100
    assert B0 == 100


def test_get_rate_ac_line_segment_returns_constant():
    assert get_rate_ac_line_segment() == 1e-20


def test_get_voltage_terminal_topologicalnode_nomivalvoltage_set_retuns_value():
    t = Terminal()
    t.TopologicalNode = TopologicalNode()
    t.TopologicalNode.BaseVoltage = BaseVoltage()
    t.TopologicalNode.BaseVoltage.nominalVoltage = 10
    assert get_voltage_terminal(t, None) == 10


def test_get_voltage_terminal_no_topologicalnode_retuns_None():
    t = Terminal()
    t.TopologicalNode = None
    assert get_voltage_terminal(t, None) is None


def test_get_topological_nodes_bus_bar_setup_terminals_return_topologicalnodelist():
    bbs = BusbarSection()
    bbs.references_to_me["Terminal"] = [Terminal()]
    result = get_topological_nodes_bus_bar(bbs)
    assert len(result) == 1  # TODO


def test_get_topological_node_bus_bar_setup_terminals_return_first_topologicalnode():
    bbs = BusbarSection()
    bbs.references_to_me["Terminal"] = [Terminal()]
    result = get_topological_node_bus_bar(bbs)
    assert result is not None  # TODO


def test_get_topological_nodes_dipole_with_valid_terminals():
    t1 = Terminal()
    t2 = Terminal()
    t1.TopologicalNode = TopologicalNode()
    t2.TopologicalNode = TopologicalNode()
    i = IdentifiedObject("a", "b")
    i.references_to_me["Terminal"] = [t1, t2]
    node1, node2 = get_topological_nodes_dipole(i)
    assert isinstance(node1, TopologicalNode)
    assert isinstance(node2, TopologicalNode)


def test_get_topological_nodes_dipole_with_valid_terminals2():
    t1 = Terminal()
    t2 = Terminal()
    t1.TopologicalNode = TopologicalNode()
    t2.TopologicalNode = TopologicalNode()
    i = IdentifiedObject("a", "b")
    i.references_to_me["aaa"] = [t1, t2]
    node1, node2 = get_topological_nodes_dipole(i)
    assert node1 is None
    assert node2 is None

def test_get_topological_nodes_dipole_with_only_one_terminal_returns_None():
    t1 = Terminal()
    t1.TopologicalNode = TopologicalNode()
    i = IdentifiedObject("a", "b")
    i.references_to_me["Terminal"] = [t1]
    node1, node2 = get_topological_nodes_dipole(i)
    assert node1 is None
    assert node2 is None