"""Opt-in Orca49 bypass command around application navigation keys.

This exercises the reader's actual Alt+Backspace command, not a product IPC
or skipped focus assertion. Only an owned, live reader with a private debug
log is accepted. The normal keyboard suite does not enable this path.
"""
import os
from pathlib import Path
import time


def navigate(native_keys, keysym):
    if os.environ.get('DESKMORPH_ORCA_NAVIGATION') != 'bypass-navigation':
        native_keys(chord=[keysym])
        return
    assert keysym in (0xff50, 0xff57, 0xff52, 0xff54)
    root = Path(os.environ['DESKMORPH_ORCA_DRIVER_ROOT']).resolve()
    assert root.parent == Path('/tmp') and root.name.startswith('deskmorph-orca-speech-')
    log = root / 'orca-debug.log'
    pid = int(os.environ['DESKMORPH_ORCA_READER_PID'])

    def owned_reader():
        env = Path(f'/proc/{pid}/environ').read_bytes().split(b'\0')
        assert f'DESKMORPH_SPEECH_LAB={root}'.encode() in env, 'Reader ownership changed'
        cmd = Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\0')
        assert b'orca' in cmd[:2] or b'/usr/bin/orca' in cmd[:2]
        assert f'DESKMORPH_ORCA_PREFS={root / "orca-prefs"}'.encode() in env

    def bypass_active():
        # Orca prints its reason while adding/removing key grabs, including
        # automatic disabling when the active script changes. Do not infer
        # current mode from a setting request or from a speech announcement.
        state = False
        for line in log.read_text(errors='replace').splitlines():
            if 'DEFAULT: Removing key grabs for' in line and ': bypass mode enabled' in line:
                state = True
            elif 'DEFAULT: Adding key grabs for' in line and ': bypass mode disabled' in line:
                state = False
        return state

    def wait_mode(expected):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            owned_reader()
            if bypass_active() == expected:
                return
            time.sleep(.05)
        raise AssertionError('Orca bypass mode did not become ' + str(expected))

    owned_reader()
    assert log.is_file()
    # GTK frame events can lag the WebKit DOM focus. A toggle applied to
    # that outgoing script is automatically undone during script activation.
    # Wait for the actual reader script, rather than repeating navigation keys.
    deadline = time.monotonic() + 10
    stable_since = None
    while time.monotonic() < deadline:
        owned_reader()
        active = next((line for line in reversed(log.read_text(errors='replace').splitlines()) if 'SCRIPT MANAGER: Active script is:' in line), '')
        ready = 'Active script is: deskmorph (module=orca.scripts.toolkits.WebKitGTK.script)' in active
        stable_since = (stable_since or time.monotonic()) if ready else None
        if stable_since is not None and time.monotonic() - stable_since >= .3:
            break
        time.sleep(.05)
    else:
        raise AssertionError('Orca did not settle on the owned WebKitGTK script')
    assert not bypass_active(), 'Reader was already in bypass mode before navigation'
    native_keys(chord=[0xffe9, 0xff08])  # Actual Orca49 Alt+Backspace toggle.
    wait_mode(True)
    try:
        native_keys(chord=[keysym])
    finally:
        owned_reader()
        if bypass_active():
            native_keys(chord=[0xffe9, 0xff08])
        wait_mode(False)
