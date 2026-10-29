"""Native popup traversal and focus recovery using owned MPRIS players only."""
import json
import os
from pathlib import Path
import subprocess
import signal
import time
from gi.repository import Atspi
from dock_layout_smoke import descendants


def run(app, click, focus_studio, native_keys, missing_audio=False):
    root = Path('/tmp/deskmorph-desktop-test')
    config = root / 'config/com.ducthanhdev.deskmorph/config.json'
    original = config.read_bytes()
    language = json.loads(original)['config']['language']
    vi = language == 'vi'
    fixtures = []
    token = f"{os.getpid()}_{time.time_ns()}"
    report = dict(pid=app.get_process_id(), language=language, missingAudio=missing_audio)
    roles = {'button', 'check box', 'radio button', 'slider', 'entry', 'combo box'}
    def wait(predicate, message):
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            result = predicate()
            if result: return result
            time.sleep(.1)
        print('FAILED',message,[(n.get_role_name(),n.get_name(),n.get_state_set().contains(Atspi.StateType.FOCUSED),n.get_state_set().contains(Atspi.StateType.CHECKED)) for n in controls()],flush=True)
        raise AssertionError(message)
    def popup():
        return next(n for n in descendants(app) if n.get_role_name() == 'frame' and n.get_name() == 'DeskMorph Context Menu')
    def controls():
        return [n for n in descendants(popup()) if n.get_role_name() in roles and n.get_state_set().contains(Atspi.StateType.VISIBLE)]
    def focused():
        return next((n for n in controls() if n.get_state_set().contains(Atspi.StateType.FOCUSED)), None)
    def find(name):
        return next((n for n in controls() if n.get_name() == name), None)
    def enabled(node):
        return all(node.get_state_set().contains(state) for state in (Atspi.StateType.ENABLED, Atspi.StateType.SENSITIVE))
    def open_popup(label):
        focus_studio('DeskMorph Taskbar')
        dock = next(n for n in descendants(app) if n.get_role_name() == 'frame' and n.get_name() == 'DeskMorph Taskbar')
        source = next(n for n in descendants(dock) if n.get_role_name() == 'button' and n.get_name() == label)
        assert source.get_component_iface().grab_focus()
        time.sleep(.2); native_keys(chord=[0xff0d])
        close = wait(lambda: find('Đóng' if vi else 'Close'), 'Close missing')
        wait(lambda: close.get_state_set().contains(Atspi.StateType.FOCUSED), 'Initial Close focus missing')
        return True
    def audit(label):
        expected = [n for n in controls() if enabled(n) and (n.get_role_name() != 'radio button' or n.get_state_set().contains(Atspi.StateType.CHECKED))]
        assert expected and all(n.get_name().strip() for n in expected)
        close = expected[0]
        assert close.get_name() == ('Đóng' if vi else 'Close')
        wait(lambda: focused() == close, 'Popup did not initially focus Close')
        sequence = []
        for index, target in enumerate(expected):
            wait(lambda: target.get_state_set().contains(Atspi.StateType.FOCUSED), 'Wrong Tab target: ' + target.get_name())
            sequence.append([target.get_role_name(), target.get_name()])
            if index + 1 < len(expected): native_keys(chord=[0xff09])
        for target in reversed(expected[:-1]):
            native_keys(chord=[0xffe1, 0xff09])
            wait(lambda: target.get_state_set().contains(Atspi.StateType.FOCUSED), 'Wrong ShiftTab target: ' + target.get_name())
        value = dict(sequence=sequence, disabledSkipped=[[n.get_role_name(), n.get_name()] for n in controls() if not enabled(n)], reverseMatches=True, closeSeededForTraversal=True)
        report[label] = value
        print(label, json.dumps(value, ensure_ascii=False), flush=True)
    def calls(index):
        path = fixtures[index][1]
        return [json.loads(line)['method'] for line in path.read_text().splitlines()] if path.exists() else []
    try:
        for suffix in ('A', 'B'):
            log = root / f'keyboard-mpris-{token}-{suffix}.jsonl'
            name = f'org.mpris.MediaPlayer2.deskmorph_test_keyboard_{token}_{suffix}'
            identity = f'DeskMorph_Keyboard_{suffix}'
            process = subprocess.Popen(['/usr/bin/python3', str(Path(__file__).with_name('mpris_fixture.py')), '--name', name, '--identity', identity, '--log', str(log), *(['--can-next'] if suffix == 'A' else [])], stdin=subprocess.PIPE, text=True)
            fixtures.append((process, log))
            wait(lambda: Path(str(log) + '.ready').exists(), 'Player fixture not ready')
        report['initialAudioCloseFocused'] = open_popup('Âm thanh' if vi else 'Audio')
        wait(lambda: find('DeskMorph_Keyboard_B'), 'Missing player chooser')
        if missing_audio:
            wait(lambda: find('Thử lại' if vi else 'Retry'), 'Missing audio error has no Retry')
        # Seed selection of our fixture only; Space and subsequent actions are native keys.
        target = find('DeskMorph_Keyboard_B'); assert target.get_component_iface().grab_focus()
        time.sleep(.2); native_keys(chord=[0x20])
        wait(lambda: target.get_state_set().contains(Atspi.StateType.CHECKED), 'Space did not select fixture')
        close = find('Đóng' if vi else 'Close'); assert close.get_component_iface().grab_focus()
        time.sleep(.2); audit('audio')
        if missing_audio:
            details = find('Chi tiết' if vi else 'Details'); assert details.get_component_iface().grab_focus()
            time.sleep(.2); native_keys(chord=[0xff0d])
            wait(lambda: details.get_state_set().contains(Atspi.StateType.EXPANDED), 'Enter did not expand error details')
            native_keys(chord=[0x20])
            wait(lambda: not details.get_state_set().contains(Atspi.StateType.EXPANDED), 'Space did not collapse error details')
            retry = find('Thử lại' if vi else 'Retry'); assert retry.get_component_iface().grab_focus()
            time.sleep(.2); native_keys(chord=[0xff0d]); time.sleep(.5)
            assert focused() and focused().get_name() == retry.get_name(), 'Retry lost keyboard position'
            report['audioErrorKeyboard'] = dict(enterDetails=True, spaceCollapses=True, enterRetryKeepsFocus=True)

        pause = find('Tạm dừng' if vi else 'Pause'); assert pause.get_component_iface().grab_focus()
        time.sleep(.2); native_keys(chord=[0xff0d])
        wait(lambda: 'Pause' in calls(1), 'Enter did not pause selected fixture')
        play = wait(lambda: find('Phát' if vi else 'Play'), 'Play state not rendered')
        wait(lambda: play.get_state_set().contains(Atspi.StateType.FOCUSED), 'Focus lost during Pause/Play state change')
        native_keys(chord=[0xff0d]); wait(lambda: 'Play' in calls(1), 'Enter did not resume fixture')
        assert not calls(0), 'Media action reached unselected fixture'
        report['mediaKeyboard'] = dict(spaceSelects=True, enterPausePlay=True, targetOnly=True, focusSurvivesState=True)
        target = find('DeskMorph_Keyboard_B'); assert target.get_component_iface().grab_focus()
        time.sleep(.2)
        fixtures[1][0].terminate(); fixtures[1][0].wait(timeout=5)
        wait(lambda: find('DeskMorph_Keyboard_B') is None, 'Exited player remained')
        wait(lambda: focused() and focused().get_name() == ('Đóng' if vi else 'Close'), 'Removed player did not restore focus to Close')
        report['removedPlayerFocusClose'] = True
        native_keys(chord=[0xff1b])
        report['initialSystemCloseFocused'] = open_popup('Tiện ích hệ thống' if vi else 'System utilities')
        wait(lambda: find('Mở Downloads' if vi else 'Open Downloads'), 'System actions missing')
        time.sleep(1); audit('system')
        native_keys(chord=[0xff1b])
        report['configUnchanged'] = config.read_bytes() == original
        assert report['configUnchanged']
    finally:
        for process, _ in fixtures:
            if process.poll() is None: process.terminate()
            process.wait(timeout=5)
        report['fixturePids'] = [process.pid for process, _ in fixtures]
        report['fixturesExited'] = all(process.poll() is not None for process, _ in fixtures)
        report['scope'] = 'Native X11 current audio/system state, radio groups use checked Tab stop; only owned MPRIS receives Space/Enter media actions. No audio writes or system app launches; no screen reader certification.'
        (root / 'popup-keyboard-result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    return report


def run_matrix(app, config_home, click, focus_studio, native_keys, start_app, set_app):
    path = Path(config_home) / 'com.ducthanhdev.deskmorph/config.json'
    original = path.read_bytes()
    (Path('/tmp/deskmorph-desktop-test') / 'popup-keyboard-original.json').write_bytes(original)
    pids = []; reports = []
    def stop():
        pid = app.get_process_id()
        proc = Path(f'/proc/{pid}')
        if not proc.exists(): return
        assert f'DESKMORPH_CONFIG_HOME={config_home}'.encode() in (proc / 'environ').read_bytes().split(b'\0')
        os.kill(pid, signal.SIGTERM)
        deadline = time.monotonic() + 7
        while (proc / 'stat').exists():
            try:
                if (proc / 'stat').read_text().rsplit(')', 1)[1].split()[0] == 'Z': break
            except FileNotFoundError: break
            assert time.monotonic() < deadline, 'Owned app failed to stop'
            time.sleep(.1)
    def start(overrides=None):
        nonlocal app
        app = start_app(env_overrides=overrides); set_app(app); pids.append(app.get_process_id())
    try:
        for language, missing in [('vi', False), ('en', False), ('vi', True), ('en', True)]:
            stop()
            fixture = json.loads(original)
            fixture['config'].update(language=language, autoHide=False, enabled=True, showAudio=True, showSystem=True)
            path.write_text(json.dumps(fixture))
            start({'PULSE_SERVER': 'unix:/tmp/deskmorph-nonexistent-keyboard-service'} if missing else None)
            reports.append(run(app, click, focus_studio, native_keys, missing))
    finally:
        stop(); path.write_bytes(original); start()
    result = dict(runs=reports, fixturePids=pids[:-1], normalPid=pids[-1], configRestored=path.read_bytes() == original)
    assert result['configRestored']
    (Path('/tmp/deskmorph-desktop-test') / 'popup-keyboard-matrix-result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    return app
