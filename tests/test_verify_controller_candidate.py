"""Reject updater changes that could bypass the offline candidate contract."""

import pytest

from tools.verify_controller_candidate import EXPECTED_STAGES, verify_resources


@pytest.fixture
def candidate():
    reference = {0x81: b"stock", 0x85: b"stock presets", 0x88: b"stock effects",
                 0x8B: b"preserved boot resource", 0x8E: b"preserved metadata"}
    firmware = b"candidate firmware"
    presets = bytes(0xB000)
    effects = bytes(0x2FE000)
    resources = dict(reference)
    resources.update({0x81: firmware, 0x85: presets, 0x88: effects})
    return resources, reference, list(EXPECTED_STAGES), firmware, presets, effects


def test_exact_inputs_are_accepted(candidate):
    verify_resources(*candidate)


@pytest.mark.parametrize("resource", [0x81, 0x85, 0x88, 0x8B, 0x8E])
def test_changed_embedded_resource_is_rejected(candidate, resource):
    candidate[0][resource] += b"changed"
    with pytest.raises(ValueError, match="differs from input"):
        verify_resources(*candidate)


@pytest.mark.parametrize("extra", [False, True])
def test_resource_set_change_is_rejected(candidate, extra):
    if extra:
        candidate[0][0x99] = b"unexpected resource"
    else:
        del candidate[0][0x8B]
    with pytest.raises(ValueError, match="resource ID set changed"):
        verify_resources(*candidate)


@pytest.mark.parametrize("row, replacement", [
    (0, (1, 0, 0x28000, 0)),                  # boot erase
    (5, (2, 0xBF000, 0, 0x81)),               # settings write
    (6, (2, 0, 0, 0x8B)),                    # hidden extra active stage
    (7, (99, 0, 0, 0)),                      # unknown inactive-row opcode
])
def test_changed_stage_including_trailing_rows_is_rejected(candidate, row, replacement):
    candidate[2][row] = replacement
    with pytest.raises(ValueError, match="eight-row stage table"):
        verify_resources(*candidate)


def test_matching_but_oversized_firmware_is_rejected(candidate):
    resources, reference, rows, _, presets, effects = candidate
    oversized = bytes(0x8C001)
    resources[0x81] = oversized
    with pytest.raises(ValueError, match="exceeds allowed flash region"):
        verify_resources(resources, reference, rows, oversized, presets, effects)


@pytest.mark.parametrize("resource, length", [(0x85, 0xAFFF), (0x88, 0x2FDFFF)])
def test_matching_but_incomplete_region_input_is_rejected(candidate, resource, length):
    resources, reference, rows, firmware, presets, effects = candidate
    resources[resource] = bytes(length)
    if resource == 0x85:
        presets = resources[resource]
    else:
        effects = resources[resource]
    with pytest.raises(ValueError, match="must occupy the entire"):
        verify_resources(resources, reference, rows, firmware, presets, effects)
