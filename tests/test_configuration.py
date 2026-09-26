"""Configuration model tests (PR-CONFIG-*).

Covers: the parameter set, validation, versioning, and the rule that no
operational threshold is hardcoded.
"""

from __future__ import annotations

import pytest

from sslv1.configuration import Schedule, TimeWindow
from sslv1.errors import ConfigurationError, ValidationError

from conftest import DAY_TICKS, make_lamp_config


# --------------------------------------------------------------------------
# the parameter set
# --------------------------------------------------------------------------
def test_configuration_covers_every_documented_parameter(lamp_identity):
    config = make_lamp_config(lamp_identity.lamp_id)
    fields = {f for f in config.__dataclass_fields__}
    for expected in (
        "lamp_id", "bus_address", "site_id", "group_id", "product_id",
        "light_on_threshold", "light_off_threshold", "light_hysteresis",
        "fault_confirmation_count", "fault_confirmation_window_ticks",
        "ack_reminder_interval_ticks", "escalation_timeout_ticks",
        "notification_retry_count", "voltage_min", "voltage_max",
        "under_current_min", "expected_current_min", "over_current_max",
        "unexpected_current_min", "power_max", "light_level_min",
        "light_level_max", "comm_timeout_ticks", "comm_retry_count",
        "reporting_interval_ticks", "configured_mode", "out_of_window_state",
        "restart_default_state", "schedule",
    ):
        assert expected in fields, expected


def test_configuration_is_a_value_object(lamp_identity):
    a = make_lamp_config(lamp_identity.lamp_id)
    b = make_lamp_config(lamp_identity.lamp_id)
    assert a == b


def test_configuration_carries_the_identity(lamp_identity):
    config = make_lamp_config(lamp_identity.lamp_id)
    assert config.lamp_id == lamp_identity.lamp_id
    assert config.site_id == lamp_identity.site_id
    assert config.group_id == lamp_identity.group_id


# --------------------------------------------------------------------------
# validation
# --------------------------------------------------------------------------
def test_valid_configuration_passes(lamp_identity):
    assert make_lamp_config(lamp_identity.lamp_id).validate() == ()


def test_validation_rejects_every_invalid_threshold(lamp_identity):
    bad = make_lamp_config(
        lamp_identity.lamp_id,
        validate=False,
        light_on_threshold=200.0,
        light_off_threshold=100.0,
        voltage_min=260.0,
        voltage_max=180.0,
        fault_confirmation_count=0,
        fault_confirmation_window_ticks=0,
        ack_reminder_interval_ticks=0,
        escalation_timeout_ticks=0,
        notification_retry_count=0,
        comm_timeout_ticks=0,
        under_current_min=-1.0,
        expected_current_min=-1.0,
        over_current_max=-1.0,
        unexpected_current_min=-1.0,
        power_max=-1.0,
        light_hysteresis=1000.0,
    )
    problems = bad.validate()
    assert len(problems) >= 12
    with pytest.raises(ValidationError):
        bad.validated()


def test_on_threshold_must_be_below_off_threshold(lamp_identity):
    config = make_lamp_config(lamp_identity.lamp_id, validate=False,
                              light_on_threshold=100.0, light_off_threshold=100.0)
    assert config.validate()
    with pytest.raises(ValidationError):
        config.validated()



def test_hysteresis_wider_than_the_dead_band_is_rejected(lamp_identity):
    """The dead band is 50..150 (width 100); a 101-unit hysteresis cannot fit."""
    too_wide = make_lamp_config(lamp_identity.lamp_id, validate=False,
                                light_hysteresis=101.0)
    assert any("hysteresis" in problem for problem in too_wide.validate())
    with pytest.raises(ValidationError):
        too_wide.validated()

    fitting = make_lamp_config(lamp_identity.lamp_id, validate=False,
                               light_hysteresis=100.0)
    assert fitting.validate() == ()


def test_current_bands_must_be_ordered(lamp_identity):
    config = make_lamp_config(lamp_identity.lamp_id, validate=False,
                              under_current_min=1.0, expected_current_min=0.1,
                              over_current_max=0.2)
    assert config.validate()


def test_escalation_must_exceed_the_reminder_interval(lamp_identity):
    config = make_lamp_config(lamp_identity.lamp_id, validate=False,
                              ack_reminder_interval_ticks=100_000,
                              escalation_timeout_ticks=1000)
    assert config.validate()


def test_schedule_window_bounds_are_validated():
    with pytest.raises(ConfigurationError):
        TimeWindow(start_tick_of_day=-1, end_tick_of_day=100)
    with pytest.raises(ConfigurationError):
        TimeWindow(start_tick_of_day=100, end_tick_of_day=100)


def test_schedule_day_length_must_be_positive():
    with pytest.raises(ValidationError):
        Schedule(day_length_ticks=0, windows=(TimeWindow(0, 100),))


def test_schedule_windows_may_wrap_midnight():
    schedule = Schedule(day_length_ticks=DAY_TICKS,
                        windows=(TimeWindow(DAY_TICKS - 1000, 1000),))
    assert schedule.is_on(DAY_TICKS - 500) is True
    assert schedule.is_on(500) is True
    assert schedule.is_on(DAY_TICKS // 2) is False


def test_an_all_day_window_is_always_on():
    schedule = Schedule(day_length_ticks=DAY_TICKS,
                        windows=(TimeWindow(0, DAY_TICKS),))
    assert all(schedule.is_on(tick)
               for tick in (0, 1, DAY_TICKS // 2, DAY_TICKS - 1))



def test_reporting_interval_is_configurable(lamp_identity, clock, bus, authorizer):
    from sslv1.nodes import LampNode
    from sslv1.identity import BusAddress

    from conftest import healthy_sources

    config = make_lamp_config(lamp_identity.lamp_id, reporting_interval_ticks=5000)
    node = LampNode(lamp_identity, BusAddress(1), config, clock=clock, bus=bus,
                    authorizer=authorizer)
    node.start()

    node.step(healthy_sources(), ticks=1000)
    assert len(node.storage) == 1
    # Inside the interval: no new record.
    node.step(healthy_sources(), ticks=2000)
    assert len(node.storage) == 1
    # Past the interval: a new record.
    node.step(healthy_sources(), ticks=7000)
    assert len(node.storage) == 2


# --------------------------------------------------------------------------
# no hardcoded thresholds
# --------------------------------------------------------------------------
def test_no_operational_threshold_is_hardcoded(lamp_identity):
    """Every threshold is a dataclass field, never a module-level constant."""
    import sslv1.configuration as configuration

    module_constants = [
        name for name, value in vars(configuration).items()
        if name.isupper() and isinstance(value, (int, float))
        and not name.startswith("_")
    ]
    assert module_constants == []


def test_two_nodes_can_use_different_thresholds(lamp_identity):
    dark = make_lamp_config(lamp_identity.lamp_id, light_on_threshold=50.0,
                            light_off_threshold=150.0)
    bright = make_lamp_config(lamp_identity.lamp_id, light_on_threshold=250.0,
                              light_off_threshold=350.0)
    from sslv1.control import ControlModel
    from sslv1.enums import LampState

    assert ControlModel(config=dark).decide(light_level=200.0, ticks=0).commanded_state \
        is LampState.OFF
    assert ControlModel(config=bright).decide(light_level=200.0, ticks=0).commanded_state \
        is LampState.ON


def test_configuration_is_immutable_once_validated(lamp_identity):
    config = make_lamp_config(lamp_identity.lamp_id).validated()
    with pytest.raises(Exception):
        config.light_on_threshold = 999.0


# --------------------------------------------------------------------------
# open-decision guard: A-09 (storage-full behaviour) must stay undecided
# --------------------------------------------------------------------------
def test_storage_full_behaviour_defaults_to_undecided(lamp_config):
    """A configuration field must not imply a decision that is still open."""
    from sslv1.configuration import StorageFullBehaviour

    assert lamp_config.storage_full_behaviour is None
    # The enum still exists so the abstraction stays explicit.
    assert len(list(StorageFullBehaviour)) >= 3


def test_retention_defaults_invent_no_duration(lamp_config):
    """A-29: no numeric retention period may be invented by a default."""
    assert lamp_config.automatic_deletion is False
    assert lamp_config.minimum_retention_ticks is None
