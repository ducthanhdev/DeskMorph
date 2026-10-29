"""Restart real private audio daemons while the isolated native popup stays open."""
import json
import os
import re
from pathlib import Path
import signal
import subprocess
import tempfile
import time
from gi.repository import Atspi, GLib
from dock_layout_smoke import descendants
from private_audio_server import PrivateAudioServer


def run(app, config_home, focus_studio, native_keys, start_app, set_app):
    path = Path(config_home) / 'com.ducthanhdev.deskmorph/config.json'
    original = path.read_bytes()
    root = Path('/tmp/deskmorph-desktop-test')
    (root / 'audio-restart-original.json').write_bytes(original)
    def host():
        info = json.loads(subprocess.check_output(['pactl', '--format=json', 'info'], text=True, timeout=5))
        return {key: info[key] for key in ('server_string', 'server_name', 'default_sink_name')}
    before = host()
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
    def start(overrides=None):
        nonlocal app
        app = start_app(env_overrides=overrides); set_app(app)
    def wait(predicate, message, timeout=15):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                result = predicate()
            except GLib.GError:
                # WebKit replaces accessible children as the sink/error UI
                # changes. Retry a fresh traversal only while the owner lives.
                proc = Path(f'/proc/{app.get_process_id()}')
                assert proc.exists() and (proc / 'stat').read_text().rsplit(')', 1)[1].split()[0] != 'Z', 'Native app exited during AT-SPI query'
                report['transientAtspiRetries'] += 1
                result = None
            if result: return result
            time.sleep(.1)
        raise AssertionError(message)
    def frame(title):
        return next((n for n in descendants(app) if n.get_role_name() == 'frame' and n.get_name() == title), None)
    def nodes():
        popup = frame('DeskMorph Context Menu')
        return list(descendants(popup)) if popup else []
    def slider(): return next((n for n in nodes() if n.get_role_name() == 'slider' and n.get_name() == 'Âm lượng'), None)
    def value():
        node = slider()
        return node.get_value_iface().get_current_value() if node else None
    def has_error(): return any((n.get_attributes() or {}).get('xml-roles') == 'alert' or n.get_role_name() in ('alert', 'notification') for n in nodes())
    def subscriptions():
        children = set()
        for p in Path(f'/proc/{app.get_process_id()}/task').glob('*/children'):
            try: children.update(p.read_text().split())
            except OSError: pass
        return [int(pid) for pid in children if Path(f'/proc/{pid}/cmdline').exists() and Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\0')[:2] == [b'pactl', b'subscribe']]
    def open_audio():
        # Startup can still deliver Studio activation after AT-SPI is ready.
        time.sleep(1)
        focus_studio('DeskMorph Taskbar')
        button = next(n for n in descendants(frame('DeskMorph Taskbar')) if n.get_role_name() == 'button' and n.get_name() == 'Âm thanh')
        assert button.get_component_iface().grab_focus()
        wait(lambda: button.get_state_set().contains(Atspi.StateType.FOCUSED), 'Audio source did not receive native focus')
        time.sleep(.2); native_keys(chord=[0xff0d])
        wait(lambda: slider(), 'Audio snapshot did not reach native popup')
    cycle_count = int(os.environ.get('DESKMORPH_RESTART_CYCLES', '3'))
    assert 3 <= cycle_count <= 100, 'Restart stress requires 3..100 cycles'
    report = dict(hostBefore=before, cycles=[], requestedCycles=cycle_count, transientAtspiRetries=0)
    with tempfile.TemporaryDirectory(prefix='deskmorph-audio-restart-') as directory:
        server = PrivateAudioServer(directory)
        try:
            server.start(); server.sink('deskmorph_before', 'DeskMorph_Private_Before')
            server.pactl('set-sink-volume', 'deskmorph_before', '37%')
            stop()
            fixture = json.loads(original)
            fixture['config'].update(autoHide=False, enabled=True, showAudio=True, language='vi')
            path.write_text(json.dumps(fixture)); start({'PULSE_SERVER': server.address})
            report['appFixturePid'] = app.get_process_id()
            open_audio(); wait(lambda: value() == 37 and len(subscriptions()) == 1, 'Initial audio/subscription mismatch')
            for index in range(cycle_count):
                old = server.pulse.pid; old_sub = subscriptions()[0]
                at = time.monotonic(); server.stop_process(server.pulse)
                wait(has_error, 'Real service stop did not expose error')
                outage = round(time.monotonic() - at, 3)
                if index % 3 == 2:
                    server.stop_process(server.core); server.start()
                else: server.start_pulse()
                name = 'deskmorph_after_' + str(index)
                label = 'DeskMorph_Private_After_' + str(index)
                server.sink(name, label); server.pactl('set-sink-volume', name, str(41 + index) + '%')
                at = time.monotonic()
                wait(lambda: value() == 41 + index and not has_error(), 'Popup did not reconnect without Retry')
                wait(lambda: len(subscriptions()) == 1 and subscriptions()[0] != old_sub, 'Reconnect did not replace exactly one subscription')
                restored = round(time.monotonic() - at, 3)
                server.pactl('set-sink-volume', name, '63%')
                wait(lambda: value() == 63, 'Reconnected subscription missed volume event')
                focus_studio('DeskMorph Context Menu')
                mute = next(n for n in nodes() if n.get_role_name() == 'check box' and n.get_name() == 'Tắt tiếng')
                wait(lambda: mute.get_state_set().contains(Atspi.StateType.ENABLED), 'Mute remained disabled after reconnect')
                assert mute.get_component_iface().grab_focus()
                wait(lambda: mute.get_state_set().contains(Atspi.StateType.FOCUSED), 'Mute did not receive native focus')
                time.sleep(.2)
                assert mute.get_state_set().contains(Atspi.StateType.FOCUSED)
                native_keys(chord=[0x20])
                sinks = lambda: json.loads(server.pactl('--format=json', 'list', 'sinks'))
                wait(lambda: next(s for s in sinks() if s['name'] == name)['mute'], 'UI mute did not reach private replacement server')
                report['cycles'].append(dict(kind='core-and-pulse' if index % 3 == 2 else 'pulse-service', oldServicePid=old, newServicePid=server.pulse.pid, oldSubscriptionPid=old_sub, newSubscriptionPid=subscriptions()[0], errorAfterSeconds=outage, recoveredAfterSeconds=restored, autoRecovery=True, externalVolumeSignal=True, uiMuteTargetsPrivateSink=True, privateSinkFactory=sinks()[0]['properties']['factory.name']))
                print(json.dumps(report['cycles'][-1]), flush=True)
            native_keys(chord=[0xff1b]); wait(lambda: not subscriptions(), 'Hidden popup kept audio subscription')
            report['hiddenStopsSubscription'] = True
            open_audio(); wait(lambda: len(subscriptions()) == 1, 'Reopen failed after service restarts')
            native_keys(chord=[0xff1b]); wait(lambda: not subscriptions(), 'Second hide leaked subscription')
            report['reopenAfterRestart'] = True
        except Exception as error:
            failure = dict(report, error=repr(error))
            try:
                active = subprocess.check_output(['xprop', '-root', '_NET_ACTIVE_WINDOW'], text=True)
                failure['activeWindow'] = active.strip()
                xid = re.search(r'0x[0-9a-fA-F]+', active).group(0)
                failure['activeOwner'] = subprocess.check_output(['xprop', '-id', xid, '_NET_WM_PID', '_NET_WM_NAME'], text=True).strip()
                failure['appState'] = Path(f'/proc/{app.get_process_id()}/stat').read_text().rsplit(')', 1)[1].split()[0]
                failure['sinks'] = json.loads(server.pactl('--format=json', 'list', 'sinks'))
                failure['popupNodes'] = [(n.get_role_name(), n.get_name(), [str(s) for s in n.get_state_set().get_states()]) for n in nodes()]
                failure['subscriptions'] = subscriptions()
            except Exception as diagnostic_error:
                failure['diagnosticError'] = repr(diagnostic_error)
            (root / 'audio-service-restart-failure.json').write_text(json.dumps(failure, ensure_ascii=False, indent=2) + '\n')
            raise
        finally:
            stop(); server.stop()
            report['servicePids'] = [p.pid for p in server.processes]
            report['servicesExited'] = all(p.poll() is not None for p in server.processes)
            for file in ('core.conf', 'pulse.conf', 'core.conf.log', 'pulse.conf.log'):
                (root / ('audio-restart-' + file)).write_bytes((server.root / file).read_bytes())
            path.write_bytes(original); start()
    report.update(normalPid=app.get_process_id(), configRestored=path.read_bytes() == original, hostAfter=host(), scope='Real private PipeWire 1.6.8 / pipewire-pulse processes, hardware-free null sinks and private sockets; native X11 popup reconnect and hidden cleanup. No host service restart, headset, system suspend or session D-Bus restart coverage.')
    assert report['hostAfter'] == before and report['configRestored'] and report['servicesExited']
    (root / 'audio-service-restart-result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    return app
