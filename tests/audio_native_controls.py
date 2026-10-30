"""Native audio keys/readback and rendered control samples on owned Xvfb only."""
from collections import Counter
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
import gi
gi.require_version('Atspi', '2.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Atspi, Gdk
from dock_layout_smoke import descendants
from contrast_audit import contrast


def measure_contrast(name, palette, scale):
    blue, white, background, unfilled = (53, 132, 228), (255, 255, 255), (23, 29, 44), (19, 24, 37)
    focus_color = (101, 216, 229)
    assert palette[background] >= 10 * scale * scale, 'Background sample absent'
    ratios = dict(focusToBackground=contrast([*focus_color, 1], [*background, 1]))
    if name in ('radio-checked', 'checkbox-checked', 'range-right'):
        assert palette[blue] >= 20 * scale * scale and palette[white] >= 2 * scale * scale, 'Expected native mark/fill palette absent'
        ratios['markToFill'] = contrast([*white, 1], [*blue, 1])
        ratios['fillToBackground'] = contrast([*blue, 1], [*background, 1])
    if name == 'range-right':
        assert palette[unfilled] >= 100 * scale * scale, 'Unfilled track sample absent'
        ratios['filledToUnfilledTrack'] = contrast([*blue, 1], [*unfilled, 1])
    if name in ('radio-unchecked', 'checkbox-unchecked'):
        interior = (18, 23, 35)
        assert palette[white] >= 20 * scale * scale and palette[interior] >= 10 * scale * scale, 'Unchecked light/dark paint sample absent'
        ratios['lightPaintToDarkPaint'] = contrast([*white, 1], [*interior, 1])
        ratios['lightPaintToBackground'] = contrast([*white, 1], [*background, 1])
    assert min(ratios.values()) >= 3, ('Native control contrast below3:1', name, ratios)
    return ratios


def audit(server, *, app, root, scale, xid, popup, language, pid):
    root = Path(root)
    assert os.environ['DESKMORPH_GEOMETRY_LAB'] == str(root)
    assert os.environ['DISPLAY'] == (root / 'display').read_text()
    assert os.environ['PULSE_SERVER'] == server.address
    assert server.root.is_relative_to(root)
    labels = json.loads((Path(__file__).resolve().parents[1] / 'src/i18n/messages.json').read_text())[language]
    report = dict(passed=False, language=language, scale=scale, captures=[], checks=[], auditSha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())

    def wait(predicate, message):
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            value = predicate()
            if value:
                return value
            time.sleep(.1)
        raise AssertionError(message)

    def control(name, role):
        return next((n for n in descendants(app) if n.get_role_name() == role and n.get_name() == name), None)

    def sinks():
        return json.loads(server.pactl('--format=json', 'list', 'sinks'))

    def default():
        return json.loads(server.pactl('--format=json', 'info'))['default_sink_name']

    def volume(name):
        values = next(s for s in sinks() if s['name'] == name)['volume'].values()
        return round(sum(float(v['value_percent'].rstrip('%')) for v in values) / len(values))

    x11 = ctypes.CDLL('libX11.so.6')
    xtst = ctypes.CDLL('libXtst.so.6')
    x11.XOpenDisplay.restype = ctypes.c_void_p
    x11.XSetInputFocus.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
    x11.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    x11.XKeysymToKeycode.restype = ctypes.c_uint
    x11.XSync.argtypes = [ctypes.c_void_p, ctypes.c_int]
    x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
    xtst.XTestFakeKeyEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]

    def keys(chord):
        props = subprocess.check_output(['xprop', '-id', xid, '_NET_WM_PID'], text=True, timeout=5)
        assert re.search(r'= ' + str(pid) + r'\b', props), 'Input target is not owned'
        connection = x11.XOpenDisplay(None)
        assert connection
        try:
            x11.XSetInputFocus(connection, int(xid, 16), 2, 0)
            codes = [x11.XKeysymToKeycode(connection, key) for key in chord]
            assert all(codes)
            for code in codes:
                assert xtst.XTestFakeKeyEvent(connection, code, 1, 0)
            for code in reversed(codes):
                assert xtst.XTestFakeKeyEvent(connection, code, 0, 0)
            x11.XSync(connection, 0)
        finally:
            x11.XCloseDisplay(connection)

    def focused(name, role):
        node = control(name, role)
        return node and node.get_state_set().contains(Atspi.StateType.FOCUSED)

    def focus(name, role):
        node = wait(lambda: control(name, role), 'Missing control: ' + name)
        assert node.get_component_iface().grab_focus()
        keys([])
        wait(lambda: focused(name, role), 'Focus missing: ' + name)
        return node

    def capture(name, node):
        time.sleep(.2)
        a = node.get_component_iface().get_extents(Atspi.CoordType.SCREEN)
        rect = [v * scale for v in (a.x, a.y, a.width, a.height)]
        x, y, width, height = rect
        px, py, pw, ph = popup
        assert px <= x and py <= y and x + width <= px + pw and y + height <= py + ph, rect
        # Radio/checkbox expose their label; sample just the native input area.
        if node.get_role_name() in ('radio button', 'check box'):
            width = min(width, 24 * scale)
        margin = 6 * scale
        region = [x - margin, y - margin, width + 2 * margin, height + 2 * margin]
        image = Gdk.pixbuf_get_from_window(Gdk.get_default_root_window(), *(v // scale for v in region))
        assert image is not None and (image.get_width(), image.get_height()) == tuple(region[2:])
        image.savev(str(root / (name + '.png')), 'png', [], [])
        data = image.get_pixels()
        stride, channels = image.get_rowstride(), image.get_n_channels()
        def pixel(ix, iy):
            offset = iy * stride + ix * channels
            return tuple(data[offset:offset + 3])
        palette = Counter(pixel(ix, iy) for iy in range(margin, margin + height)
                          for ix in range(margin, margin + width))
        focus_color = (101, 216, 229)
        focus_count = sum(pixel(ix, iy) == focus_color for iy in range(region[3]) for ix in range(region[2]))
        sample = dict(name=name, role=node.get_role_name(), rect=rect,
            palette=[dict(rgb=list(color), count=count) for color, count in palette.most_common(10)],
            focusPixels=focus_count, capture=str(root / (name + '.png')))
        report['captures'].append(sample)
        sample['contrastRatios'] = measure_contrast(name, palette, scale)
        assert focus_count >= 8 * scale * scale, ('Native focus pixels missing', sample)

    try:
        radio = focus('DeskMorph_Audio_B', 'radio button')
        keys([0x20])
        wait(lambda: default() == 'deskmorph_audio_b', 'Space did not select private output B')
        wait(lambda: focused('DeskMorph_Audio_B', 'radio button'), 'Output change lost focus')
        capture('radio-checked', control('DeskMorph_Audio_B', 'radio button'))
        report['checks'].append('Space selects private output B and restores focus')
        slider = focus(labels['audioVolume'], 'slider')
        before = volume('deskmorph_audio_b')
        keys([0xff53])
        wait(lambda: volume('deskmorph_audio_b') == before + 1, 'Right did not write volume+1')
        wait(lambda: focused(labels['audioVolume'], 'slider'), 'Volume change lost focus')
        capture('range-right', control(labels['audioVolume'], 'slider'))
        keys([0xff51])
        wait(lambda: volume('deskmorph_audio_b') == before, 'Left did not restore volume')
        report['checks'].append('Right/Left write and restore private sink volume')
        focus(labels['audioMute'], 'check box')
        keys([0x20])
        wait(lambda: next(s for s in sinks() if s['name'] == 'deskmorph_audio_b')['mute'], 'Space did not mute B')
        wait(lambda: focused(labels['audioMute'], 'check box'), 'Mute request lost focus')
        capture('checkbox-checked', control(labels['audioMute'], 'check box'))
        keys([0x20])
        wait(lambda: not next(s for s in sinks() if s['name'] == 'deskmorph_audio_b')['mute'], 'Space did not unmute B')
        wait(lambda: focused(labels['audioMute'], 'check box'), 'Unmute request lost focus')
        capture('checkbox-unchecked', control(labels['audioMute'], 'check box'))
        report['checks'].append('Space toggles private sink mute and restores focus')
        focus('DeskMorph_Audio_A', 'radio button')
        keys([0x20])
        wait(lambda: default() == 'deskmorph_audio_a', 'Output A not restored')
        capture('radio-unchecked', focus('DeskMorph_Audio_B', 'radio button'))
        assert volume('deskmorph_audio_b') == before
        report.update(passed=True, privateOutputAndVolumeRestored=True,
                      contrastStatus='Native checked mark/fill, unchecked light/dark paint and exterior, range filled/unfilled and focus/background all >=3:1',
                      policyEnabled=server.policy, sinkFactories=[s['properties'].get('factory.name') for s in sinks()])
        return report
    except Exception as error:
        report['error'] = repr(error)
        report['defaultSinkOnFailure'] = default()
        report['controlsOnFailure'] = [dict(role=n.get_role_name(), name=n.get_name(), checked=n.get_state_set().contains(Atspi.StateType.CHECKED), focused=n.get_state_set().contains(Atspi.StateType.FOCUSED)) for n in descendants(app) if n.get_role_name() in ('radio button', 'slider', 'check box', 'button', 'alert')]
        report['metadataOnFailure'] = subprocess.check_output(['pw-metadata', '-n', 'default'], env=server.env, text=True, timeout=5)
        raise
    finally:
        (root / 'audio-controls-result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
