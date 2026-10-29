"""Read-only native entry/navigation of a pinned app context popup."""
import json
import os
import signal
import select
import subprocess
from pathlib import Path
import time
from gi.repository import Atspi
from dock_layout_smoke import descendants


def run(app, focus_studio, native_keys, fixture, command):
    config = Path('/tmp/deskmorph-desktop-test/config/com.ducthanhdev.deskmorph/config.json')
    original = config.read_bytes()
    def wait(predicate, message):
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            result = predicate()
            if result: return result
            time.sleep(.1)
        popup = frame('DeskMorph Context Menu')
        print('ACTIVE', subprocess.check_output(['xprop','-root','_NET_ACTIVE_WINDOW'],text=True), flush=True)
        print('FAIL',message,[(n.get_role_name(),n.get_name(),n.get_attributes().get('xml-roles')) for n in descendants(popup)] if popup else 'popup hidden',flush=True)
        raise AssertionError(message)
    def frame(title):
        return next((n for n in descendants(app) if n.get_role_name() == 'frame' and n.get_name() == title), None)
    def buttons():
        popup = frame('DeskMorph Context Menu')
        return [n for n in descendants(popup) if n.get_role_name() == 'button'] if popup else []
    def enabled(node):
        return all(node.get_state_set().contains(s) for s in (Atspi.StateType.ENABLED, Atspi.StateType.SENSITIVE))
    observations = []
    for keys in ([0xffe1, 0xffc7], [0xff67]):  # Shift+F10 / Menu, never a VT chord.
        focus_studio('DeskMorph Taskbar')
        pin = wait(lambda: next((n for n in descendants(frame('DeskMorph Taskbar')) if n.get_role_name() == 'button' and n.get_name().startswith('DeskMorph Context Keyboard • 3 ')), None), 'Owned fixture windows not grouped')
        assert pin.get_component_iface().grab_focus()
        time.sleep(.5)
        wait(lambda: pin.get_state_set().contains(Atspi.StateType.FOCUSED), 'Source pin did not focus')
        native_keys(chord=keys)
        wait(lambda: buttons(), 'Context key did not open custom popup: ' + str(keys))
        expected = [n for n in buttons() if enabled(n)]
        wait(lambda: expected[0].get_state_set().contains(Atspi.StateType.FOCUSED), 'Missing initial context focus')
        sequence = []
        for index, node in enumerate(expected):
            wait(lambda: node.get_state_set().contains(Atspi.StateType.FOCUSED), 'Wrong Tab target ' + node.get_name())
            sequence.append(node.get_name()); assert sequence[-1].strip()
            if index + 1 < len(expected): native_keys(chord=[0xff09])
        for node in reversed(expected[:-1]):
            native_keys(chord=[0xffe1, 0xff09])
            wait(lambda: node.get_state_set().contains(Atspi.StateType.FOCUSED), 'Wrong reverse Tab target')
        for key, target in [(0xff57, expected[-1]), (0xff54, expected[0]), (0xff52, expected[-1]), (0xff50, expected[0])]:
            native_keys(chord=[key])
            wait(lambda: target.get_state_set().contains(Atspi.StateType.FOCUSED), 'Wrong context navigation target')
        disabled = [n.get_name() for n in buttons() if not enabled(n)]
        native_keys(chord=[0xff1b])
        wait(lambda: frame('DeskMorph Context Menu') is None, 'Escape did not dismiss')
        wait(lambda: pin.get_state_set().contains(Atspi.StateType.FOCUSED), 'Escape lost source pin focus')
        observations.append(dict(keys=keys, sequence=sequence, disabledSkipped=disabled, reverseMatches=True, arrowWrapAndHomeEnd=True, escapeRestores=True))
    vi = json.loads(original)['config']['language'] == 'vi'
    def button(label): return next((n for n in buttons() if n.get_name() == label), None)
    def focused(label):
        node = button(label)
        return bool(node and node.get_state_set().contains(Atspi.StateType.FOCUSED))
    # Use only the three windows owned by the fixture process.
    focus_studio('DeskMorph Taskbar')
    assert pin.get_component_iface().grab_focus()
    time.sleep(.2); native_keys(chord=[0xffe1, 0xffc7])
    launch = 'Mở ứng dụng' if vi else 'Open application'
    wait(lambda: button(launch), 'Launch action missing')
    time.sleep(.5)
    # The fixture pin command deliberately points to a nonexistent file.
    assert button(launch).get_component_iface().grab_focus()
    time.sleep(.2); native_keys(chord=[0xff0d])
    wait(lambda: any(n.get_role_name() in ('alert', 'notification') or n.get_attributes().get('xml-roles') == 'alert' for n in descendants(frame('DeskMorph Context Menu'))), 'Failed launch has no alert')
    wait(lambda: focused(launch), 'Failed request lost action focus')
    force = 'Buộc dừng…' if vi else 'Force quit…'
    cancel = 'Hủy' if vi else 'Cancel'
    force_node = wait(lambda: button(force), 'Force action missing')
    assert force_node.get_component_iface().grab_focus()
    time.sleep(.2); native_keys(chord=[0xff0d])
    wait(lambda: focused(cancel), 'Force review must focus Cancel')
    from gi.repository import Gdk
    rect = frame('DeskMorph Context Menu').get_component_iface().get_extents(Atspi.CoordType.SCREEN)
    image = Gdk.pixbuf_get_from_window(Gdk.get_default_root_window(), rect.x, rect.y, rect.width, rect.height)
    assert image is not None
    screenshot = f'/tmp/deskmorph-desktop-test/context-confirm-{"vi" if vi else "en"}.png'
    image.savev(screenshot, 'png', [], [])
    native_keys(chord=[0xff0d])
    wait(lambda: button(cancel) is None and focused(force), 'Cancel did not restore force trigger')
    assert fixture.poll() is None, 'Review/cancel terminated fixture'
    close3 = ('Đóng ' if vi else 'Close ') + 'DeskMorph Window Test 3'
    node = wait(lambda: button(close3), 'Owned window row missing')
    assert node.get_component_iface().grab_focus(); time.sleep(.2)
    command('close', 3)
    wait(lambda: button(close3) is None, 'Removed window stayed in context')
    wait(lambda: next(n for n in buttons() if enabled(n)).get_state_set().contains(Atspi.StateType.FOCUSED), 'Removed context row lost fallback focus')
    close2 = ('Đóng ' if vi else 'Close ') + 'DeskMorph Window Test 2'
    node = wait(lambda: button(close2), 'Second owned row missing')
    assert node.get_component_iface().grab_focus(); time.sleep(.2)
    native_keys(chord=[0xff0d])
    wait(lambda: frame('DeskMorph Context Menu') is None, 'Successful close did not dismiss context')
    state = command('title', 1, title='DeskMorph Window Test 1')
    assert '2' not in state and '1' in state, 'Close action did not close exactly fixture window 2'
    assert config.read_bytes() == original
    report = dict(pid=app.get_process_id(), screenshot=screenshot, observations=observations, configUnchanged=True, failedLaunchFocus=True, forceReviewCancelFocus=True, removedRowFallback=True, enterClosesOwnedWindow=True, scope='Native pinned fixture context entry/Tab/arrows/Escape, nonexistent command failure, force review/cancel only, external row removal and Enter close of owned fixture window2; no user app actions, no force kill or unpinned context coverage')
    Path('/tmp/deskmorph-desktop-test/context-keyboard-result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report, ensure_ascii=False), flush=True)
    return report


def run_matrix(app, config_home, focus_studio, native_keys, start_app, set_app):
    path = Path(config_home) / 'com.ducthanhdev.deskmorph/config.json'
    original = path.read_bytes()
    (Path('/tmp/deskmorph-desktop-test') / 'context-keyboard-original.json').write_bytes(original)
    pids = []; fixtures = []; reports = []
    def stop():
        pid = app.get_process_id(); proc = Path(f'/proc/{pid}')
        if not proc.exists(): return
        assert f'DESKMORPH_CONFIG_HOME={config_home}'.encode() in (proc / 'environ').read_bytes().split(b'\0')
        os.kill(pid, signal.SIGTERM)
        deadline = time.monotonic() + 7
        while (proc / 'stat').exists():
            try:
                if (proc / 'stat').read_text().rsplit(')', 1)[1].split()[0] == 'Z': break
            except FileNotFoundError: break
            assert time.monotonic() < deadline
            time.sleep(.1)
    def start():
        nonlocal app
        app = start_app(); set_app(app); pids.append(app.get_process_id())
    try:
        for language in ('vi', 'en'):
            stop()
            cfg = json.loads(original)
            cfg['config'].update(language=language, autoHide=False, enabled=True, showApps=True)
            cfg['config']['pinnedApps'].insert(0, dict(id='deskmorph-context-keyboard', name='DeskMorph Context Keyboard', command='/tmp/deskmorph-desktop-test/context-keyboard-nonexistent', matchClasses=['DeskMorphContextKeyboard'], enabled=True, iconType='custom'))
            assert not Path('/tmp/deskmorph-desktop-test/context-keyboard-nonexistent').exists()
            path.write_text(json.dumps(cfg))
            env = dict(os.environ, DESKMORPH_CONFIG_HOME=config_home, DESKMORPH_WINDOW_FIXTURE_CLASS='DeskMorphContextKeyboard')
            fixture = subprocess.Popen(['/usr/bin/python3', str(Path(__file__).with_name('desktop_smoke.py').resolve()), '--window-fixture'], env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
            fixtures.append(fixture)
            def response():
                assert select.select([fixture.stdout], [], [], 5)[0], 'No owned fixture response'
                line = fixture.stdout.readline(); assert line
                return json.loads(line)
            def command(action, index, **kwargs):
                fixture.stdin.write(json.dumps(dict(action=action, index=index, **kwargs)) + '\n'); fixture.stdin.flush()
                return response()
            response(); start(); time.sleep(1)
            try: reports.append(run(app, focus_studio, native_keys, fixture, command))
            finally:
                fixture.terminate(); fixture.wait(timeout=5)
    finally:
        for fixture in fixtures:
            if fixture.poll() is None: fixture.terminate()
            fixture.wait(timeout=5)
        stop(); path.write_bytes(original); start()
    report = dict(runs=reports, fixturePids=pids[:-1], windowFixturePids=[fixture.pid for fixture in fixtures], normalPid=pids[-1], configRestored=path.read_bytes() == original)
    assert report['configRestored']
    Path('/tmp/deskmorph-desktop-test/context-keyboard-matrix-result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    return app
