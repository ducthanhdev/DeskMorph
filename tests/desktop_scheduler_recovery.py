"""Opt-in integration test of missed deadlines, missing images and recovery.

By default SIGSTOP pauses only the isolated app, not the system.
DESKMORPH_REAL_SUSPEND=1 opts into system suspend and requires a human to
wake and unlock the desktop after at least 125 seconds asleep.
The caller owns library/config and GNOME wallpaper restoration.
"""
import json
import os
from pathlib import Path
import signal
import subprocess
import time
from gi.repository import Atspi


def run_scheduler_recovery(app, root, config, toggle, descendants, require_unlocked):
    pid = app.get_process_id()
    env = Path(f'/proc/{pid}/environ').read_bytes().split(b'\0')
    assert b'DESKMORPH_CONFIG_HOME=/tmp/deskmorph-desktop-test/config' in env
    images = {path: path.read_bytes() for path in (root / 'one image.png', root / 'nested/two.png')}
    assert not config()['wallpaperScheduleEnabled']

    def uris():
        return {key: subprocess.check_output(['gsettings', 'get', 'org.gnome.desktop.background', key],
                                             text=True, timeout=5).strip()
                for key in ('picture-uri', 'picture-uri-dark')}

    def wait_for(predicate, message, timeout=75):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(0.5)
        raise AssertionError(message)

    def failed():
        catalog = json.loads((Path(__file__).resolve().parents[1] / 'src/i18n/messages.json').read_text())[config()['language']]
        for node, _ in descendants(app):
            if node.get_role_name() not in ('alert', 'notification') and (node.get_attributes() or {}).get('xml-roles') != 'alert':
                continue
            children = list(descendants(node))
            labels = []
            for child, _ in children:
                labels.append(child.get_name() or '')
                try: labels.append(Atspi.Text.get_text(child, 0, -1))
                except Exception: pass
            if not any(catalog['scheduleError'] in label for label in labels): continue
            if any('No readable images in the configured wallpaper folders' in label for label in labels): return True
            # Translated ErrorText keeps the original diagnostic collapsed.
            # Expand only this scheduler alert, never unrelated library errors.
            for child, _ in children:
                if child.get_role_name() == 'button' and child.get_name() == catalog['details'] and not child.get_state_set().contains(Atspi.StateType.EXPANDED):
                    assert child.get_action_iface().do_action(0)
        return False

    real_suspend = os.environ.get('DESKMORPH_REAL_SUSPEND') == '1'
    report = {'pid': pid, 'kind': 'real-system-suspend' if real_suspend else 'owned-process-pause; not system sleep', 'passed': []}
    destination = Path('/tmp/deskmorph-desktop-test') / ('scheduler-suspend-result.json' if real_suspend else 'scheduler-recovery-result.json')
    def checkpoint():
        destination.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    watchdog = None
    stopped = False
    try:
        toggle()
        assert config()['wallpaperScheduleEnabled']
        # Establish the worker's deadline before stopping all app threads.
        time.sleep(3)
        before = uris()
        if real_suspend:
            require_unlocked()
            clocks = lambda: (time.clock_gettime(time.CLOCK_BOOTTIME), time.monotonic())
            boot_before, mono_before = clocks()
            def suspended_seconds():
                boot, mono = clocks()
                return (boot - boot_before) - (mono - mono_before)
            print('REAL_SUSPEND_REQUEST: wake after at least 125 seconds asleep, then unlock desktop', flush=True)
            subprocess.run(['systemctl', 'suspend'], check=True, timeout=30)
            wait_for(lambda: suspended_seconds() > 1, 'No kernel suspend interval detected', timeout=90)
            report['suspendedSeconds'] = round(suspended_seconds(), 3)
            checkpoint()
            assert report['suspendedSeconds'] >= 120, 'Wake was too early to miss two one-minute scheduler intervals'
            # Read-only checks may proceed while locked, but send no native
            # input until the user has explicitly unlocked the resumed session.
            def unlocked():
                value = subprocess.check_output(['gdbus', 'call', '--session', '--dest', 'org.gnome.ScreenSaver',
                    '--object-path', '/org/gnome/ScreenSaver', '--method', 'org.gnome.ScreenSaver.GetActive'], text=True, timeout=5)
                return value.strip() == '(false,)'
            print('REAL_SUSPEND_RESUMED: waiting for desktop unlock', flush=True)
            wait_for(unlocked, 'Desktop remained locked after resume', timeout=180)
        else:
            # Independent fallback guarantees CONT if the test process dies mid-pause.
            watchdog = subprocess.Popen(['/usr/bin/python3', '-c',
                                         'import os,signal,time; time.sleep(145); os.kill(int(__import__("sys").argv[1]), signal.SIGCONT)', str(pid)])
            os.kill(pid, signal.SIGSTOP)
            stopped = True
            print('Scheduler recovery: pausing isolated process for 125 seconds (not system sleep)', flush=True)
            started = time.monotonic()
            time.sleep(125)
            assert uris() == before, 'Wallpaper changed while the isolated scheduler was paused'
            os.kill(pid, signal.SIGCONT)
            stopped = False
            report['pauseSeconds'] = round(time.monotonic() - started, 2)
        wait_for(lambda: all(uris()[key] != before[key] for key in before),
                 'Missed deadline was not processed after CONT', timeout=12)
        after = uris()
        assert len(set(after.values())) == 1, 'Light/dark wallpaper values disagree'
        for _ in range(20):
            time.sleep(0.5)
            assert uris() == after, 'Scheduler issued a catch-up burst after the pause'
        report['passed'].append('one observed change after two missed intervals; stable for 10 seconds')
        checkpoint()
        print('Scheduler recovery: resume passed; deleting owned images for the next deadline', flush=True)
        for path in images:
            path.unlink()
        wait_for(failed, 'Next scheduled scan did not expose missing-image error')
        assert uris() == after, 'Failed scheduled attempt changed wallpaper settings'
        report['passed'].append('deleted library reports native error and preserves both wallpaper URIs')
        checkpoint()
        for path, data in images.items():
            path.write_bytes(data)
        print('Scheduler recovery: error confirmed; restored images, waiting for automatic recovery', flush=True)
        wait_for(lambda: all(uris()[key] != after[key] for key in after),
                 'Scheduler did not recover on the next deadline')
        wait_for(lambda: not failed(), 'Recovered schedule kept stale error', timeout=10)
        report['passed'].append('restored images recover on next scheduled tick and clear error without toggling')
        checkpoint()
        toggle()
        assert not config()['wallpaperScheduleEnabled']
        disabled = uris()
        time.sleep(3)
        assert uris() == disabled
        report['passed'].append('disable preserves wallpaper')
        report['complete'] = True
    except Exception as error:
        report['error'] = repr(error)
        checkpoint()
        raise
    finally:
        if stopped:
            os.kill(pid, signal.SIGCONT)
        if watchdog:
            watchdog.terminate()
            watchdog.wait(timeout=5)
        for path, data in images.items():
            path.write_bytes(data)
        if config()['wallpaperScheduleEnabled']:
            require_unlocked()
            toggle()
        report['imagesRestored'] = all(path.read_bytes() == data for path, data in images.items())
        report['schedulerDisabled'] = not config()['wallpaperScheduleEnabled']
        checkpoint()
    report['imagesRestored'] = all(path.read_bytes() == data for path, data in images.items())
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, ensure_ascii=False), flush=True)
