"""Identity, hierarchy and addressing tests (PR-IDENTITY-*)."""


import pytest

from sslv1.errors import ConfigurationError, ValidationError
from sslv1.identity import (
    MAX_BUS_ADDRESS,
    MIN_BUS_ADDRESS,
    BusAddress,
    DeviceIdentity,
    Identifier,
    McuUniqueId,
)
from sslv1.comm import InMemoryBus
from sslv1.nodes import GroupController, GroupControllerConfig, LampNode

from conftest import GROUP, PRODUCT, SITE, make_lamp_config


def test_identity_hierarchy_is_complete(lamp_identity):
    assert str(lamp_identity) == "SSL-V1/SITE-A/GRP-01/LAMP-01"
    assert lamp_identity.mcu_unique_id.hex == "0a0b0c0d"


def test_identity_is_deterministic_and_value_based():
    a = Identifier("LAMP-01")
    b = Identifier("LAMP-01")
    assert a == b
    assert hash(a) == hash(b)
    assert {a, b} == {a}


def test_empty_identifier_is_rejected():
    with pytest.raises(ValidationError):
        Identifier("   ")


def test_bus_address_range_is_enforced():
    assert int(BusAddress(MIN_BUS_ADDRESS)) == MIN_BUS_ADDRESS
    assert int(BusAddress(MAX_BUS_ADDRESS)) == MAX_BUS_ADDRESS
    with pytest.raises(ValidationError):
        BusAddress(0)
    with pytest.raises(ValidationError):
        BusAddress(MAX_BUS_ADDRESS + 1)


def test_mcu_unique_id_requires_bytes():
    with pytest.raises(ValidationError):
        McuUniqueId(b"")


def test_duplicate_bus_address_is_detected(group_controller, lamp_identity):
    group_controller.register_node(lamp_identity.lamp_id, BusAddress(1))
    with pytest.raises(ConfigurationError):
        group_controller.register_node(Identifier("LAMP-02"), BusAddress(1))


def test_duplicate_lamp_id_is_detected(group_controller, lamp_identity):
    group_controller.register_node(lamp_identity.lamp_id, BusAddress(1))
    with pytest.raises(ConfigurationError):
        group_controller.register_node(lamp_identity.lamp_id, BusAddress(2))


def test_group_maximum_is_configurable(group_controller):
    controller = GroupController(
        identity=group_controller.identity,
        config=GroupControllerConfig(max_nodes=2),
        clock=group_controller.clock,
        bus=InMemoryBus(),
    )
    controller.register_node(Identifier("L1"), BusAddress(1))
    controller.register_node(Identifier("L2"), BusAddress(2))
    with pytest.raises(ConfigurationError):
        controller.register_node(Identifier("L3"), BusAddress(3))


def test_node_identity_is_independent_of_restart(lamp_node):
    before = lamp_node.snapshot()
    lamp_node.restart()
    after = lamp_node.snapshot()
    assert before["lamp_id"] == after["lamp_id"]
    assert before["bus_address"] == after["bus_address"]


def test_node_rejects_a_configuration_for_another_lamp(clock, bus, authorizer,
                                                       lamp_identity):
    """A node must not adopt a configuration belonging to a different lamp."""
    other = DeviceIdentity(product_id=PRODUCT, site_id=SITE, group_id=GROUP,
                           lamp_id=Identifier("LAMP-99"))
    config = make_lamp_config(lamp_identity.lamp_id, bus_address=1)
    with pytest.raises(ConfigurationError):
        LampNode(other, BusAddress(1), config, clock=clock, bus=bus,
                 authorizer=authorizer)


def test_node_rejects_a_mismatched_bus_address(clock, bus, authorizer,
                                               lamp_identity):
    config = make_lamp_config(lamp_identity.lamp_id, bus_address=1)
    with pytest.raises(ConfigurationError):
        LampNode(lamp_identity, BusAddress(2), config, clock=clock, bus=bus,
                 authorizer=authorizer)
