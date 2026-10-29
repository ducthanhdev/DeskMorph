"""Matched before/after process measurements; isolated profile, owned fixtures only."""
from collections import Counter
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import time
from gi.repository import Atspi
from dock_layout_smoke import descendants
from performance_measure import measure, exec_counts


def run(app, config_home, click, focus_studio, native_keys, test_app, start_app, set_app,
        close_studio, reopen_studio, require_unlocked, assert_pointer_owned):
    root = Path('/tmp/deskmorph-desktop-test')
    output = root / ('performance-matrix-' + str(time.time_ns()))
    output.mkdir()
    config_path = Path(config_home) / 'com.ducthanhdev.deskmorph/config.json'
    original = config_path.read_bytes()
    resume = os.environ.get('DESKMORPH_PERFORMANCE_RESUME')
    if resume:
        previous = Path(resume)
        reports_before = json.loads((previous / 'results.json').read_text())
        saved = previous / 'original-config.json'
        if saved.exists():
            original = saved.read_bytes()
    else:
        reports_before = []
    (output / 'original-config.json').write_bytes(original)
    project = Path(__file__).resolve().parents[1]
    binaries = {
        'before-debug': Path('/tmp/deskmorph-performance-binaries/before-debug/deskmorph'),
        'before-release': Path('/tmp/deskmorph-performance-binaries/before-release/deskmorph'),
        'after-debug': project / 'src-tauri/target/agent/debug/deskmorph',
        'after-release': project / 'src-tauri/target/agent/release/deskmorph',
    }
    assert all(binary.is_file() for binary in binaries.values())
    reports, pids = [], []
    tracer = None
    fixture = None
    config = lambda: json.loads(config_path.read_text())['config']

    def wait(predicate, message, seconds=12):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            value = predicate()
            if value:
                return value
            time.sleep(.1)
        raise AssertionError(message)

    def stopped(pid):
        try:
            return Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[0] == 'Z'
        except FileNotFoundError:
            return True

    def stop():
        nonlocal tracer
        pid = test_app().get_process_id()
        assert pid == app.get_process_id()
        assert f'DESKMORPH_CONFIG_HOME={config_home}'.encode() in Path(f'/proc/{pid}/environ').read_bytes().split(b'\0')
        os.kill(pid, signal.SIGTERM)
        wait(lambda: stopped(pid), 'Owned app did not exit')
        if tracer is not None:
            tracer.wait(timeout=7)
            tracer = None
        try:
            os.waitpid(pid, os.WNOHANG)
        except ChildProcessError:
            pass

    def stop_tracer():
        nonlocal tracer
        if tracer is None:
            return
        # The process group was created by this harness; terminate tracees too.
        if tracer.poll() is None:
            os.killpg(tracer.pid, signal.SIGTERM)
            try:
                tracer.wait(timeout=7)
            except subprocess.TimeoutExpired:
                os.killpg(tracer.pid, signal.SIGKILL)
                tracer.wait(timeout=5)
        tracer = None

    def start(label, trace_path=None):
        nonlocal app, tracer
        require_unlocked()
        begin = time.monotonic()
        if trace_path is None:
            app = start_app(binary_override=binaries[label])
        else:
            env = dict(os.environ, DESKMORPH_CONFIG_HOME=config_home, XDG_DATA_HOME=str(root / 'data'),
                       XDG_CACHE_HOME=str(root / 'cache'), WEBKIT_DISABLE_DMABUF_RENDERER='1', DESKMORPH_TRACE_COMMANDS='1')
            with (output / 'runtime.log').open('a') as log:
                tracer = subprocess.Popen(['strace', '-f', '-qq', '-ttt', '-e', 'trace=execve', '-o', str(trace_path), str(binaries[label])], env=env, stdout=log, stderr=log, start_new_session=True)
            def candidate():
                assert tracer.poll() is None, 'Tracer exited during startup'
                try:
                    value = test_app()
                    pid = value.get_process_id()
                    parent = int(Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[1])
                    assert parent == tracer.pid, 'Traced candidate is not the owned tracer child'
                    return value if any(n.get_role_name() == 'button' for n in descendants(value)) else None
                except RuntimeError:
                    return None
            app = wait(candidate, 'Traced app did not expose buttons')
        startup = time.monotonic() - begin
        set_app(app)
        pid = app.get_process_id()
        pids.append(pid)
        assert Path(f'/proc/{pid}/exe').resolve() == binaries[label].resolve()
        return startup

    def find(name, role=None):
        return next((n for n in descendants(app) if n.get_name() == name and (role is None or n.get_role_name() == role)), None)

    def move(target):
        require_unlocked()
        rect = target.get_component_iface().get_extents(Atspi.CoordType.SCREEN)
        x11 = ctypes.CDLL('libX11.so.6'); xtst = ctypes.CDLL('libXtst.so.6')
        x11.XOpenDisplay.restype = ctypes.c_void_p
        x11.XSync.argtypes = [ctypes.c_void_p, ctypes.c_int]
        x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
        xtst.XTestFakeMotionEvent.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_ulong]
        display = x11.XOpenDisplay(None); assert display
        try:
            assert xtst.XTestFakeMotionEvent(display, -1, rect.x + rect.width // 2, rect.y + rect.height // 2, 0)
            x11.XSync(display, 0); assert_pointer_owned()
        finally:
            x11.XCloseDisplay(display)

    def clients():
        return re.findall(r'0x[0-9a-fA-F]+', subprocess.check_output(['xprop', '-root', '_NET_CLIENT_LIST'], text=True))

    def mapped(title):
        for identifier in clients():
            properties = subprocess.check_output(['xprop', '-id', identifier, '_NET_WM_PID', '_NET_WM_NAME'], text=True)
            if re.search(r'_NET_WM_PID.*= ' + str(app.get_process_id()) + r'\b', properties) and f'"{title}"' in properties:
                return 'Map State: IsViewable' in subprocess.check_output(['xwininfo', '-id', identifier], text=True)
        return False

    def prepare(phase):
        focus_studio()
        move(find('DeskMorph', 'heading'))
        if phase == 'dock':
            close_studio()
        elif phase == 'autohidden':
            close_studio()
            wait(lambda: find('DeskMorph Taskbar', 'frame').get_component_iface().get_extents(Atspi.CoordType.SCREEN).height <= 4, 'Dock did not auto-hide', seconds=15)
        elif phase == 'system':
            click('Ứng dụng')  # Preview unmounted; isolate Dock+popup consumers.
            click('Tiện ích hệ thống', 'button')
            focus_studio('DeskMorph Context Menu')
            move(find('Tiện ích hệ thống', 'heading') or find('DeskMorph Context Menu', 'frame'))
        time.sleep(3)

    def validate(phase):
        require_unlocked()
        assert test_app().get_process_id() == app.get_process_id()
        if phase in ('dock', 'autohidden'):
            assert not mapped('DeskMorph Studio'), 'Studio remained visible in hidden phase'
        if phase == 'autohidden':
            assert find('DeskMorph Taskbar', 'frame').get_component_iface().get_extents(Atspi.CoordType.SCREEN).height <= 4, 'Pointer interference revealed hidden Dock'
        elif phase == 'system':
            assert mapped('DeskMorph Context Menu'), 'Measured system popup closed'
        if phase in ('studio', 'many'):
            assert mapped('DeskMorph Studio'), 'Measured Studio was hidden'

    baseline = dict(json.loads(original)['config'], language='vi', enabled=True, autoHide=False, position='bottom',
                    showApps=True, showStats=True, showAudio=True, showClock=True, clockSeconds=True,
                    showSystem=True, showBattery=False, showNetwork=False, keepDockOnClose=True, wallpaperScheduleEnabled=False,
                    reduceMotion=False, magnification=True)
    # Measure two untraced matched runs, then separate trace; never use traced CPU for budgets.
    jobs = [(label, 'studio', traced, repeat) for repeat in range(2) for label in binaries for traced in [False]]
    jobs += [(label, 'studio', True, 0) for label in binaries]
    jobs += [(label, phase, traced, 0) for phase in ('dock', 'autohidden', 'system', 'many')
             for label in ('after-debug', 'after-release') for traced in (False, True)]
    try:
        stop()
        for index, (label, phase, traced, repeat) in enumerate(jobs):
            prior = next((r for r in reports_before if (r['label'], r['phase'], r['traced'], r['repeat']) == (label, phase, traced, repeat)), None)
            if prior:
                assert prior['binarySha256'] == hashlib.sha256(binaries[label].read_bytes()).hexdigest()
                reports.append(prior)
                continue
            document = json.loads(original)
            document['config'] = dict(baseline, autoHide=phase == 'autohidden')
            config_path.write_text(json.dumps(document))
            if phase == 'many' and fixture is None:
                script = output / 'windows.py'
                script.write_text('''import gi
gi.require_version('Gtk','3.0')
from gi.repository import Gtk
windows=[]
for i in range(12):
 w=Gtk.Window(title='DeskMorph Performance Fixture '+str(i))
 w.set_wmclass('deskmorph-performance','DeskMorphPerformance')
 w.set_default_size(160,90);w.set_focus_on_map(False)
 w.add(Gtk.Label(label='Owned performance fixture'));w.show_all();windows.append(w)
print('ready',flush=True)
Gtk.main()
''')
                fixture = subprocess.Popen(['/usr/bin/python3', str(script)], stdout=subprocess.PIPE, text=True,
                                           env=dict(os.environ, DESKMORPH_CONFIG_HOME=config_home))
                import select
                assert select.select([fixture.stdout], [], [], 10)[0], 'Window fixture did not start'
                assert fixture.stdout.readline().strip() == 'ready'
            trace_path = output / f'execve-{index}.log' if traced else None
            startup = start(label, trace_path)
            prepare(phase)
            count_before = len(clients())
            result = measure(app.get_process_id(), validate=lambda: validate(phase))
            count_after = len(clients())
            assert count_before == count_after, 'Managed window count changed during measurement'
            result.update(label=label, phase=phase, traced=traced, repeat=repeat, pid=app.get_process_id(),
                          startupToAccessibleButtonsSeconds=round(startup, 3), managedClients=count_before,
                          binarySha256=hashlib.sha256(binaries[label].read_bytes()).hexdigest(), config=config())
            if traced:
                begin, end = result['samples'][0]['wall'], result['samples'][-1]['wall']
                result.update(exec_counts(trace_path.read_text().splitlines(), begin, end))
                events = []
                for line in (output / 'runtime.log').read_text().splitlines():
                    if line.startswith('deskmorph_command '):
                        event = json.loads(line.removeprefix('deskmorph_command '))
                        if event['pid'] == app.get_process_id() and begin * 1000 <= event['atUnixMs'] <= end * 1000:
                            events.append(event)
                result['debugCommandStarts'] = dict(Counter(event['command'] for event in events if event['phase'] == 'start'))
            reports.append(result)
            (output / 'results.json').write_text(json.dumps(reports, indent=2))
            print(json.dumps({key: value for key, value in result.items() if key not in ('samples', 'config')}), flush=True)
            stop()
        assert fixture is not None
    finally:
        try:
            try:
                current = test_app()
            except RuntimeError:
                current = None
            if current:
                stop()
        finally:
            try:
                stop_tracer()
                if fixture is not None:
                    fixture.terminate(); fixture.wait(timeout=7)
            finally:
                config_path.write_bytes(original)
                app = start_app()
                set_app(app)
    report = dict(runs=reports, fixturePids=pids, fixtureWindowPid=fixture.pid if fixture else None,
                  normalPid=app.get_process_id(), configRestored=config_path.read_bytes() == original,
                  allTestPidsExited=all(stopped(pid) for pid in pids), output=str(output))
    (root / 'performance-matrix-result.json').write_text(json.dumps(report, indent=2))
    print(json.dumps({key: value for key, value in report.items() if key != 'runs'}), flush=True)
    return app
