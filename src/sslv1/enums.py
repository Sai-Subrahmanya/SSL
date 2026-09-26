"""Controlled vocabularies (enums) for the Smart Street Light V1 domain model.

Every enum here is a *domain* concept. No enum encodes a hardware-specific
detail: the domain layer must remain usable behind a later hardware
abstraction layer without modification.

See ``docs/03_data_model.md`` for the authoritative field/value documentation.
"""

from __future__ import annotations

from enum import Enum


class StrEnum(str, Enum):
    """String enum that also compares equal to its raw value.

    ``str`` mixin behaviour changed across Python versions; this base class
    keeps ``json``-friendly values and stable ``repr`` output everywhere.
    """

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value


# --------------------------------------------------------------------------
# Operating modes
# --------------------------------------------------------------------------
class ConfiguredMode(StrEnum):
    """Persistent *automatic* operating modes.

    ``FORCE_ON`` / ``FORCE_OFF`` are deliberately excluded: they are
    overrides, not configured automatic modes (see ``D-031``).
    """

    AUTO_SENSOR = "AUTO_SENSOR"
    AUTO_SCHEDULE_SENSOR = "AUTO_SCHEDULE_SENSOR"
    FIXED_SCHEDULE = "FIXED_SCHEDULE"


class OverrideState(StrEnum):
    """Active operator override. ``NONE`` means automatic control is in force."""

    NONE = "NONE"
    FORCE_ON = "FORCE_ON"
    FORCE_OFF = "FORCE_OFF"


class OperatingMode(StrEnum):
    """The operating mode actually in force (the *effective* mode).

    Derived from ``ConfiguredMode`` and ``OverrideState``. ``AUTO_SENSOR``,
    ``AUTO_SCHEDULE_SENSOR`` and ``FIXED_SCHEDULE`` are the persistent
    automatic modes; ``FORCE_ON`` and ``FORCE_OFF`` appear here only while an
    override is active.

    Note: ``RETURN_TO_AUTO`` is *not* a mode. It is an operator command that
    clears the active override (``PR-LIGHT-005``, ``D-031``).
    """

    AUTO_SENSOR = "AUTO_SENSOR"
    AUTO_SCHEDULE_SENSOR = "AUTO_SCHEDULE_SENSOR"
    FIXED_SCHEDULE = "FIXED_SCHEDULE"
    FORCE_ON = "FORCE_ON"
    FORCE_OFF = "FORCE_OFF"


# --------------------------------------------------------------------------
# Lamp / switching state
# --------------------------------------------------------------------------
class LampState(StrEnum):
    ON = "ON"
    OFF = "OFF"
    UNKNOWN = "UNKNOWN"


class SensorStatus(StrEnum):
    VALID = "VALID"
    DEGRADED = "DEGRADED"
    INVALID = "INVALID"


class CommunicationStatus(StrEnum):
    COMM_HEALTHY = "COMM_HEALTHY"
    RETRY = "RETRY"
    DEGRADED = "DEGRADED"
    COMM_FAULT = "COMM_FAULT"
    RECOVERY = "RECOVERY"


class ControllerStatus(StrEnum):
    NORMAL = "NORMAL"
    DEGRADED = "DEGRADED"
    FAULT = "FAULT"
    RESTARTED = "RESTARTED"


# --------------------------------------------------------------------------
# Fault model
# --------------------------------------------------------------------------
class FaultType(StrEnum):
    """Fault *categories* (reporting buckets), not root causes."""

    LAMP_LOAD = "LAMP_LOAD"
    UNDER_CURRENT = "UNDER_CURRENT"
    OVER_CURRENT = "OVER_CURRENT"
    SUPPLY_VOLTAGE = "SUPPLY_VOLTAGE"
    LIGHT_SENSOR = "LIGHT_SENSOR"
    COMMUNICATION = "COMMUNICATION"
    CONTROLLER = "CONTROLLER"
    ENVIRONMENTAL = "ENVIRONMENTAL"
    TAMPER = "TAMPER"
    UNKNOWN = "UNKNOWN"
    INSPECTION_REQUIRED = "INSPECTION_REQUIRED"


class FaultState(StrEnum):
    """Fault lifecycle states.

    ``NOTIFIED`` is intentionally absent: notification progress is tracked in
    :class:`NotificationState` (``PR-FAULT-013``, ``D-033``).
    """

    NORMAL = "NORMAL"
    SUSPECTED = "SUSPECTED"
    CONFIRMED = "CONFIRMED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    UNDER_REPAIR = "UNDER_REPAIR"
    VERIFYING = "VERIFYING"
    CLOSED = "CLOSED"


class DiagnosticClassification(StrEnum):
    """Evidence-based interpretation of measurements.

    A classification is never a confirmed physical root cause
    (``PR-FAULT-014``, ``D-034``).
    """

    NORMAL = "NORMAL"
    POSSIBLE_OPEN_LOAD = "POSSIBLE_OPEN_LOAD"
    POSSIBLE_UNDER_CURRENT = "POSSIBLE_UNDER_CURRENT"
    POSSIBLE_OVER_CURRENT = "POSSIBLE_OVER_CURRENT"
    UNEXPECTED_CURRENT = "UNEXPECTED_CURRENT"
    SWITCHING_PATH_INCONSISTENCY = "SWITCHING_PATH_INCONSISTENCY"
    SUPPLY_ABNORMALITY = "SUPPLY_ABNORMALITY"
    SENSOR_ABNORMALITY = "SENSOR_ABNORMALITY"
    MEASUREMENT_ABNORMALITY = "MEASUREMENT_ABNORMALITY"
    COMMUNICATION_ABNORMALITY = "COMMUNICATION_ABNORMALITY"
    CONTROLLER_ABNORMALITY = "CONTROLLER_ABNORMALITY"
    ENVIRONMENTAL_OR_EXTERNAL = "ENVIRONMENTAL_OR_EXTERNAL"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class FaultSeverity(StrEnum):
    INFO = "INFO"
    MINOR = "MINOR"
    MAJOR = "MAJOR"
    CRITICAL = "CRITICAL"


# --------------------------------------------------------------------------
# Notification (independent of the fault lifecycle)
# --------------------------------------------------------------------------
class NotificationState(StrEnum):
    NOT_REQUIRED = "NOT_REQUIRED"
    PENDING = "PENDING"
    SENT = "SENT"
    ACK_PENDING = "ACK_PENDING"
    REMINDER_DUE = "REMINDER_DUE"
    ESCALATED = "ESCALATED"
    DELIVERY_FAILED = "DELIVERY_FAILED"


class RepairStatus(StrEnum):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    REPAIRED = "REPAIRED"
    NOT_REPAIRED = "NOT_REPAIRED"


class VerificationStatus(StrEnum):
    NOT_VERIFIED = "NOT_VERIFIED"
    VERIFYING = "VERIFYING"
    VERIFIED = "VERIFIED"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"


# --------------------------------------------------------------------------
# Command model
# --------------------------------------------------------------------------
class CommandType(StrEnum):
    SET_MODE = "SET_MODE"
    FORCE_ON = "FORCE_ON"
    FORCE_OFF = "FORCE_OFF"
    RETURN_TO_AUTO = "RETURN_TO_AUTO"
    READ_CONFIG = "READ_CONFIG"
    WRITE_CONFIG = "WRITE_CONFIG"
    TIME_SYNC = "TIME_SYNC"
    IDENTIFY = "IDENTIFY"
    ACKNOWLEDGE_FAULT = "ACKNOWLEDGE_FAULT"
    START_REPAIR = "START_REPAIR"
    VERIFY_REPAIR = "VERIFY_REPAIR"
    CLOSE_FAULT = "CLOSE_FAULT"
    HEARTBEAT = "HEARTBEAT"


class ControlSubtype(StrEnum):
    """Actions carried inside ``CONTROL_COMMAND`` (``PR-COMM-010``, ``D-038``)."""

    LAMP_ON = "LAMP_ON"
    LAMP_OFF = "LAMP_OFF"
    RESET_ENERGY = "RESET_ENERGY"
    SET_MODE = "SET_MODE"
    RETURN_TO_AUTO = "RETURN_TO_AUTO"


class CommandState(StrEnum):
    """Command lifecycle. Receipt alone is never success (``PR-CONTROL-002``)."""

    CREATED = "CREATED"
    RECEIVED = "RECEIVED"
    EXECUTED = "EXECUTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    ACTUAL_STATE_VERIFIED = "ACTUAL_STATE_VERIFIED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class AuthorizationStatus(StrEnum):
    AUTHORIZED = "AUTHORIZED"
    UNAUTHORIZED = "UNAUTHORIZED"
    UNKNOWN = "UNKNOWN"


# --------------------------------------------------------------------------
# Roles
# --------------------------------------------------------------------------
class Role(StrEnum):
    VIEWER = "VIEWER"
    OPERATOR = "OPERATOR"
    ENGINEER = "ENGINEER"
    ADMIN = "ADMIN"
    OWNER = "OWNER"


class Action(StrEnum):
    """Authorizable actions used by the preliminary role model."""

    VIEW_STATUS = "VIEW_STATUS"
    CONTROL_LAMP = "CONTROL_LAMP"
    ACKNOWLEDGE_FAULT = "ACKNOWLEDGE_FAULT"
    CONFIGURE = "CONFIGURE"
    RESET_ENERGY = "RESET_ENERGY"
    START_REPAIR = "START_REPAIR"
    VERIFY_REPAIR = "VERIFY_REPAIR"
    CLOSE_FAULT = "CLOSE_FAULT"
    ADMINISTER = "ADMINISTER"
    DELETE_RECORD = "DELETE_RECORD"


# --------------------------------------------------------------------------
# Time
# --------------------------------------------------------------------------
class TimeSyncState(StrEnum):
    SYNCHRONIZED = "SYNCHRONIZED"
    UNSYNCHRONIZED = "UNSYNCHRONIZED"
    UNCERTAIN = "UNCERTAIN"
    LOST = "LOST"


# --------------------------------------------------------------------------
# Storage
# --------------------------------------------------------------------------
class RecordLifecycleState(StrEnum):
    """Record lifecycle (``PR-STORAGE-009``, ``D-035``).

    ``CONFIRMED`` permits removal from the *pending upload queue* only; it
    never deletes the retained historical record.
    """

    CREATED = "CREATED"
    STORED = "STORED"
    PENDING_UPLOAD = "PENDING_UPLOAD"
    UPLOADED = "UPLOADED"
    CONFIRMED = "CONFIRMED"
    RETAINED = "RETAINED"
    CORRUPT = "CORRUPT"
    DELETED = "DELETED"


class RecordType(StrEnum):
    MEASUREMENT = "MEASUREMENT"
    EVENT = "EVENT"
    FAULT = "FAULT"
    BUFFERED = "BUFFERED"


class StorageFullBehaviour(StrEnum):
    """Candidate behaviours when the store is full.

    No option is selected yet: this remains an open engineering decision
    (assumption ``A-09``). The enum exists so the abstraction is explicit.
    """

    RAISE_CONDITION_ONLY = "RAISE_CONDITION_ONLY"
    STOP_RECORDING = "STOP_RECORDING"
    OVERWRITE_OLDEST = "OVERWRITE_OLDEST"


# --------------------------------------------------------------------------
# Communication protocol
# --------------------------------------------------------------------------
class MessageType(StrEnum):
    STATUS_REQUEST = "STATUS_REQUEST"
    STATUS_RESPONSE = "STATUS_RESPONSE"
    MEASUREMENT_REQUEST = "MEASUREMENT_REQUEST"
    MEASUREMENT_RESPONSE = "MEASUREMENT_RESPONSE"
    CONTROL_COMMAND = "CONTROL_COMMAND"
    CONTROL_ACK = "CONTROL_ACK"
    FAULT_REPORT = "FAULT_REPORT"
    EVENT_REPORT = "EVENT_REPORT"
    CONFIG_READ = "CONFIG_READ"
    CONFIG_WRITE = "CONFIG_WRITE"
    CONFIG_ACK = "CONFIG_ACK"
    TIME_SYNC = "TIME_SYNC"
    TIME_ACK = "TIME_ACK"
    IDENTIFY = "IDENTIFY"
    IDENTIFY_ACK = "IDENTIFY_ACK"
    HEARTBEAT = "HEARTBEAT"
    HEARTBEAT_ACK = "HEARTBEAT_ACK"


class CommState(StrEnum):
    COMM_HEALTHY = "COMM_HEALTHY"
    RETRY = "RETRY"
    DEGRADED = "DEGRADED"
    COMM_FAULT = "COMM_FAULT"
    RECOVERY = "RECOVERY"


# --------------------------------------------------------------------------
# Events
# --------------------------------------------------------------------------
class EventType(StrEnum):
    # control
    LAMP_ON = "LAMP_ON"
    LAMP_OFF = "LAMP_OFF"
    MODE_CHANGED = "MODE_CHANGED"
    OVERRIDE_APPLIED = "OVERRIDE_APPLIED"
    OVERRIDE_RELEASED = "OVERRIDE_RELEASED"
    # command
    COMMAND_RECEIVED = "COMMAND_RECEIVED"
    COMMAND_EXECUTED = "COMMAND_EXECUTED"
    COMMAND_REJECTED = "COMMAND_REJECTED"
    COMMAND_DUPLICATE = "COMMAND_DUPLICATE"
    COMMAND_VERIFIED = "COMMAND_VERIFIED"
    COMMAND_VERIFICATION_FAILED = "COMMAND_VERIFICATION_FAILED"
    # measurement
    MEASUREMENT_OUT_OF_RANGE = "MEASUREMENT_OUT_OF_RANGE"
    MEASUREMENT_INCONSISTENT = "MEASUREMENT_INCONSISTENT"
    SENSOR_INVALID = "SENSOR_INVALID"
    SENSOR_RECOVERED = "SENSOR_RECOVERED"
    # fault
    FAULT_SUSPECTED = "FAULT_SUSPECTED"
    FAULT_CONFIRMED = "FAULT_CONFIRMED"
    FAULT_ACKNOWLEDGED = "FAULT_ACKNOWLEDGED"
    FAULT_REMINDER_DUE = "FAULT_REMINDER_DUE"
    FAULT_ESCALATED = "FAULT_ESCALATED"
    FAULT_NOTIFICATION_FAILED = "FAULT_NOTIFICATION_FAILED"
    FAULT_REPAIR_STARTED = "FAULT_REPAIR_STARTED"
    FAULT_VERIFICATION_FAILED = "FAULT_VERIFICATION_FAILED"
    FAULT_CLOSED = "FAULT_CLOSED"
    # communication
    COMM_STATE_CHANGED = "COMM_STATE_CHANGED"
    COMM_FAULT_DETECTED = "COMM_FAULT_DETECTED"
    COMM_RECOVERED = "COMM_RECOVERED"
    FRAME_REJECTED = "FRAME_REJECTED"
    DUPLICATE_FRAME_DETECTED = "DUPLICATE_FRAME_DETECTED"
    STALE_FRAME_DETECTED = "STALE_FRAME_DETECTED"
    # storage
    RECORD_STORED = "RECORD_STORED"
    RECORD_UPLOADED = "RECORD_UPLOADED"
    RECORD_CONFIRMED = "RECORD_CONFIRMED"
    RECORD_CORRUPT = "RECORD_CORRUPT"
    RECORD_DELETED = "RECORD_DELETED"
    STORAGE_FULL = "STORAGE_FULL"
    # time
    TIME_SYNCHRONIZED = "TIME_SYNCHRONIZED"
    TIME_UNCERTAIN = "TIME_UNCERTAIN"
    TIME_LOST = "TIME_LOST"
    # system
    NODE_STARTED = "NODE_STARTED"
    NODE_RESTARTED = "NODE_RESTARTED"
    CONFIG_CHANGED = "CONFIG_CHANGED"
    CONFIG_REJECTED = "CONFIG_REJECTED"
    IDENTITY_CONFLICT = "IDENTITY_CONFLICT"
    TAMPER_INDICATION = "TAMPER_INDICATION"
    ENERGY_RESET = "ENERGY_RESET"
    FAULT_TRANSITION_REJECTED = "FAULT_TRANSITION_REJECTED"
    FAULT_NOTIFIED = "FAULT_NOTIFIED"
    FAULT_REPAIR_REPORTED = "FAULT_REPAIR_REPORTED"


class EventSeverity(StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class EventSource(StrEnum):
    CONTROL = "CONTROL"
    MEASUREMENT = "MEASUREMENT"
    DIAGNOSTICS = "DIAGNOSTICS"
    FAULT = "FAULT"
    NOTIFICATION = "NOTIFICATION"
    COMMUNICATION = "COMMUNICATION"
    STORAGE = "STORAGE"
    TIME = "TIME"
    CONFIGURATION = "CONFIGURATION"
    SYSTEM = "SYSTEM"
    SECURITY = "SECURITY"
