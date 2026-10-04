"""Master Control Center data layer tests (Phase 15).

The MCC is the logical layer above the Group Controllers: a site -> group ->
lamp registry plus aggregation over what the groups already report. These
tests exercise it as a system: real lamp nodes, real group controllers, the
real command/authorization path and the real storage records - the MCC is
never handed a stand-in.

Every test establishes a known initial state before any injection or action
and asserts the state after the action, including what must *not* change.
Nothing here claims physical validation.
"""

import pytest

from conftest import healthy_sources
from mcc_harness import MccSim, site_identifier
from sslv1.comm import MessageType
from sslv1.enums import (
    AggregateHealth,
    CommState,
    CommandState,
    CommandType,
    ConfiguredMode,
    ControlSubtype,
    ControllerStatus,
    EventSeverity,
    EventType,
    FaultSeverity,
    FaultState,
    FaultType,
    Freshness,
    LampAvailability,
    LampState,
    NotificationState,
    OperatingMode,
    OverrideState,
    RecordType,
    SensorStatus,
    TimeSyncState,
)
from sslv1.errors import ConfigurationError
from sslv1.identity import DeviceIdentity, Identifier
from sslv1.mcc import (
    FaultSummary,
    GroupRegistration,
    GroupStatus,
    LampRegistration,
    LampStatus,
    MasterControlCenterConfig,
    SiteRegistration,
    SiteStatus,
)
from sslv1.nodes import GroupController, GroupControllerConfig
from sslv1.time_model import LogicalClock

from fault_injection import (
    ADMIN,
    BRIGHT,
    ENGINEER,
    OPERATOR,
    VIEWER,
    supply_abnormal,
    under_current,
)

SITE = "SITE-A"
GRP1 = "GRP-01"
GRP2 = "GRP-02"


def bright_off():
    """A bright-ambient observation of a load that really is de-energised.

    ``BRIGHT`` alone keeps the switching feedback and the electrical readings of
    an energised lamp, which is an inconsistent sample: auto logic then leaves
    the load as it found it. Turning a lamp off in auto mode needs the whole
    observation to agree that it is off.
    """
    return healthy_sources(light_level=900.0, switching_feedback=LampState.OFF,
                           current=0.0, power=0.0)


def build(site_count=1, group_count=1, lamps_per_group=4, **kwargs):
    """A small deterministic system; tests that need 16 lamps ask for 16."""
    return MccSim(
        site_count=site_count,
        group_count=group_count,
        lamps_per_group=lamps_per_group,
        **kwargs,
    )


def observe_all(sim, status_max_age_ticks_guard=True):
    """Bring every group to a fully observed state: lamps stepped and polled."""
    for site_registration in sim.mcc.sites:
        site = site_registration.site_id
        for group_registration in sim.mcc.groups(site):
            sim.step_group(site, group_registration.group_id, ticks=sim.clock.ticks + 1000)
    sim.rounds(2, MessageType.STATUS_REQUEST)
    sim.rounds(2, MessageType.MEASUREMENT_REQUEST)


# ==========================================================================
# 1. SITE REGISTRY
# ==========================================================================
def test_site_is_created_and_listed():
    sim = build()
    assert sim.mcc.has_site(SITE) is True
    assert [str(s.site_id) for s in sim.mcc.sites] == [SITE]
    registration = sim.mcc.site(SITE)
    assert isinstance(registration, SiteRegistration)
    assert registration.group_count == 1
    assert registration.lamp_count == 4


def test_duplicate_site_is_rejected_and_changes_nothing():
    sim = build()
    before = tuple(str(s.site_id) for s in sim.mcc.sites)
    with pytest.raises(ConfigurationError):
        sim.mcc.create_site(Identifier(SITE))
    assert tuple(str(s.site_id) for s in sim.mcc.sites) == before


def test_unknown_site_is_reported_not_invented():
    sim = build()
    with pytest.raises(ConfigurationError):
        sim.mcc.site("SITE-Z")
    assert sim.mcc.has_site("SITE-Z") is False


def test_multiple_sites_are_distinct():
    sim = build(site_count=2, lamps_per_group=2)
    assert [str(s.site_id) for s in sim.mcc.sites] == [SITE, "SITE-B"]
    assert sim.mcc.site("SITE-B").lamp_count == 2
    assert len(sim.mcc.lamps()) == 4
    assert len(sim.mcc.lamps(SITE)) == 2


# ==========================================================================
# 2. GROUP REGISTRY
# ==========================================================================
def test_group_is_registered_and_listed_per_site():
    sim = build(group_count=2, lamps_per_group=3)
    groups = sim.mcc.groups(SITE)
    assert all(isinstance(g, GroupRegistration) for g in groups)
    assert [str(g.group_id) for g in groups] == [GRP1, GRP2]
    assert [g.lamp_count for g in groups] == [3, 3]
    assert str(sim.mcc.group(SITE, GRP2).controller.group_id) == GRP2


def test_duplicate_group_at_one_site_is_rejected(): 
    sim = build(group_count=1, lamps_per_group=2)
    controller = sim.gc(SITE, GRP1)
    before = len(sim.mcc.groups(SITE))
    with pytest.raises(ConfigurationError):
        sim.mcc.register_group(SITE, GRP1, controller)
    assert len(sim.mcc.groups(SITE)) == before


def test_same_group_id_at_two_sites_is_not_a_conflict():
    """Group identity is scoped to its site; identical ids stay distinct."""
    sim = build(site_count=2, group_count=1, lamps_per_group=2)
    first = sim.mcc.group(SITE, GRP1)
    second = sim.mcc.group("SITE-B", GRP1)
    assert first is not second
    assert first.controller is not second.controller
    assert str(first.site_id) != str(second.site_id)


def test_group_identity_mismatch_is_rejected():
    sim = build(group_count=1, lamps_per_group=2)
    foreign = GroupController(
        identity=DeviceIdentity(
            product_id=Identifier("SSL-V1"), site_id=Identifier("SITE-Z"),
            group_id=Identifier("GRP-99"),
        ),
        config=GroupControllerConfig(max_nodes=4),
        clock=sim.clock,
        authorizer=sim.authorizer,
    )
    with pytest.raises(ConfigurationError):
        sim.mcc.register_group(SITE, GRP1, foreign)
    assert str(foreign.group_id) not in [str(g.group_id) for g in sim.mcc.groups(SITE)]


def test_group_controller_with_a_foreign_clock_is_rejected():
    """Aggregation over two timelines would be nonsense, so it is refused."""
    sim = build(group_count=1, lamps_per_group=2)
    other_clock = LogicalClock()
    controller = GroupController(
        identity=DeviceIdentity(
            product_id=Identifier("SSL-V1"), site_id=Identifier(SITE),
            group_id=Identifier("GRP-77"),
        ),
        config=GroupControllerConfig(max_nodes=4),
        clock=other_clock,
        authorizer=sim.authorizer,
    )
    with pytest.raises(ConfigurationError):
        sim.mcc.register_group(SITE, "GRP-77", controller)


# ==========================================================================
# 3. LAMP INVENTORY AND IDENTITY HIERARCHY
# ==========================================================================
def test_lamp_inventory_preserves_the_identity_hierarchy():
    sim = build(group_count=2, lamps_per_group=3)
    lamp = sim.mcc.lamp(SITE, GRP1, "LAMP-02")
    node = sim.node(SITE, GRP1, "LAMP-02")
    assert isinstance(lamp, LampRegistration)
    assert str(lamp.site_id) == SITE
    assert str(lamp.group_id) == GRP1
    assert str(lamp.lamp_id) == "LAMP-02"
    assert lamp.bus_address == node.bus_address
    assert node.identity.site_id == lamp.site_id
    assert node.identity.group_id == lamp.group_id


def test_lamp_listing_is_scoped_by_group_and_site():
    sim = build(group_count=2, lamps_per_group=3)
    assert len(sim.mcc.lamps(SITE, GRP1)) == 3
    assert len(sim.mcc.lamps(SITE)) == 6
    assert [str(l.group_id) for l in sim.mcc.lamps(SITE, GRP2)] == [GRP2] * 3


def test_duplicate_lamp_registration_is_rejected():
    sim = build(lamps_per_group=2)
    node = sim.node(SITE, GRP1, "LAMP-01")
    before = len(sim.mcc.lamps(SITE, GRP1))
    with pytest.raises(ConfigurationError):
        sim.mcc.register_lamp(SITE, GRP1, node)
    assert len(sim.mcc.lamps(SITE, GRP1)) == before


def test_identical_lamp_ids_in_different_groups_are_different_lamps():
    """The registry key is (site, group, lamp): a bare lamp id is not unique."""
    sim = build(group_count=2, lamps_per_group=2)
    first = sim.mcc.lamp(SITE, GRP1, "LAMP-01")
    second = sim.mcc.lamp(SITE, GRP2, "LAMP-01")
    assert str(first.lamp_id) == str(second.lamp_id) == "LAMP-01"
    assert str(first.group_id) != str(second.group_id)
    assert first is not second
    assert first.bus_address == second.bus_address, (
        "the same bus address in two groups is still two different lamps"
    )

    # Only group 1 answers, so only group 1's LAMP-01 becomes healthy.
    sim.step_group(SITE, GRP1, ticks=1000)
    sim.rounds(2, MessageType.MEASUREMENT_REQUEST, site=SITE, group=GRP1)
    assert sim.mcc.lamp_status(SITE, GRP1, "LAMP-01").last_seen_ticks is not None
    assert sim.mcc.lamp_status(SITE, GRP2, "LAMP-01").last_seen_ticks is None
    assert sim.mcc.lamp_status(SITE, GRP2, "LAMP-01").voltage is None


def test_inconsistent_lamp_hierarchy_is_rejected():
    sim = build(group_count=2, lamps_per_group=2)
    node = sim.node(SITE, GRP1, "LAMP-01")
    before = len(sim.mcc.lamps(SITE, GRP2))
    with pytest.raises(ConfigurationError):
        sim.mcc.register_lamp(SITE, GRP2, node)
    assert len(sim.mcc.lamps(SITE, GRP2)) == before
    assert str(sim.mcc.lamp(SITE, GRP1, "LAMP-01").group_id) == GRP1


def test_lamp_that_belongs_to_another_site_is_rejected():
    sim = build(site_count=2, lamps_per_group=2)
    node = sim.node("SITE-B", GRP1, "LAMP-01")
    with pytest.raises(ConfigurationError):
        sim.mcc.register_lamp(SITE, GRP1, node)


def test_unknown_lamp_lookup_is_rejected():
    sim = build(lamps_per_group=2)
    with pytest.raises(ConfigurationError):
        sim.mcc.lamp(SITE, GRP1, "LAMP-99")


# ==========================================================================
# 4. LIVE LAMP SNAPSHOT
# ==========================================================================
def test_lamp_status_reports_every_field_the_group_reported():
    sim = build(lamps_per_group=2, status_max_age_ticks=10_000)
    sim.step_group(SITE, GRP1, ticks=1000)
    sim.rounds(1, MessageType.STATUS_REQUEST, site=SITE, group=GRP1)
    sim.rounds(1, MessageType.MEASUREMENT_REQUEST, site=SITE, group=GRP1)
    sim.rounds(1, MessageType.CONFIG_READ, site=SITE, group=GRP1)

    status = sim.mcc.lamp_status(SITE, GRP1, "LAMP-01")
    assert isinstance(status, LampStatus)
    assert status.availability is LampAvailability.HEALTHY
    assert status.comm_state is CommState.COMM_HEALTHY
    assert status.freshness is Freshness.FRESH
    assert status.effective_mode is OperatingMode.AUTO_SENSOR
    assert status.configured_mode is ConfiguredMode.AUTO_SENSOR
    assert status.active_override is OverrideState.NONE
    assert status.commanded_state is LampState.ON
    assert status.switching_feedback is LampState.ON
    assert status.actual_state is LampState.ON
    assert status.sensor_status is SensorStatus.VALID
    assert status.controller_status is ControllerStatus.NORMAL
    assert status.voltage == pytest.approx(230.0)
    assert status.current == pytest.approx(0.45)
    assert status.power == pytest.approx(103.5)
    assert status.energy == pytest.approx(0.029)  # quantised by the existing model
    assert status.light_level == pytest.approx(10.0)
    assert status.measured_ticks is not None
    assert status.time_sync_state is TimeSyncState.UNCERTAIN, "no synchronisation was claimed"
    assert status.last_seen_ticks is not None
    assert status.age_ticks == sim.clock.ticks - status.last_seen_ticks
    assert status.faults == ()


def test_lamp_status_invents_no_measurements_before_anything_is_reported():
    sim = build(lamps_per_group=2, status_max_age_ticks=10_000)
    sim.step_group(SITE, GRP1, ticks=1000)

    status = sim.mcc.lamp_status(SITE, GRP1, "LAMP-01")
    assert status.availability is LampAvailability.UNKNOWN
    assert status.freshness is Freshness.UNKNOWN
    assert status.age_ticks is None
    assert status.last_seen_ticks is None
    assert status.voltage is None and status.current is None and status.power is None
    assert status.energy is None and status.light_level is None
    assert status.measured_ticks is None
    assert status.commanded_state is None and status.actual_state is None
    assert status.effective_mode is None and status.active_override is None
    assert status.configured_mode is None
    assert status.faults == ()

    # The lamp itself is healthy and lit: absence of data is not a lamp fault.
    assert sim.node(SITE, GRP1, "LAMP-01").control.lamp_is_on is True
    assert sim.mcc.active_faults(SITE, GRP1) == ()


def test_lamp_status_is_stale_after_the_freshness_limit_and_not_healthy():
    sim = build(lamps_per_group=2, status_max_age_ticks=2000)
    sim.step_group(SITE, GRP1, ticks=1000)
    sim.rounds(1, MessageType.MEASUREMENT_REQUEST, site=SITE, group=GRP1)
    fresh = sim.mcc.lamp_status(SITE, GRP1, "LAMP-01")
    assert fresh.freshness is Freshness.FRESH and fresh.availability is LampAvailability.HEALTHY

    sim.advance(3000)  # no further polls: the group has nothing newer to show
    stale = sim.mcc.lamp_status(SITE, GRP1, "LAMP-01")
    assert stale.age_ticks > 2000
    assert stale.freshness is Freshness.STALE
    assert stale.availability is LampAvailability.UNKNOWN, \
        "an aged observation must not be presented as current truth"
    assert stale.voltage == fresh.voltage, "the value is unchanged, its currency is not"


def test_freshness_is_unknown_when_no_limit_is_configured():
    sim = build(lamps_per_group=1)  # status_max_age_ticks not set
    sim.step_group(SITE, GRP1, ticks=1000)
    sim.rounds(1, MessageType.MEASUREMENT_REQUEST, site=SITE, group=GRP1)
    status = sim.mcc.lamp_status(SITE, GRP1, "LAMP-01")
    assert status.freshness is Freshness.UNKNOWN
    assert status.age_ticks is not None, "the age is still exposed"
    assert status.last_seen_ticks is not None
    assert status.availability is LampAvailability.HEALTHY, "comm health is known and current"


def test_invalid_freshness_limit_is_rejected():
    with pytest.raises(ConfigurationError):
        MasterControlCenterConfig(status_max_age_ticks=0).validated()
    with pytest.raises(ConfigurationError):
        MasterControlCenterConfig(status_max_age_ticks="soon").validated()


def test_group_must_be_selected_with_its_site():
    sim = build(group_count=2, lamps_per_group=1)
    with pytest.raises(ConfigurationError):
        sim.mcc.active_faults(group=GRP1)
    with pytest.raises(ConfigurationError):
        sim.mcc.lamps(group=GRP1)


# ==========================================================================
# 5. GROUP AND SITE AGGREGATION
# ==========================================================================
def test_sixteen_lamp_group_aggregates_independently():
    sim = build(group_count=1, lamps_per_group=16, status_max_age_ticks=50_000)
    observe_all(sim)
    status = sim.mcc.group_status(SITE, GRP1)
    assert isinstance(status, GroupStatus)
    assert status.total_lamps == 16
    assert status.healthy_lamps == 16
    assert status.health is AggregateHealth.HEALTHY
    assert status.comm_summary["COMM_HEALTHY"] == 16
    assert status.aggregate_power == pytest.approx(16 * 103.5)
    assert status.aggregate_energy == pytest.approx(16 * 0.029)
    assert status.degraded_lamps == status.unavailable_lamps == ()
    assert status.active_faults == 0 and status.highest_severity is None
    assert status.upstream_available is True
    assert status.latest_observation_ticks is not None


def test_two_group_site_aggregates_each_group_and_the_site():
    sim = build(group_count=2, lamps_per_group=16, status_max_age_ticks=50_000)
    observe_all(sim)
    site_status = sim.mcc.site_status(SITE)
    assert isinstance(site_status, SiteStatus)
    assert site_status.health is AggregateHealth.HEALTHY
    assert site_status.total_groups == 2
    assert site_status.total_lamps == 32
    assert site_status.healthy_lamps == 32
    assert [str(g.group_id) for g in site_status.groups] == [GRP1, GRP2]
    assert site_status.aggregate_power == pytest.approx(32 * 103.5)
    assert site_status.aggregate_energy == pytest.approx(32 * 0.029)
    assert site_status.unhealthy_groups == ()
    assert site_status.active_faults == 0

    # Each group is aggregated from its own controller, not from a global pool.
    assert sim.mcc.group_status(SITE, GRP1).aggregate_power == pytest.approx(16 * 103.5)
    assert sim.mcc.group_status(SITE, GRP2).aggregate_power == pytest.approx(16 * 103.5)
    assert len(sim.mcc.lamp_statuses(SITE, GRP1)) == 16


def test_group_with_no_reported_data_is_unknown_not_healthy():
    sim = build(group_count=1, lamps_per_group=3, status_max_age_ticks=10_000)
    sim.step_group(SITE, GRP1, ticks=1000)  # lamps run, nothing was polled
    status = sim.mcc.group_status(SITE, GRP1)
    assert status.health is AggregateHealth.UNKNOWN
    assert len(status.unknown_lamps) == 3
    assert status.healthy_lamps == 0
    assert sim.mcc.site_status(SITE).health is AggregateHealth.UNKNOWN


# ==========================================================================
# 6. FAILURE CONTAINMENT AND DEGRADATION
# ==========================================================================
def test_one_unavailable_lamp_is_named_and_the_rest_stay_healthy():
    sim = build(group_count=1, lamps_per_group=4, status_max_age_ticks=50_000)
    observe_all(sim)
    assert sim.mcc.group_status(SITE, GRP1).health is AggregateHealth.HEALTHY

    sim.silence_lamp(SITE, GRP1, "LAMP-03")
    for _ in range(sim.gc(SITE, GRP1).config.poll_retry_count + 2):
        sim.advance(1000)
        sim.gc(SITE, GRP1).poll(MessageType.MEASUREMENT_REQUEST)
        sim.pump(SITE, GRP1)
        sim.gc(SITE, GRP1).service_timeouts()
        sim.gc(SITE, GRP1).collect_responses()

    status = sim.mcc.group_status(SITE, GRP1)
    assert status.health is AggregateHealth.DEGRADED
    assert status.unavailable_lamps == (Identifier("LAMP-03"),)
    assert status.healthy_lamps == 3
    assert status.comm_summary["COMM_FAULT"] == 1
    assert status.comm_summary["COMM_HEALTHY"] == 3
    # The silent lamp's own lighting keeps working: communication is not control.
    assert sim.node(SITE, GRP1, "LAMP-03").control.lamp_is_on is True


def test_multiple_unavailable_lamps_are_all_listed():
    sim = build(group_count=1, lamps_per_group=4, status_max_age_ticks=50_000)
    observe_all(sim)
    for lamp in ("LAMP-02", "LAMP-04"):
        sim.silence_lamp(SITE, GRP1, lamp)
    for _ in range(sim.gc(SITE, GRP1).config.poll_retry_count + 2):
        sim.advance(1000)
        sim.gc(SITE, GRP1).poll(MessageType.MEASUREMENT_REQUEST)
        sim.pump(SITE, GRP1)
        sim.gc(SITE, GRP1).service_timeouts()
        sim.gc(SITE, GRP1).collect_responses()

    status = sim.mcc.group_status(SITE, GRP1)
    assert status.unavailable_lamps == (Identifier("LAMP-02"), Identifier("LAMP-04"))
    assert status.healthy_lamps == 2
    assert status.unknown_lamps == (), "the failed links are confirmed, not unknown"
    assert sim.mcc.lamp_status(SITE, GRP1, "LAMP-01").availability is LampAvailability.HEALTHY


def test_one_group_failure_does_not_hide_the_other_groups_health():
    sim = build(group_count=2, lamps_per_group=4, status_max_age_ticks=50_000)
    observe_all(sim)
    assert sim.mcc.site_status(SITE).health is AggregateHealth.HEALTHY

    # group 1 loses its link toward the MCC
    sim.set_upstream(SITE, GRP1, False)
    groups = {str(g.group_id): g for g in sim.mcc.site_status(SITE).groups}
    assert groups[GRP1].health is AggregateHealth.UNAVAILABLE
    assert groups[GRP1].upstream_available is False
    assert groups[GRP2].health is AggregateHealth.HEALTHY, "the healthy group is still reported"
    assert groups[GRP2].healthy_lamps == 4
    site_status = sim.mcc.site_status(SITE)
    assert site_status.health is AggregateHealth.DEGRADED
    assert site_status.unhealthy_groups == (Identifier(GRP1),)
    assert site_status.healthy_lamps == 4

    # Every lamp of the unreachable group is unavailable, not healthy.
    assert sim.mcc.lamp_status(SITE, GRP1, "LAMP-01").availability is LampAvailability.UNAVAILABLE
    assert sim.mcc.lamp_status(SITE, GRP2, "LAMP-01").availability is LampAvailability.HEALTHY

    # Group 2 was never disturbed: a fresh exchange still succeeds while the
    # failed group stays unavailable.
    sim.rounds(1, MessageType.MEASUREMENT_REQUEST, site=SITE, group=GRP2)
    assert sim.mcc.lamp_status(SITE, GRP2, "LAMP-01").freshness is Freshness.FRESH
    assert sim.mcc.group_status(SITE, GRP2).health is AggregateHealth.HEALTHY
    assert sim.mcc.group_status(SITE, GRP1).health is AggregateHealth.UNAVAILABLE

    # Restoring the link recovers that group; group 2 is unaffected either way.
    sim.set_upstream(SITE, GRP1, True)
    assert sim.mcc.group_status(SITE, GRP1).health is AggregateHealth.HEALTHY
    assert sim.mcc.group_status(SITE, GRP2).health is AggregateHealth.HEALTHY
    assert sim.mcc.site_status(SITE).health is AggregateHealth.HEALTHY


def test_group_and_site_health_are_unavailable_when_all_groups_are_unreachable():
    sim = build(group_count=2, lamps_per_group=2, status_max_age_ticks=50_000)
    observe_all(sim)
    sim.set_upstream(SITE, GRP1, False)
    sim.set_upstream(SITE, GRP2, False)
    assert sim.mcc.group_status(SITE, GRP1).health is AggregateHealth.UNAVAILABLE
    site_status = sim.mcc.site_status(SITE)
    assert site_status.health is AggregateHealth.UNAVAILABLE
    assert site_status.unhealthy_groups == (Identifier(GRP1), Identifier(GRP2))


def test_degraded_link_is_reported_as_degraded_not_unavailable():
    sim = build(group_count=1, lamps_per_group=3, status_max_age_ticks=50_000)
    observe_all(sim)
    sim.silence_lamp(SITE, GRP1, "LAMP-01")
    sim.round(SITE, GRP1, MessageType.MEASUREMENT_REQUEST)  # LAMP-01 does not answer
    assert sim.mcc.lamp_status(SITE, GRP1, "LAMP-02").comm_state is CommState.COMM_HEALTHY
    sim.advance(sim.gc(SITE, GRP1).config.poll_timeout_ticks)
    sim.gc(SITE, GRP1).service_timeouts()  # first failure: RETRY

    status = sim.mcc.lamp_status(SITE, GRP1, "LAMP-01")
    assert status.comm_state is CommState.RETRY
    assert status.availability is LampAvailability.DEGRADED
    # Degradation is scoped to the failing lamp, not the whole group.
    assert sim.mcc.group_status(SITE, GRP1).degraded_lamps == (Identifier("LAMP-01"),)
    assert sim.mcc.lamp_status(SITE, GRP1, "LAMP-02").availability is LampAvailability.HEALTHY
    assert sim.mcc.group_status(SITE, GRP1).health is AggregateHealth.DEGRADED


def test_healthy_group_does_not_conceal_a_faulted_lamp():
    sim = build(group_count=1, lamps_per_group=4, status_max_age_ticks=50_000)
    observe_all(sim)
    sim.confirm_fault(SITE, GRP1, "LAMP-02", under_current())
    sim.rounds(1, MessageType.FAULT_REPORT, site=SITE, group=GRP1)

    status = sim.mcc.group_status(SITE, GRP1)
    assert status.health is AggregateHealth.DEGRADED
    assert status.active_faults == 1
    assert status.faulted_lamps == (Identifier("LAMP-02"),)
    assert status.highest_severity is FaultSeverity.MINOR
    assert status.healthy_lamps == 3
    # The three unaffected lamps are still individually healthy.
    assert sim.mcc.lamp_status(SITE, GRP1, "LAMP-01").faults == ()
    assert sim.mcc.lamp_status(SITE, GRP1, "LAMP-04").availability is LampAvailability.HEALTHY


# ==========================================================================
# 7. FAULT VISIBILITY (no second fault lifecycle)
# ==========================================================================
def test_active_fault_visibility_carries_identity_state_and_severity():
    sim = build(group_count=2, lamps_per_group=3, status_max_age_ticks=50_000)
    observe_all(sim)
    sim.confirm_fault(SITE, GRP1, "LAMP-02", under_current())
    sim.rounds(1, MessageType.FAULT_REPORT, site=SITE, group=GRP1)

    faults = sim.mcc.active_faults(SITE, GRP1)
    assert len(faults) == 1
    fault = faults[0]
    assert isinstance(fault, FaultSummary)
    assert str(fault.site_id) == SITE
    assert str(fault.group_id) == GRP1
    assert str(fault.lamp_id) == "LAMP-02"
    assert fault.fault_id.startswith("F-")
    assert fault.fault_type is FaultType.UNDER_CURRENT
    assert fault.state is FaultState.CONFIRMED
    assert fault.severity is FaultSeverity.MINOR
    assert fault.notification_state is NotificationState.ACK_PENDING
    assert fault.confirmation_count == 3
    assert fault.first_reported_ticks <= fault.latest_reported_ticks
    assert fault.is_active is True
    # The summary points back at the existing record it was read from, so the
    # fault is traceable into the audit trail rather than living only here.
    linked = [r for r in sim.mcc.fault_records(SITE, GRP1)
              if r.sequence_number == fault.latest_record_sequence]
    assert len(linked) == 1 and linked[0].payload["fault_id"] == fault.fault_id
    assert linked[0].payload["lamp_id"] == "LAMP-02"
    # Scoped queries agree with the unscoped one.
    assert sim.mcc.active_faults() == faults
    assert sim.mcc.active_faults(SITE, GRP1, "LAMP-01") == ()
    assert sim.mcc.active_faults(SITE, GRP2) == ()


def test_repeated_fault_polls_add_records_but_not_fault_identities():
    """The MCC summarises; it never grows a second lifecycle."""
    sim = build(group_count=1, lamps_per_group=2, status_max_age_ticks=50_000)
    observe_all(sim)
    sim.confirm_fault(SITE, GRP1, "LAMP-01", under_current())
    for _ in range(3):
        sim.rounds(1, MessageType.FAULT_REPORT, site=SITE, group=GRP1)

    records = sim.mcc.fault_records(SITE, GRP1)
    assert len(records) == 3, "each report is a record, as the existing model does"
    assert all(r.record_type is RecordType.FAULT for r in records)
    summaries = sim.mcc.active_faults(SITE, GRP1)
    assert len(summaries) == 1
    assert summaries[0].latest_record_sequence == records[-1].sequence_number
    assert summaries[0].first_reported_ticks <= summaries[0].latest_reported_ticks


def test_cleared_fault_disappears_from_the_active_view():
    sim = build(group_count=1, lamps_per_group=2, status_max_age_ticks=50_000)
    observe_all(sim)
    fault = sim.confirm_fault(SITE, GRP1, "LAMP-01", under_current())
    sim.rounds(1, MessageType.FAULT_REPORT, site=SITE, group=GRP1)
    assert len(sim.mcc.active_faults(SITE, GRP1)) == 1

    # Repair the condition and close the fault through the existing lifecycle.
    node = sim.node(SITE, GRP1, "LAMP-01")
    node.step(healthy_sources(), ticks=sim.clock.ticks + 1)
    node.acknowledge_fault(fault.fault_id, OPERATOR, ticks=sim.clock.ticks + 2)
    node.start_repair(fault.fault_id, ENGINEER, ticks=sim.clock.ticks + 3)
    node.report_repaired(fault.fault_id, ENGINEER, ticks=sim.clock.ticks + 4)
    node.verify_repair(fault.fault_id, ENGINEER, verified=True, ticks=sim.clock.ticks + 5)
    assert fault.state is FaultState.CLOSED

    sim.rounds(1, MessageType.FAULT_REPORT, site=SITE, group=GRP1)
    assert sim.mcc.active_faults(SITE, GRP1) == ()
    assert sim.mcc.group_status(SITE, GRP1).active_faults == 0

    # The history keeps both exchanges: the report that raised the fault and the
    # one where the node stopped reporting it. No fault identity is invented.
    records = sim.mcc.fault_records(SITE, GRP1)
    assert [r.payload["fault_id"] for r in records] == [fault.fault_id, fault.fault_id]
    assert records[-1].payload.get("cleared") is True
    assert sim.mcc.fault_records(SITE, GRP1, "LAMP-02") == ()

    # Clearing is a transition, not a per-poll report: further polls of the
    # healthy node add nothing, exactly like any other idle poll.
    sim.rounds(3, MessageType.FAULT_REPORT, site=SITE, group=GRP1)
    assert sim.mcc.fault_records(SITE, GRP1) == records
    assert sim.mcc.active_faults(SITE, GRP1) == ()


def test_fault_visibility_does_not_read_unreported_node_state():
    """The MCC cannot know a fault the group never received a report about."""
    sim = build(group_count=1, lamps_per_group=2, status_max_age_ticks=50_000)
    observe_all(sim)
    node = sim.node(SITE, GRP1, "LAMP-01")
    sim.confirm_fault(SITE, GRP1, "LAMP-01", under_current())
    assert node.faults.active_faults, "the node itself has a fault"

    assert sim.mcc.active_faults(SITE, GRP1) == (), \
        "without a FAULT_REPORT pull the group has nothing to report"
    sim.rounds(1, MessageType.FAULT_REPORT, site=SITE, group=GRP1)
    assert len(sim.mcc.active_faults(SITE, GRP1)) == 1


def test_site_fault_count_spans_the_groups_without_mixing_them():
    sim = build(group_count=2, lamps_per_group=3, status_max_age_ticks=100_000)
    observe_all(sim)
    sim.confirm_fault(SITE, GRP1, "LAMP-01", under_current())
    sim.confirm_fault(SITE, GRP2, "LAMP-03", supply_abnormal())
    sim.rounds(1, MessageType.FAULT_REPORT, site=SITE, group=GRP1)
    sim.rounds(1, MessageType.FAULT_REPORT, site=SITE, group=GRP2)

    faults = sim.mcc.active_faults(SITE)
    assert {str(f.group_id) for f in faults} == {GRP1, GRP2}
    assert sim.mcc.site_status(SITE).active_faults == 2
    assert sim.mcc.site_status(SITE).highest_severity is FaultSeverity.MAJOR
    assert sim.mcc.group_status(SITE, GRP1).faulted_lamps == (Identifier("LAMP-01"),)
    assert sim.mcc.group_status(SITE, GRP2).faulted_lamps == (Identifier("LAMP-03"),)


# ==========================================================================
# 8. EVENT AND AUDIT VISIBILITY
# ==========================================================================
def test_identical_group_ids_at_two_sites_never_mix_their_faults():
    """A group id is unique only within a site, at every layer."""
    sim = build(site_count=2, lamps_per_group=2, status_max_age_ticks=50_000)
    observe_all(sim)
    sim.confirm_fault("SITE-B", GRP1, "LAMP-02", under_current())
    sim.rounds(1, MessageType.FAULT_REPORT, site="SITE-B", group=GRP1)

    site_b = sim.mcc.active_faults("SITE-B", GRP1)
    assert len(site_b) == 1
    assert str(site_b[0].site_id) == "SITE-B"
    assert str(site_b[0].group_id) == GRP1
    assert str(site_b[0].lamp_id) == "LAMP-02"

    # SITE-A/GRP-01 is a different group with the same id and has no fault.
    assert sim.mcc.active_faults("SITE-A", GRP1) == ()
    assert sim.mcc.active_faults() == site_b
    assert sim.mcc.group_status("SITE-A", GRP1).active_faults == 0
    assert sim.mcc.group_status("SITE-A", GRP1).health is AggregateHealth.HEALTHY
    assert sim.mcc.site_status("SITE-A").active_faults == 0


def test_events_are_aggregated_from_the_existing_group_logs():
    sim = build(group_count=2, lamps_per_group=2, status_max_age_ticks=50_000)
    observe_all(sim)
    events = sim.mcc.events()
    assert events, "group controllers record their own audit events"
    assert all(isinstance(e.timestamp.ticks, int) for e in events)
    assert list(events) == sorted(events, key=lambda e: (e.timestamp.ticks, str(e.device_id), e.event_id))

    group_2_events = sim.mcc.events(SITE, GRP2)
    assert group_2_events
    assert all(e.group_id == Identifier(GRP2) for e in group_2_events)
    assert all(any(e is other for other in events) for e in group_2_events), \
        "the view returns the very records the controllers keep"

    filtered = sim.mcc.events(SITE, GRP1, event_type=EventType.NODE_STARTED)
    assert filtered and all(e.event_type is EventType.NODE_STARTED for e in filtered)
    error_events = sim.mcc.events(min_severity=EventSeverity.ERROR)
    assert all(e.severity in (EventSeverity.ERROR, EventSeverity.CRITICAL) for e in error_events)


def test_node_events_reach_the_mcc_only_through_the_group_records():
    sim = build(group_count=1, lamps_per_group=2, status_max_age_ticks=50_000)
    observe_all(sim)
    assert sim.mcc.reported_events(SITE, GRP1) == ()

    sim.rounds(1, MessageType.EVENT_REPORT, site=SITE, group=GRP1)
    records = sim.mcc.reported_events(SITE, GRP1)
    assert records, "the group received node events"
    assert all(r.record_type is RecordType.EVENT for r in records)
    assert {r.payload["lamp_id"] for r in records} == {"LAMP-01", "LAMP-02"}

    for lamp in ("LAMP-01", "LAMP-02"):
        per_lamp = sim.mcc.reported_events(SITE, GRP1, lamp)
        assert per_lamp
        assert all(r.payload["lamp_id"] == lamp for r in per_lamp)

    # The MCC exposes the group's records themselves, not a copy or a second log.
    stored = {id(r) for r in sim.gc(SITE, GRP1).storage.records
              if r.record_type is RecordType.EVENT}
    assert {id(r) for r in records} <= stored


# ==========================================================================
# 9. OPERATOR COMMANDS THROUGH THE EXISTING PATH
# ==========================================================================
def test_authorized_force_on_is_verified_from_a_fresh_observation():
    sim = build(group_count=1, lamps_per_group=2, status_max_age_ticks=50_000)
    observe_all(sim)
    # The lamp starts genuinely OFF: dark-room stepping would energise it again,
    # so the OFF observation is the last thing the node saw before the command.
    sim.step(SITE, GRP1, "LAMP-01", sources=bright_off(), ticks=sim.clock.ticks + 1)
    sim.rounds(1, MessageType.STATUS_REQUEST, site=SITE, group=GRP1)
    sim.rounds(1, MessageType.MEASUREMENT_REQUEST, site=SITE, group=GRP1)
    assert sim.lamp_is_on(SITE, GRP1, "LAMP-01") is False
    assert sim.mcc.lamp_status(SITE, GRP1, "LAMP-01").actual_state is LampState.OFF

    record = sim.mcc.force_on(SITE, GRP1, "LAMP-01", OPERATOR, command_id="mcc-on-1")
    assert record.command.actor == OPERATOR, "the actor identity is preserved"
    assert record.state is CommandState.RECEIVED, "delivery is not success"
    sim.pump(SITE, GRP1)
    sim.gc(SITE, GRP1).collect_responses()
    assert record.state is CommandState.ACKNOWLEDGED
    assert record.state is not CommandState.ACTUAL_STATE_VERIFIED

    sim.step(SITE, GRP1, "LAMP-01", ticks=sim.clock.ticks + 1)
    sim.pump(SITE, GRP1)
    sim.gc(SITE, GRP1).collect_responses()
    assert record.state is CommandState.ACTUAL_STATE_VERIFIED
    assert sim.lamp_is_on(SITE, GRP1, "LAMP-01") is True
    assert sim.mcc.command(SITE, GRP1, "mcc-on-1") is record


def test_authorized_force_off_and_return_to_auto():
    sim = build(group_count=1, lamps_per_group=2, status_max_age_ticks=50_000)
    sim.step_group(SITE, GRP1, ticks=1000)
    observe_all(sim)
    assert sim.lamp_is_on(SITE, GRP1, "LAMP-01") is True

    off = sim.mcc.force_off(SITE, GRP1, "LAMP-01", OPERATOR, command_id="mcc-off")
    sim.pump(SITE, GRP1)
    sim.gc(SITE, GRP1).collect_responses()
    assert off.state is CommandState.ACKNOWLEDGED
    sim.step(SITE, GRP1, "LAMP-01", sources=bright_off(), ticks=sim.clock.ticks + 1)
    sim.pump(SITE, GRP1)
    sim.gc(SITE, GRP1).collect_responses()
    assert off.state is CommandState.ACTUAL_STATE_VERIFIED
    assert sim.node(SITE, GRP1, "LAMP-01").control.active_override is OverrideState.FORCE_OFF

    auto = sim.mcc.return_to_auto(SITE, GRP1, "LAMP-01", OPERATOR, command_id="mcc-auto")
    sim.pump(SITE, GRP1)
    sim.gc(SITE, GRP1).collect_responses()
    assert auto.state is CommandState.ACTUAL_STATE_VERIFIED
    assert sim.node(SITE, GRP1, "LAMP-01").control.active_override is OverrideState.NONE
    assert sim.node(SITE, GRP1, "LAMP-01").control.effective_mode is OperatingMode.AUTO_SENSOR


def test_every_supported_subtype_can_be_requested_through_the_mcc():
    sim = build(group_count=1, lamps_per_group=2, status_max_age_ticks=50_000)
    sim.step_group(SITE, GRP1, ticks=1000)
    observe_all(sim)

    set_mode = sim.mcc.request_control(
        SITE, GRP1, "LAMP-02", ControlSubtype.SET_MODE, ADMIN,
        command_id="mcc-mode", parameter=list(ConfiguredMode).index(ConfiguredMode.AUTO_SENSOR))
    assert set_mode.state is CommandState.RECEIVED
    assert set_mode.command.subtype is ControlSubtype.SET_MODE

    reset = sim.mcc.request_control(
        SITE, GRP1, "LAMP-02", ControlSubtype.RESET_ENERGY, ENGINEER,
        command_id="mcc-reset", parameter=0)
    assert reset.state is CommandState.RECEIVED
    assert reset.command.command_type is CommandType.SET_MODE
    assert reset.command.subtype is ControlSubtype.RESET_ENERGY
    assert len(sim.mcc.commands(SITE, GRP1)) == 2


def test_unauthorized_command_is_rejected_before_anything_is_transmitted():
    sim = build(group_count=1, lamps_per_group=2, status_max_age_ticks=50_000)
    observe_all(sim)
    sim.step(SITE, GRP1, "LAMP-01", sources=bright_off(), ticks=sim.clock.ticks + 1)
    sim.rounds(1, MessageType.STATUS_REQUEST, site=SITE, group=GRP1)
    sim.rounds(1, MessageType.MEASUREMENT_REQUEST, site=SITE, group=GRP1)
    transmitted = sim.bus(SITE, GRP1).stats.transmitted
    lamp_before = sim.lamp_is_on(SITE, GRP1, "LAMP-01")
    assert lamp_before is False

    record = sim.mcc.force_on(SITE, GRP1, "LAMP-01", VIEWER, command_id="mcc-denied")
    assert record.state is CommandState.REJECTED
    assert record.succeeded is False
    assert sim.bus(SITE, GRP1).stats.transmitted == transmitted, "nothing reached the bus"
    assert sim.lamp_is_on(SITE, GRP1, "LAMP-01") is lamp_before is False
    assert sim.node(SITE, GRP1, "LAMP-01").control.active_override is OverrideState.NONE

    rejected = [e for e in sim.mcc.events(SITE, GRP1)
                if e.event_type is EventType.COMMAND_REJECTED]
    assert rejected, "the refusal is audited"
    assert rejected[-1].actor == VIEWER.actor_id
    assert sim.mcc.command(SITE, GRP1, "mcc-denied").state is CommandState.REJECTED


def test_engineering_only_action_is_protected_even_through_the_mcc():
    sim = build(group_count=1, lamps_per_group=2, status_max_age_ticks=50_000)
    sim.step_group(SITE, GRP1, ticks=1000)
    observe_all(sim)
    node = sim.node(SITE, GRP1, "LAMP-01")
    node.step(healthy_sources(), ticks=sim.clock.ticks + 1)
    energy_before = node.last_measurement.energy
    assert energy_before and energy_before > 0

    record = sim.mcc.request_control(
        SITE, GRP1, "LAMP-01", ControlSubtype.RESET_ENERGY, OPERATOR,
        command_id="mcc-reset-denied")
    sim.pump(SITE, GRP1)
    sim.gc(SITE, GRP1).collect_responses()
    assert record.state in (CommandState.FAILED, CommandState.REJECTED)
    assert "RESET_ENERGY" in record.result or "not authorized" in record.result
    node.step(healthy_sources(), ticks=sim.clock.ticks + 1)
    assert node.last_measurement.energy >= energy_before, \
        "a denied reset must not drop the accumulator"


def test_admin_time_distribution_is_not_reachable_through_the_mcc_data_layer():
    """The MCC data layer adds no privileged operation of its own."""
    sim = build(group_count=1, lamps_per_group=1)
    admin_only = [name for name in dir(sim.mcc)
                  if name in ("synchronize_time", "write_configuration", "authorize")]
    assert admin_only == []


# ==========================================================================
# 10. AUDIT PRESERVATION
# ==========================================================================
def test_mcc_command_is_traceable_to_actor_command_target_and_outcome():
    sim = build(group_count=1, lamps_per_group=2, status_max_age_ticks=50_000)
    sim.step_group(SITE, GRP1, ticks=1000)
    observe_all(sim)

    record = sim.mcc.force_off(SITE, GRP1, "LAMP-02", OPERATOR, command_id="mcc-audit-1")
    assert record.command.actor.actor_id == OPERATOR.actor_id
    assert record.command.actor.role.value == "OPERATOR"
    assert str(record.command.target.lamp_id) == "LAMP-02"
    sim.pump(SITE, GRP1)
    sim.gc(SITE, GRP1).collect_responses()

    audit = [e for e in sim.mcc.events(SITE, GRP1)
             if e.event_type is EventType.COMMAND_RECEIVED]
    assert audit, "the existing command audit recorded the action"
    assert audit[-1].actor == OPERATOR.actor_id
    assert "mcc-audit-1" in audit[-1].reason
    stored = sim.mcc.command(SITE, GRP1, "mcc-audit-1")
    assert stored is record and stored.command.actor.actor_id == OPERATOR.actor_id


def test_duplicate_command_id_is_idempotent_through_the_mcc():
    sim = build(group_count=1, lamps_per_group=2, status_max_age_ticks=50_000)
    sim.step(SITE, GRP1, "LAMP-01", sources=BRIGHT, ticks=1000)
    observe_all(sim)
    first = sim.mcc.force_on(SITE, GRP1, "LAMP-01", OPERATOR, command_id="mcc-dup")
    sim.pump(SITE, GRP1)
    sim.gc(SITE, GRP1).collect_responses()
    transmitted = sim.bus(SITE, GRP1).stats.transmitted

    second = sim.mcc.force_on(SITE, GRP1, "LAMP-01", OPERATOR, command_id="mcc-dup")
    assert second is first
    assert sim.bus(SITE, GRP1).stats.transmitted == transmitted, "no second transmission"
    assert len([e for e in sim.mcc.events(SITE, GRP1)
                if e.event_type is EventType.COMMAND_DUPLICATE]) == 1


# ==========================================================================
# 11. CONFIGURATION VISIBILITY
# ==========================================================================
def test_configuration_readback_is_exposed_and_bounded():
    sim = build(group_count=2, lamps_per_group=2, status_max_age_ticks=50_000)
    observe_all(sim)
    assert sim.mcc.configuration_snapshot(SITE, GRP1, "LAMP-01") is None

    sim.mcc.read_configuration(SITE, GRP1, "LAMP-01")
    sim.pump(SITE, GRP1)
    sim.gc(SITE, GRP1).collect_responses()
    snapshot = sim.mcc.configuration_snapshot(SITE, GRP1, "LAMP-01")
    assert snapshot is not None
    assert snapshot["accepted"] is True
    parameters = snapshot["parameters"]
    assert parameters["configured_mode"] == list(ConfiguredMode).index(ConfiguredMode.AUTO_SENSOR)
    assert parameters["light_on_threshold"] == 50
    assert parameters["measurement_interval_ticks"] == 1000
    assert sim.mcc.lamp_status(SITE, GRP1, "LAMP-01").configured_mode is ConfiguredMode.AUTO_SENSOR
    # The readback is per lamp and per group; other lamps stay unread.
    assert sim.mcc.configuration_snapshot(SITE, GRP1, "LAMP-02") is None
    assert sim.mcc.configuration_snapshot(SITE, GRP2, "LAMP-01") is None


def test_structured_configuration_writing_is_not_exposed_by_the_mcc():
    """PR-CONFIG-001/-002 stay PARTIAL: the MCC only reads configuration."""
    sim = build(lamps_per_group=1)
    public = {name for name in dir(sim.mcc) if not name.startswith("_")}
    assert "write_configuration" not in public
    assert "distribute_configuration" not in public
    assert "apply_configuration" not in public
    node_before = sim.node(SITE, GRP1, "LAMP-01").config.light_on_threshold
    with pytest.raises(AttributeError):
        sim.mcc.write_configuration(SITE, GRP1, "LAMP-01", {"light_on_threshold": 10})
    assert sim.node(SITE, GRP1, "LAMP-01").config.light_on_threshold == node_before


# ==========================================================================
# 12. LOCAL OPERATION IS INDEPENDENT OF THE MCC
# ==========================================================================
def test_lamps_keep_operating_while_the_mcc_has_never_polled():
    sim = build(group_count=2, lamps_per_group=3, status_max_age_ticks=10_000)
    # No MCC interaction at all: the field layer runs on its own.
    sim.step_group(SITE, GRP1, ticks=1000)
    sim.step_group(SITE, GRP2, ticks=1000)
    assert all(sim.lamp_is_on(SITE, GRP1, lamp) for lamp in sim.lamp_ids(SITE, GRP1))
    assert all(sim.lamp_is_on(SITE, GRP2, lamp) for lamp in sim.lamp_ids(SITE, GRP2))

    # Sensors keep controlling each lamp after the MCC becomes unreachable.
    sim.set_upstream(SITE, GRP1, False)
    sim.set_upstream(SITE, GRP2, False)
    sim.advance(5000)
    for lamp in sim.lamp_ids(SITE, GRP1):
        sim.node(SITE, GRP1, lamp).step(
            healthy_sources(light_level=900.0, switching_feedback=LampState.OFF,
                            current=0.0, power=0.0),
            ticks=sim.clock.ticks + 1)
    assert all(not sim.lamp_is_on(SITE, GRP1, lamp) for lamp in sim.lamp_ids(SITE, GRP1))
    assert sim.mcc.site_status(SITE).health is AggregateHealth.UNAVAILABLE
    assert sim.mcc.site_status(SITE).healthy_lamps == 0, \
        "an unreachable site reports no healthy lamps, however the field is doing"


def test_local_records_are_kept_while_the_mcc_is_unreachable():
    sim = build(group_count=1, lamps_per_group=2, status_max_age_ticks=50_000)
    observe_all(sim)
    sim.set_upstream(SITE, GRP1, False)
    sim.rounds(2, MessageType.MEASUREMENT_REQUEST, site=SITE, group=GRP1)

    group_status = sim.mcc.group_status(SITE, GRP1)
    assert group_status.upstream_available is False
    assert group_status.pending_upload > 0, "records wait in the existing buffer"
    assert group_status.health is AggregateHealth.UNAVAILABLE

    sim.set_upstream(SITE, GRP1, True)
    forwarded = sim.gc(SITE, GRP1).forward_upstream()
    assert forwarded["uploaded"] == forwarded["confirmed"] > 0
    assert sim.mcc.group_status(SITE, GRP1).pending_upload == 0
    assert sim.mcc.group_status(SITE, GRP1).retained_records > 0


# ==========================================================================
# 13. END-TO-END SCENARIOS
# ==========================================================================
def test_scenario_two_group_site_with_an_isolated_failure():
    """Site A: GRP-01 (16 lamps) healthy, GRP-02 (16 lamps) with one dead node."""
    sim = build(group_count=2, lamps_per_group=16, status_max_age_ticks=100_000)
    observe_all(sim)
    assert sim.mcc.site_status(SITE).healthy_lamps == 32

    sim.silence_lamp(SITE, GRP2, "LAMP-09")
    for _ in range(sim.gc(SITE, GRP2).config.poll_retry_count + 2):
        sim.advance(1000)
        sim.gc(SITE, GRP2).poll(MessageType.MEASUREMENT_REQUEST)
        sim.pump(SITE, GRP2)
        sim.gc(SITE, GRP2).service_timeouts()
        sim.gc(SITE, GRP2).collect_responses()

    site_status = sim.mcc.site_status(SITE)
    groups = {str(g.group_id): g for g in site_status.groups}
    assert groups[GRP1].health is AggregateHealth.HEALTHY
    assert groups[GRP1].healthy_lamps == 16
    assert groups[GRP2].health is AggregateHealth.DEGRADED
    assert groups[GRP2].unavailable_lamps == (Identifier("LAMP-09"),)
    assert groups[GRP2].healthy_lamps == 15
    assert site_status.health is AggregateHealth.DEGRADED
    assert site_status.unhealthy_groups == (Identifier(GRP2),)
    assert site_status.healthy_lamps == 31
    # GRP-01's LAMP-09 is a different lamp and is untouched.
    assert sim.mcc.lamp_status(SITE, GRP1, "LAMP-09").availability is LampAvailability.HEALTHY


def test_scenario_operator_handles_a_faulted_lamp_from_the_mcc():
    """Detect -> confirm -> notify -> acknowledge -> repair -> verify -> close."""
    sim = build(group_count=1, lamps_per_group=3, status_max_age_ticks=100_000)
    observe_all(sim)
    lamp = "LAMP-02"
    fault = sim.confirm_fault(SITE, GRP1, lamp, under_current())
    assert fault.state is FaultState.CONFIRMED
    sim.rounds(1, MessageType.FAULT_REPORT, site=SITE, group=GRP1)
    visible = sim.mcc.active_faults(SITE, GRP1)[0]
    assert visible.state is FaultState.CONFIRMED
    assert visible.notification_state is NotificationState.ACK_PENDING

    node = sim.node(SITE, GRP1, lamp)
    node.acknowledge_fault(fault.fault_id, OPERATOR, ticks=sim.clock.ticks + 1)
    node.start_repair(fault.fault_id, ENGINEER, ticks=sim.clock.ticks + 2)
    node.report_repaired(fault.fault_id, ENGINEER, ticks=sim.clock.ticks + 3)
    sim.rounds(1, MessageType.FAULT_REPORT, site=SITE, group=GRP1)
    mid = sim.mcc.active_faults(SITE, GRP1)[0]
    assert mid.state is FaultState.VERIFYING and mid.is_active is True

    node.step(healthy_sources(), ticks=sim.clock.ticks + 1)
    node.verify_repair(fault.fault_id, ENGINEER, verified=True, ticks=sim.clock.ticks + 2)
    sim.rounds(1, MessageType.FAULT_REPORT, site=SITE, group=GRP1)
    assert fault.state is FaultState.CLOSED
    assert sim.mcc.active_faults(SITE, GRP1) == ()
    assert sim.mcc.group_status(SITE, GRP1).health is AggregateHealth.HEALTHY


def test_scenario_command_to_a_node_that_cannot_execute_it():
    """A command the target refuses is reported as a failure, never a success."""
    sim = build(group_count=1, lamps_per_group=2, status_max_age_ticks=50_000)
    observe_all(sim)
    sim.silence_lamp(SITE, GRP1, "LAMP-02")

    record = sim.mcc.force_on(SITE, GRP1, "LAMP-02", OPERATOR, command_id="mcc-lost")
    assert record.state is CommandState.RECEIVED
    for _ in range(sim.gc(SITE, GRP1).config.poll_retry_count + 1):
        sim.advance(sim.gc(SITE, GRP1).config.poll_timeout_ticks)
        sim.gc(SITE, GRP1).service_timeouts()
    sim.gc(SITE, GRP1).collect_responses()

    assert record.state is CommandState.FAILED
    assert record.verified_ticks is None
    assert sim.node(SITE, GRP1, "LAMP-02").control.active_override is OverrideState.NONE
    assert sim.mcc.lamp_status(SITE, GRP1, "LAMP-02").availability is LampAvailability.UNAVAILABLE


def test_scenario_second_site_stays_isolated_from_the_first():
    sim = build(site_count=2, group_count=1, lamps_per_group=4, status_max_age_ticks=50_000)
    observe_all(sim)
    other = site_identifier(1)
    assert sim.mcc.site_status(other).health is AggregateHealth.HEALTHY

    sim.silence_lamp(SITE, GRP1, "LAMP-01")
    for _ in range(sim.gc(SITE, GRP1).config.poll_retry_count + 2):
        sim.advance(1000)
        sim.gc(SITE, GRP1).poll(MessageType.MEASUREMENT_REQUEST)
        sim.pump(SITE, GRP1)
        sim.gc(SITE, GRP1).service_timeouts()
        sim.gc(SITE, GRP1).collect_responses()

    assert sim.mcc.site_status(SITE).health is AggregateHealth.DEGRADED
    assert sim.mcc.site_status(other).health is AggregateHealth.HEALTHY
    assert sim.mcc.site_status(other).unhealthy_groups == ()
    assert sim.mcc.lamp_status(other, GRP1, "LAMP-01").availability is LampAvailability.HEALTHY
