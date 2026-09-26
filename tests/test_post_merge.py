"""Post-merge counterexamples: real bus pumps, observations and deadlines."""
from dataclasses import replace

import pytest

from conftest import healthy_sources, make_lamp_config
from sslv1.authorization import Actor
from sslv1.comm import Frame, decode_frame, decode_payload, encode_payload, PROTOCOL_VERSION
from sslv1.comm.crc import crc16_xmodem
from sslv1.configuration import Schedule, TimeWindow
from sslv1.control import ControlModel
from sslv1.enums import (
    CommandState, CommState, ConfiguredMode, ControlSubtype, EventType,
    LampState, MessageType, NotificationState, RecordType, Role,
    TimeSyncState, SensorStatus,
)
from sslv1.errors import AuthorizationError, ConfigurationError, ProtocolError, StorageError, IllegalTransitionError
from sslv1.nodes import LampNode
from sslv1.nodes.group_controller import SequenceTracker
from sslv1.storage import RecordStore
from sslv1.time_model import Timestamp


@pytest.fixture
def pair(group_controller, lamp_node):
    group_controller.register_node(lamp_node.lamp_id, lamp_node.bus_address)
    return group_controller, lamp_node


def pump(gc, node):
    responses = node.process_incoming()
    for response in responses:
        gc.bus.send(response)
    gc.collect_responses()
    return responses


@pytest.mark.parametrize('role', [Role.VIEWER, Role.OPERATOR, Role.ENGINEER, Role.ADMIN, Role.OWNER])
@pytest.mark.parametrize('subtype', list(ControlSubtype))
def test_remote_role_matrix_before_transmission(pair, role, subtype):
    gc, node = pair
    actor = Actor('remote-' + role.value, role)
    engineer_action = subtype in (ControlSubtype.SET_MODE, ControlSubtype.RESET_ENERGY)
    allowed = role is not Role.VIEWER and (not engineer_action or role is not Role.OPERATOR)
    before = gc.bus.stats.transmitted
    record = gc.forward_control(node.lamp_id, subtype, actor)
    if not allowed:
        assert record.state is CommandState.REJECTED
        assert gc.bus.stats.transmitted == before
        assert node.process_incoming() == []
        assert node.control.active_override.value == 'NONE'
        assert gc.events.events[-1].actor == actor.actor_id
    else:
        assert record.state is CommandState.RECEIVED
        assert not record.succeeded
        pump(gc, node)
        if subtype in (ControlSubtype.LAMP_ON, ControlSubtype.LAMP_OFF):
            assert record.state is CommandState.ACKNOWLEDGED
            on = subtype is ControlSubtype.LAMP_ON
            node.step(healthy_sources(current=.45 if on else 0, power=103.5 if on else 0,
                                      switching_feedback=LampState.ON if on else LampState.OFF))
            pump(gc, node)
        assert record.state is CommandState.ACTUAL_STATE_VERIFIED
        assert record.evidence['command_id'] == record.command_id
        assert any(e.actor == actor.actor_id for e in node.events)


@pytest.mark.parametrize('authenticated', [True, False])
def test_unauthorized_config_never_transmitted(pair, authenticated):
    gc, node = pair
    actor = Actor('denied', Role.VIEWER if authenticated else Role.OWNER, authenticated)
    old = node.config
    before = gc.bus.stats.transmitted
    result = gc.distribute_configuration(node.lamp_id, {'light_on_threshold': 40}, actor)
    assert result.state is CommandState.REJECTED
    assert gc.bus.stats.transmitted == before
    assert node.process_incoming() == []
    assert node.config is old


def test_direct_transport_does_not_manufacture_privilege(pair):
    gc, node = pair
    for subtype in (ControlSubtype.RESET_ENERGY, ControlSubtype.SET_MODE):
        payload = encode_payload(MessageType.CONTROL_COMMAND, {
            'subtype': subtype, 'command_id': subtype.value, 'parameter': 0,
            'target_state': LampState.UNKNOWN, 'actor': Actor('viewer', Role.VIEWER)})
        gc.bus.send(Frame(0, 1, MessageType.CONTROL_COMMAND, payload, sequence=list(ControlSubtype).index(subtype)))
        ack = node.process_incoming()[0]
        assert decode_payload(MessageType.CONTROL_ACK, ack.payload)['execution_status'] is CommandState.REJECTED


def test_delivery_and_ack_are_not_actual_verification(pair, operator):
    gc, node = pair
    node.step(healthy_sources())  # even a matching PRE-command observation is stale
    record = gc.forward_control(node.lamp_id, ControlSubtype.LAMP_ON, operator)
    assert record.state is CommandState.RECEIVED
    assert record.executed_ticks is None
    pump(gc, node)
    assert record.state is CommandState.ACKNOWLEDGED
    assert not record.succeeded
    assert record.verified_ticks is None
    node.step(healthy_sources())
    pump(gc, node)
    assert record.succeeded


def test_observation_mismatch_fails_instead_of_false_verification(pair, operator):
    gc, node = pair
    result = gc.forward_control(node.lamp_id, ControlSubtype.LAMP_ON, operator)
    pump(gc, node)
    node.step(healthy_sources(current=0, power=0, switching_feedback=LampState.OFF))
    pump(gc, node)
    assert result.state is CommandState.FAILED
    assert not result.succeeded
    assert node.control.lamp_is_on  # failure does not silently switch lighting off


def test_command_timeout_and_late_response_cannot_resurrect(pair, operator):
    gc, node = pair
    record = gc.forward_control(node.lamp_id, ControlSubtype.LAMP_ON, operator)
    for _ in range(gc.config.poll_retry_count + 1):
        gc.clock.advance(gc.config.poll_timeout_ticks)
        gc.collect_responses()
    assert record.state is CommandState.FAILED
    pump(gc, node)
    node.step(healthy_sources())
    pump(gc, node)
    assert record.state is CommandState.FAILED


def test_duplicate_command_never_retransmits(pair, operator):
    gc, node = pair
    first = gc.forward_control(node.lamp_id, ControlSubtype.LAMP_ON, operator, command_id='stable')
    count = gc.bus.stats.transmitted
    duplicate = gc.forward_control(node.lamp_id, ControlSubtype.LAMP_ON, operator, command_id='stable')
    assert duplicate is first
    assert gc.bus.stats.transmitted == count
    pump(gc, node)
    assert node.control.lamp_is_on


@pytest.mark.parametrize('version', [0, 1, PROTOCOL_VERSION + 1, 255])
def test_unsupported_version_rejected_before_payload(version):
    wire = bytearray(Frame(1, 0, MessageType.HEARTBEAT_ACK).encode())
    wire[1] = version
    wire[-2:] = crc16_xmodem(wire[:-2]).to_bytes(2, 'big')
    with pytest.raises(ProtocolError):
        decode_frame(bytes(wire))


def test_malformed_frame_does_not_consume_sequence_or_finish_poll(pair):
    gc, node = pair
    gc.poll()
    valid = node.process_incoming()[0]
    reg = gc.registration_for(node.lamp_id)
    gc.receive(replace(valid, payload=b'broken'))
    gc.collect_responses()
    assert reg.sequences.newest is None
    assert reg.last_seen_ticks is None
    assert reg.awaiting_response
    gc.receive(valid)
    gc.collect_responses()
    assert reg.sequences.newest == valid.sequence
    assert not reg.awaiting_response
    assert reg.status['actual_state'] is LampState.UNKNOWN


def test_wrong_destination_or_version_does_not_poison_receive(pair):
    gc, node = pair
    gc.poll()
    valid = node.process_incoming()[0]
    for bad in (replace(valid, destination=3), replace(valid, protocol_version=99)):
        gc.receive(bad)
        gc.collect_responses()
    assert gc.registration_for(node.lamp_id).sequences.newest is None
    gc.receive(valid)
    gc.collect_responses()
    assert gc.registration_for(node.lamp_id).sequences.newest == valid.sequence


def test_full_sequence_reuse_and_bounded_history():
    tracker = SequenceTracker()
    for sequence in range(65536):
        assert tracker.classify(sequence) == 'new'
        tracker.record(sequence)
    assert tracker.classify(0) == 'new'
    tracker.record(0)
    assert tracker.classify(0) == 'duplicate'
    assert tracker.classify(65000) == 'stale'
    assert len(tracker.counts()) <= tracker.window + 1


def test_transmit_wraps_on_both_nodes(pair):
    gc, node = pair
    gc._sequence = node._sequence = 65535
    gc.poll()
    response = pump(gc, node)[0]
    assert gc._sequence == response.sequence == 0
    assert gc.registration_for(node.lamp_id).last_seen_ticks is not None


def test_attached_silent_node_waits_retries_and_recovers(pair):
    gc, node = pair
    reg = gc.registration_for(node.lamp_id)
    assert gc.poll() == {1: False}
    assert reg.awaiting_response
    transmitted = gc.bus.stats.transmitted
    gc.clock.advance(gc.config.poll_timeout_ticks - 1)
    gc.poll()
    assert gc.bus.stats.transmitted == transmitted
    gc.clock.advance(1)
    gc.service_timeouts()
    assert gc.bus.stats.transmitted == transmitted + 1
    assert reg.comm.state is CommState.RETRY
    for _ in range(gc.config.poll_retry_count):
        gc.clock.advance(gc.config.poll_timeout_ticks)
        gc.service_timeouts()
    assert reg.comm.state is CommState.COMM_FAULT
    assert not reg.awaiting_response
    # Discard obsolete requests at the node; only a current matched response recovers.
    node.process_incoming()
    gc.poll()
    pump(gc, node)
    assert reg.comm.state is CommState.RECOVERY
    gc.poll()
    pump(gc, node)
    assert reg.comm.state is CommState.COMM_HEALTHY


def test_corrupt_request_does_not_abort_other_nodes(pair, lamp_identity):
    gc, node = pair
    identity = lamp_identity.with_lamp(type(node.lamp_id)('LAMP-02'))
    cfg = make_lamp_config(identity.lamp_id, bus_address=2)
    second = LampNode(identity, cfg.bus_address, cfg, bus=gc.bus)
    gc.register_node(second.lamp_id, second.bus_address)
    gc.bus.corrupt_next_frame()
    gc.poll()
    pump(gc, second)
    assert gc.registration_for(second.lamp_id).last_seen_ticks is not None
    assert gc.registration_for(node.lamp_id).last_seen_ticks is None


@pytest.mark.parametrize('version,accepted', [(1, True), (2, True), (0, False)])
def test_first_configuration_version(pair, engineer, version, accepted):
    gc, node = pair
    assert node.config_version == 0
    record = gc.distribute_configuration(node.lamp_id, {'light_on_threshold': 40}, engineer, version)
    assert not record.succeeded
    pump(gc, node)
    assert record.succeeded is accepted
    assert node.config_version == (version if accepted else 0)


def test_config_ordering_and_readback(pair, engineer):
    gc, node = pair
    for version, expected in [(1, True), (2, True), (1, False), (2, False), (0, False)]:
        record = gc.distribute_configuration(node.lamp_id, {'fault_confirmation_count': 5}, engineer, version)
        pump(gc, node)
        assert record.succeeded is expected
        ack = gc.registration_for(node.lamp_id).configuration
        assert ack['config_version'] == version
        assert ack['accepted'] is expected
        assert ack['reason']
    assert node.config_version == 2
    gc.read_configuration(node.lamp_id)
    pump(gc, node)
    assert gc.registration_for(node.lamp_id).configuration['parameters']['fault_confirmation_count'] == 5


@pytest.mark.parametrize('parameters', [{'unknown': 1}, {'configured_mode': -1}, {'configured_mode': 99}, {'fault_confirmation_count': 0}])
def test_invalid_config_is_atomic_and_nacks(pair, engineer, parameters):
    gc, node = pair
    previous = node.config
    record = gc.distribute_configuration(node.lamp_id, parameters, engineer)
    pump(gc, node)
    assert record.state is CommandState.FAILED
    assert node.config is previous
    assert node.config_version == 0


def test_mode_single_source_through_both_paths(pair, engineer):
    gc, node = pair
    node.set_configured_mode(ConfiguredMode.FIXED_SCHEDULE, engineer)
    assert node.config.configured_mode is node.control.configured_mode
    command = gc.distribute_configuration(node.lamp_id, {'configured_mode': 1}, engineer, config_version=2)
    pump(gc, node)
    assert command.succeeded
    assert node.config.configured_mode is ConfiguredMode.AUTO_SCHEDULE_SENSOR
    assert node.control.effective_mode.value == node.config.configured_mode.value


def test_identity_time_heartbeat_ack_dispatch(pair, admin):
    gc, node = pair
    gc.identify(node.lamp_id)
    gc.synchronize_time(actor=admin)
    pump(gc, node)
    reg = gc.registration_for(node.lamp_id)
    assert reg.identity_ack['lamp_id'] == str(node.lamp_id)
    assert reg.time_ack['local_ticks'] == gc.clock.ticks
    gc.poll(MessageType.HEARTBEAT)
    pump(gc, node)
    assert reg.heartbeat_ack['local_ticks'] == gc.clock.ticks


def test_time_distribution_denied_before_bus(pair, viewer):
    gc, node = pair
    before = gc.bus.stats.transmitted
    with pytest.raises(AuthorizationError):
        gc.synchronize_time(actor=viewer)
    assert gc.bus.stats.transmitted == before


@pytest.mark.parametrize('day', [1, 2, 100, 86400000])
def test_always_on_all_boundaries_and_no_transition(day):
    schedule = Schedule.always_on(day)
    assert all(schedule.is_on(t) for t in (0, 1, day // 2, day - 1, day, day + 1))
    assert schedule.next_transition(0) is None
    assert schedule.next_transition(day - 1) is None


def test_schedule_overlapping_boundaries_are_not_false_transitions():
    schedule = Schedule(10, (TimeWindow(1, 6), TimeWindow(4, 9)))
    assert schedule.next_transition(2) == 9
    assert Schedule(10, (TimeWindow(0, 5), TimeWindow(5, 10))).next_transition(3) is None


def test_hysteresis_margin_affects_both_boundaries(lamp_identity):
    control = ControlModel(make_lamp_config(lamp_identity.lamp_id, light_hysteresis=20))
    assert control.decide(45, 0).commanded_state is LampState.OFF
    assert control.decide(40, 1).commanded_state is LampState.ON
    assert control.decide(155, 2).commanded_state is LampState.ON
    assert control.decide(160, 3).commanded_state is LampState.OFF
    assert control.decide(100, 4).commanded_state is LampState.OFF


def confirmed_fault(node):
    for tick in (1000, 2000, 3000):
        node.step(healthy_sources(current=0, power=0), ticks=tick)
    return node.faults.active_faults[0]


def test_persistent_fault_does_not_reset_notification_deadlines(lamp_node):
    fault = confirmed_fault(lamp_node)
    lamp_node.step(healthy_sources(current=0, power=0), ticks=40000)
    assert fault.notification_state is NotificationState.REMINDER_DUE
    lamp_node.step(healthy_sources(current=0, power=0), ticks=160000)
    assert fault.notification_state is NotificationState.ESCALATED
    assert lamp_node.control.lamp_is_on
    events = lamp_node.events.filter(related_fault_id=fault.fault_id)
    assert set(e.event_id for e in events) <= set(fault.related_event_ids)
    assert sum(e.event_type is EventType.FAULT_ESCALATED for e in events) == 1


def test_illegal_fault_transition_is_audited_without_mutation(lamp_node, engineer):
    fault = confirmed_fault(lamp_node)
    before = fault.state
    with pytest.raises(IllegalTransitionError):
        lamp_node.start_repair(fault.fault_id, engineer)
    assert fault.state is before
    event = lamp_node.events.filter(event_type=EventType.FAULT_TRANSITION_REJECTED)[-1]
    assert event.actor == engineer.actor_id
    assert event.event_id in fault.related_event_ids


@pytest.mark.parametrize('operation', ['acknowledge_fault', 'start_repair', 'report_repaired', 'verify_repair'])
def test_fault_actor_authorization_before_action(lamp_node, viewer, operation):
    fault = confirmed_fault(lamp_node)
    state = fault.state
    kwargs = {'verified': True} if operation == 'verify_repair' else {}
    with pytest.raises(AuthorizationError):
        getattr(lamp_node, operation)(fault.fault_id, viewer, **kwargs)
    assert fault.state is state
    assert lamp_node.events.events[-1].actor == viewer.actor_id


def test_configured_retention_is_enforced_by_node(lamp_identity, admin):
    cfg = make_lamp_config(lamp_identity.lamp_id, minimum_retention_ticks=5000)
    node = LampNode(lamp_identity, cfg.bus_address, cfg)
    node.step(healthy_sources())
    record = node.storage.records[0]
    node.storage.mark_uploaded(record.sequence)
    node.storage.mark_confirmed(record.sequence)
    with pytest.raises(StorageError):
        node.storage.delete(record.sequence, admin, record.timestamp.ticks + 4999)
    node.storage.delete(record.sequence, admin, record.timestamp.ticks + 5000)
    event = node.events.filter(event_type=EventType.RECORD_DELETED)[-1]
    assert event.actor == admin.actor_id
    assert event.event_data['sequence_number'] == record.sequence


@pytest.mark.parametrize('role', [Role.VIEWER, Role.OPERATOR, Role.ENGINEER])
def test_retained_deletion_requires_administration(role):
    store = RecordStore()
    record = store.create(RecordType.EVENT, {}, Timestamp(0, TimeSyncState.UNCERTAIN), 'device')
    store.mark_uploaded(record.sequence)
    store.mark_confirmed(record.sequence)
    with pytest.raises(AuthorizationError):
        store.delete(record.sequence, Actor('denied', role), 10)
    assert store.retained == (record,)


def test_bare_store_audits_deletion_and_reclaims_capacity(admin):
    store = RecordStore(capacity=1)
    record = store.create(RecordType.EVENT, {}, Timestamp(0, TimeSyncState.UNCERTAIN), 'device')
    store.mark_uploaded(record.sequence)
    store.mark_confirmed(record.sequence)
    store.delete(record.sequence, admin, 10)
    assert store.events.events[-1].actor == admin.actor_id
    with pytest.raises(StorageError):
        store.delete(record.sequence, admin, 11)
    store.create(RecordType.EVENT, {}, Timestamp(12, TimeSyncState.UNCERTAIN), 'device')


def test_corrupt_record_never_uploaded_or_confirmed(group_controller):
    gc = group_controller
    record = gc.storage.create(RecordType.EVENT, {}, Timestamp(0, TimeSyncState.UNCERTAIN), gc.identity.device_id)
    gc.storage.corrupt(record.sequence)
    assert gc.forward_upstream() == {'uploaded': 0, 'confirmed': 0, 'failed': 1}
    assert gc.upstream.uploaded == []
    with pytest.raises(StorageError):
        gc.storage.mark_confirmed(record.sequence)
    assert gc.events.filter(event_type=EventType.RECORD_CORRUPT)


def test_ack_round_trip_has_execution_evidence():
    fields = {'command_id': 'c', 'execution_status': CommandState.ACKNOWLEDGED,
              'actual_state': LampState.UNKNOWN, 'request_sequence': 123,
              'effective_mode': __import__('sslv1.enums', fromlist=['OperatingMode']).OperatingMode.FORCE_ON,
              'active_override': __import__('sslv1.enums', fromlist=['OverrideState']).OverrideState.FORCE_ON,
              'configured_mode': ConfiguredMode.AUTO_SENSOR, 'energy': 3.5}
    assert decode_payload(MessageType.CONTROL_ACK, encode_payload(MessageType.CONTROL_ACK, fields)) == fields


@pytest.mark.parametrize('extra', [b'\x00', b'junk', b'\xff' * 8])
def test_payload_trailing_bytes_rejected(extra):
    payload = encode_payload(MessageType.HEARTBEAT_ACK, {'local_ticks': 1})
    with pytest.raises(ProtocolError):
        decode_payload(MessageType.HEARTBEAT_ACK, payload + extra)


def test_measurement_uncertainty_and_absence_survive_bus(pair):
    gc, node = pair
    node.step(healthy_sources(power=None, voltage=None, current=None))
    gc.poll(MessageType.MEASUREMENT_REQUEST)
    pump(gc, node)
    measurement = gc.measurements()[0]
    assert measurement.timestamp.uncertain
    assert measurement.voltage is measurement.current is measurement.power is None


@pytest.mark.parametrize('value', [float('nan'), float('inf'), 'bad'])
def test_nonfinite_or_nonnumeric_config_rejected(lamp_identity, value):
    with pytest.raises(ConfigurationError):
        make_lamp_config(lamp_identity.lamp_id, light_on_threshold=value)


def test_negative_or_nonfinite_energy_samples_do_not_decrement(lamp_node):
    lamp_node.step(healthy_sources())
    energy = lamp_node._energy
    for power in (-1, float('nan'), float('inf')):
        lamp_node.step(healthy_sources(power=power))
        assert lamp_node._energy == energy


def test_missing_current_cannot_verify_off(lamp_node, operator):
    record = lamp_node.force_off(operator)
    lamp_node.step(healthy_sources(switching_feedback=LampState.OFF, current=None, power=0))
    assert record.state is CommandState.ACKNOWLEDGED
    assert lamp_node.last_measurement.actual_state is LampState.UNKNOWN


def test_backwards_sync_is_not_falsely_synchronized(lamp_node):
    lamp_node.time.synchronize(1000)
    stamp = lamp_node.time.synchronize(1)
    assert stamp.ticks == 1000
    assert stamp.sync_state is TimeSyncState.UNCERTAIN


def test_invalid_sensor_cannot_drive_automatic_control(lamp_node):
    lamp_node.step(healthy_sources(light_level=0, sensor_status=SensorStatus.INVALID))
    assert not lamp_node.control.lamp_is_on


def test_lamp_replay_cache_is_idempotent_and_rejects_changed_payload(pair, engineer):
    gc, node = pair
    request = Frame(0, 1, MessageType.CONFIG_WRITE, encode_payload(MessageType.CONFIG_WRITE,
        {'config_version': 1, 'parameters': {'light_on_threshold': 40}, 'actor': engineer}), 42)
    node.receive(request)
    first = node.process_incoming()[0]
    assert node.config_version == 1
    node.receive(request)
    repeated = node.process_incoming()[0]
    assert decode_payload(MessageType.CONFIG_ACK, repeated.payload)['accepted']
    assert repeated.sequence != first.sequence
    assert node.config_version == 1
    changed = replace(request, payload=encode_payload(MessageType.CONFIG_WRITE,
        {'config_version': 2, 'parameters': {'light_on_threshold': 30}, 'actor': engineer}))
    node.receive(changed)
    assert node.process_incoming() == []
    assert node.config.light_on_threshold == 40
    node.receive(replace(request, sequence=1))
    assert node.process_incoming() == []
    assert node.config_version == 1


def test_event_report_loss_retry_and_confirm_does_not_lose_history(pair, operator):
    gc, node = pair
    node.return_to_auto(operator)
    gc.poll(MessageType.EVENT_REPORT)
    lost = node.process_incoming()[0]  # deliberately do not deliver
    event_id = decode_payload(MessageType.EVENT_REPORT, lost.payload)['event_id']
    assert not node._reported_events.get(event_id)
    gc.clock.advance(gc.config.poll_timeout_ticks)
    gc.service_timeouts()
    pump(gc, node)
    reg = gc.registration_for(node.lamp_id)
    assert reg.confirmed_event_id == event_id
    assert event_id in {e.event_id for e in node.events}
    gc.poll(MessageType.EVENT_REPORT)
    pump(gc, node)
    assert node._reported_events[event_id]
    matching = [r for r in gc.storage.records if r.payload.get('event_id') == event_id]
    assert len(matching) == 1
    assert event_id in {e.event_id for e in node.events}


def test_fault_report_is_aggregated_without_mutating_local_lifecycle(pair):
    gc, node = pair
    fault = confirmed_fault(node)
    state = fault.state
    gc.poll(MessageType.FAULT_REPORT)
    pump(gc, node)
    records = [r for r in gc.storage.records if r.record_type is RecordType.FAULT]
    assert records[-1].payload['fault_id'] == fault.fault_id
    assert fault.state is state


def test_notification_does_not_overwrite_confirmation_reason(lamp_node):
    fault = confirmed_fault(lamp_node)
    assert 'confirmed after' in fault.confirmation_reason
    reason = fault.confirmation_reason
    lamp_node.notifications.tick(fault, 160000)
    assert fault.confirmation_reason == reason
    assert fault.notification_reason
    event = lamp_node.events.filter(event_type=EventType.FAULT_ESCALATED)[-1]
    assert event.timestamp.ticks == 160000
    assert event.actor is None


def test_repair_event_actor_and_original_evidence_are_preserved(lamp_node, operator, engineer):
    fault = confirmed_fault(lamp_node)
    evidence = dict(fault.evidence)
    lamp_node.step(healthy_sources(current=.01, power=2.3), ticks=4000)
    assert fault.evidence == evidence
    assert fault.latest_evidence != evidence
    lamp_node.acknowledge_fault(fault.fault_id, operator, ticks=5000)
    lamp_node.start_repair(fault.fault_id, engineer, ticks=6000)
    lamp_node.report_repaired(fault.fault_id, engineer, ticks=7000)
    lamp_node.verify_repair(fault.fault_id, engineer, True, ticks=8000)
    events = lamp_node.events.filter(related_fault_id=fault.fault_id)
    reported = [e for e in events if e.event_type is EventType.FAULT_REPAIR_REPORTED][0]
    assert reported.actor == engineer.actor_id
    assert reported.timestamp.ticks == 7000
    assert reported.event_id in fault.related_event_ids
    assert events[-1].event_type is EventType.FAULT_CLOSED
    assert events[-1].actor == engineer.actor_id


def test_restart_invalidates_unverified_command(lamp_node, operator):
    result = lamp_node.force_on(operator)
    lamp_node.restart()
    lamp_node.step(healthy_sources())
    assert result.state is CommandState.FAILED
    assert result.verified_ticks is None


def test_mode_command_is_versioned_and_audited(lamp_node, engineer):
    result = lamp_node.set_configured_mode(ConfiguredMode.FIXED_SCHEDULE, engineer)
    assert result.succeeded
    assert lamp_node.config_version == 1
    event = lamp_node.events.filter(event_type=EventType.MODE_CHANGED)[-1]
    assert event.actor == engineer.actor_id
    assert event.event_data['previous_value'] == ConfiguredMode.AUTO_SENSOR.value
    assert event.event_data['new_value'] == ConfiguredMode.FIXED_SCHEDULE.value
    lamp_node.restart()
    assert lamp_node.config_version == 1
    assert lamp_node.config.configured_mode is ConfiguredMode.FIXED_SCHEDULE


def test_remote_retention_update_changes_store_policy(pair, engineer):
    gc, node = pair
    result = gc.distribute_configuration(node.lamp_id, {'minimum_retention_ticks': 5000}, engineer)
    pump(gc, node)
    assert result.succeeded
    assert node.storage.retention.minimum_retention_ticks == 5000
    event = node.events.filter(event_type=EventType.CONFIG_CHANGED)[-1]
    assert event.actor == engineer.actor_id
    assert event.event_data['previous']['minimum_retention_ticks'] == -1
    assert event.event_data['applied']['minimum_retention_ticks'] == 5000


def test_bad_measurement_numbers_cannot_classify_as_normal(lamp_config):
    from sslv1.diagnostics import DiagnosticEngine, DiagnosticEvidence
    evidence = DiagnosticEvidence(LampState.ON, LampState.ON, 230, float('nan'), 100)
    assert not DiagnosticEngine(lamp_config).evaluate(evidence).is_normal


def test_missing_evidence_cannot_classify_as_normal(lamp_config):
    from sslv1.diagnostics import DiagnosticEngine, DiagnosticEvidence
    evidence = DiagnosticEvidence(LampState.OFF, LampState.OFF, 230, None, None)
    assert not DiagnosticEngine(lamp_config).evaluate(evidence).is_normal


def test_storage_crc_protects_time_validity(group_controller):
    gc = group_controller
    record = gc.storage.create(RecordType.EVENT, {}, Timestamp(0, TimeSyncState.UNCERTAIN), gc.identity.device_id)
    record.timestamp = Timestamp(0, TimeSyncState.SYNCHRONIZED)
    assert not record.is_valid()
    assert gc.forward_upstream()['confirmed'] == 0


def test_sample_time_is_shared_consistently(pair, lamp_identity):
    gc, node = pair
    other_id = lamp_identity.with_lamp(type(node.lamp_id)('OTHER'))
    cfg = make_lamp_config(other_id.lamp_id, bus_address=2)
    second = LampNode(other_id, cfg.bus_address, cfg, clock=gc.clock)
    node.step(healthy_sources(), ticks=10000)
    second.step(healthy_sources(), ticks=10000)
    assert gc.clock.ticks == 10000
    assert node.last_measurement.timestamp.ticks == second.last_measurement.timestamp.ticks == 10000


def test_unregistration_fails_pending_command(pair, operator):
    gc, node = pair
    result = gc.forward_control(node.lamp_id, ControlSubtype.LAMP_ON, operator)
    gc.unregister_node(1)
    assert result.state is CommandState.FAILED
    assert not gc._pending


def test_large_energy_payload_round_trip(pair):
    gc, node = pair
    node._energy = 1 << 35
    node.step(healthy_sources(power=0))
    gc.poll(MessageType.MEASUREMENT_REQUEST)
    pump(gc, node)
    assert gc.measurements()[0].energy == node._energy


def test_gc_deletion_audits_structured_actor(group_controller, admin):
    gc = group_controller
    record = gc.storage.create(RecordType.EVENT, {}, Timestamp(0, TimeSyncState.UNCERTAIN), gc.identity.device_id)
    gc.forward_upstream()
    gc.storage.delete(record.sequence, admin, 10)
    event = gc.events.filter(event_type=EventType.RECORD_DELETED)[-1]
    assert event.actor == admin.actor_id
    assert event.event_data['sequence_number'] == record.sequence


def test_confirmation_requires_consecutive_matching_classification(lamp_node):
    from sslv1.diagnostics import DiagnosticEvidence, DiagnosticEngine
    engine = DiagnosticEngine(lamp_node.config)
    a = engine.evaluate(DiagnosticEvidence(LampState.ON, LampState.ON, 230, 0, 0))
    b = engine.evaluate(DiagnosticEvidence(LampState.ON, LampState.ON, 90, .4, 36, voltage_valid=False))
    for tick, result in enumerate([a, b, a, b, a, b], 1):
        lamp_node.faults.observe(lamp_node.site_id, lamp_node.group_id, lamp_node.lamp_id, result, tick)
    assert all(not f.is_confirmed for f in lamp_node.faults.active_faults)


def test_recurrence_links_to_closed_fault(lamp_node, operator, engineer):
    first = confirmed_fault(lamp_node)
    lamp_node.acknowledge_fault(first.fault_id, operator)
    lamp_node.start_repair(first.fault_id, engineer)
    lamp_node.report_repaired(first.fault_id, engineer)
    lamp_node.verify_repair(first.fault_id, engineer, True)
    lamp_node.step(healthy_sources(current=0, power=0), ticks=4000)
    assert lamp_node.faults.active_faults[0].previous_fault_id == first.fault_id


def test_conflicting_duplicate_id_is_rejected_without_action(pair, operator):
    gc, node = pair
    original = gc.forward_control(node.lamp_id, ControlSubtype.LAMP_ON, operator, command_id='same-id')
    before = gc.bus.stats.transmitted
    conflict = gc.forward_control(node.lamp_id, ControlSubtype.LAMP_OFF, operator, command_id='same-id')
    assert conflict.state is CommandState.REJECTED
    assert gc.commands.get('same-id') is original
    assert gc.bus.stats.transmitted == before


def test_forged_actual_verification_ack_cannot_complete_command(pair, operator):
    gc, node = pair
    result = gc.forward_control(node.lamp_id, ControlSubtype.LAMP_ON, operator)
    response = node.process_incoming()[0]
    fields = decode_payload(MessageType.CONTROL_ACK, response.payload)
    fields.update(execution_status=CommandState.ACTUAL_STATE_VERIFIED, actual_state=LampState.OFF)
    gc.receive(replace(response, payload=encode_payload(MessageType.CONTROL_ACK, fields)))
    gc.collect_responses()
    assert result.state is CommandState.RECEIVED
    assert gc.registration_for(node.lamp_id).sequences.newest is None
    gc.receive(response)
    gc.collect_responses()
    assert result.state is CommandState.ACKNOWLEDGED


def test_long_audit_reason_round_trips_without_loss():
    fields = {'event_id': 1, 'event_type': EventType.CONFIG_CHANGED,
              'reason': 'engineering configuration ' * 40, 'actor': 'engineer'}
    result = decode_payload(MessageType.EVENT_REPORT, encode_payload(MessageType.EVENT_REPORT, fields))
    assert result['reason'] == fields['reason']
    assert result['actor'] == 'engineer'


def test_offline_measurement_history_is_replayed_and_retained(pair):
    gc, node = pair
    for power in (23, 46, 69):
        node.step(healthy_sources(power=power, current=power/230))
    original = tuple(node.storage.pending_upload)
    assert len(original) == 3
    for _ in range(4):  # fourth request confirms third record
        gc.poll(MessageType.MEASUREMENT_REQUEST)
        pump(gc, node)
    records = [r for r in gc.storage.records if r.record_type is RecordType.MEASUREMENT]
    assert [r.payload['power'] for r in records[:3]] == [23, 46, 69]
    assert len(node.storage.pending_upload) == 0
    assert node.storage.retained == original


def test_lost_measurement_response_retries_without_duplicate_history(pair):
    gc, node = pair
    node.step(healthy_sources())
    gc.poll(MessageType.MEASUREMENT_REQUEST)
    node.process_incoming()  # lost response
    assert node.storage.pending_upload
    gc.clock.advance(gc.config.poll_timeout_ticks)
    gc.service_timeouts()
    pump(gc, node)
    gc.poll(MessageType.MEASUREMENT_REQUEST)
    pump(gc, node)
    assert not node.storage.pending_upload
    assert len(node.storage.retained) == 1


def test_group_buffers_command_and_sync_audit(pair, engineer, admin):
    gc, node = pair
    gc.distribute_configuration(node.lamp_id, {'light_on_threshold': 40}, engineer)
    gc.synchronize_time(actor=admin)
    pump(gc, node)
    events = [r.payload for r in gc.storage.records if 'group_event_id' in r.payload]
    assert any(e['actor'] == engineer.actor_id for e in events)
    assert any(e['event_type'] == EventType.TIME_SYNCHRONIZED.value for e in events)


def test_denied_deletion_is_audited_with_identity(viewer):
    store = RecordStore()
    record = store.create(RecordType.EVENT, {}, Timestamp(0, TimeSyncState.UNCERTAIN), 'device')
    with pytest.raises(AuthorizationError):
        store.delete(record.sequence, viewer, 10)
    event = store.events.events[-1]
    assert event.actor == viewer.actor_id
    assert event.event_data['sequence_number'] == record.sequence
    assert event.event_type is EventType.COMMAND_REJECTED


def test_late_ack_is_rejected_even_if_timeouts_were_not_serviced(pair, operator):
    gc, node = pair
    record = gc.forward_control(node.lamp_id, ControlSubtype.LAMP_ON, operator)
    response = node.process_incoming()[0]
    gc.clock.advance(gc.config.poll_timeout_ticks * (gc.config.poll_retry_count + 1))
    gc.receive(response)
    gc.collect_responses()
    assert record.state is CommandState.FAILED
    assert gc.registration_for(node.lamp_id).sequences.newest is None


def test_command_audit_uses_supplied_action_time(lamp_node, operator):
    lamp_node.force_on(operator, ticks=1234)
    for event in lamp_node.events.filter(event_type=EventType.COMMAND_RECEIVED):
        assert event.timestamp.ticks == 1234


def test_inconsistent_command_subtype_cannot_escalate_local_privileges(lamp_node, operator):
    from sslv1.command import Command
    from sslv1.enums import CommandType
    from sslv1.errors import CommandError
    with pytest.raises(CommandError):
        Command('escalation', CommandType.SET_MODE, lamp_node.identity, operator, 0,
                subtype=ControlSubtype.LAMP_ON, parameters={'mode': 2})
    assert lamp_node.config.configured_mode is ConfiguredMode.AUTO_SENSOR


def test_delayed_timeout_service_cannot_extend_absolute_deadline(pair, operator):
    gc, node = pair
    result = gc.forward_control(node.lamp_id, ControlSubtype.LAMP_ON, operator)
    gc.clock.advance(900)
    gc.service_timeouts()
    gc.clock.advance(500)
    gc.service_timeouts()
    gc.clock.advance(100)
    gc.service_timeouts()
    assert result.state is CommandState.FAILED
    assert not gc._pending


def test_retry_exhaustion_does_not_invent_missed_exchanges(pair):
    gc, node = pair
    gc.config.poll_retry_count = 0
    gc.poll()
    gc.clock.advance(gc.config.poll_timeout_ticks)
    gc.service_timeouts()
    reg = gc.registration_for(node.lamp_id)
    assert reg.comm.state is CommState.COMM_FAULT
    assert reg.comm.consecutive_failures == 1


def test_sequence_window_must_fit_modular_half_space():
    from sslv1.errors import ValidationError
    with pytest.raises(ValidationError):
        SequenceTracker(window=32768)


@pytest.mark.parametrize('operation', ['configuration', 'mode'])
def test_fractional_wire_config_is_rejected_not_silently_coerced(pair, engineer, operation):
    gc, node = pair
    old = node.config
    sent = gc.bus.stats.transmitted
    if operation == 'configuration':
        record = gc.distribute_configuration(node.lamp_id, {'light_on_threshold': 40.5}, engineer)
    else:
        record = gc.forward_control(node.lamp_id, ControlSubtype.SET_MODE, engineer, parameter=.5)
    assert record.state is CommandState.FAILED
    assert node.config is old
    assert gc.bus.stats.transmitted == sent


def test_malformed_actor_is_a_protocol_error(engineer):
    payload = encode_payload(MessageType.TIME_SYNC, {'master_ticks': 0, 'actor': Actor('x', Role.ADMIN)})
    # Metadata actor-present, length, ID, role, authenticated; replace ID with empty.
    malformed = payload[:-5] + b'\x00\x00' + payload[-2:]
    with pytest.raises(ProtocolError):
        decode_payload(MessageType.TIME_SYNC, malformed)


def test_fractional_local_mode_is_rejected_without_mutation(lamp_node, engineer):
    from sslv1.command import Command
    from sslv1.enums import CommandType
    before = lamp_node.config
    record = lamp_node.commands.submit(Command('fractional-mode', CommandType.SET_MODE,
        lamp_node.identity, engineer, 0, parameters={'mode': .5}), 0)
    assert record.state is CommandState.FAILED
    assert lamp_node.config is before
    assert lamp_node.config_version == 0


@pytest.mark.parametrize('light,initial', [(-1, False), (100_001, True), (float('inf'), True)])
def test_invalid_light_value_does_not_drive_automatic_control(lamp_config, light, initial):
    control = ControlModel(lamp_config, _lamp_is_on=initial)
    decision = control.decide(light, 0)
    assert control.lamp_is_on is initial
    assert decision.commanded_state is (LampState.ON if initial else LampState.OFF)
    assert 'no valid light' in decision.reason


@pytest.mark.parametrize('name', ['max_nodes', 'poll_timeout_ticks', 'poll_retry_count', 'storage_capacity'])
@pytest.mark.parametrize('value', [float('nan'), 1.5, True, '2'])
def test_group_configuration_rejects_invalid_numeric_types(name, value):
    from sslv1.nodes.group_controller import GroupControllerConfig
    with pytest.raises(ConfigurationError):
        GroupControllerConfig(**{name: value}).validated()
