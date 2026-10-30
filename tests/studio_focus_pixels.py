"""Native focus pixels alongside the shared Studio traversal, private Xvfb only."""
from pathlib import Path
import os
import json
import time
from gi.repository import Atspi, Gdk
from studio_tab_smoke import run


def audit(app, root, scale, studio, keys, native, config, original):
    root = Path(root)
    assert os.environ['DESKMORPH_GEOMETRY_LAB'] == str(root)
    assert os.environ['DISPLAY'] == (root / 'display').read_text()
    samples = []
    representatives = set()

    def observe(page, index, node):
        time.sleep(.12)  # Allow native scroll-to-focus and paint to finish.
        area = node.get_component_iface().get_extents(Atspi.CoordType.SCREEN)
        rect = [value * scale for value in (area.x, area.y, area.width, area.height)]
        frame = native('DeskMorph Studio')['rect']
        x, y, width, height = rect
        fx, fy, fw, fh = frame
        assert width > 0 and height > 0 and node.get_state_set().contains(Atspi.StateType.SHOWING), (page, index, rect)
        if not (fx <= x and fy <= y and x + width <= fx + fw and y + height <= fy + fh):
            image = Gdk.pixbuf_get_from_window(Gdk.get_default_root_window(), *(value // scale for value in frame))
            image.savev(str(root / 'clipped-focus-window.png'), 'png', [], [])
            raise AssertionError((node.get_name(), rect, frame))
        margin = 8 * scale
        left, top = max(fx, x - margin), max(fy, y - margin)
        right, bottom = min(fx + fw, x + width + margin), min(fy + fh, y + height + margin)
        region = [left, top, right - left, bottom - top]
        assert all(value % scale == 0 for value in region), region
        image = Gdk.pixbuf_get_from_window(Gdk.get_default_root_window(), *(value // scale for value in region))
        assert image is not None and (image.get_width(), image.get_height()) == tuple(region[2:])
        data = image.get_pixels()
        stride, channels = image.get_rowstride(), image.get_n_channels()
        focus = (103, 232, 249)
        count = sum(tuple(data[py * stride + px * channels:py * stride + px * channels + 3]) == focus
                    for py in range(image.get_height()) for px in range(image.get_width()))
        sample = dict(page=page, index=index, role=node.get_role_name(), name=node.get_name(),
                      rect=rect, focusPixels=count, expectedFocusColor=list(focus))
        if page == 3 and node.get_role_name() == 'toggle button' and height > 100 * scale:
            from contrast_audit import contrast
            def at(px, py):
                offset = (py - top) * stride + (px - left) * channels
                return tuple(data[offset:offset + 3])
            ring = at(x + width // 2, y + 5 * scale)
            backing = at(x + width // 2, y + 2 * scale)
            artwork = at(x + width // 2, y + 40 * scale)
            expected_artwork = (0, 0, 0) if node.get_name().endswith('black.png') else (255, 255, 255)
            assert artwork == expected_artwork, ('Fixture image not rendered', artwork, node.get_name())
            assert ring == focus and backing == (12, 16, 23), (ring, backing)
            ratio = contrast([*ring, 1], [*backing, 1])
            sample['artworkFocusContrast'] = dict(ring=list(ring), backing=list(backing), artwork=list(artwork), ratio=ratio, threshold=3)
            assert ratio >= 3, sample
        if node.get_role_name() == 'combo box':
            from collections import Counter
            from contrast_audit import contrast
            def pixel(px, py):
                offset = (py - top) * stride + (px - left) * channels
                return tuple(data[offset:offset + 3])
            arrow = (148, 163, 184)
            background = (17, 24, 39)
            arrow_region = Counter(pixel(px, py)
                for py in range(y + height // 2 - 4 * scale, y + height // 2 + 4 * scale)
                for px in range(x + width - 22 * scale, x + width - 10 * scale))
            assert arrow_region[arrow] >= 2 * scale * scale and arrow_region[background] >= 10 * scale * scale, arrow_region
            border = pixel(x + width // 2, y)
            exterior = pixel(x + width // 2, y - 2 * scale)
            assert border == (130, 145, 168), ('Unexpected select border', border)
            ratios = dict(arrowToFill=contrast([*arrow, 1], [*background, 1]),
                          borderToFill=contrast([*border, 1], [*background, 1]),
                          borderToExterior=contrast([*border, 1], [*exterior, 1]))
            sample['selectContrast'] = dict(arrow=list(arrow), fill=list(background),
                border=list(border), exterior=list(exterior), ratios=ratios, threshold=3)
            assert min(ratios.values()) >= 3, sample['selectContrast']
        samples.append(sample)
        (root / 'focus-samples.json').write_text(json.dumps(samples, ensure_ascii=False, indent=2) + '\n')
        representative = (page, node.get_role_name())
        if representative not in representatives or count < 8 * scale * scale:
            path = root / f'focus-page{page}-control{index}.png'
            image.savev(str(path), 'png', [], [])
            sample['capture'] = str(path)
            representatives.add(representative)
        assert count >= 8 * scale * scale, ('Keyboard focus pixels absent', sample)

    report = run(app, lambda: keys(studio, []),
                 lambda value=None, chord=None: keys(studio, chord or []),
                 report_root=root, on_focus=observe)
    assert config.read_bytes() == original, 'Tab traversal changed private config'
    return dict(passed=True, traversal=report, focusSamples=samples, configUnchanged=True,
                limits=['First seeded nav control excluded from pixel acceptance',
                        'Current fixture pages only, not all dynamic states or every outline edge'])
