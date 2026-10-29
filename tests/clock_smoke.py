"""Live vi/en clock settings on Dock, preview and calendar; no host clock changes."""
from datetime import datetime
import json
import os
from pathlib import Path
import re
import signal
import time
from gi.repository import Atspi
from dock_layout_smoke import descendants


def run(app, config_home, click, focus_studio, native_keys, test_app, start_app, set_app):
    root = Path('/tmp/deskmorph-desktop-test')
    config_path = Path(config_home) / 'com.ducthanhdev.deskmorph/config.json'
    original = config_path.read_bytes()
    config = lambda: json.loads(config_path.read_text())['config']
    observations = []
    owned_pids = []
    clock_pattern = re.compile(r'(?<!\d)(\d{2}):(\d{2})(?::(\d{2}))?(?:\s*(AM|PM|SA|CH))?')

    def stop():
        try:
            current = test_app()
        except RuntimeError:
            return
        pid = current.get_process_id()
        assert pid == app.get_process_id()
        env = Path(f'/proc/{pid}/environ').read_bytes().split(b'\0')
        assert f'DESKMORPH_CONFIG_HOME={config_home}'.encode() in env
        os.kill(pid, signal.SIGTERM)
        deadline = time.monotonic() + 7
        while Path(f'/proc/{pid}/stat').exists():
            try:
                if Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[0] == 'Z':
                    break
            except FileNotFoundError:
                break
            assert time.monotonic() < deadline, 'Owned app did not stop'
            time.sleep(.1)
        try:
            os.waitpid(pid, os.WNOHANG)
        except ChildProcessError:
            pass

    def start():
        nonlocal app
        app = start_app()
        set_app(app)
        owned_pids.append(app.get_process_id())

    def wait(predicate, message):
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            value = predicate()
            if value:
                return value
            time.sleep(.15)
        raise AssertionError(message)

    def text(node):
        output = []
        for child in descendants(node):
            if child.get_name():
                output.append(child.get_name())
            try:
                output.append(Atspi.Text.get_text(child, 0, -1))
            except Exception:
                pass
        return '\n'.join(output).replace('\u202f', ' ').replace('\u00a0', ' ')

    def find(name, role=None):
        return next((node for node in descendants(app) if node.get_name() == name and
                     (role is None or node.get_role_name() == role)), None)

    def valid_clock(value, language, mode24, seconds):
        for match in clock_pattern.finditer(value):
            hour, minute, second, period = match.groups()
            if (second is not None) != seconds or bool(period) == mode24:
                continue
            for offset in range(-4, 5):
                now = datetime.fromtimestamp(time.time() + offset)
                expected_hour = now.hour if mode24 else (now.hour % 12 or 12)
                expected_period = None if mode24 else ('AM' if now.hour < 12 else 'PM') if language == 'en' else ('SA' if now.hour < 12 else 'CH')
                if (int(hour), int(minute), period) == (expected_hour, now.minute, expected_period) and (not seconds or int(second) == now.second):
                    return match.group(0)
        return None

    def localized_date(value, language):
        now = datetime.now()
        if language == 'vi':
            return bool(re.search(r'\b' + str(now.day) + r'\s+thg\s+' + str(now.month) + r'\b', value))
        month = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')[now.month - 1]
        return bool(re.search(month + r'\s+' + str(now.day) + r'\b', value))

    def settings(language, mode24, seconds):
        current_language = config()['language']
        focus_studio()
        if language != current_language:
            click('Hệ thống' if current_language == 'vi' else 'System')
            click('Tiếng Việt' if language == 'vi' else 'English')
            wait(lambda: config()['language'] == language, 'Language was not persisted')
        click('Taskbar Studio')
        for field, desired, label in (
                ('clock24', mode24, 'Định dạng 24 giờ' if language == 'vi' else '24-hour clock'),
                ('clockSeconds', seconds, 'Hiện giây' if language == 'vi' else 'Show seconds')):
            if config()[field] != desired:
                click(label, 'check box')
                wait(lambda: config()[field] == desired, 'Clock preference was not saved: ' + field)

    def observe(language, mode24, seconds):
        calendar = 'Mở lịch' if language == 'vi' else 'Open calendar'
        preview = 'Xem trước Dock' if language == 'vi' else 'Dock preview'
        dock = wait(lambda: find(calendar, 'button'), 'Clock button absent')
        description = wait(lambda: dock.get_description() if valid_clock(dock.get_description(), language, mode24, seconds) else None,
                           'Dock description did not receive clock settings')
        assert localized_date(description, language), 'Dock date is not localized: ' + description
        preview_node = wait(lambda: find(preview, 'landmark'), 'Preview not accessible')
        preview_text = wait(lambda: text(preview_node) if valid_clock(text(preview_node), language, mode24, seconds) else None,
                            'Preview clock differs from saved preferences')
        assert localized_date(preview_text, language), 'Preview date is not localized'
        focus_studio()
        click(calendar)
        popup = wait(lambda: find('DeskMorph Calendar', 'frame'), 'Calendar not shown')
        popup_text = wait(lambda: text(popup) if valid_clock(text(popup), language, mode24, seconds) else None,
                          'Calendar clock differs from saved preferences')
        assert ('tháng ' + str(datetime.now().month) in popup_text if language == 'vi' else
                ('January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December')[datetime.now().month - 1] in popup_text), 'Calendar date/month is not localized'
        native_keys(chord=[0xff1b])
        wait(lambda: not find('DeskMorph Calendar', 'frame'), 'Calendar did not dismiss')
        return {'language': language, 'clock24': mode24, 'clockSeconds': seconds,
                'dockDescription': description, 'previewClock': valid_clock(preview_text, language, mode24, seconds),
                'calendarClock': valid_clock(popup_text, language, mode24, seconds)}

    try:
        stop()
        fixture = json.loads(original)
        fixture['config'].update(enabled=True, showClock=True, autoHide=False, language='vi', keepDockOnClose=True)
        config_path.write_text(json.dumps(fixture))
        start()
        for language in ('vi', 'en'):
            for mode24 in (True, False):
                for seconds in (True, False):
                    settings(language, mode24, seconds)
                    observation = observe(language, mode24, seconds)
                    observations.append(observation)
                    print(json.dumps(observation, ensure_ascii=False), flush=True)
        assert config()['language'] == 'en' and not config()['clock24'] and not config()['clockSeconds']
        stop()
        start()
        focus_studio()
        click('Taskbar Studio')
        persisted = observe('en', False, False)
        report = {'passed': ['8 live combinations on Dock, preview and calendar', 'localized dates on three surfaces',
                             'English 12-hour clock without seconds persists across restart'],
                  'observations': observations, 'afterRestart': persisted, 'testPids': owned_pids[:],
                  'scope': 'Actual host time; midnight/noon/year rollover use deterministic formatter tests. Host clock unchanged.'}
    finally:
        stop()
        config_path.write_bytes(original)
        start()
    report.update(normalPid=app.get_process_id(), preferencesRestored=config_path.read_bytes() == original)
    assert report['preferencesRestored']
    (root / 'clock-result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, ensure_ascii=False), flush=True)
    return app
