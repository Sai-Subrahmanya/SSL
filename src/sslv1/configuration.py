"""Lamp node configuration model and validation.

Every operational threshold lives here. Business logic must never hardcode a
threshold (``PR-CONFIG-006``).

Units are deliberately expressed in *logical ticks* rather than seconds so
that the digital prototype stays deterministic and independent of wall-clock
time. A scenario chooses the ticks-per-second convention it wants.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Optional, Tuple

from .enums import (
    ConfiguredMode,
    LampState,
    Role,
    StorageFullBehaviour,
)
from .errors import ConfigurationError
from .identity import BusAddress, Identifier

# --------------------------------------------------------------------------
# Schedule
# --------------------------------------------------------------------------
@dataclass(frozen=True, order=True)
class TimeWindow:
    """A daily window expressed in ticks-of-day.

    ``start > end`` denotes a window that wraps past midnight.
    """

    start_tick_of_day: int
    end_tick_of_day: int

    def __post_init__(self) -> None:
        if self.start_tick_of_day < 0 or self.end_tick_of_day < 0:
            raise ConfigurationError("time window bounds must be non-negative")
        if self.start_tick_of_day == self.end_tick_of_day:
            raise ConfigurationError("time window must not be empty")

    def contains(self, tick_of_day: int) -> bool:
        if self.start_tick_of_day < self.end_tick_of_day:
            return self.start_tick_of_day <= tick_of_day < self.end_tick_of_day
        # wraps past midnight
        return tick_of_day >= self.start_tick_of_day or tick_of_day < self.end_tick_of_day

@dataclass(frozen=True)
class Schedule:
    """A daily schedule composed of one or more windows."""

    day_length_ticks: int
    windows: Tuple[TimeWindow, ...] = ()

    def __post_init__(self) -> None:
        if self.day_length_ticks <= 0:
            raise ConfigurationError("day_length_ticks must be positive")
        for window in self.windows:
            if window.start_tick_of_day >= self.day_length_ticks:
                raise ConfigurationError("window start outside the day")
            if window.end_tick_of_day > self.day_length_ticks:
                raise ConfigurationError("window end outside the day")

    @classmethod
    def always_off(cls, day_length_ticks: int) -> "Schedule":
        return cls(day_length_ticks=day_length_ticks, windows=())

    @classmethod
    def always_on(cls, day_length_ticks: int) -> "Schedule":
        return cls(
            day_length_ticks=day_length_ticks,
            windows=(TimeWindow(0, day_length_ticks),),
        )

    def is_on(self, ticks: int) -> bool:
        """Return whether the schedule requests ON at the given logical tick."""
        tick_of_day = ticks % self.day_length_ticks
        return any(window.contains(tick_of_day) for window in self.windows)

    def next_transition(self, ticks: int) -> Optional[int]:
        """Return the tick of the next ON/OFF transition, if any."""
        tick_of_day = ticks % self.day_length_ticks
        candidates = []
        for window in self.windows:
            for bound in (window.start_tick_of_day, window.end_tick_of_day):
                if self.is_on(bound - 1) == self.is_on(bound):
                    continue
                delta = (bound - tick_of_day) % self.day_length_ticks
                candidates.append(delta if delta else self.day_length_ticks)
        if not candidates:
            return None
        return ticks + min(candidates)

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class LampConfiguration:
    """Complete configuration for one lamp node.

    All values are configuration, never requirements. No numeric operational
    threshold is committed by the documentation set; scenarios and tests
    supply values explicitly.
    """

    # -- identity / addressing --------------------------------------------
    lamp_id: Identifier
    bus_address: BusAddress
    site_id: Identifier
    group_id: Identifier
    product_id: Identifier

    # -- lighting control --------------------------------------------------
    configured_mode: ConfiguredMode = ConfiguredMode.AUTO_SENSOR
    light_on_threshold: float = 50.0
    light_off_threshold: float = 150.0
    light_hysteresis: float = 0.0
    schedule: Schedule = field(default_factory=lambda: Schedule.always_off(86_400_000))
    #: State applied outside the configured window in AUTO_SCHEDULE_SENSOR.
    out_of_window_state: LampState = LampState.OFF

    # -- measurement / reporting ------------------------------------------
    measurement_interval_ticks: int = 1000
    reporting_interval_ticks: int = 5000

    # -- measurement thresholds (all configurable) ------------------------
    voltage_min: float = 180.0
    voltage_max: float = 260.0
    under_current_min: float = 0.05
    expected_current_min: float = 0.20
    over_current_max: float = 1.50
    unexpected_current_min: float = 0.05
    power_max: float = 400.0
    #: Relative tolerance for the power ~= voltage * current consistency check.
    power_consistency_tolerance: float = 0.25
    light_level_min: float = 0.0
    light_level_max: float = 100_000.0

    # -- fault handling ----------------------------------------------------
    fault_confirmation_count: int = 3
    fault_confirmation_window_ticks: int = 10_000

    # -- communication -----------------------------------------------------
    comm_retry_count: int = 2
    comm_timeout_ticks: int = 500

    # -- notification / escalation ----------------------------------------
    ack_required: bool = True
    ack_reminder_interval_ticks: int = 30_000
    escalation_timeout_ticks: int = 120_000
    escalation_destination: str = "operations"
    escalation_role: Role = Role.OPERATOR
    notification_retry_count: int = 2

    # -- restart / retention ----------------------------------------------
    restart_default_state: LampState = LampState.OFF
    automatic_deletion: bool = False
    minimum_retention_ticks: Optional[int] = None
    #: Deliberately ``None``. A-09 (storage-full behaviour) is an **open**
    #: engineering decision, so the default must not name an option. The
    #: store raises StorageFullError so the condition is never silent;
    #: that is a simulation detail, not the decided V1 behaviour.
    storage_full_behaviour: Optional[StorageFullBehaviour] = None

    # -- energy ------------------------------------------------------------
    energy_reset_role: Role = Role.ENGINEER

    # -- group -------------------------------------------------------------
    max_nodes_in_group: int = 16

    # ------------------------------------------------------------------
    def validate(self) -> Tuple[str, ...]:
        """Return a tuple of validation error messages (empty when valid)."""
        errors: list[str] = []

        from math import isfinite
        from dataclasses import fields
        enums = {"configured_mode": ConfiguredMode, "out_of_window_state": LampState,
                 "restart_default_state": LampState, "escalation_role": Role, "energy_reset_role": Role}
        for name, enum_type in enums.items():
            if not isinstance(getattr(self, name), enum_type):
                errors.append(name + " has invalid enum value")
        for name in ("lamp_id", "site_id", "group_id", "product_id"):
            if not isinstance(getattr(self, name), Identifier):
                errors.append(name + " must be an Identifier")
        if not isinstance(self.bus_address, BusAddress) or not isinstance(self.schedule, Schedule):
            errors.append("invalid address or schedule")
        for name in ("ack_required", "automatic_deletion"):
            if type(getattr(self, name)) is not bool:
                errors.append(name + " must be boolean")
        for item in fields(self):
            value = getattr(self, item.name)
            if isinstance(item.default, (int, float)) and not isinstance(item.default, bool):
                if type(value) not in (int, float) or not isfinite(value):
                    errors.append(item.name + " must be finite numeric")
                elif isinstance(item.default, int) and type(value) is not int:
                    errors.append(item.name + " must be an integer")
        if self.minimum_retention_ticks is not None and type(self.minimum_retention_ticks) is not int:
            errors.append("minimum_retention_ticks must be an integer or None")
        if not isinstance(self.escalation_destination, str):
            errors.append("escalation_destination must be a string")
        if errors:
            return tuple(errors)
        if self.energy_reset_role not in (Role.ENGINEER, Role.ADMIN, Role.OWNER):
            errors.append("energy_reset_role cannot grant below engineering privilege")
        if self.restart_default_state not in (LampState.ON, LampState.OFF):
            errors.append("restart_default_state must be ON or OFF")
        if self.storage_full_behaviour is not None:
            errors.append("storage-full product policy is undecided; use None")

        # lighting control
        if self.light_on_threshold >= self.light_off_threshold:
            errors.append(
                "light_on_threshold (%s) must be strictly less than "
                "light_off_threshold (%s)" % (self.light_on_threshold, self.light_off_threshold)
            )
        if self.light_hysteresis < 0:
            errors.append("light_hysteresis must be non-negative")
        dead_band = self.light_off_threshold - self.light_on_threshold
        if self.light_hysteresis > dead_band:
            errors.append(
                "light_hysteresis (%s) cannot exceed the dead band width (%s)"
                % (self.light_hysteresis, dead_band)
            )
        if self.out_of_window_state not in (LampState.ON, LampState.OFF):
            errors.append("out_of_window_state must be ON or OFF")

        # measurement / reporting intervals
        if self.measurement_interval_ticks <= 0:
            errors.append("measurement_interval_ticks must be positive")
        if self.reporting_interval_ticks <= 0:
            errors.append("reporting_interval_ticks must be positive")

        # measurement thresholds
        if self.voltage_min >= self.voltage_max:
            errors.append("voltage_min must be less than voltage_max")
        if self.under_current_min < 0:
            errors.append("under_current_min must be non-negative")
        if self.expected_current_min <= self.under_current_min:
            errors.append(
                "expected_current_min must be greater than under_current_min"
            )
        if self.over_current_max <= self.expected_current_min:
            errors.append("over_current_max must be greater than expected_current_min")
        if self.unexpected_current_min < 0:
            errors.append("unexpected_current_min must be non-negative")
        if self.power_max <= 0:
            errors.append("power_max must be positive")
        if not (0.0 <= self.power_consistency_tolerance <= 1.0):
            errors.append("power_consistency_tolerance must be within [0, 1]")
        if self.light_level_min >= self.light_level_max:
            errors.append("light_level_min must be less than light_level_max")

        # fault confirmation
        if self.fault_confirmation_count < 1:
            errors.append("fault_confirmation_count must be at least 1")
        if self.fault_confirmation_window_ticks <= 0:
            errors.append("fault_confirmation_window_ticks must be positive")

        # communication
        if self.comm_retry_count < 0:
            errors.append("comm_retry_count must be non-negative")
        if self.comm_timeout_ticks <= 0:
            errors.append("comm_timeout_ticks must be positive")

        # notification
        if self.ack_reminder_interval_ticks <= 0:
            errors.append("ack_reminder_interval_ticks must be positive")
        if self.escalation_timeout_ticks <= 0:
            errors.append("escalation_timeout_ticks must be positive")
        if self.escalation_timeout_ticks <= self.ack_reminder_interval_ticks:
            errors.append(
                "escalation_timeout_ticks (%s) must be greater than "
                "ack_reminder_interval_ticks (%s)"
                % (self.escalation_timeout_ticks, self.ack_reminder_interval_ticks)
            )
        if self.notification_retry_count < 0:
            errors.append("notification_retry_count must be non-negative")
        if not self.escalation_destination.strip():
            errors.append("escalation_destination must not be empty")

        # retention
        if self.minimum_retention_ticks is not None and self.minimum_retention_ticks < 0:
            errors.append("minimum_retention_ticks must be non-negative")

        # group
        if self.max_nodes_in_group < 1:
            errors.append("max_nodes_in_group must be at least 1")

        return tuple(errors)

    def validated(self) -> "LampConfiguration":
        """Return the configuration, raising if it is invalid."""
        errors = self.validate()
        if errors:
            raise ConfigurationError(
                "invalid lamp configuration for %s: %s"
                % (self.lamp_id, "; ".join(errors))
            )
        return self

    def with_mode(self, mode: ConfiguredMode) -> "LampConfiguration":
        return replace(self, configured_mode=mode)

    # -- derived helpers ---------------------------------------------------
    def expected_current_band(self) -> Tuple[float, float]:
        return (self.expected_current_min, self.over_current_max)
