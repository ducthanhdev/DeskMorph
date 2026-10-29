"""Real GIO Terminal=true launch through DeskMorph's accessible UI, lab only."""
import json
import os
from pathlib import Path
import signal
import subprocess


class TerminalProbe:
    def __init__(self, root, env):
        self.root = root
        self.env = env
        self.pid = None
        assert env['XDG_RUNTIME_DIR'] == str(root / 'runtime')
        assert not env.get('DISPLAY')
        self.marker = root / 'terminal-result.json'
        self.stop = root / 'terminal-stop'
        helper = root / 'terminal-child.py'
        helper.write_text('''import json, os, time
from pathlib import Path
root = Path(os.environ['DESKMORPH_COMPOSITOR_LAB'])
ancestors = []
pid = os.getpid()
for _ in range(8):
    proc = Path('/proc') / str(pid)
    try:
        exe = str((proc / 'exe').resolve())
        ancestors.append(dict(pid=pid, exe=exe))
        if Path(exe).name == 'cosmic-term': break
        pid = int((proc / 'stat').read_text().rsplit(')', 1)[1].split()[1])
    except OSError:
        break
    if pid <= 1: break
(root / 'terminal-result.json').write_text(json.dumps(ancestors))
deadline = time.monotonic() + 40
while not (root / 'terminal-stop').exists() and time.monotonic() < deadline:
    time.sleep(.1)
''')
        applications = Path(env['XDG_DATA_HOME']) / 'applications'
        applications.mkdir(parents=True, exist_ok=True)
        self.desktop = applications / 'deskmorph-terminal-probe.desktop'
        self.desktop.write_text(
            '[Desktop Entry]\nType=Application\nName=000 DeskMorph Terminal Probe\n'
            f'Exec=/usr/bin/python3 {helper}\nTerminal=true\n')

    def run(self, app, descendants, wait, dispatch, app_pid):
        button = wait(lambda: next((n for n in descendants(app)
            if n.get_role_name() == 'button' and n.get_name() in (
                'Mở 000 DeskMorph Terminal Probe', 'Open 000 DeskMorph Terminal Probe')), None),
            'Terminal fixture missing from real launcher catalogue')
        action = button.get_action_iface()
        assert action and action.do_action(0), 'Accessible launch action rejected'
        try:
            wait(self.marker.exists, 'Real terminal did not execute the desktop entry command')
        except AssertionError:
            trace = self.root / 'terminal-exec.trace'
            try:
                diagnostic = subprocess.run(['strace', '-f', '-e', 'trace=execve', '-s', '4096', '-o', str(trace),
                    '/usr/bin/python3', '-c', 'from gi.repository import Gio; import sys; Gio.DesktopAppInfo.new_from_filename(sys.argv[1]).launch([], None)', str(self.desktop)],
                    env=self.env, capture_output=True, text=True, timeout=5)
                print('TERMINAL_GIO_TRACE', trace.read_text(), flush=True)
                print('TERMINAL_GIO_STDERR', diagnostic.stderr, flush=True)
            except subprocess.TimeoutExpired:
                print('TERMINAL_GIO_TIMEOUT', trace.read_text(), flush=True)
            try:
                diagnostic = subprocess.run(['/usr/bin/cosmic-term', '-e', '/bin/true'],
                    env=self.env, capture_output=True, text=True, timeout=5)
                print('TERMINAL_DIRECT', diagnostic.returncode, diagnostic.stdout, diagnostic.stderr, flush=True)
            except subprocess.TimeoutExpired as error:
                print('TERMINAL_DIRECT_TIMEOUT', error.stdout, error.stderr, flush=True)
            # Preserve any surviving owned emulator for failure diagnosis.
            for proc in Path('/proc').iterdir():
                if not proc.name.isdigit(): continue
                try:
                    if (proc / 'exe').resolve().name != 'cosmic-term': continue
                    if f'DESKMORPH_COMPOSITOR_LAB={self.root}'.encode() not in (proc / 'environ').read_bytes().split(b'\0'): continue
                    print('TERMINAL_DIAGNOSTIC', (proc / 'cmdline').read_bytes().split(b'\0'), flush=True)
                    dispatch(op='target', pid=int(proc.name))
                    print('TERMINAL_WINDOWS', dispatch(op='state'), flush=True)
                except OSError: pass
            raise
        ancestors = json.loads(self.marker.read_text())
        terminal = next((a for a in ancestors if Path(a['exe']).name == 'cosmic-term'), None)
        assert terminal, ancestors
        self.pid = terminal['pid']
        assert f'DESKMORPH_COMPOSITOR_LAB={self.root}'.encode() in Path(f'/proc/{self.pid}/environ').read_bytes().split(b'\0')
        dispatch(op='target', pid=self.pid)
        windows = wait(lambda: [w for w in dispatch(op='state')['windows']
            if w['frame']['width'] > 0 and w['frame']['height'] > 0], 'Real terminal window did not map')
        assert all(w['clientType'] == 0 for w in windows), windows
        dispatch(op='target', pid=app_pid)
        self.stop.touch()
        return dict(desktopEntryTerminalTrue=True, launcherAccessibleButton=True,
            commandExecuted=True, ancestors=ancestors, terminalWindows=windows,
            emulatorVersion=subprocess.check_output(['/usr/bin/cosmic-term', '--version'], text=True).strip(),
            scope='Real COSMIC Terminal selected by system GIO; command launched from DeskMorph UI on private GNOME Wayland. No fake terminal executable.')

    def close(self):
        self.stop.touch()
        if self.pid:
            try:
                if f'DESKMORPH_COMPOSITOR_LAB={self.root}'.encode() in Path(f'/proc/{self.pid}/environ').read_bytes().split(b'\0'):
                    os.kill(self.pid, signal.SIGTERM)
            except (FileNotFoundError, ProcessLookupError):
                pass
