"""Control model tests (PR-LIGHT-*, PR-CONTROL-*).

Covers: automatic sensor ON/OFF, hysteresis, invalid hysteresis configuration,
fixed schedule, schedule+sensor mode, FORCE_ON/FORCE_OFF, RETURN_TO_AUTO,
override priority and safety priority.
"""


import pytest

from sslv1.configuration import Schedule, TimeWindow
from sslv1.control import ControlLayer
from sslv1.enums import ConfiguredMode, LampState, OperatingMode, OverrideState
from sslv1.errors import ValidationError
from sslv1.nodes import LampNode

from conftest import DAY_TICKS, TICKS_PER_SECOND, healthy_sources, make_lamp_config


# --------------------------------------------------------------------------
# 1. automatic sensor ON
# --------------------------------------------------------------------------
def test_automatic_sensor_switches_lamp_on_below_threshold(lamp_node):
    decision = lamp_node.step(healthy_sources(light_level=10.0), ticks=1000)
    assert decision.commanded_state is LampState.ON
    assert decision.effective_mode is OperatingMode.AUTO_SENSOR
    assert decision.decided_by == ControlLayer.SENSOR_SCHEDULE_LOGIC
    assert lamp_node.control.lamp_is_on is True


# --------------------------------------------------------------------------
# 2. automatic sensor OFF
# --------------------------------------------------------------------------
def test_automatic_sensor_switches_lamp_off_above_threshold(lamp_node):
    lamp_node.step(healthy_sources(light_level=10.0), ticks=1000)
    decision = lamp_node.step(healthy_sources(light_level=400.0), ticks=2000)
    assert decision.commanded_state is LampState.OFF
    assert lamp_node.control.lamp_is_on is False


# --------------------------------------------------------------------------
# 3. hysteresis / dead band
# --------------------------------------------------------------------------
def test_hysteresis_retains_state_inside_dead_band(lamp_node):
    lamp_node.step(healthy_sources(light_level=10.0), ticks=1000)
    assert lamp_node.control.lamp_is_on is True

    # Between the ON (50) and OFF (150) thresholds: retain the ON state.
    decision = lamp_node.step(healthy_sources(light_level=100.0), ticks=2000)
    assert decision.commanded_state is LampState.ON
    assert "dead band" in decision.reason

    # Now start from OFF and confirm the dead band retains OFF.
    lamp_node.step(healthy_sources(light_level=400.0), ticks=3000)
    decision = lamp_node.step(healthy_sources(light_level=100.0), ticks=4000)
    assert decision.commanded_state is LampState.OFF


def test_hysteresis_prevents_oscillation_around_threshold(lamp_node):
    """A light level hovering at the threshold must not toggle the lamp."""
    states = []
    for index, level in enumerate([49.0, 51.0, 49.0, 51.0, 49.0, 51.0]):
        decision = lamp_node.step(
            healthy_sources(light_level=level), ticks=1000 * (index + 1)
        )
        states.append(decision.commanded_state)
    # 49 -> ON, then 51 is inside the dead band so the lamp stays ON.
    assert states == [LampState.ON] * 6


# --------------------------------------------------------------------------
# 4. invalid hysteresis configuration
# --------------------------------------------------------------------------
def test_invalid_threshold_configuration_is_rejected(lamp_identity):
    with pytest.raises(ValidationError):
        make_lamp_config(
            lamp_identity.lamp_id,
            light_on_threshold=150.0,
            light_off_threshold=50.0,
        )


def test_equal_thresholds_are_rejected(lamp_identity):
    with pytest.raises(ValidationError):
        make_lamp_config(
            lamp_identity.lamp_id,
            light_on_threshold=100.0,
            light_off_threshold=100.0,
        )


def test_negative_hysteresis_is_rejected(lamp_identity):
    with pytest.raises(ValidationError):
        make_lamp_config(lamp_identity.lamp_id, light_hysteresis=-1.0)


def test_validation_reports_every_problem(lamp_identity):
    config = make_lamp_config(
        lamp_identity.lamp_id,
        validate=False,
        light_on_threshold=150.0,
        light_off_threshold=50.0,
        fault_confirmation_count=0,
        comm_timeout_ticks=0,
    )
    errors = config.validate()
    assert len(errors) >= 3
    with pytest.raises(ValidationError):
        config.validated()


# --------------------------------------------------------------------------
# 5. fixed schedule
# --------------------------------------------------------------------------
def test_fixed_schedule_ignores_light_level(clock, bus, authorizer, lamp_identity):
    schedule = Schedule(
        day_length_ticks=DAY_TICKS,
        windows=(TimeWindow(8 * 3600 * TICKS_PER_SECOND, 18 * 3600 * TICKS_PER_SECOND),),
    )
    config = make_lamp_config(
        lamp_identity.lamp_id,
        configured_mode=ConfiguredMode.FIXED_SCHEDULE,
        schedule=schedule,
    )
    node = LampNode(lamp_identity, config.bus_address, config, clock=clock, bus=bus,
                    authorizer=authorizer)
    node.start()

    inside = 10 * 3600 * TICKS_PER_SECOND
    outside = 23 * 3600 * TICKS_PER_SECOND

    on_decision = node.step(healthy_sources(light_level=900.0), ticks=inside)
    assert on_decision.commanded_state is LampState.ON
    assert on_decision.effective_mode is OperatingMode.FIXED_SCHEDULE

    off_decision = node.step(healthy_sources(light_level=10.0), ticks=outside)
    assert off_decision.commanded_state is LampState.OFF


def test_fixed_schedule_handles_window_wrapping_midnight(clock, bus, authorizer,
                                                         lamp_identity):
    schedule = Schedule(
        day_length_ticks=DAY_TICKS,
        windows=(TimeWindow(22 * 3600 * TICKS_PER_SECOND, 2 * 3600 * TICKS_PER_SECOND),),
    )
    config = make_lamp_config(
        lamp_identity.lamp_id,
        configured_mode=ConfiguredMode.FIXED_SCHEDULE,
        schedule=schedule,
    )
    assert config.schedule.is_on(23 * 3600 * TICKS_PER_SECOND) is True
    assert config.schedule.is_on(1 * 3600 * TICKS_PER_SECOND) is True
    assert config.schedule.is_on(12 * 3600 * TICKS_PER_SECOND) is False


# --------------------------------------------------------------------------
# 6. schedule + sensor mode
# --------------------------------------------------------------------------
def test_schedule_sensor_mode_uses_sensor_inside_window(clock, bus, authorizer,
                                                        lamp_identity):
    schedule = Schedule(
        day_length_ticks=DAY_TICKS,
        windows=(TimeWindow(0, DAY_TICKS - 1),),
    )
    config = make_lamp_config(
        lamp_identity.lamp_id,
        configured_mode=ConfiguredMode.AUTO_SCHEDULE_SENSOR,
        schedule=schedule,
    )
    node = LampNode(lamp_identity, config.bus_address, config, clock=clock, bus=bus,
                    authorizer=authorizer)
    node.start()
    decision = node.step(healthy_sources(light_level=10.0), ticks=1000)
    assert decision.effective_mode is OperatingMode.AUTO_SCHEDULE_SENSOR
    assert decision.commanded_state is LampState.ON


def test_schedule_sensor_mode_applies_out_of_window_state(clock, bus, authorizer,
                                                          lamp_identity):
    schedule = Schedule(
        day_length_ticks=DAY_TICKS,
        windows=(TimeWindow(8 * 3600 * TICKS_PER_SECOND, 18 * 3600 * TICKS_PER_SECOND),),
    )
    config = make_lamp_config(
        lamp_identity.lamp_id,
        configured_mode=ConfiguredMode.AUTO_SCHEDULE_SENSOR,
        schedule=schedule,
        out_of_window_state=LampState.OFF,
    )
    node = LampNode(lamp_identity, config.bus_address, config, clock=clock, bus=bus,
                    authorizer=authorizer)
    node.start()
    decision = node.step(healthy_sources(light_level=1.0), ticks=23 * 3600 * TICKS_PER_SECOND)
    assert decision.commanded_state is LampState.OFF
    assert decision.decided_by == ControlLayer.NORMAL_AUTOMATIC
    assert "outside configured window" in decision.reason


# --------------------------------------------------------------------------
# 7./8./9. FORCE_ON, FORCE_OFF, RETURN_TO_AUTO
# --------------------------------------------------------------------------
def test_force_on_overrides_automatic_logic(lamp_node, operator):
    lamp_node.step(healthy_sources(light_level=900.0), ticks=1000)
    assert lamp_node.control.lamp_is_on is False

    record = lamp_node.force_on(operator, ticks=2000)
    assert record.succeeded is True
    assert lamp_node.control.effective_mode is OperatingMode.FORCE_ON

    decision = lamp_node.step(healthy_sources(light_level=900.0), ticks=3000)
    assert decision.commanded_state is LampState.ON
    assert decision.decided_by == ControlLayer.AUTHORIZED_OVERRIDE


def test_force_off_overrides_automatic_logic(lamp_node, operator):
    lamp_node.step(healthy_sources(light_level=10.0), ticks=1000)
    assert lamp_node.control.lamp_is_on is True

    lamp_node.force_off(operator, ticks=2000)
    decision = lamp_node.step(healthy_sources(light_level=10.0), ticks=3000)
    assert decision.commanded_state is LampState.OFF
    assert lamp_node.control.effective_mode is OperatingMode.FORCE_OFF


def test_return_to_auto_clears_override(lamp_node, operator):
    lamp_node.force_on(operator, ticks=1000)
    assert lamp_node.control.active_override is OverrideState.FORCE_ON

    record = lamp_node.return_to_auto(operator, ticks=2000)
    assert record.succeeded is True
    assert lamp_node.control.active_override is OverrideState.NONE
    assert lamp_node.control.effective_mode is OperatingMode.AUTO_SENSOR

    # Automatic logic is back in force.
    decision = lamp_node.step(healthy_sources(light_level=900.0), ticks=3000)
    assert decision.commanded_state is LampState.OFF


def test_return_to_auto_is_not_a_persistent_mode(lamp_node, operator):
    """RETURN_TO_AUTO must never become a mode."""
    lamp_node.force_on(operator, ticks=1000)
    lamp_node.return_to_auto(operator, ticks=2000)
    assert lamp_node.control.configured_mode is ConfiguredMode.AUTO_SENSOR
    assert lamp_node.control.effective_mode is OperatingMode.AUTO_SENSOR
    assert OverrideState.NONE is lamp_node.control.active_override


def test_override_survives_repeated_control_cycles(lamp_node, operator):
    lamp_node.force_on(operator, ticks=1000)
    for index in range(5):
        decision = lamp_node.step(healthy_sources(light_level=900.0), ticks=2000 + index)
        assert decision.commanded_state is LampState.ON


def test_control_model_separates_configured_override_and_effective(lamp_node, operator):
    assert lamp_node.control.configured_mode is ConfiguredMode.AUTO_SENSOR
    assert lamp_node.control.active_override is OverrideState.NONE
    assert lamp_node.control.effective_mode is OperatingMode.AUTO_SENSOR

    lamp_node.force_on(operator, ticks=1000)
    assert lamp_node.control.configured_mode is ConfiguredMode.AUTO_SENSOR
    assert lamp_node.control.active_override is OverrideState.FORCE_ON
    assert lamp_node.control.effective_mode is OperatingMode.FORCE_ON

    lamp_node.return_to_auto(operator, ticks=2000)
    assert lamp_node.control.active_override is OverrideState.NONE
    assert lamp_node.control.effective_mode is OperatingMode.AUTO_SENSOR


def test_set_configured_mode_changes_only_the_configured_mode(lamp_node, engineer):
    record = lamp_node.set_configured_mode(ConfiguredMode.FIXED_SCHEDULE, engineer, ticks=1000)
    assert record.succeeded is True
    assert lamp_node.control.configured_mode is ConfiguredMode.FIXED_SCHEDULE
    assert lamp_node.control.active_override is OverrideState.NONE


# --------------------------------------------------------------------------
# 10. override priority
# --------------------------------------------------------------------------
def test_override_beats_automatic_mode(lamp_node, operator):
    lamp_node.set_configured_mode(ConfiguredMode.FIXED_SCHEDULE, operator, ticks=1000)
    lamp_node.force_on(operator, ticks=2000)
    decision = lamp_node.step(healthy_sources(light_level=900.0), ticks=3000)
    assert decision.decided_by == ControlLayer.AUTHORIZED_OVERRIDE
    assert decision.commanded_state is LampState.ON


# --------------------------------------------------------------------------
# 11. safety priority
# --------------------------------------------------------------------------
def test_safety_protection_beats_override(lamp_node, operator):
    lamp_node.force_on(operator, ticks=1000)
    lamp_node.set_protection(True, LampState.OFF, reason="test protection condition")
    decision = lamp_node.step(healthy_sources(light_level=10.0), ticks=2000)
    assert decision.decided_by == ControlLayer.SAFETY_PROTECTION
    assert decision.commanded_state is LampState.OFF


def test_no_protection_condition_is_defined_in_v1(lamp_node, operator):
    """V1 defines no protection condition, so none is active by default."""
    assert lamp_node.protection.active is False
    lamp_node.force_on(operator, ticks=1000)
    decision = lamp_node.step(healthy_sources(light_level=10.0), ticks=2000)
    assert decision.decided_by != ControlLayer.SAFETY_PROTECTION


# --------------------------------------------------------------------------
# no automatic shutdown for non-protective conditions
# --------------------------------------------------------------------------
def test_fault_does_not_switch_lamp_off(lamp_node, engineer):
    """A detected fault must not shut the lamp down (PR-CONTROL-006)."""
    for index in range(5):
        lamp_node.step(
            healthy_sources(current=0.0, power=0.0, light_level=10.0,
                            switching_feedback=LampState.ON),
            ticks=1000 * (index + 1),
        )
    assert lamp_node.control.lamp_is_on is True
    assert lamp_node.faults.active_faults


def test_unacknowledged_alert_does_not_switch_lamp_off(lamp_node, operator):
    for index in range(5):
        lamp_node.step(
            healthy_sources(current=0.0, power=0.0, light_level=10.0,
                            switching_feedback=LampState.ON),
            ticks=1000 * (index + 1),
        )
    fault = lamp_node.faults.active_faults[0]
    assert fault.state.value == "CONFIRMED"
    # Deliberately do not acknowledge; the lamp must stay ON.
    decision = lamp_node.step(healthy_sources(light_level=10.0), ticks=10_000)
    assert decision.commanded_state is LampState.ON


def test_invalid_sensor_retains_previous_state(lamp_node):
    from sslv1.enums import SensorStatus

    lamp_node.step(healthy_sources(light_level=10.0), ticks=1000)
    decision = lamp_node.step(
        healthy_sources(light_level=None, sensor_status=SensorStatus.INVALID), ticks=2000
    )
    assert decision.commanded_state is LampState.ON
