"""Audit real Tab/Shift+Tab traversal and names in each Studio settings page.
No settings are changed. AT-SPI only seeds focus at the first navigation button.
"""
import json
from pathlib import Path
import time
from gi.repository import Atspi
from dock_layout_smoke import descendants


def run(app, focus_studio, native_keys, only_tab=None):
    send_keys = native_keys
    def native_keys(value=None, chord=None):
        # Restore only our owned Studio if a desktop notification/application stole
        # native activation. The shared helper rechecks PID before sending keys.
        try:
            send_keys(value=value, chord=chord)
        except AssertionError as error:
            if str(error) != 'Keyboard focus left isolated app and explicitly owned fixture':
                raise
            focus_studio()
            send_keys(value=value, chord=chord)
    roles = {'button', 'toggle button', 'check box', 'radio button', 'entry', 'text', 'slider', 'combo box', 'color chooser'}
    def frame():
        return next(n for n in descendants(app) if n.get_role_name() == 'frame' and n.get_name() == 'DeskMorph Studio')
    def controls():
        return [n for n in descendants(frame()) if n.get_role_name() in roles and (n.get_state_set().contains(Atspi.StateType.FOCUSABLE) or not enabled(n)) and n.get_state_set().contains(Atspi.StateType.VISIBLE)]
    def enabled(node):
        return node.get_state_set().contains(Atspi.StateType.ENABLED) and node.get_state_set().contains(Atspi.StateType.SENSITIVE)
    def wait(predicate, message):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            result = predicate()
            if result:
                return result
            time.sleep(.05)
        raise AssertionError(message)
    def identity(node):
        return [node.get_role_name(), node.get_name()]
    observations = []
    focus_studio()
    tabs = controls()[:5]
    assert len(tabs) == 5 and all(n.get_role_name() == 'button' for n in tabs)
    tab_names = [n.get_name() for n in tabs]
    for tab_index, tab_name in enumerate(tab_names):
        if only_tab is not None and tab_index != only_tab:
            continue
        # Select each page with real keys, then start the traversal at nav button 1.
        assert tabs[tab_index].get_component_iface().grab_focus()
        native_keys(chord=[0xff0d]); time.sleep(.8)
        assert tabs[0].get_component_iface().grab_focus()
        expected = [n for n in controls() if enabled(n)]
        disabled = [identity(n) for n in controls() if not enabled(n)]
        assert expected and all(n.get_name().strip() for n in expected), [('unnamed', identity(n)) for n in expected if not n.get_name().strip()]
        visited = []
        for index, target in enumerate(expected):
            wait(lambda: target.get_state_set().contains(Atspi.StateType.FOCUSED), 'Wrong Tab target: ' + tab_name + ' ' + str(identity(target)))
            current = target
            visited.append(identity(current))
            if index + 1 < len(expected):
                native_keys(chord=[0xff09])
                wait(lambda: not current.get_state_set().contains(Atspi.StateType.FOCUSED), 'Tab focus stuck on ' + str(identity(current)))
        # Reverse the same traversal to detect traps/different reverse order.
        for target in reversed(expected[:-1]):
            native_keys(chord=[0xffe1, 0xff09])
            wait(lambda: target.get_state_set().contains(Atspi.StateType.FOCUSED), 'Shift+Tab order differs: ' + str(identity(target)))
        disclosure = None
        if tab_index == 1:
            summary = next(n for n in controls() if n.get_role_name() == 'button' and n.get_state_set().contains(Atspi.StateType.EXPANDABLE))
            assert summary.get_component_iface().grab_focus()
            native_keys(chord=[0xff0d])
            wait(lambda: summary.get_state_set().contains(Atspi.StateType.EXPANDED), 'Enter did not expose expanded state')
            native_keys(chord=[0xff09])
            field = next(n for n in controls() if n.get_role_name() in ('entry', 'text') and n.get_state_set().contains(Atspi.StateType.MULTI_LINE) and n.get_name() == summary.get_name())
            wait(lambda: field.get_state_set().contains(Atspi.StateType.FOCUSED), 'Tab did not reach class textarea')
            from gi.repository import Gdk
            rect = frame().get_component_iface().get_extents(Atspi.CoordType.SCREEN)
            screenshot = '/tmp/deskmorph-desktop-test/studio-disclosure-focus.png'
            pixbuf = Gdk.pixbuf_get_from_window(Gdk.get_default_root_window(), rect.x, rect.y, rect.width, rect.height)
            assert pixbuf is not None
            pixbuf.savev(screenshot, 'png', [], [])
            assert summary.get_component_iface().grab_focus()
            native_keys(chord=[0x20])
            wait(lambda: not summary.get_state_set().contains(Atspi.StateType.EXPANDED), 'Space did not collapse disclosure')
            disclosure = dict(enterExpands=True, tabReachesTextarea=True, spaceCollapses=True, screenshot=screenshot)
        observations.append(dict(disclosure=disclosure, tab=tab_name, sequence=visited, disabledSkipped=disabled, reverseMatches=True))
        Path(f'/tmp/deskmorph-desktop-test/studio-tab-{tab_index}-result.json').write_text(json.dumps(dict(pid=app.get_process_id(), **observations[-1]), ensure_ascii=False, indent=2))
        print(json.dumps(dict(tab=tab_name, count=len(visited), disabled=len(disabled)), ensure_ascii=False), flush=True)
    report = dict(pid=app.get_process_id(), tabs=observations, scope='Native X11 current Studio state, existing profile; Tab/ShiftTab names/order/disabled, first class disclosure Enter/Space/textarea; no settings mutation, popup, color-save or open-review coverage')
    Path('/tmp/deskmorph-desktop-test/studio-tab-result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    return report
