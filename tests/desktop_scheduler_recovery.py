"""Opt-in integration test of missed deadlines, missing images and recovery.

SIGSTOP pauses only the isolated app. This is not a system suspend test.
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

    def names():
        texts = []
        for node, _ in descendants(app):
            texts.append(node.get_name() or '')
            try:
                texts.append(Atspi.Text.get_text(node, 0, -1))
            except Exception:
                pass
        return texts

    def wait_for(predicate, message, timeout=75):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(0.5)
        raise AssertionError(message)

    def failed():
        return any('No readable images in the configured wallpaper folders' in name for name in names())

    report = {'pid': pid, 'kind': 'owned-process-pause; not system sleep', 'passed': []}
    watchdog = None
    stopped = False
    try:
        toggle()
        assert config()['wallpaperScheduleEnabled']
        # Establish the worker's deadline before stopping all app threads.
        time.sleep(3)
        before = uris()
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
        print('Scheduler recovery: resume passed; deleting owned images for the next deadline', flush=True)
        for path in images:
            path.unlink()
        wait_for(failed, 'Next scheduled scan did not expose missing-image error')
        assert uris() == after, 'Failed scheduled attempt changed wallpaper settings'
        report['passed'].append('deleted library reports native error and preserves both wallpaper URIs')
        for path, data in images.items():
            path.write_bytes(data)
        print('Scheduler recovery: error confirmed; restored images, waiting for automatic recovery', flush=True)
        wait_for(lambda: all(uris()[key] != after[key] for key in after),
                 'Scheduler did not recover on the next deadline')
        wait_for(lambda: not failed(), 'Recovered schedule kept stale error', timeout=10)
        report['passed'].append('restored images recover on next scheduled tick and clear error without toggling')
        toggle()
        assert not config()['wallpaperScheduleEnabled']
        disabled = uris()
        time.sleep(3)
        assert uris() == disabled
        report['passed'].append('disable preserves wallpaper')
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
    destination = Path('/tmp/deskmorph-desktop-test/scheduler-recovery-result.json')
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, ensure_ascii=False), flush=True)
