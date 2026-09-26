"""Group controller, multi-node and offline/recovery tests.

Covers: node registration and addressing, polling, communication failure,
retry, degraded communication, communication recovery, multi-node isolation,
time synchronization, offline timestamps, configuration distribution and
store-and-forward.
"""


import pytest

from sslv1.enums import (
    CommState,
    LampState,
    MessageType,
    TimeSyncState,
)
from sslv1.identity import BusAddress, DeviceIdentity, Identifier
from sslv1.nodes import (
    GroupController,
    GroupControllerConfig,
    LampNode,
)

from conftest import GROUP, PRODUCT, SITE, healthy_sources, make_lamp_config


def build_node(clock, bus, authorizer, lamp_number: int) -> LampNode:
    identity = DeviceIdentity(
        product_id=PRODUCT,
        site_id=SITE,
        group_id=GROUP,
        lamp_id=Identifier("LAMP-%02d" % lamp_number),
    )
    config = make_lamp_config(identity.lamp_id, bus_address=lamp_number)
    node = LampNode(identity, BusAddress(lamp_number), config, clock=clock, bus=bus,
                    authorizer=authorizer)
    node.start()
    return node


def run_cycle(group: GroupController, nodes, ticks, message_type=MessageType.STATUS_REQUEST):
    group.poll(message_type)
    for node in nodes:
        for frame in node.process_incoming():
            group.bus.send(frame)
    group.collect_responses()


# --------------------------------------------------------------------------
# 40. group controller handling multiple nodes
# --------------------------------------------------------------------------
def test_group_controller_manages_multiple_nodes(clock, bus, authorizer,
                                                 group_controller):
    nodes = [build_node(clock, bus, authorizer, i) for i in range(1, 5)]
    for node in nodes:
        group_controller.register_node(node.lamp_id, node.bus_address)
    assert group_controller.node_count == 4

    results = group_controller.poll()
    assert results == {1: True, 2: True, 3: True, 4: True}
    for node in nodes:
        node.process_incoming()
    assert group_controller.communication_summary()["COMM_HEALTHY"] == 4


def test_group_controller_supports_the_initial_group_target(clock, bus, authorizer,
                                                            group_controller):
    nodes = [build_node(clock, bus, authorizer, i) for i in range(1, 17)]
    for node in nodes:
        group_controller.register_node(node.lamp_id, node.bus_address)
    assert group_controller.node_count == 16


def test_group_controller_is_not_limited_to_sixteen(clock, bus, authorizer,
                                                    group_identity):
    controller = GroupController(
        identity=group_identity,
        config=GroupControllerConfig(max_nodes=32),
        clock=clock,
        bus=bus,
    )
    nodes = [build_node(clock, bus, authorizer, i) for i in range(1, 25)]
    for node in nodes:
        controller.register_node(node.lamp_id, node.bus_address)
    assert controller.node_count == 24


# --------------------------------------------------------------------------
# 39. multi-node isolation
# --------------------------------------------------------------------------
def test_one_silent_node_does_not_block_the_others(clock, bus, authorizer,
                                                   group_controller):
    nodes = [build_node(clock, bus, authorizer, i) for i in range(1, 5)]
    for node in nodes:
        group_controller.register_node(node.lamp_id, node.bus_address)

    # Node 2 stops responding.
    bus.set_silent(2)
    results = group_controller.poll()
    assert results[2] is False
    assert all(results[address] for address in (1, 3, 4))

    for node in nodes:
        if int(node.bus_address) != 2:
            node.process_incoming()
    group_controller.collect_responses()

    assert group_controller.registration_for(
        Identifier("LAMP-02")
    ).comm.state is not CommState.COMM_HEALTHY
    assert group_controller.registration_for(
        Identifier("LAMP-01")
    ).comm.state is CommState.COMM_HEALTHY


def test_one_faulty_node_does_not_degrade_the_group(clock, bus, authorizer,
                                                    group_controller):
    nodes = [build_node(clock, bus, authorizer, i) for i in range(1, 4)]
    for node in nodes:
        group_controller.register_node(node.lamp_id, node.bus_address)

    for index in range(5):
        for position, node in enumerate(nodes, start=1):
            sources = healthy_sources()
            if position == 1:
                sources = healthy_sources(current=0.0, power=0.0,
                                          switching_feedback=LampState.ON)
            node.step(sources, ticks=1000 * (index + 1))

    assert nodes[0].faults.active_faults
    assert nodes[1].faults.active_faults == ()
    assert nodes[2].faults.active_faults == ()
    assert all(node.control.lamp_is_on for node in nodes[1:])


# --------------------------------------------------------------------------
# 20./21./22. communication failure, retry, degraded
# --------------------------------------------------------------------------
def test_communication_fault_is_detected_after_retries(clock, bus, authorizer,
                                                       group_controller):
    nodes = [build_node(clock, bus, authorizer, i) for i in range(1, 3)]
    for node in nodes:
        group_controller.register_node(node.lamp_id, node.bus_address)

    bus.set_silent(1)
    for _ in range(5):
        run_cycle(group_controller, nodes, 0)

    registration = group_controller.registration_for(Identifier("LAMP-01"))
    assert registration.comm.state is CommState.COMM_FAULT
    assert Identifier("LAMP-01") in group_controller.degraded_nodes()
    # The other node is unaffected.
    assert group_controller.registration_for(
        Identifier("LAMP-02")
    ).comm.state is CommState.COMM_HEALTHY


def test_communication_fault_does_not_stop_local_lighting(clock, bus, authorizer,
                                                          group_controller):
    nodes = [build_node(clock, bus, authorizer, i) for i in range(1, 3)]
    for node in nodes:
        group_controller.register_node(node.lamp_id, node.bus_address)
    bus.set_silent(1)

    for index in range(6):
        nodes[0].step(healthy_sources(light_level=10.0), ticks=1000 * (index + 1))

    # The node keeps controlling its lamp with no bus traffic at all.
    assert nodes[0].control.lamp_is_on is True
    assert nodes[0].control.effective_mode.value == "AUTO_SENSOR"


# --------------------------------------------------------------------------
# 23. communication recovery
# --------------------------------------------------------------------------
def test_communication_recovery_resynchronizes(clock, bus, authorizer,
                                               group_controller):
    nodes = [build_node(clock, bus, authorizer, i) for i in range(1, 3)]
    for node in nodes:
        group_controller.register_node(node.lamp_id, node.bus_address)

    bus.set_silent(1)
    for _ in range(5):
        run_cycle(group_controller, nodes, 0)
    assert group_controller.registration_for(
        Identifier("LAMP-01")
    ).comm.state is CommState.COMM_FAULT

    bus.set_silent(1, silent=False)
    run_cycle(group_controller, nodes, 0)
    registration = group_controller.registration_for(Identifier("LAMP-01"))
    assert registration.comm.state in (CommState.RECOVERY, CommState.COMM_HEALTHY)

    run_cycle(group_controller, nodes, 0)
    assert registration.comm.state is CommState.COMM_HEALTHY
    assert group_controller.degraded_nodes() == ()


# --------------------------------------------------------------------------
# 35./36. time synchronization and offline timestamps
# --------------------------------------------------------------------------
def test_time_synchronization_reaches_every_node(clock, bus, authorizer,
                                                 group_controller):
    nodes = [build_node(clock, bus, authorizer, i) for i in range(1, 4)]
    for node in nodes:
        group_controller.register_node(node.lamp_id, node.bus_address)

    clock.advance(5000)
    results = group_controller.synchronize_time(master_ticks=clock.ticks)
    assert results == {1: True, 2: True, 3: True}
    for node in nodes:
        node.process_incoming()
    for node in nodes:
        assert node.time.sync_state is TimeSyncState.SYNCHRONIZED
        assert node.time.ticks == clock.ticks


def test_offline_timestamps_are_flagged_uncertain(clock, bus, authorizer,
                                                  group_controller):
    node = build_node(clock, bus, authorizer, 1)
    node.time.mark_unsynchronized()
    node.time.uncertainty_threshold_ticks = 1000

    node.step(healthy_sources(), ticks=100)
    node.time.advance(5000)
    node.step(healthy_sources(), ticks=5100)

    record = node.storage.records[-1]
    assert record.timestamp.sync_state is TimeSyncState.UNCERTAIN
    assert record.timestamp.uncertain is True


def test_records_are_ordered_by_sequence_when_time_is_uncertain(clock, bus,
                                                                authorizer):
    node = build_node(clock, bus, authorizer, 1)
    node.time.mark_unsynchronized()
    for index in range(4):
        node.step(healthy_sources(), ticks=1000 * (index + 1))
    sequences = [r.sequence_number for r in node.storage.records]
    assert sequences == sorted(sequences)


# --------------------------------------------------------------------------
# 37. configuration distribution
# --------------------------------------------------------------------------
def test_configuration_distribution_is_acknowledged(clock, bus, authorizer,
                                                    group_controller, engineer):
    node = build_node(clock, bus, authorizer, 1)
    group_controller.register_node(node.lamp_id, node.bus_address)

    record = group_controller.distribute_configuration(
        node.lamp_id, {"fault_confirmation_count": 5}, engineer, config_version=2
    )
    assert record.succeeded is True

    for frame in node.process_incoming():
        group_controller.bus.send(frame)
    group_controller.collect_responses()
    assert node.config.fault_confirmation_count == 5
    assert node.config_version == 2


def test_invalid_configuration_is_rejected_by_the_node(clock, bus, authorizer,
                                                       group_controller, engineer):
    node = build_node(clock, bus, authorizer, 1)
    group_controller.register_node(node.lamp_id, node.bus_address)
    original = node.config.fault_confirmation_count

    group_controller.distribute_configuration(
        node.lamp_id, {"fault_confirmation_count": 0}, engineer, config_version=2
    )
    for frame in node.process_incoming():
        group_controller.bus.send(frame)
    group_controller.collect_responses()

    assert node.config.fault_confirmation_count == original
    assert any(e.event_type.value == "CONFIG_REJECTED" for e in node.events)


# --------------------------------------------------------------------------
# store-and-forward
# --------------------------------------------------------------------------
def test_records_are_buffered_while_upstream_is_unavailable(clock, bus, authorizer,
                                                            group_controller):
    node = build_node(clock, bus, authorizer, 1)
    group_controller.register_node(node.lamp_id, node.bus_address)
    group_controller.upstream.set_available(False)

    for index in range(3):
        node.step(healthy_sources(), ticks=1000 * (index + 1))
    run_cycle(group_controller, [node], 0, MessageType.MEASUREMENT_REQUEST)

    assert len(group_controller.storage.pending_upload) >= 1
    result = group_controller.forward_upstream()
    assert result["failed"] >= 1
    assert result["confirmed"] == 0
    # Nothing was lost and nothing was deleted.
    assert len(group_controller.storage.pending_upload) >= 1


def test_buffered_records_are_uploaded_after_recovery(clock, bus, authorizer,
                                                      group_controller):
    node = build_node(clock, bus, authorizer, 1)
    group_controller.register_node(node.lamp_id, node.bus_address)
    group_controller.upstream.set_available(False)

    for index in range(3):
        node.step(healthy_sources(), ticks=1000 * (index + 1))
    run_cycle(group_controller, [node], 0, MessageType.MEASUREMENT_REQUEST)
    pending_before = len(group_controller.storage.pending_upload)

    group_controller.upstream.set_available(True)
    result = group_controller.forward_upstream()
    assert result["confirmed"] == pending_before
    assert len(group_controller.storage.pending_upload) == 0
    # Upload confirmation did not delete the retained records.
    assert len(group_controller.storage.retained) == pending_before
    assert len(group_controller.storage) == pending_before


def test_no_duplicate_upload_of_the_same_record(clock, bus, authorizer,
                                                group_controller):
    node = build_node(clock, bus, authorizer, 1)
    group_controller.register_node(node.lamp_id, node.bus_address)

    for index in range(3):
        node.step(healthy_sources(), ticks=1000 * (index + 1))
    run_cycle(group_controller, [node], 0, MessageType.MEASUREMENT_REQUEST)

    group_controller.forward_upstream()
    uploaded_once = list(group_controller.upstream.uploaded)
    group_controller.forward_upstream()
    assert group_controller.upstream.uploaded == uploaded_once


def test_measurement_aggregation(clock, bus, authorizer, group_controller):
    nodes = [build_node(clock, bus, authorizer, i) for i in range(1, 4)]
    for node in nodes:
        group_controller.register_node(node.lamp_id, node.bus_address)

    for index in range(3):
        for node in nodes:
            node.step(healthy_sources(), ticks=1000 * (index + 1))
        run_cycle(group_controller, nodes, 0, MessageType.MEASUREMENT_REQUEST)

    assert len(group_controller.measurements()) == 3
    assert group_controller.aggregate_power() == pytest.approx(103.5 * 3)


def test_group_controller_local_storage_is_abstract(clock, bus, authorizer,
                                                    group_controller):
    """The Group Controller buffers without any physical medium being named."""
    node = build_node(clock, bus, authorizer, 1)
    group_controller.register_node(node.lamp_id, node.bus_address)
    for index in range(2):
        node.step(healthy_sources(), ticks=1000 * (index + 1))
    run_cycle(group_controller, [node], 0, MessageType.MEASUREMENT_REQUEST)
    assert len(group_controller.storage) >= 1


def test_group_snapshot_reports_communication_state(clock, bus, authorizer,
                                                    group_controller):
    nodes = [build_node(clock, bus, authorizer, i) for i in range(1, 4)]
    for node in nodes:
        group_controller.register_node(node.lamp_id, node.bus_address)
    run_cycle(group_controller, nodes, 0)
    snapshot = group_controller.snapshot()
    assert snapshot["nodes"] == 3
    assert snapshot["communication"]["COMM_HEALTHY"] == 3


def test_unregistered_frame_is_rejected(clock, bus, authorizer, group_controller):
    from sslv1.comm import Frame

    group_controller.receive(
        Frame(source=99, destination=0, message_type=MessageType.STATUS_RESPONSE,
              sequence=1)
    )
    group_controller.collect_responses()
    assert any(
        e.event_type.value == "FRAME_REJECTED" for e in group_controller.events
    )
