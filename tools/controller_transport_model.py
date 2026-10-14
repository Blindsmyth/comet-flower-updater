"""Offline reference policy for a proposed controller MIDI worker integration.

This is a state-machine model, not pedal firmware. `worker_step` models an
all-or-nothing three-byte ring append and commits state only after acceptance.
It does not claim that the USB host received an accepted ring message.
"""

from collections import deque


class AtomicRingModel:
    """Stock 1025-position ring with a proposed locked three-byte append."""

    POSITIONS = 1025

    def __init__(self):
        self.read = 0
        self.write = 0
        self.data = bytearray(self.POSITIONS)

    def free(self):
        used = self.write - self.read if self.write >= self.read else self.write + self.POSITIONS - self.read
        return self.POSITIONS - 1 - used

    def append_cc(self, cc):
        if len(cc) != 3 or self.free() < 3:
            return False
        for byte in cc:
            self.data[self.write] = byte
            self.write = (self.write + 1) % self.POSITIONS
        return True

    def consume(self, count):
        if count < 0 or count > self.POSITIONS - 1 - self.free():
            raise ValueError("invalid consume count")
        result = []
        for _ in range(count):
            result.append(self.data[self.read])
            self.read = (self.read + 1) % self.POSITIONS
        return result


class ControllerTransportModel:
    BUTTONS = 12
    QUEUE_CAPACITY = 15

    def __init__(self):
        self.connected = True
        self.connection_epoch = 0
        self.observed_epoch = 0
        self.desired_buttons = [0] * self.BUTTONS
        self.enqueued_buttons = [0] * self.BUTTONS
        self.edges = deque()
        self.knobs = [64] * 4
        self.enqueued_knobs = [64] * 4
        self.expression = None
        self.enqueued_expression = None
        self.wake_requested = False
        self.retry_on_space = False

    def publish_button(self, index, pressed):
        if not 0 <= index < self.BUTTONS:
            raise ValueError("button index out of range")
        value = 127 if pressed else 0
        self.desired_buttons[index] = value
        if self.connected and len(self.edges) < self.QUEUE_CAPACITY:
            self.edges.append((index, value))
        # On overflow, latest desired state repairs a dropped release after
        # all older edges drain. Rapid taps can be lost; final state cannot.
        if self.connected:
            self.wake_requested = True

    def publish_knob(self, index, value):
        if not 0 <= index < 4 or not 0 <= value <= 127:
            raise ValueError("knob/value out of range")
        self.knobs[index] = value
        if self.connected:
            self.wake_requested = True

    def publish_expression(self, value):
        if not 0 <= value <= 127:
            raise ValueError("expression out of range")
        self.expression = value
        if self.connected:
            self.wake_requested = True

    def disconnect(self):
        self.connection_epoch += 1
        self.connected = False
        self.edges.clear()  # old transient edges must not replay later
        self.wake_requested = False
        self.retry_on_space = False
        self.enqueued_buttons = [None] * self.BUTTONS
        self.enqueued_knobs = [None] * 4
        self.enqueued_expression = None

    def reconnect(self):
        self.connection_epoch += 1
        self.connected = True
        self.wake_requested = True

    def ring_reset(self):
        """Reset-only event: readiness remains true; worker observes a token."""
        self.connection_epoch = (self.connection_epoch + 1) & 0xFFFFFFFF
        self.wake_requested = True

    def _observe_epoch(self):
        if self.observed_epoch != self.connection_epoch:
            self.observed_epoch = self.connection_epoch
            self.edges.clear()
            self.enqueued_buttons = [None] * self.BUTTONS
            self.enqueued_knobs = [None] * 4
            self.enqueued_expression = None

    def pending(self):
        return self.observed_epoch != self.connection_epoch or bool(self.edges) or any(a != b for a, b in zip(self.desired_buttons, self.enqueued_buttons)) or any(
            a != b for a, b in zip(self.knobs, self.enqueued_knobs)
        ) or self.expression != self.enqueued_expression

    def ring_space_available(self):
        if self.connected and self.retry_on_space and self.pending():
            self.retry_on_space = False
            self.wake_requested = True

    def _next(self):
        if self.edges:
            index, value = self.edges[0]
            return (20 + index, value, "edge", index)
        for index, (desired, enqueued) in enumerate(zip(self.desired_buttons, self.enqueued_buttons)):
            if desired != enqueued:
                return (20 + index, desired, "button", index)
        for index, (desired, enqueued) in enumerate(zip(self.knobs, self.enqueued_knobs)):
            if desired != enqueued:
                return (40 + index, desired, "knob", index)
        if self.expression != self.enqueued_expression and self.expression is not None:
            return (11, self.expression, "expression", 0)
        return None

    def worker_step(self, free_bytes, limit=4, during_append=None):
        """Return accepted CC tuples; append is atomic when free_bytes >= 3.

        `during_append` injects a producer update before acceptance to test
        that a newer absolute value remains pending. The real integration
        must supply equivalent locking and a ring-space wake trigger.
        """
        if free_bytes < 0 or limit < 0:
            raise ValueError("negative capacity or limit")
        self.wake_requested = False
        if not self.connected:
            return []
        self._observe_epoch()
        accepted = []
        for _ in range(limit):
            item = self._next()
            if item is None:
                break
            if free_bytes < 3:
                self.retry_on_space = True
                break
            cc, value, kind, index = item
            epoch = self.connection_epoch
            if during_append is not None:
                during_append(self)
                during_append = None
            if not self.connected or self.connection_epoch != epoch:
                # A USB reset invalidates acceptance observed in the old
                # session. Reconnect will replay absolute state.
                break
            accepted.append((0xB0, cc, value))
            free_bytes -= 3
            if kind == "edge":
                self.edges.popleft()
                self.enqueued_buttons[index] = value
            elif kind == "button":
                self.enqueued_buttons[index] = value
            elif kind == "knob":
                self.enqueued_knobs[index] = value
            else:
                self.enqueued_expression = value
        if self.pending():
            if free_bytes >= 3:
                self.wake_requested = True
            else:
                self.retry_on_space = True
        else:
            self.retry_on_space = False
        return accepted
