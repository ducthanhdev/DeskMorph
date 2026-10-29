"""Installed Snap runtime launched by the real UI; explicitly headless scope."""
import hashlib
import json
import os
from pathlib import Path
import shlex
import socket
import subprocess
import time
import urllib.request
import websocket
from gi.repository import GLib


class SnapProbe:
    def __init__(self, root, env):
        self.env = dict(env, DBUS_SESSION_BUS_ADDRESS='unix:path=/run/user/' + str(os.getuid()) + '/bus', XDG_RUNTIME_DIR='/run/user/' + str(os.getuid()))
        self.root = root
        self.report = None
        self.closed = False
        self.profile = '/tmp/deskmorph-snap-probe-' + root.name.removeprefix('deskmorph-wayland-lab-')
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            self.port = sock.getsockname()[1]
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        self.source = Path('/var/lib/snapd/desktop/applications/chromium_chromium.desktop')
        key = GLib.KeyFile()
        key.load_from_file(str(self.source), GLib.KeyFileFlags.KEEP_TRANSLATIONS)
        assert key.get_string('Desktop Entry', 'Exec') == '/snap/bin/chromium %U'
        assert key.get_string('Desktop Entry', 'X-SnapInstanceName') == 'chromium'
        # Override only this lab's desktop ID to keep the installed Snap entry's
        # metadata and system launcher while supplying an independent profile.
        key.set_string('Desktop Entry', 'Name', '000 DeskMorph Snap Probe')
        for name in key.get_keys('Desktop Entry')[0]:
            if name.startswith('Name['): key.remove_key('Desktop Entry', name)
        self.flag = '--user-data-dir=' + self.profile
        key.set_string('Desktop Entry', 'Exec', '/usr/bin/env DBUS_SESSION_BUS_ADDRESS=' + self.env['DBUS_SESSION_BUS_ADDRESS'] + ' XDG_RUNTIME_DIR=' + self.env['XDG_RUNTIME_DIR'] + ' /snap/bin/chromium --headless '
            + self.flag + ' --crash-dumps-dir=' + self.profile + '/crashes --no-first-run --no-default-browser-check --disable-background-networking '
            + f'--remote-debugging-address=127.0.0.1 --remote-debugging-port={self.port} about:blank %U')
        directory = Path(env['XDG_DATA_HOME']) / 'applications'
        directory.mkdir(parents=True, exist_ok=True)
        self.desktop = directory / self.source.name
        key.save_to_file(str(self.desktop))
        assert not env.get('DISPLAY') and env['XDG_RUNTIME_DIR'] == str(root / 'runtime')

    def owned_browser(self):
        found = []
        for proc in Path('/proc').iterdir():
            if not proc.name.isdigit(): continue
            try:
                args = [a for a in (proc / 'cmdline').read_bytes().split(b'\0') if a]
                # Chromium rewrites its process title into one space-separated
                # argv string on this build. Lab paths deliberately have no spaces.
                if not args: continue
                if len(args) == 1: args = [a.encode() for a in shlex.split(args[0].decode())]
                exe = args[0].decode()
                label = (proc / 'attr/current').read_text().strip()
                if self.flag.encode() not in args or not exe.startswith('/snap/chromium/') or not exe.endswith('/chrome') or not label.startswith('snap.chromium.chromium'): continue
                found.append(dict(pid=int(proc.name), executableArgv0=exe, appArmorLabel=label, argv=[a.decode() for a in args if a]))
            except OSError: pass
        return found

    def get(self, path):
        with self.opener.open(f'http://127.0.0.1:{self.port}' + path, timeout=1) as response:
            return json.load(response)

    def run(self, app, descendants, wait):
        button = wait(lambda: next((n for n in descendants(app)
            if n.get_role_name() == 'button' and n.get_name() in (
                'Mở 000 DeskMorph Snap Probe', 'Open 000 DeskMorph Snap Probe')), None),
            'Installed Snap desktop override missing from launcher')
        assert button.get_action_iface().do_action(0)
        browser = wait(self.owned_browser, 'Installed Chromium Snap did not start with the isolated profile')
        def version():
            try: return self.get('/json/version')
            except (OSError, ValueError): return None
        info = wait(version, 'Snap CDP endpoint not available')
        assert 'Chrome/156.' in info['Browser'], info
        targets = self.get('/json/list')
        target = next(t for t in targets if t['type'] == 'page')
        # No origin override and no authentication change: local CDP is scoped
        # to this unique, empty, headless profile and ephemeral loopback port.
        ws = websocket.create_connection(target['webSocketDebuggerUrl'], timeout=3, suppress_origin=True,
            http_proxy_host=None)
        try:
            expression = 'document.title="DeskMorph Snap Runtime Probe"; document.body.textContent="deskmorph-snap-ok"; document.body.textContent'
            ws.send(json.dumps(dict(id=1, method='Runtime.evaluate', params=dict(expression=expression, returnByValue=True))))
            while True:
                reply = json.loads(ws.recv())
                if reply.get('id') == 1: break
            assert reply['result']['result']['value'] == 'deskmorph-snap-ok', reply
        finally: ws.close()
        self.report = dict(headless=True, snapUsesHostUserBusForCgroup=True, desktopId=self.source.name, launcherAccessibleButton=True,
            installedEntrySha256=hashlib.sha256(self.source.read_bytes()).hexdigest(),
            labEntrySha256=hashlib.sha256(self.desktop.read_bytes()).hexdigest(),
            ownedBrowser=[p for p in browser if not any(a.startswith('--type=') for a in p['argv'])], browserVersion=info['Browser'], renderedDocumentVerified=True,
            scope='Actual installed Chromium Snap via /snap/bin/chromium and DeskMorph UI/GIO. Lab desktop override supplies unique temporary profile and headless flags. Does not certify a visible Snap window, unmodified desktop-entry launch, or Flatpak runtime.')
        return self.report

    def close(self):
        if self.closed: return
        # AppArmor can reject host signals to a confined Snap. Close only the
        # unique browser through its own CDP endpoint after checking ownership.
        if self.owned_browser():
            info = self.get('/json/version')
            ws = websocket.create_connection(info['webSocketDebuggerUrl'], timeout=3,
                suppress_origin=True, http_proxy_host=None)
            try:
                ws.send(json.dumps(dict(id=99, method='Browser.close')))
                reply = json.loads(ws.recv())
                assert reply.get('id') == 99 and 'result' in reply, reply
            finally: ws.close()
        deadline = time.monotonic() + 5
        while self.owned_browser() and time.monotonic() < deadline: time.sleep(.1)
        assert not self.owned_browser(), 'Owned Snap browser did not exit'
        # Crashpad helpers can outlive Browser.close. Only signal helpers with
        # this exact lab marker from a shell bearing the same Snap confinement.
        helpers = []
        marker = f'DESKMORPH_COMPOSITOR_LAB={self.root}'.encode()
        for proc in Path('/proc').iterdir():
            if not proc.name.isdigit(): continue
            try:
                if marker not in (proc / 'environ').read_bytes().split(b'\0'): continue
                argv0 = (proc / 'cmdline').read_bytes().split(b'\0')[0]
                if argv0.startswith(b'/snap/chromium/') and argv0.endswith(b'/chrome_crashpad_handler'):
                    helpers.append(int(proc.name))
            except OSError: pass
        if helpers:
            subprocess.run(['snap', 'run', '--shell', 'chromium', '-c',
                'kill -TERM ' + ' '.join(map(str, helpers))], env=self.env,
                capture_output=True, text=True, timeout=15, check=True)
        # /tmp is private inside this Snap; remove only this exact random profile.
        assert self.profile.startswith('/tmp/deskmorph-snap-probe-') and '/' not in self.profile[5:]
        subprocess.run(['snap', 'run', '--shell', 'chromium', '-c',
            'rm -rf -- ' + shlex.quote(self.profile) + ' && test ! -e ' + shlex.quote(self.profile)], env=self.env,
            capture_output=True, text=True, timeout=15, check=True)
        if self.report is not None:
            self.report['browserClosedThroughCdp'] = True
            self.report['temporaryProfileRemoved'] = True
            self.report['ownedCrashpadPidsClosed'] = helpers
        self.closed = True
