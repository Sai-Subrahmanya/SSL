"""Deterministic lighting control model.

Three values are modelled separately (``PR-CONTROL-007``, ``D-031``):

* ``configured_mode``  - the persistent automatic mode,
* ``active_override``  - the active forced override, or ``NONE``,
* ``effective_mode``   - the mode actually in force right now.

``RETURN_TO_AUTO`` is an operator *command* that clears the override. It is
never modelled as a persistent mode (``PR-LIGHT-005``).

Priority resolution (``PR-CONTROL-001``):

1. safety / hardware protection,
2. authorized manual override,
3. configured automatic mode,
4. sensor / schedule logic.

No automatic protective shutdown behaviour is implemented, because V1 defines
no protection condition (``PR-CONTROL-006``). The hook exists and is inactive
by default.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .configuration import LampConfiguration
from .enums import (
    ConfiguredMode,
    LampState,
    OperatingMode,
    OverrideState,
)
from .errors import ValidationError


class ControlLayer:
    """Identifies which priority layer produced a control decision."""

    SAFETY_PROTECTION = "SAFETY_PROTECTION"
    AUTHORIZED_OVERRIDE = "AUTHORIZED_OVERRIDE"
    NORMAL_AUTOMATIC = "NORMAL_AUTOMATIC"
    SENSOR_SCHEDULE_LOGIC = "SENSOR_SCHEDULE_LOGIC"


@dataclass(frozen=True)
class ControlDecision:
    """The outcome of one control evaluation."""

    commanded_state: LampState
    effective_mode: OperatingMode
    decided_by: str
    reason: str
    ticks: int


@dataclass
class ProtectionState:
    """Hook for genuine protection conditions.

    V1 defines **no** protection condition, so ``active`` is ``False`` by
    default and no automatic shutdown behaviour exists
    (``PR-CONTROL-006``).
    """

    active: bool = False
    forced_state: LampState = LampState.OFF
    reason: str = ""


@dataclass
class ControlModel:
    """Deterministic control state for a single lamp."""

    config: LampConfiguration
    protection: ProtectionState = field(default_factory=ProtectionState)
    _configured_mode: Optional[ConfiguredMode] = None
    _active_override: OverrideState = OverrideState.NONE
    _lamp_is_on: bool = False

    def __post_init__(self) -> None:
        if self._configured_mode is None:
            self._configured_mode = self.config.configured_mode

    # ------------------------------------------------------------------
    # State accessors
    # ------------------------------------------------------------------
    @property
    def configured_mode(self) -> ConfiguredMode:
        return self._configured_mode

    @property
    def active_override(self) -> OverrideState:
        return self._active_override

    @property
    def effective_mode(self) -> OperatingMode:
        """The mode actually in force, derived from configuration + override."""
        if self._active_override is OverrideState.FORCE_ON:
            return OperatingMode.FORCE_ON
        if self._active_override is OverrideState.FORCE_OFF:
            return OperatingMode.FORCE_OFF
        return _AUTOMATIC_TO_OPERATING[self._configured_mode]

    @property
    def lamp_is_on(self) -> bool:
        return self._lamp_is_on

    # ------------------------------------------------------------------
    # Mutators
    # ------------------------------------------------------------------
    def set_configured_mode(self, mode: ConfiguredMode) -> None:
        """Set the persistent automatic operating mode."""
        if not isinstance(mode, ConfiguredMode):
            raise ValidationError("configured mode must be a ConfiguredMode")
        self._configured_mode = mode

    def apply_override(self, override: OverrideState) -> None:
        """Apply (or clear) a forced override.

        An override takes effect immediately: the commanded state follows the
        override at once rather than at the next control cycle. This is what
        makes actual-state verification meaningful for override commands.
        """
        if override not in (
            OverrideState.NONE,
            OverrideState.FORCE_ON,
            OverrideState.FORCE_OFF,
        ):
            raise ValidationError("invalid override state: %r" % (override,))
        self._active_override = override
        if override is OverrideState.FORCE_ON:
            self._lamp_is_on = True
        elif override is OverrideState.FORCE_OFF:
            self._lamp_is_on = False

    def clear_override(self) -> None:
        """``RETURN_TO_AUTO``: clear the override, returning to automatic control."""
        self._active_override = OverrideState.NONE

    def set_protection(self, active: bool, forced_state: LampState = LampState.OFF,
                       reason: str = "") -> None:
        self.protection.active = active
        self.protection.forced_state = forced_state
        self.protection.reason = reason

    # ------------------------------------------------------------------
    # Decision
    # ------------------------------------------------------------------
    def decide(self, light_level: Optional[float], ticks: int) -> ControlDecision:
        """Resolve the commanded lamp state for the current tick."""
        # 1. safety / hardware protection
        if self.protection.active:
            self._lamp_is_on = self.protection.forced_state is LampState.ON
            return ControlDecision(
                commanded_state=self.protection.forced_state,
                effective_mode=self.effective_mode,
                decided_by=ControlLayer.SAFETY_PROTECTION,
                reason=self.protection.reason or "protection condition active",
                ticks=ticks,
            )

        # 2. authorized manual override
        if self._active_override is OverrideState.FORCE_ON:
            self._lamp_is_on = True
            return ControlDecision(
                commanded_state=LampState.ON,
                effective_mode=OperatingMode.FORCE_ON,
                decided_by=ControlLayer.AUTHORIZED_OVERRIDE,
                reason="operator override FORCE_ON",
                ticks=ticks,
            )
        if self._active_override is OverrideState.FORCE_OFF:
            self._lamp_is_on = False
            return ControlDecision(
                commanded_state=LampState.OFF,
                effective_mode=OperatingMode.FORCE_OFF,
                decided_by=ControlLayer.AUTHORIZED_OVERRIDE,
                reason="operator override FORCE_OFF",
                ticks=ticks,
            )

        # 3./4. configured automatic mode, delegating to sensor/schedule logic
        mode = self._configured_mode
        if mode is ConfiguredMode.FIXED_SCHEDULE:
            requested = self.config.schedule.is_on(ticks)
            self._lamp_is_on = requested
            return ControlDecision(
                commanded_state=LampState.ON if requested else LampState.OFF,
                effective_mode=OperatingMode.FIXED_SCHEDULE,
                decided_by=ControlLayer.NORMAL_AUTOMATIC,
                reason="fixed schedule %s" % ("ON" if requested else "OFF"),
                ticks=ticks,
            )

        if mode is ConfiguredMode.AUTO_SCHEDULE_SENSOR:
            if not self.config.schedule.is_on(ticks):
                self._lamp_is_on = self.config.out_of_window_state is LampState.ON
                return ControlDecision(
                    commanded_state=self.config.out_of_window_state,
                    effective_mode=OperatingMode.AUTO_SCHEDULE_SENSOR,
                    decided_by=ControlLayer.NORMAL_AUTOMATIC,
                    reason="outside configured window; out_of_window_state=%s"
                    % self.config.out_of_window_state.value,
                    ticks=ticks,
                )
            decision = self._sensor_decision(light_level, ticks)
            return ControlDecision(
                commanded_state=decision,
                effective_mode=OperatingMode.AUTO_SCHEDULE_SENSOR,
                decided_by=ControlLayer.SENSOR_SCHEDULE_LOGIC,
                reason="inside window; " + self._sensor_reason(light_level),
                ticks=ticks,
            )

        # AUTO_SENSOR
        decision = self._sensor_decision(light_level, ticks)
        return ControlDecision(
            commanded_state=decision,
            effective_mode=OperatingMode.AUTO_SENSOR,
            decided_by=ControlLayer.SENSOR_SCHEDULE_LOGIC,
            reason=self._sensor_reason(light_level),
            ticks=ticks,
        )

    # ------------------------------------------------------------------
    # Sensor logic with hysteresis
    # ------------------------------------------------------------------
    def _sensor_decision(self, light_level: Optional[float], ticks: int) -> LampState:
        """Light-level decision with hysteresis (dead band).

        * ``light <= on_threshold``  -> request ON
        * ``light >= off_threshold`` -> request OFF
        * in between                 -> retain the previous effective state
        """
        if light_level is None:
            # No valid light reading: retain the previous state rather than
            # guessing. Sensor validity is handled by diagnostics.
            return LampState.ON if self._lamp_is_on else LampState.OFF
        if light_level <= self.config.light_on_threshold:
            self._lamp_is_on = True
            return LampState.ON
        if light_level >= self.config.light_off_threshold:
            self._lamp_is_on = False
            return LampState.OFF
        return LampState.ON if self._lamp_is_on else LampState.OFF

    def _sensor_reason(self, light_level: Optional[float]) -> str:
        if light_level is None:
            return "no valid light level; retaining previous state"
        if light_level <= self.config.light_on_threshold:
            return "light level %s <= on threshold %s" % (
                light_level,
                self.config.light_on_threshold,
            )
        if light_level >= self.config.light_off_threshold:
            return "light level %s >= off threshold %s" % (
                light_level,
                self.config.light_off_threshold,
            )
        return "light level %s inside dead band [%s, %s); retaining state" % (
            light_level,
            self.config.light_on_threshold,
            self.config.light_off_threshold,
        )


_AUTOMATIC_TO_OPERATING = {
    ConfiguredMode.AUTO_SENSOR: OperatingMode.AUTO_SENSOR,
    ConfiguredMode.AUTO_SCHEDULE_SENSOR: OperatingMode.AUTO_SCHEDULE_SENSOR,
    ConfiguredMode.FIXED_SCHEDULE: OperatingMode.FIXED_SCHEDULE,
}
