"""USB Audio Class 1.0 (UAC1) + MIDI 1.0 Configuration Descriptor Validator.

Checks configuration descriptor byte streams against:
  - Universal Serial Bus Specification Revision 2.0 (USB 2.0 ch. 9)
  - Universal Serial Bus Device Class Definition for Audio Devices Release 1.0 (audio10.pdf)
  - Universal Serial Bus Device Class Definition for Audio Data Formats Release 1.0
  - Universal Serial Bus Device Class Definition for MIDI Devices Release 1.0 (midi10.pdf)

Returns a list of (check_id, message) violation tuples.
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import List, Tuple, Optional, Dict, Set, Any


CHECK_IDS = [
    "framing",
    "configuration",
    "interfaces",
    "audio_control",
    "terminals",
    "audio_streaming",
    "midi_streaming",
    "endpoint_addresses",
    "bandwidth",
]


class DescriptorRecord:
    """Parsed single USB descriptor header and payload."""

    def __init__(self, offset: int, bLength: int, bDescriptorType: int, raw: bytes):
        self.offset = offset
        self.bLength = bLength
        self.bDescriptorType = bDescriptorType
        self.raw = raw
        self.bDescriptorSubtype = raw[2] if len(raw) > 2 else 0

    def __repr__(self) -> str:
        return (
            f"Desc(offset=0x{self.offset:02x}, len={self.bLength}, "
            f"type=0x{self.bDescriptorType:02x}, sub=0x{self.bDescriptorSubtype:02x})"
        )


class EndpointGroup:
    """Standard endpoint descriptor and its trailing class-specific endpoint descriptors."""

    def __init__(self, standard_ep: DescriptorRecord):
        self.standard = standard_ep
        self.cs_endpoints: List[DescriptorRecord] = []

    @property
    def bEndpointAddress(self) -> int:
        return self.standard.raw[2]

    @property
    def bmAttributes(self) -> int:
        return self.standard.raw[3]

    @property
    def wMaxPacketSize(self) -> int:
        return self.standard.raw[4] | (self.standard.raw[5] << 8)

    @property
    def bInterval(self) -> int:
        return self.standard.raw[6] if len(self.standard.raw) > 6 else 0


class InterfaceAltSetting:
    """One alternate setting of an interface and all its associated descriptors."""

    def __init__(self, desc: DescriptorRecord):
        self.desc = desc
        self.bInterfaceNumber = desc.raw[2]
        self.bAlternateSetting = desc.raw[3]
        self.bNumEndpoints = desc.raw[4]
        self.bInterfaceClass = desc.raw[5]
        self.bInterfaceSubClass = desc.raw[6]
        self.bInterfaceProtocol = desc.raw[7]
        self.cs_descriptors: List[DescriptorRecord] = []
        self.endpoints: List[EndpointGroup] = []


class InterfaceGroup:
    """An interface (identified by bInterfaceNumber) with one or more alternate settings."""

    def __init__(self, bInterfaceNumber: int):
        self.bInterfaceNumber = bInterfaceNumber
        self.alts: List[InterfaceAltSetting] = []


def walk_descriptors(data: bytes, violations: List[Tuple[str, str]]) -> Optional[List[DescriptorRecord]]:
    """Walk raw bytes and validate framing (Check 1).

    Citations:
      - USB 2.0 §9.6.3 Table 9-10 (Configuration Descriptor: bLength=9, wTotalLength)
      - USB 2.0 §9.6.5 Table 9-12 (Interface Descriptor: bLength=9)
      - USB 2.0 §9.6.6 Table 9-13 (Endpoint Descriptor: bLength=7)
      - USB Audio 1.0 §4.6.1.1 Table 4-17 (Audio Standard Endpoint: bLength=9)
      - USB MIDI 1.0 §6.2.1 Table 6-6 (MIDI Standard Endpoint: bLength=9)
      - USB Audio 1.0 §4.3.2 Table 4-2 (Class-Specific AC Header: bLength=8+bInCollection)
      - USB Audio 1.0 §4.3.2.1 Table 4-3 (Input Terminal: bLength=12)
      - USB Audio 1.0 §4.3.2.2 Table 4-4 (Output Terminal: bLength=9)
      - USB Audio 1.0 §4.5.2 Table 4-19 (Class-Specific AS Interface Header: bLength=7)
      - USB Audio Formats 1.0 §2.2 Table 2-1 (Type I Format Descriptor)
      - USB Audio 1.0 §4.6.1.2 Table 4-18 (Class-Specific AS Endpoint: bLength=7)
      - USB MIDI 1.0 §6.1.2.1 Table 6-2 (Class-Specific MS Interface Header: bLength=7)
      - USB MIDI 1.0 §6.1.2.2 Table 6-3 (MIDI IN Jack: bLength=6)
      - USB MIDI 1.0 §6.1.2.2 Table 6-4/6-5 (MIDI OUT Jack: bLength=6+2*bNrInputPins+1)
      - USB MIDI 1.0 §6.2.2 Table 6-8 (Class-Specific MS Endpoint: bLength=4+bNumEmbMIDIJack)
    """
    if len(data) < 9:
        violations.append((
            "framing",
            f"Configuration descriptor data length {len(data)} is too short (minimum 9 bytes per USB 2.0 §9.6.3)"
        ))
        return None

    if data[0] != 9 or data[1] != 0x02:
        violations.append((
            "framing",
            f"First descriptor at byte 0 has bLength={data[0]}, bDescriptorType=0x{data[1]:02x} "
            f"(expected bLength=9, bDescriptorType=0x02 per USB 2.0 §9.6.3 Table 9-10)"
        ))
        return None

    wTotalLength = data[2] | (data[3] << 8)
    if wTotalLength != len(data):
        violations.append((
            "framing",
            f"wTotalLength ({wTotalLength}) does not match actual byte count ({len(data)}) "
            f"per USB 2.0 §9.6.3 Table 9-10"
        ))

    records: List[DescriptorRecord] = []
    offset = 0
    total_len = len(data)

    current_class = 0
    current_subclass = 0

    while offset < total_len:
        bLength = data[offset]
        if bLength < 2:
            violations.append((
                "framing",
                f"Descriptor at offset {offset} has invalid bLength {bLength} < 2 "
                f"(malformed descriptor walk per USB 2.0 §9.5)"
            ))
            return None

        if offset + bLength > total_len:
            violations.append((
                "framing",
                f"Descriptor at offset {offset} with bLength {bLength} overflows data length {total_len} "
                f"per USB 2.0 §9.6.3"
            ))
            return None

        bType = data[offset + 1]
        raw = data[offset : offset + bLength]
        rec = DescriptorRecord(offset, bLength, bType, raw)

        # Track interface class context for class-specific type checking
        if bType == 0x04:  # Interface
            if bLength != 9:
                violations.append((
                    "framing",
                    f"Interface descriptor at offset {offset} has bLength={bLength} (expected 9 per USB 2.0 §9.6.5 Table 9-12)"
                ))
            if len(raw) >= 7:
                current_class = raw[5]
                current_subclass = raw[6]

        elif bType == 0x02:  # Configuration
            if bLength != 9:
                violations.append((
                    "framing",
                    f"Configuration descriptor at offset {offset} has bLength={bLength} (expected 9 per USB 2.0 §9.6.3 Table 9-10)"
                ))

        elif bType == 0x05:  # Endpoint
            # Standard endpoint is 7 bytes; Audio/MIDI class standard endpoint is 9 bytes
            if bLength not in (7, 9):
                violations.append((
                    "framing",
                    f"Endpoint descriptor at offset {offset} has bLength={bLength} "
                    f"(expected 7 or 9 per USB 2.0 §9.6.6 Table 9-13 / USB Audio 1.0 §4.6.1.1 Table 4-17)"
                ))

        elif bType == 0x0B:  # Interface Association
            if bLength != 8:
                violations.append((
                    "framing",
                    f"Interface Association descriptor at offset {offset} has bLength={bLength} (expected 8 per USB ECN)"
                ))

        elif bType == 0x24:  # CS_INTERFACE
            sub = rec.bDescriptorSubtype
            if current_class == 0x01:  # Audio Class
                if current_subclass == 0x01:  # AudioControl
                    if sub == 0x01:  # HEADER
                        if len(raw) >= 8:
                            expected_len = 8 + raw[7]
                            if bLength != expected_len:
                                violations.append((
                                    "framing",
                                    f"AC HEADER descriptor at offset {offset} has bLength={bLength} "
                                    f"(expected {expected_len} for bInCollection={raw[7]} per USB Audio 1.0 §4.3.2 Table 4-2)"
                                ))
                    elif sub == 0x02:  # INPUT_TERMINAL
                        if bLength != 12:
                            violations.append((
                                "framing",
                                f"Input Terminal descriptor at offset {offset} has bLength={bLength} "
                                f"(expected 12 per USB Audio 1.0 §4.3.2.1 Table 4-3)"
                            ))
                    elif sub == 0x03:  # OUTPUT_TERMINAL
                        if bLength != 9:
                            violations.append((
                                "framing",
                                f"Output Terminal descriptor at offset {offset} has bLength={bLength} "
                                f"(expected 9 per USB Audio 1.0 §4.3.2.2 Table 4-4)"
                            ))
                    elif sub == 0x05:  # SELECTOR_UNIT
                        if len(raw) >= 5:
                            expected_len = 6 + raw[4]
                            if bLength != expected_len:
                                violations.append((
                                    "framing",
                                    f"Selector Unit descriptor at offset {offset} has bLength={bLength} "
                                    f"(expected {expected_len} per USB Audio 1.0 §4.3.2.4 Table 4-6)"
                                ))
                elif current_subclass == 0x02:  # AudioStreaming
                    if sub == 0x01:  # AS_GENERAL
                        if bLength != 7:
                            violations.append((
                                "framing",
                                f"AS_GENERAL descriptor at offset {offset} has bLength={bLength} "
                                f"(expected 7 per USB Audio 1.0 §4.5.2 Table 4-19)"
                            ))
                    elif sub == 0x02:  # FORMAT_TYPE
                        if len(raw) >= 4 and raw[3] == 0x01:  # FORMAT_TYPE_I
                            if len(raw) >= 8:
                                sam_freq_type = raw[7]
                                expected_len = 14 if sam_freq_type == 0 else 8 + 3 * sam_freq_type
                                if bLength != expected_len:
                                    violations.append((
                                        "framing",
                                        f"FORMAT_TYPE_I descriptor at offset {offset} has bLength={bLength} "
                                        f"(expected {expected_len} per USB Audio Formats 1.0 §2.2 Table 2-1)"
                                    ))
                elif current_subclass == 0x03:  # MIDIStreaming
                    if sub == 0x01:  # MS_HEADER
                        if bLength != 7:
                            violations.append((
                                "framing",
                                f"MS_HEADER descriptor at offset {offset} has bLength={bLength} "
                                f"(expected 7 per USB MIDI 1.0 §6.1.2.1 Table 6-2)"
                            ))
                    elif sub == 0x02:  # MIDI_IN_JACK
                        if bLength != 6:
                            violations.append((
                                "framing",
                                f"MIDI_IN_JACK descriptor at offset {offset} has bLength={bLength} "
                                f"(expected 6 per USB MIDI 1.0 §6.1.2.2 Table 6-3)"
                            ))
                    elif sub == 0x03:  # MIDI_OUT_JACK
                        if len(raw) >= 6:
                            expected_len = 6 + 2 * raw[5] + 1
                            if bLength != expected_len:
                                violations.append((
                                    "framing",
                                    f"MIDI_OUT_JACK descriptor at offset {offset} has bLength={bLength} "
                                    f"(expected {expected_len} per USB MIDI 1.0 §6.1.2.2 Table 6-4/6-5)"
                                ))

        elif bType == 0x25:  # CS_ENDPOINT
            sub = rec.bDescriptorSubtype
            if current_class == 0x01:
                if current_subclass == 0x02:  # AudioStreaming
                    if sub == 0x01 and bLength != 7:
                        violations.append((
                            "framing",
                            f"AS Isochronous Audio Data Endpoint descriptor at offset {offset} has bLength={bLength} "
                            f"(expected 7 per USB Audio 1.0 §4.6.1.2 Table 4-18)"
                        ))
                elif current_subclass == 0x03:  # MIDIStreaming
                    if sub == 0x01 and len(raw) >= 4:
                        expected_len = 4 + raw[3]
                        if bLength != expected_len:
                            violations.append((
                                "framing",
                                f"MS Bulk Data Endpoint descriptor at offset {offset} has bLength={bLength} "
                                f"(expected {expected_len} per USB MIDI 1.0 §6.2.2 Table 6-8)"
                            ))

        records.append(rec)
        offset += bLength

    if offset != total_len:
        violations.append((
            "framing",
            f"Walk finished at offset {offset} but total length is {total_len} "
            f"per USB 2.0 §9.6.3"
        ))

    return records


def validate(data: bytes) -> List[Tuple[str, str]]:
    """Validate a UAC1 / USB-MIDI configuration descriptor byte buffer.

    Returns a list of (check_id, message) tuples where check_id is one of:
      - 'framing'
      - 'configuration'
      - 'interfaces'
      - 'audio_control'
      - 'terminals'
      - 'audio_streaming'
      - 'midi_streaming'
      - 'endpoint_addresses'
      - 'bandwidth'
    """
    violations: List[Tuple[str, str]] = []

    # Check 1: Framing
    records = walk_descriptors(data, violations)
    if records is None:
        return violations

    # Partition records into Configuration and Interface structures
    config_desc = records[0]

    interfaces_by_num: Dict[int, InterfaceGroup] = {}
    current_alt: Optional[InterfaceAltSetting] = None
    current_ep: Optional[EndpointGroup] = None

    for rec in records[1:]:
        if rec.bDescriptorType == 0x04:  # Interface
            if_num = rec.raw[2]
            current_alt = InterfaceAltSetting(rec)
            current_ep = None
            if if_num not in interfaces_by_num:
                interfaces_by_num[if_num] = InterfaceGroup(if_num)
            interfaces_by_num[if_num].alts.append(current_alt)

        elif rec.bDescriptorType == 0x05:  # Standard Endpoint
            current_ep = EndpointGroup(rec)
            if current_alt is not None:
                current_alt.endpoints.append(current_ep)

        elif rec.bDescriptorType == 0x24:  # CS_INTERFACE
            if current_alt is not None:
                current_alt.cs_descriptors.append(rec)

        elif rec.bDescriptorType == 0x25:  # CS_ENDPOINT
            if current_ep is not None:
                current_ep.cs_endpoints.append(rec)
            elif current_alt is not None:
                current_alt.cs_descriptors.append(rec)

    # -------------------------------------------------------------------------
    # Check 2: Configuration
    # Spec: USB 2.0 §9.6.3 Table 9-10
    # bNumInterfaces equals distinct bInterfaceNumber values, 0..n-1 with no gaps.
    # bmAttributes bit 7 is set. bMaxPower > 0.
    # -------------------------------------------------------------------------
    bNumInterfaces = config_desc.raw[4]
    distinct_if_nums = sorted(list(interfaces_by_num.keys()))

    if len(distinct_if_nums) != bNumInterfaces:
        violations.append((
            "configuration",
            f"Configuration bNumInterfaces ({bNumInterfaces}) != distinct interface count ({len(distinct_if_nums)}) "
            f"per USB 2.0 §9.6.3 Table 9-10"
        ))

    expected_range = list(range(len(distinct_if_nums)))
    if distinct_if_nums != expected_range:
        violations.append((
            "configuration",
            f"Interface numbers {distinct_if_nums} are not contiguous 0..n-1 without gaps "
            f"per USB 2.0 §9.6.3 Table 9-10"
        ))

    bmAttributes = config_desc.raw[7]
    if not (bmAttributes & 0x80):
        violations.append((
            "configuration",
            f"Configuration bmAttributes (0x{bmAttributes:02x}) bit 7 is not set "
            f"(reserved bit 7 must be 1 per USB 2.0 §9.6.3 Table 9-10)"
        ))

    bMaxPower = config_desc.raw[8]
    if bMaxPower == 0:
        violations.append((
            "configuration",
            f"Configuration bMaxPower is 0 (must be non-zero per USB 2.0 §9.6.3 Table 9-10)"
        ))

    # -------------------------------------------------------------------------
    # Check 3: Interfaces
    # Spec: USB 2.0 §9.6.5 Table 9-12
    # Alternate settings for one interface are contiguous and start at 0.
    # bNumEndpoints matches endpoint descriptors that follow each interface descriptor.
    # -------------------------------------------------------------------------
    for if_num, if_group in interfaces_by_num.items():
        alt_indices = sorted([alt.bAlternateSetting for alt in if_group.alts])
        expected_alts = list(range(len(alt_indices)))
        if alt_indices != expected_alts:
            violations.append((
                "interfaces",
                f"Interface {if_num} alternate settings {alt_indices} are not contiguous starting at 0 "
                f"per USB 2.0 §9.6.5 Table 9-12"
            ))

        for alt in if_group.alts:
            actual_ep_count = len(alt.endpoints)
            if actual_ep_count != alt.bNumEndpoints:
                violations.append((
                    "interfaces",
                    f"Interface {if_num} alt {alt.bAlternateSetting} specifies bNumEndpoints={alt.bNumEndpoints} "
                    f"but {actual_ep_count} endpoint descriptors follow per USB 2.0 §9.6.5 Table 9-12"
                ))

    # -------------------------------------------------------------------------
    # Check 4: Audio Control
    # Spec: USB Audio 1.0 §4.3.2 Table 4-2, §3.2
    # Each AC interface (class 1, subclass 1) has exactly one CS HEADER.
    # wTotalLength equals sum of CS AC descriptors that follow it.
    # baInterfaceNr names interfaces that exist and are AudioStreaming (subclass 2)
    # or MIDIStreaming (subclass 3).
    # An interface listed by two AC headers is an error.
    # -------------------------------------------------------------------------
    claimed_streaming_interfaces: Dict[int, int] = {}
    ac_interfaces_by_num: Dict[int, InterfaceGroup] = {}

    for if_num, if_group in interfaces_by_num.items():
        # Check if alt 0 is AudioControl (class 1, subclass 1)
        alt0 = if_group.alts[0]
        if alt0.bInterfaceClass == 0x01 and alt0.bInterfaceSubClass == 0x01:
            ac_interfaces_by_num[if_num] = if_group
            headers = [d for d in alt0.cs_descriptors if d.bDescriptorSubtype == 0x01]
            if len(headers) != 1:
                violations.append((
                    "audio_control",
                    f"AudioControl interface {if_num} has {len(headers)} CS HEADER descriptors "
                    f"(expected exactly 1 per USB Audio 1.0 §4.3.2 Table 4-2)"
                ))
                continue

            hdr = headers[0]
            wTotalLength = hdr.raw[5] | (hdr.raw[6] << 8)
            sum_cs = sum(d.bLength for d in alt0.cs_descriptors)
            if wTotalLength != sum_cs:
                violations.append((
                    "audio_control",
                    f"AudioControl interface {if_num} CS HEADER wTotalLength ({wTotalLength}) != "
                    f"sum of CS AC descriptors ({sum_cs}) per USB Audio 1.0 §4.3.2 Table 4-2"
                ))

            bInCollection = hdr.raw[7]
            baInterfaceNr = list(hdr.raw[8 : 8 + bInCollection])

            for target_if in baInterfaceNr:
                if target_if not in interfaces_by_num:
                    violations.append((
                        "audio_control",
                        f"AudioControl interface {if_num} baInterfaceNr lists non-existent interface {target_if} "
                        f"per USB Audio 1.0 §4.3.2 Table 4-2"
                    ))
                    continue

                target_group = interfaces_by_num[target_if]
                target_alt0 = target_group.alts[0]
                is_as_or_ms = (
                    target_alt0.bInterfaceClass == 0x01
                    and target_alt0.bInterfaceSubClass in (0x02, 0x03)
                )
                if not is_as_or_ms:
                    violations.append((
                        "audio_control",
                        f"AudioControl interface {if_num} lists interface {target_if} with class {target_alt0.bInterfaceClass}, "
                        f"subclass {target_alt0.bInterfaceSubClass} (must be AudioStreaming (2) or MIDIStreaming (3) "
                        f"per USB Audio 1.0 §4.3.2 Table 4-2)"
                    ))

                if target_if in claimed_streaming_interfaces:
                    violations.append((
                        "audio_control",
                        f"Interface {target_if} is claimed by multiple AC headers (interface {claimed_streaming_interfaces[target_if]} "
                        f"and interface {if_num}) per USB Audio 1.0 §3.2"
                    ))
                else:
                    claimed_streaming_interfaces[target_if] = if_num

    # -------------------------------------------------------------------------
    # Check 5: Terminals
    # Spec: USB Audio 1.0 §4.3.2.1 Table 4-3, §4.3.2.2 Table 4-4
    # Terminal IDs are unique within an AC interface, and every bSourceID /
    # bAssocTerminal refers to an existing ID (0 = none).
    # An Output Terminal of type USB streaming (0x0101) must be linked by an
    # AS interface's bTerminalLink.
    # -------------------------------------------------------------------------
    as_terminal_links: Set[int] = set()
    for if_group in interfaces_by_num.values():
        for alt in if_group.alts:
            if alt.bInterfaceClass == 0x01 and alt.bInterfaceSubClass == 0x02:
                for d in alt.cs_descriptors:
                    if d.bDescriptorSubtype == 0x01 and len(d.raw) >= 4:  # AS_GENERAL
                        as_terminal_links.add(d.raw[3])  # bTerminalLink

    for ac_if_num, ac_group in ac_interfaces_by_num.items():
        alt0 = ac_group.alts[0]
        terminals_by_id: Dict[int, DescriptorRecord] = {}
        terminal_ids: Set[int] = set()

        for d in alt0.cs_descriptors:
            sub = d.bDescriptorSubtype
            if sub in (0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08):
                tid = d.raw[3]
                if tid in terminal_ids:
                    violations.append((
                        "terminals",
                        f"AudioControl interface {ac_if_num} contains duplicate Terminal/Unit ID {tid} "
                        f"per USB Audio 1.0 §4.3.2"
                    ))
                else:
                    terminal_ids.add(tid)
                    terminals_by_id[tid] = d

        for tid, d in terminals_by_id.items():
            sub = d.bDescriptorSubtype
            if sub == 0x02:  # INPUT_TERMINAL
                assoc = d.raw[6]
                if assoc != 0 and assoc not in terminal_ids:
                    violations.append((
                        "terminals",
                        f"Input Terminal {tid} in AC interface {ac_if_num} references nonexistent bAssocTerminal {assoc} "
                        f"per USB Audio 1.0 §4.3.2.1 Table 4-3"
                    ))
            elif sub == 0x03:  # OUTPUT_TERMINAL
                assoc = d.raw[6]
                source = d.raw[7]
                wTerminalType = d.raw[4] | (d.raw[5] << 8)

                if assoc != 0 and assoc not in terminal_ids:
                    violations.append((
                        "terminals",
                        f"Output Terminal {tid} in AC interface {ac_if_num} references nonexistent bAssocTerminal {assoc} "
                        f"per USB Audio 1.0 §4.3.2.2 Table 4-4"
                    ))
                if source != 0 and source not in terminal_ids:
                    violations.append((
                        "terminals",
                        f"Output Terminal {tid} in AC interface {ac_if_num} references nonexistent bSourceID {source} "
                        f"per USB Audio 1.0 §4.3.2.2 Table 4-4"
                    ))

                # USB Streaming Output Terminal (0x0101) must be linked by an AS interface's bTerminalLink
                if wTerminalType == 0x0101:
                    if tid not in as_terminal_links:
                        violations.append((
                            "terminals",
                            f"Output Terminal {tid} of type USB streaming (0x0101) in AC interface {ac_if_num} "
                            f"is not linked by any AudioStreaming interface bTerminalLink per USB Audio 1.0 §4.3.2.2"
                        ))
            elif sub in (0x04, 0x05):  # MIXER or SELECTOR
                num_pins = d.raw[4]
                for p in range(num_pins):
                    src = d.raw[5 + p]
                    if src != 0 and src not in terminal_ids:
                        violations.append((
                            "terminals",
                            f"Unit {tid} in AC interface {ac_if_num} references nonexistent source {src} "
                            f"per USB Audio 1.0 §4.3.2"
                        ))
            elif sub == 0x06:  # FEATURE_UNIT
                src = d.raw[4]
                if src != 0 and src not in terminal_ids:
                    violations.append((
                        "terminals",
                        f"Feature Unit {tid} in AC interface {ac_if_num} references nonexistent source {src} "
                        f"per USB Audio 1.0 §4.3.2.5 Table 4-7"
                    ))

    # -------------------------------------------------------------------------
    # Check 6: AudioStreaming
    # Spec: USB Audio 1.0 §2.4.2.1, §4.5.1, §4.5.2, §4.6.1.1, §4.6.1.2;
    #       USB Audio Formats 1.0 §2.2
    # Alt 0 has zero endpoints.
    # An alt with an endpoint has CS AS_GENERAL (bTerminalLink pointing at
    # USB-streaming terminal) and FORMAT_TYPE_I descriptor:
    # bNrChannels, bSubframeSize, bBitResolution, tSamFreq.
    # wMaxPacketSize >= ceil(maxrate/1000) * channels * subframe, full-speed bInterval == 1.
    # ISO endpoint descriptor is 9 bytes (audio-class form, with bRefresh/bSynchAddress).
    # CS_ENDPOINT (0x25) EP_GENERAL follows it.
    # Endpoint direction matches the terminal (IN endpoint feeds host input / USB streaming OT).
    # -------------------------------------------------------------------------
    all_terminals_by_id: Dict[int, DescriptorRecord] = {}
    for ac_group in ac_interfaces_by_num.values():
        for d in ac_group.alts[0].cs_descriptors:
            if d.bDescriptorSubtype in (0x02, 0x03):
                all_terminals_by_id[d.raw[3]] = d

    for if_num, if_group in interfaces_by_num.items():
        alt0 = if_group.alts[0]
        if alt0.bInterfaceClass != 0x01 or alt0.bInterfaceSubClass != 0x02:
            continue

        if alt0.bNumEndpoints != 0:
            violations.append((
                "audio_streaming",
                f"AudioStreaming interface {if_num} alt 0 has {alt0.bNumEndpoints} endpoints "
                f"(must be 0 for zero-bandwidth idle setting per USB Audio 1.0 §2.4.2.1 / §4.5)"
            ))

        for alt in if_group.alts:
            if alt.bNumEndpoints == 0:
                continue

            as_gen_descs = [d for d in alt.cs_descriptors if d.bDescriptorSubtype == 0x01]
            fmt_descs = [d for d in alt.cs_descriptors if d.bDescriptorSubtype == 0x02]

            if not as_gen_descs:
                violations.append((
                    "audio_streaming",
                    f"AudioStreaming interface {if_num} alt {alt.bAlternateSetting} missing CS AS_GENERAL descriptor "
                    f"per USB Audio 1.0 §4.5.2 Table 4-19"
                ))
                continue

            as_gen = as_gen_descs[0]
            bTerminalLink = as_gen.raw[3]
            linked_terminal = all_terminals_by_id.get(bTerminalLink)

            if linked_terminal is None:
                violations.append((
                    "audio_streaming",
                    f"AudioStreaming interface {if_num} alt {alt.bAlternateSetting} bTerminalLink {bTerminalLink} "
                    f"does not reference an existing Terminal per USB Audio 1.0 §4.5.2 Table 4-19"
                ))
            else:
                wTerminalType = linked_terminal.raw[4] | (linked_terminal.raw[5] << 8)
                if wTerminalType != 0x0101:
                    violations.append((
                        "audio_streaming",
                        f"AudioStreaming interface {if_num} alt {alt.bAlternateSetting} bTerminalLink {bTerminalLink} "
                        f"references terminal of type 0x{wTerminalType:04x} (expected USB Streaming 0x0101 "
                        f"per USB Audio 1.0 §4.5.2 Table 4-19)"
                    ))

            if not fmt_descs:
                violations.append((
                    "audio_streaming",
                    f"AudioStreaming interface {if_num} alt {alt.bAlternateSetting} missing FORMAT_TYPE descriptor "
                    f"per USB Audio Formats 1.0 §2"
                ))
                continue

            fmt = fmt_descs[0]
            bFormatType = fmt.raw[3]
            if bFormatType != 0x01:
                violations.append((
                    "audio_streaming",
                    f"AudioStreaming interface {if_num} alt {alt.bAlternateSetting} format type is {bFormatType} "
                    f"(expected FORMAT_TYPE_I 0x01 per USB Audio Formats 1.0 §2.2)"
                ))
                continue

            bNrChannels = fmt.raw[4]
            bSubframeSize = fmt.raw[5]
            bBitResolution = fmt.raw[6]
            bSamFreqType = fmt.raw[7]

            if bSamFreqType == 0:
                tUpperSamFreq = fmt.raw[11] | (fmt.raw[12] << 8) | (fmt.raw[13] << 16)
                maxrate = tUpperSamFreq
            else:
                freqs = [
                    fmt.raw[8 + 3 * i] | (fmt.raw[9 + 3 * i] << 8) | (fmt.raw[10 + 3 * i] << 16)
                    for i in range(bSamFreqType)
                ]
                maxrate = max(freqs) if freqs else 0

            # Endpoint checks
            iso_eps = [ep for ep in alt.endpoints if (ep.bmAttributes & 0x03) == 0x01]
            if not iso_eps:
                violations.append((
                    "audio_streaming",
                    f"AudioStreaming interface {if_num} alt {alt.bAlternateSetting} has no Isochronous endpoint "
                    f"per USB Audio 1.0 §4.6.1.1"
                ))
                continue

            for ep_group in iso_eps:
                ep_rec = ep_group.standard
                if ep_rec.bLength != 9:
                    violations.append((
                        "audio_streaming",
                        f"AudioStreaming ISO endpoint at offset {ep_rec.offset} has bLength={ep_rec.bLength} "
                        f"(expected 9 bytes with bRefresh and bSynchAddress per USB Audio 1.0 §4.6.1.1 Table 4-17)"
                    ))

                if ep_group.bInterval != 1:
                    violations.append((
                        "audio_streaming",
                        f"AudioStreaming ISO endpoint at offset {ep_rec.offset} has bInterval={ep_group.bInterval} "
                        f"(expected 1 for full-speed 1ms per USB Audio 1.0 §4.6.1.1 Table 4-17)"
                    ))

                min_packet_size = math.ceil(maxrate / 1000) * bNrChannels * bSubframeSize
                if ep_group.wMaxPacketSize < min_packet_size:
                    violations.append((
                        "audio_streaming",
                        f"AudioStreaming ISO endpoint at offset {ep_rec.offset} wMaxPacketSize ({ep_group.wMaxPacketSize}) < "
                        f"required ({min_packet_size}) for maxrate={maxrate}, ch={bNrChannels}, subframe={bSubframeSize} "
                        f"per USB Audio Formats 1.0 §2.2"
                    ))

                # Direction match with terminal
                if linked_terminal is not None:
                    # Output Terminal of type 0x0101 sends to host -> endpoint must be IN (bit 7 set)
                    # Input Terminal of type 0x0101 receives from host -> endpoint must be OUT (bit 7 clear)
                    is_in_ep = bool(ep_group.bEndpointAddress & 0x80)
                    if linked_terminal.bDescriptorSubtype == 0x03 and not is_in_ep:
                        violations.append((
                            "audio_streaming",
                            f"AudioStreaming ISO endpoint at offset {ep_rec.offset} is OUT but linked to Output Terminal "
                            f"(expected IN endpoint feeding host input per USB Audio 1.0 §2.3.2.1 / §4.6.1.1)"
                        ))
                    elif linked_terminal.bDescriptorSubtype == 0x02 and is_in_ep:
                        violations.append((
                            "audio_streaming",
                            f"AudioStreaming ISO endpoint at offset {ep_rec.offset} is IN but linked to Input Terminal "
                            f"(expected OUT endpoint receiving from host per USB Audio 1.0 §2.3.2.1 / §4.6.1.1)"
                        ))

                # CS_ENDPOINT (0x25) EP_GENERAL must follow
                cs_ep_general = [
                    d for d in ep_group.cs_endpoints
                    if d.bDescriptorType == 0x25 and d.bDescriptorSubtype == 0x01
                ]
                if not cs_ep_general:
                    violations.append((
                        "audio_streaming",
                        f"AudioStreaming ISO endpoint at offset {ep_rec.offset} is not followed by CS_ENDPOINT "
                        f"EP_GENERAL (0x25, 0x01) per USB Audio 1.0 §4.6.1.2 Table 4-18"
                    ))

    # -------------------------------------------------------------------------
    # Check 7: MIDIStreaming
    # Spec: USB MIDI 1.0 §6.1.2.1 Table 6-2, §6.1.2.2 Table 6-3, §6.2.2 Table 6-8
    # MS HEADER wTotalLength matches sum of CS MS descriptors.
    # Jack IDs are unique, and each CS MS endpoint's baAssocJackID refers to
    # existing embedded jacks.
    # -------------------------------------------------------------------------
    for if_num, if_group in interfaces_by_num.items():
        alt0 = if_group.alts[0]
        if alt0.bInterfaceClass != 0x01 or alt0.bInterfaceSubClass != 0x03:
            continue

        ms_headers = [d for d in alt0.cs_descriptors if d.bDescriptorSubtype == 0x01]
        if not ms_headers:
            violations.append((
                "midi_streaming",
                f"MIDIStreaming interface {if_num} missing MS HEADER descriptor "
                f"per USB MIDI 1.0 §6.1.2.1 Table 6-2"
            ))
            continue

        ms_hdr = ms_headers[0]
        wTotalLength = ms_hdr.raw[5] | (ms_hdr.raw[6] << 8)
        sum_cs = sum(d.bLength for d in alt0.cs_descriptors)
        if wTotalLength != sum_cs:
            violations.append((
                "midi_streaming",
                f"MIDIStreaming interface {if_num} MS HEADER wTotalLength ({wTotalLength}) != "
                f"sum of CS MS descriptors ({sum_cs}) per USB MIDI 1.0 §6.1.2.1 Table 6-2"
            ))

        jack_ids: Set[int] = set()
        embedded_jack_ids: Set[int] = set()

        for d in alt0.cs_descriptors:
            if d.bDescriptorSubtype in (0x02, 0x03):  # IN_JACK or OUT_JACK
                bJackType = d.raw[3]  # 1 = EMBEDDED, 2 = EXTERNAL
                bJackID = d.raw[4]
                if bJackID in jack_ids:
                    violations.append((
                        "midi_streaming",
                        f"MIDIStreaming interface {if_num} contains duplicate Jack ID {bJackID} "
                        f"per USB MIDI 1.0 §6.1.2.2"
                    ))
                else:
                    jack_ids.add(bJackID)
                    if bJackType == 0x01:
                        embedded_jack_ids.add(bJackID)

        # CS MS endpoints
        for ep_group in alt0.endpoints:
            for cs_ep in ep_group.cs_endpoints:
                if cs_ep.bDescriptorType == 0x25 and cs_ep.bDescriptorSubtype == 0x01:
                    bNumEmbMIDIJack = cs_ep.raw[3]
                    baAssocJackID = list(cs_ep.raw[4 : 4 + bNumEmbMIDIJack])
                    for jid in baAssocJackID:
                        if jid not in embedded_jack_ids:
                            violations.append((
                                "midi_streaming",
                                f"CS MS endpoint at offset {cs_ep.offset} references non-embedded or nonexistent "
                                f"Jack ID {jid} per USB MIDI 1.0 §6.2.2 Table 6-8"
                            ))

    # -------------------------------------------------------------------------
    # Check 8: Endpoint addresses
    # Spec: USB 2.0 §9.6.6 Table 9-13
    # No endpoint address appears twice across different interfaces, except in
    # alternates of the same interface.
    # -------------------------------------------------------------------------
    ep_to_interfaces: Dict[int, Set[int]] = {}
    for if_num, if_group in interfaces_by_num.items():
        for alt in if_group.alts:
            for ep_group in alt.endpoints:
                ep_addr = ep_group.bEndpointAddress
                if ep_addr not in ep_to_interfaces:
                    ep_to_interfaces[ep_addr] = set()
                ep_to_interfaces[ep_addr].add(if_num)

    for ep_addr, if_set in ep_to_interfaces.items():
        if len(if_set) > 1:
            violations.append((
                "endpoint_addresses",
                f"Endpoint address 0x{ep_addr:02x} is used in multiple distinct interfaces {sorted(list(if_set))} "
                f"per USB 2.0 §9.6.6"
            ))

    # -------------------------------------------------------------------------
    # Check 9: Full-speed bandwidth
    # Spec: USB 2.0 §5.6.3, §9.6.6 Table 9-13
    # The ISO wMaxPacketSize is <= 1023, and the sum of the periodic endpoints
    # fits a full-speed frame.
    # -------------------------------------------------------------------------
    total_periodic_bandwidth = 0

    for if_num, if_group in interfaces_by_num.items():
        max_alt_periodic = 0
        for alt in if_group.alts:
            alt_periodic = 0
            for ep_group in alt.endpoints:
                is_iso = (ep_group.bmAttributes & 0x03) == 0x01
                is_interrupt = (ep_group.bmAttributes & 0x03) == 0x03

                if is_iso:
                    if ep_group.wMaxPacketSize > 1023:
                        violations.append((
                            "bandwidth",
                            f"Isochronous endpoint 0x{ep_group.bEndpointAddress:02x} wMaxPacketSize "
                            f"({ep_group.wMaxPacketSize}) > 1023 for full-speed per USB 2.0 §5.6.3"
                        ))

                if is_iso or is_interrupt:
                    alt_periodic += ep_group.wMaxPacketSize

            if alt_periodic > max_alt_periodic:
                max_alt_periodic = alt_periodic

        total_periodic_bandwidth += max_alt_periodic

    if total_periodic_bandwidth > 1023:
        violations.append((
            "bandwidth",
            f"Total periodic endpoint bandwidth ({total_periodic_bandwidth} bytes/frame) "
            f"exceeds full-speed 1ms frame limit (1023 bytes) per USB 2.0 §5.6.3 / §5.7.4"
        ))

    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate UAC1/MIDI configuration descriptors")
    parser.add_argument("file", nargs="?", help="Binary descriptor file or '-' for stdin")
    parser.add_argument("--hex", dest="hex_str", help="Hex string of descriptor bytes")
    parser.add_argument("--proto", action="store_true", help="Validate prototype bytes from host harness")
    args = parser.parse_args()

    data: Optional[bytes] = None

    if args.hex_str:
        data = bytes.fromhex(args.hex_str.replace(" ", "").replace("\n", ""))
    elif args.file:
        if args.file == "-":
            data = sys.stdin.buffer.read()
        else:
            with open(args.file, "rb") as f:
                data = f.read()
    else:
        # Default to prototype harness if available
        try:
            from test_usb_audio_proto import build_host_library  # type: ignore
            import ctypes
            lib = build_host_library()
            lib.host_reset()
            lib.usb_audio_copy_descriptors.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint]
            lib.usb_audio_copy_descriptors.restype = ctypes.c_uint
            storage = (ctypes.c_ubyte * 1024)()
            count = lib.usb_audio_copy_descriptors(ctypes.byref(storage, 0), 65535, 1024)
            data = bytes(storage[:count])
            print(f"Loaded {len(data)} bytes from prototype harness.")
        except Exception as e:
            print(f"Error loading prototype harness: {e}", file=sys.stderr)
            parser.print_help(file=sys.stderr)
            return 2

    violations = validate(data)
    if not violations:
        print(f"VALIDATION PASSED: 0 violations across {len(CHECK_IDS)} check rules.")
        return 0
    else:
        print(f"VALIDATION FAILED: {len(violations)} violation(s) found:")
        for check_id, msg in violations:
            print(f"  [{check_id}] {msg}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
