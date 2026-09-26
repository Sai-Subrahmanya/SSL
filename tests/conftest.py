"""Shared fixtures for the Smart Street Light V1 digital prototype tests.

All fixtures are deterministic: no wall-clock time, no randomness, no I/O.
"""


import pytest

from sslv1.authorization import Actor, AuthorizationService
from sslv1.comm import InMemoryBus
from sslv1.configuration import LampConfiguration, Schedule, TimeWindow
from sslv1.enums import ConfiguredMode, Role
from sslv1.identity import BusAddress, DeviceIdentity, Identifier, McuUniqueId
from sslv1.nodes import GroupController, GroupControllerConfig, LampNode
from sslv1.time_model import LogicalClock

#: 1000 logical ticks per second.
TICKS_PER_SECOND = 1000
#: A 24-hour day in logical ticks.
DAY_TICKS = 24 * 60 * 60 * TICKS_PER_SECOND

PRODUCT = Identifier("SSL-V1")
SITE = Identifier("SITE-A")
GROUP = Identifier("GRP-01")


@pytest.fixture
def clock() -> LogicalClock:
    return LogicalClock()


@pytest.fixture
def bus() -> InMemoryBus:
    return InMemoryBus()


@pytest.fixture
def authorizer() -> AuthorizationService:
    return AuthorizationService()


@pytest.fixture
def viewer() -> Actor:
    return Actor(actor_id="viewer-01", role=Role.VIEWER)


@pytest.fixture
def operator() -> Actor:
    return Actor(actor_id="operator-01", role=Role.OPERATOR)


@pytest.fixture
def engineer() -> Actor:
    return Actor(actor_id="engineer-01", role=Role.ENGINEER)


@pytest.fixture
def admin() -> Actor:
    return Actor(actor_id="admin-01", role=Role.ADMIN)


@pytest.fixture
def owner() -> Actor:
    return Actor(actor_id="owner-01", role=Role.OWNER)


def make_lamp_config(
    lamp_id: Identifier,
    bus_address: int = 1,
    validate: bool = True,
    **overrides,
) -> LampConfiguration:
    """Build a lamp configuration with test-friendly defaults.

    ``validate=False`` skips validation so that validation behaviour itself
    can be tested.
    """
    params = dict(
        lamp_id=lamp_id,
        bus_address=BusAddress(bus_address),
        site_id=SITE,
        group_id=GROUP,
        product_id=PRODUCT,
        configured_mode=ConfiguredMode.AUTO_SENSOR,
        light_on_threshold=50.0,
        light_off_threshold=150.0,
        measurement_interval_ticks=TICKS_PER_SECOND,
        reporting_interval_ticks=TICKS_PER_SECOND,
        fault_confirmation_count=3,
        fault_confirmation_window_ticks=10 * TICKS_PER_SECOND,
        comm_retry_count=2,
        comm_timeout_ticks=500,
        ack_reminder_interval_ticks=30 * TICKS_PER_SECOND,
        escalation_timeout_ticks=120 * TICKS_PER_SECOND,
        notification_retry_count=2,
        voltage_min=180.0,
        voltage_max=260.0,
        under_current_min=0.05,
        expected_current_min=0.20,
        over_current_max=1.50,
        unexpected_current_min=0.05,
        power_max=400.0,
        schedule=Schedule(day_length_ticks=DAY_TICKS, windows=(TimeWindow(0, DAY_TICKS - 1),)),
    )
    params.update(overrides)
    config = LampConfiguration(**params)
    return config.validated() if validate else config


@pytest.fixture
def lamp_identity() -> DeviceIdentity:
    return DeviceIdentity(
        product_id=PRODUCT,
        site_id=SITE,
        group_id=GROUP,
        lamp_id=Identifier("LAMP-01"),
        mcu_unique_id=McuUniqueId(bytes.fromhex("0a0b0c0d")),
    )


@pytest.fixture
def lamp_config(lamp_identity: DeviceIdentity) -> LampConfiguration:
    return make_lamp_config(lamp_identity.lamp_id)


@pytest.fixture
def lamp_node(clock, bus, authorizer, lamp_identity, lamp_config) -> LampNode:
    node = LampNode(
        identity=lamp_identity,
        bus_address=lamp_config.bus_address,
        config=lamp_config,
        clock=clock,
        bus=bus,
        authorizer=authorizer,
    )
    node.start()
    return node


@pytest.fixture
def group_identity() -> DeviceIdentity:
    return DeviceIdentity(product_id=PRODUCT, site_id=SITE, group_id=GROUP)


@pytest.fixture
def group_controller(clock, bus, authorizer, group_identity) -> GroupController:
    return GroupController(
        identity=group_identity,
        config=GroupControllerConfig(max_nodes=16),
        clock=clock,
        bus=bus,
        authorizer=authorizer,
    )


def healthy_sources(**overrides):
    """A reading set that represents a normally operating ON lamp."""
    from sslv1.nodes import LampNodeSources
    from sslv1.enums import LampState, SensorStatus

    params = dict(
        voltage=230.0,
        current=0.45,
        power=103.5,
        light_level=10.0,
        switching_feedback=LampState.ON,
        sensor_status=SensorStatus.VALID,
    )
    params.update(overrides)
    return LampNodeSources(**params)
