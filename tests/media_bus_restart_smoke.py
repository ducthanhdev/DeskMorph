"""Restart a private session bus while the real native media popup stays open."""
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time
from gi.repository import Atspi, Gio, GLib
from dock_layout_smoke import descendants


def run(app, config_home, focus_studio, native_keys, start_app, set_app):
    path = Path(config_home) / 'com.ducthanhdev.deskmorph/config.json'
    original = path.read_bytes(); reports = []; processes = []
    app_pid = app.get_process_id()
    root = Path('/tmp/deskmorph-desktop-test')
    (root / 'media-bus-restart-original.json').write_bytes(original)
    host = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    host_id = host.call_sync('org.freedesktop.DBus', '/org/freedesktop/DBus', 'org.freedesktop.DBus', 'GetId', None, None, Gio.DBusCallFlags.NONE, 3000, None).unpack()[0]
    a11y = host.call_sync('org.a11y.Bus', '/org/a11y/bus', 'org.a11y.Bus', 'GetAddress', None, None, Gio.DBusCallFlags.NONE, 3000, None).unpack()[0]
    def wait(predicate, message):
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            result = predicate()
            if result: return result
            time.sleep(.1)
        raise AssertionError(message)
    def stop_app():
        pid = app_pid; proc = Path(f'/proc/{pid}')
        if not proc.exists(): return
        if (proc / 'stat').read_text().rsplit(')', 1)[1].split()[0] == 'Z': return
        assert f'DESKMORPH_CONFIG_HOME={config_home}'.encode() in (proc / 'environ').read_bytes().split(b'\0')
        os.kill(pid, signal.SIGTERM)
        deadline = time.monotonic() + 7
        while (proc / 'stat').exists():
            try:
                if (proc / 'stat').read_text().rsplit(')', 1)[1].split()[0] == 'Z': break
            except FileNotFoundError: break
            assert time.monotonic() < deadline
            time.sleep(.1)
    def start_app_with(overrides=None):
        nonlocal app, app_pid
        app = start_app(env_overrides=overrides); set_app(app); app_pid = app.get_process_id()
    def frame(title):
        return next((n for n in descendants(app) if n.get_role_name() == 'frame' and n.get_name() == title), None)
    def nodes():
        popup = frame('DeskMorph Context Menu')
        return list(descendants(popup)) if popup else []
    def button(label): return next((n for n in nodes() if n.get_role_name() == 'button' and n.get_name() == label), None)
    def has_text(value):
        for node in nodes():
            text = node.get_text_iface()
            if text and value in Atspi.Text.get_text(text, 0, -1): return True
        return False
    def stop(process):
        if process.poll() is None:
            process.terminate()
            try: process.wait(timeout=5)
            except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=5)
    report = dict(hostBusId=host_id)
    with tempfile.TemporaryDirectory(prefix='deskmorph-media-bus-') as directory:
        lab = Path(directory); address = 'unix:path=' + str(lab / 'session.sock')
        config = lab / 'bus.conf'
        config.write_text('<busconfig><type>session</type><listen>' + address + '</listen><auth>EXTERNAL</auth><policy context="default"><allow user="*"/><allow own="*"/><allow send_destination="*"/><allow receive_sender="*"/></policy></busconfig>')
        env = dict(os.environ, DBUS_SESSION_BUS_ADDRESS=address, DESKMORPH_MEDIA_BUS_LAB=str(lab))
        def daemon():
            with (root / 'media-bus-daemon.log').open('a') as log:
                process = subprocess.Popen(['dbus-daemon', '--nofork', '--config-file=' + str(config)], env=env, stdout=log, stderr=log)
            processes.append(process)
            wait(lambda: (lab / 'session.sock').exists() and process.poll() is None, 'Private bus socket unavailable')
            return process
        def player(index):
            log = root / f'media-restart-{os.getpid()}-{index}.jsonl'
            name = f'org.mpris.MediaPlayer2.deskmorph_test_restart_{os.getpid()}'
            with (root / 'media-bus-player.log').open('a') as output:
                process = subprocess.Popen(['/usr/bin/python3', str(Path(__file__).with_name('mpris_fixture.py')), '--name', name, '--identity', 'DeskMorph_Restart_' + str(index), '--log', str(log)], env=env, stdin=subprocess.PIPE, stdout=output, stderr=output, text=True)
            processes.append(process)
            wait(lambda: Path(str(log) + '.ready').exists() and process.poll() is None, 'Player fixture unavailable')
            return process, log
        def media_rules():
            connection = Gio.DBusConnection.new_for_address_sync(address, Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION, None, None)
            try:
                values = connection.call_sync('org.freedesktop.DBus', '/org/freedesktop/DBus', 'org.freedesktop.DBus.Debug.Stats', 'GetAllMatchRules', None, None, Gio.DBusCallFlags.NONE, 3000, None).unpack()[0]
                return [rule for rules in values.values() for rule in rules if 'path=\"/org/mpris/MediaPlayer2\"' in rule or "path='/org/mpris/MediaPlayer2'" in rule]
            finally: connection.close_sync(None)
        def calls(log): return [json.loads(line)['method'] for line in log.read_text().splitlines()] if log.exists() else []
        bus = None; current = None
        try:
            bus = daemon(); current, log = player(0)
            stop_app()
            fixture = json.loads(original); fixture['config'].update(autoHide=False, enabled=True, showAudio=True, language='vi')
            path.write_text(json.dumps(fixture))
            start_app_with(dict(DBUS_SESSION_BUS_ADDRESS=address, AT_SPI_BUS_ADDRESS=a11y, DESKMORPH_MEDIA_BUS_LAB=str(lab)))
            report['appFixturePid'] = app.get_process_id()
            focus_studio('DeskMorph Taskbar')
            source = next(n for n in descendants(frame('DeskMorph Taskbar')) if n.get_role_name() == 'button' and n.get_name() == 'Âm thanh')
            assert source.get_component_iface().grab_focus(); time.sleep(.3); native_keys(chord=[0xff0d])
            wait(lambda: has_text('DeskMorph_Restart_0 Track'), 'Private player did not reach native popup')
            wait(lambda: len(media_rules()) == 1, 'Expected one visible MPRIS metadata subscription')
            for index in (1, 2):
                old_bus = bus.pid; lost_at = time.monotonic(); stop(bus); stop(current)
                wait(lambda: any((n.get_attributes() or {}).get('xml-roles') == 'alert' or n.get_role_name() in ('notification', 'alert') for n in nodes()), 'Session bus loss did not expose media error')
                # Keep the socket unavailable across more than one retry. A
                # quick daemon replacement alone misses the failed-connect path.
                wait(lambda: time.monotonic() - lost_at >= 4.5, 'Outage interval did not elapse')
                at = time.monotonic(); bus = daemon(); current, log = player(index)
                wait(lambda: has_text(f'DeskMorph_Restart_{index} Track'), 'Media subscription did not reconnect to restarted bus')
                elapsed = round(time.monotonic() - at, 3)
                wait(lambda: len(media_rules()) == 1, 'Reconnected bus has duplicate/missing metadata subscription')
                pause = wait(lambda: button('Tạm dừng'), 'Reconnected player controls missing')
                assert pause.get_component_iface().grab_focus(); time.sleep(.2); native_keys(chord=[0xff0d])
                wait(lambda: 'Pause' in calls(log) and button('Phát'), 'Pause did not reach replacement fixture')
                current.stdin.write(json.dumps({'title': 'Restart_Signal_' + str(index)}) + '\n'); current.stdin.flush()
                wait(lambda: has_text('Restart_Signal_' + str(index)), 'New bus signal subscription missed metadata')
                reports.append(dict(oldBusPid=old_bus, newBusPid=bus.pid, replacementPlayerPid=current.pid, outageSeconds=round(at - lost_at, 3), recoverySeconds=elapsed, automaticRecovery=True, pauseTargetsReplacement=True, metadataSignalAfterReconnect=True))
                print(json.dumps(reports[-1]), flush=True)
            native_keys(chord=[0xff1b]); wait(lambda: frame('DeskMorph Context Menu') is None, 'Escape did not hide popup')
            wait(lambda: not media_rules(), 'Hidden popup retained MPRIS metadata match rule')
            report['escapeAfterRestart'] = True
            report['oneMetadataSubscriptionAndHiddenCleanup'] = True
        except Exception as error:
            diagnostic = dict(report, cycles=reports, error=repr(error))
            try:
                diagnostic['metadataRules'] = media_rules()
                diagnostic['popupNodes'] = [(n.get_role_name(), n.get_name()) for n in nodes()]
            except Exception as diagnostic_error:
                diagnostic['diagnosticError'] = repr(diagnostic_error)
            (root / 'media-bus-restart-failure.json').write_text(json.dumps(diagnostic, ensure_ascii=False, indent=2) + '\n')
            raise
        finally:
            stop_app()
            for process in reversed(processes): stop(process)
            path.write_bytes(original); start_app_with()
    report.update(cycles=reports, ownedPids=[p.pid for p in processes], ownedProcessesExited=all(p.poll() is not None for p in processes), normalPid=app.get_process_id(), configRestored=path.read_bytes() == original, hostBusIdAfter=host.call_sync('org.freedesktop.DBus', '/org/freedesktop/DBus', 'org.freedesktop.DBus', 'GetId', None, None, Gio.DBusCallFlags.NONE, 3000, None).unpack()[0], scope='Native X11 media popup with private restartable session dbus-daemon and owned MPRIS fixtures; host AT-SPI address explicitly preserved. No host bus restart or real media commands.')
    assert report['hostBusId'] == report['hostBusIdAfter'] and report['ownedProcessesExited'] and report['configRestored']
    (root / 'media-bus-restart-result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    return app
