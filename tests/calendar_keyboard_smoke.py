"""Real keyboard calendar navigation in the isolated native application."""
import json
import re
from datetime import date, timedelta
import calendar
from pathlib import Path
import time
from gi.repository import Atspi
from dock_layout_smoke import descendants


def run(app, click, focus_studio, native_keys):
    def wait(predicate, message):
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            result = predicate()
            if result:
                return result
            time.sleep(.1)
        raise AssertionError(message)

    def nodes():
        return list(descendants(app))

    def focused():
        return next((n for n in descendants(popup) if n.get_role_name() in ('button', 'toggle button') and n.get_state_set().contains(Atspi.StateType.FOCUSED)), None)

    focus_studio()
    name = next(n.get_name() for n in nodes() if n.get_role_name() == 'button' and n.get_name() in ('Mở lịch', 'Open calendar'))
    click(name)
    observations = []
    def civil(name):
        match = re.search(r'(\d+) tháng (\d+), (\d+)', name)
        if match:
            day, month, year = map(int, match.groups())
            return date(year, month, day)
        for month, label in enumerate(calendar.month_name):
            match = re.search(rf'{label} (\d+), (\d+)', name) if label else None
            if match:
                return date(int(match[2]), month, int(match[1]))
        raise AssertionError('Unknown accessible date: ' + name)
    def destination(value, label):
        if label in ('right', 'left', 'down', 'up'):
            return value + timedelta(days={'right': 1, 'left': -1, 'down': 7, 'up': -7}[label])
        if label in ('Monday', 'Sunday'):
            return value + timedelta(days=(0 if label == 'Monday' else 6) - value.weekday())
        offset = {'next month': 1, 'previous month': -1, 'next year': 12}[label]
        year, month = divmod(value.year * 12 + value.month - 1 + offset, 12)
        return date(year, month + 1, min(value.day, calendar.monthrange(year, month + 1)[1]))
    try:
        popup = wait(lambda: next((n for n in nodes() if n.get_role_name() == 'frame' and n.get_name() == 'DeskMorph Calendar'), None), 'Calendar missing')
        click('Hôm nay' if name == 'Mở lịch' else 'Today')
        # Enter the single date tab stop from the navigation controls.
        days = [n for n in descendants(popup) if n.get_role_name() in ('toggle button', 'button') and ',' in n.get_name()]
        assert len(days) >= 35, [(n.get_role_name(), n.get_name()) for n in descendants(popup)]
        today = next(n for n in days if n.get_state_set().contains(Atspi.StateType.PRESSED))
        assert today.get_component_iface().grab_focus()
        time.sleep(.2)
        initial = focused().get_name()
        print('Initial date focus:', initial, flush=True)
        for keys, label in [([0xff53], 'right'), ([0xff51], 'left'), ([0xff54], 'down'), ([0xff52], 'up'), ([0xff56], 'next month'), ([0xff55], 'previous month'), ([0xff50], 'Monday'), ([0xff57], 'Sunday'), ([0xffe1, 0xff56], 'next year')]:
            before = focused().get_name()
            native_keys(chord=keys)
            after = wait(lambda: focused().get_name() if focused() and civil(focused().get_name()) == destination(civil(before), label) else None, 'Wrong date focus: ' + label)
            assert civil(after) == destination(civil(before), label), (label, before, after)
            observations.append({'key': label, 'before': before, 'after': after})
        native_keys(chord=[0xff0d])
        wait(lambda: focused().get_state_set().contains(Atspi.StateType.PRESSED), 'Enter did not select date')
        selected = focused().get_name()
        native_keys(chord=[0xffe1, 0xff09])
        assert focused().get_name() != selected, 'Shift Tab must leave dates in one step'
        native_keys(chord=[0xff09])
        assert focused().get_name() == selected, 'Tab must return to single roving date stop'
        from gi.repository import Gdk
        rect = popup.get_component_iface().get_extents(Atspi.CoordType.SCREEN)
        screenshot = '/tmp/deskmorph-desktop-test/calendar-keyboard.png'
        pixbuf = Gdk.pixbuf_get_from_window(Gdk.get_default_root_window(), rect.x, rect.y, rect.width, rect.height)
        assert pixbuf is not None
        pixbuf.savev(screenshot, 'png', [], [])
        report = {'screenshot': screenshot, 'pid': app.get_process_id(), 'initial': initial, 'navigation': observations, 'enterSelects': True, 'singleDateTabStop': True}
    finally:
        native_keys(chord=[0xff1b])
    wait(lambda: not any(n.get_role_name() == 'frame' and n.get_name() == 'DeskMorph Calendar' for n in nodes()), 'Escape did not dismiss')
    report['escapeDismisses'] = True
    Path('/tmp/deskmorph-desktop-test/calendar-keyboard-result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, ensure_ascii=False))
