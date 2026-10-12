"""Failure-path checks for the proposed controller transport policy."""

from tools.controller_transport_model import AtomicRingModel, ControllerTransportModel


def drain_all(model):
    messages = []
    for _ in range(20):
        if not model.pending():
            return messages
        messages.extend(model.worker_step(1024))
    raise AssertionError("pending state did not drain")


def test_full_ring_keeps_release_until_space_returns():
    m = ControllerTransportModel()
    m.publish_button(0, True)
    assert m.worker_step(2) == []
    assert m.retry_on_space and m.pending()
    m.ring_space_available()
    assert m.wake_requested
    assert m.worker_step(3) == [(0xB0, 20, 127)]
    m.publish_button(0, False)
    assert m.worker_step(0) == []
    m.ring_space_available()
    assert m.worker_step(3) == [(0xB0, 20, 0)]
    assert not m.pending()


def test_queue_overflow_repairs_dropped_release():
    m = ControllerTransportModel()
    m.publish_button(0, True)
    for _ in range(14):
        m.publish_button(1, True)
    assert len(m.edges) == 15
    m.publish_button(0, False)  # release cannot fit in the edge queue
    messages = drain_all(m)
    assert messages[0] == (0xB0, 20, 127)
    assert messages[-1] == (0xB0, 20, 0)
    assert m.enqueued_buttons[0] == m.desired_buttons[0] == 0


def test_newer_motion_survives_worker_snapshot():
    m = ControllerTransportModel()
    m.publish_expression(25)
    first = m.worker_step(3, during_append=lambda state: state.publish_expression(90))
    assert first == [(0xB0, 11, 25)]
    assert m.pending() and m.wake_requested
    assert m.worker_step(3) == [(0xB0, 11, 90)]


def test_disconnect_discards_old_edges_and_replays_absolute_state():
    m = ControllerTransportModel()
    m.publish_button(0, True)
    m.worker_step(3)
    m.disconnect()
    m.publish_button(0, False)
    m.publish_knob(2, 99)
    m.reconnect()
    messages = drain_all(m)
    assert (0xB0, 20, 127) not in messages
    assert (0xB0, 20, 0) in messages
    assert (0xB0, 42, 99) in messages
    assert all(m.enqueued_buttons[i] == m.desired_buttons[i] for i in range(12))


def test_limit_requests_another_worker_pass_without_losing_edges():
    m = ControllerTransportModel()
    for i in range(6):
        m.publish_button(i, True)
    assert len(m.worker_step(1024, limit=4)) == 4
    assert m.wake_requested and m.pending()
    assert len(m.worker_step(1024, limit=4)) == 2
    assert not m.pending()


def test_wrap_capacity_boundary_never_accepts_partial_cc():
    m = ControllerTransportModel()
    m.publish_button(3, True)
    assert m.worker_step(1) == []
    assert m.worker_step(2) == []
    assert m.worker_step(3) == [(0xB0, 23, 127)]


def test_reset_during_worker_snapshot_requires_replay():
    m = ControllerTransportModel()
    m.publish_button(0, True)

    def reset(state):
        state.disconnect()
        state.reconnect()

    assert m.worker_step(3, during_append=reset) == []
    assert m.pending()
    messages = drain_all(m)
    assert (0xB0, 20, 127) in messages


def test_ring_wrap_and_atomic_capacity_at_1025_positions():
    ring = AtomicRingModel()
    for _ in range(341):
        assert ring.append_cc((0xB0, 20, 127))
    assert ring.free() == 1
    before = ring.write
    assert not ring.append_cc((0xB0, 21, 0))
    assert ring.write == before  # no accepted prefix
    assert ring.consume(1020) == [0xB0, 20, 127] * 340
    assert ring.append_cc((0xB0, 21, 0))
    assert ring.write == 1  # wrapped after writing positions 1023, 1024, 0
    assert ring.consume(6) == [0xB0, 20, 127, 0xB0, 21, 0]
