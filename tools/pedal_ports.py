"""MIDI port names the pedal can have.

Stock firmware enumerates as "ZOOM G Series"; Comet Flower firmware (tools/cf_usb_name.py)
as "Comet Flower". Update mode always shows "ZOOM G Series" (the boot program's
own strings). Windows appends an index ("ZOOM G Series 0").
"""
PREFIXES = ("ZOOM G", "Comet Flower")


def is_pedal_port(name):
    return name.startswith(PREFIXES)


def register_zoomzt2(module):
    """Let stomphacks' zoomzt2.connect() find a Comet Flower-named pedal too."""
    for prefix in PREFIXES:
        if prefix not in module.midinames:
            module.midinames.append(prefix)
    return module
