"""Opt-in GNOME X11 fractional/mixed native allocation survey.

Tests top Dock + launcher on both monitors; no host key/mouse injection.
Retains exact feature user value, modes, refresh, primary and origins. Uses
Mutter VERIFY before TEMPORARY apply; never persistent method 2. Keep the
current evidence limits: bottom Dock and the other popups are not covered.
"""
import sys, os, json, time, copy, subprocess, tempfile, re, signal, hashlib, math
from pathlib import Path
REPO = Path(__file__).resolve().parents[1]
import gi
gi.require_version('Gdk', '3.0')
gi.require_version('Atspi', '2.0')
from gi.repository import Gio, GLib, Gdk, Atspi
import mutter_scaling_probe as m
BINARY = REPO / 'src-tauri/target/agent/debug/deskmorph'

def wait(f, msg, seconds=12):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        v = f()
        if v:
            return v
        time.sleep(0.15)
    raise AssertionError(msg)

def walk(n):
    yield n
    for i in range(n.get_child_count()):
        yield from walk(n.get_child_at_index(i))

def worker(root, monitor, position):
    result = {'passed': False, 'monitor': monitor, 'position': position, 'observations': []}
    app = None
    try:
        assert os.environ['DESKMORPH_DPI_WORKER_ROOT'] == str(root) and root.parent.name.startswith('deskmorph-dpi-native-') and (root.parent.parent == Path('/tmp'))
        d = Gdk.Display.get_default()
        mns = []
        for i in range(d.get_n_monitors()):
            n = d.get_monitor(i)
            a = n.get_workarea()
            s = n.get_scale_factor()
            mns.append({'name': n.get_model(), 'gtkScale': s, 'area': [v * s for v in (a.x, a.y, a.width, a.height)]})
        result['gdkMonitors'] = mns
        target = next((n for n in mns if n['name'] == monitor))
        s = target['gtkScale']
        ax, ay, aw, ah = target['area']
        cfg = json.loads((REPO / 'src/config/defaults.json').read_text())
        cfg.update(monitor=monitor, position=position, language='vi', autoHide=False, enabled=True, showStats=False, showShuffle=False, pinnedApps=[], reduceMotion=True, wallpaperScheduleEnabled=False)
        config = root / 'config/com.ducthanhdev.deskmorph/config.json'
        config.parent.mkdir(parents=True)
        config.write_text(json.dumps({'schemaVersion': 1, 'revision': 0, 'config': cfg, 'warning': None}))
        original = config.read_bytes()
        env = dict(os.environ, DESKMORPH_CONFIG_HOME=str(root / 'config'), DESKMORPH_DPI_NATIVE_LAB=str(root), WEBKIT_DISABLE_DMABUF_RENDERER='1')
        with (root / 'app.log').open('w') as log:
            app = subprocess.Popen([str(BINARY)], env=env, stdout=log, stderr=log)
        result['pid'] = app.pid

        def owned():
            desktop = Atspi.get_desktop(0)
            return next((desktop.get_child_at_index(i) for i in range(desktop.get_child_count()) if desktop.get_child_at_index(i).get_process_id() == app.pid), None)
        accessible = wait(owned, 'Owned accessibility app absent')
        window_ids = {}

        def raw_native(title):
            tree = subprocess.check_output(['xwininfo', '-root', '-tree'], text=True)
            for xid in re.findall('(0x[0-9a-f]+) "' + re.escape(title) + '"', tree):
                props = subprocess.check_output(['xprop', '-id', xid, '_NET_WM_PID'], text=True)
                if not re.search('= ' + str(app.pid) + '\\b', props):
                    continue
                info = subprocess.check_output(['xwininfo', '-id', xid], text=True)
                if 'Map State: IsViewable' not in info:
                    continue
                window_ids[title] = xid
                return [int(re.search(k + ':\\s+(-?\\d+)', info).group(1)) for k in ('Absolute upper-left X', 'Absolute upper-left Y', 'Width', 'Height')]

        def native(title):
            try:
                return raw_native(title)
            except subprocess.CalledProcessError:
                result['transientX11Queries'] = result.get('transientX11Queries', 0) + 1
                return None

        def stable(title):
            last = None
            count = 0

            def sample():
                nonlocal last, count
                v = native(title)
                count = count + 1 if v and v == last else 0
                last = v
                return v if count >= 3 else None
            return wait(sample, title + ' unstable')
        dock = stable('DeskMorph Taskbar')
        result['dock'] = dock
        assert dock[3] == 52 * s and abs(dock[0] + dock[2] / 2 - ax - aw / 2) <= 2, (dock, target)
        assert abs(dock[1] - (ay + 16 * s if position == 'top' else ay + ah - 68 * s)) <= 2, (dock, target)
        for label, title, size in [('Tìm ứng dụng', 'DeskMorph Context Menu', [500, 580])]:

            def source():
                f = next((n for n in walk(accessible) if n.get_role_name() == 'frame' and n.get_name() == 'DeskMorph Taskbar'), None)
                return next((n for n in walk(f) if n.get_role_name() == 'button' and n.get_name() == label), None) if f else None
            b = wait(source, 'Dock source absent ' + label)
            a = b.get_component_iface().get_extents(Atspi.CoordType.SCREEN)
            anchor = (a.x + a.width / 2) * s
            assert b.get_action_iface().do_action(0)
            popup = stable(title)
            x, y, w, h = popup
            expected = [min(size[0] * s, aw - 20 * s), min(size[1] * s, ah - 20 * s)]
            assert [w, h] == expected, (label, popup, expected)
            ex = max(ax + 10 * s, min(round(anchor) - w // 2, ax + aw - w - 10 * s))
            ey = max(ay + 10 * s, min(dock[1] + dock[3] + 14 * s if position == 'top' else dock[1] - h - 14 * s, ay + ah - h - 10 * s))
            assert ax <= x and ay <= y and (x + w <= ax + aw) and (y + h <= ay + ah), (popup, target)
            assert abs(x - ex) <= 2 and abs(y - ey) <= 2, (label, popup, ex, ey)
            result['observations'].append({'source': label, 'popup': popup, 'anchor': anchor, 'expectedOrigin': [ex, ey]})
        assert config.read_bytes() == original
        result.update(passed=True, configUnchanged=True)
    except Exception as e:
        result['error'] = repr(e)
    finally:
        if app:
            app.terminate()
            try:
                app.wait(timeout=8)
            except subprocess.TimeoutExpired:
                app.kill()
                app.wait(timeout=5)
            result['appExit'] = app.returncode
        (root / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    return result

def run():
    deadline = time.monotonic() + 240
    root = Path(tempfile.mkdtemp(prefix='deskmorph-dpi-native-'))
    out = root / 'result.json'
    display = m.proxy()
    settings = Gio.Settings.new('org.gnome.mutter')
    before = m.snapshot(display)
    original = settings.get_user_value('experimental-features')
    features = list(settings.get_strv('experimental-features'))
    report = {'passed': False, 'before': before, 'features': features, 'originalUserValue': None if original is None else original.print_(True), 'root': str(root), 'binarySha256': hashlib.sha256(BINARY.read_bytes()).hexdigest(), 'cases': [], 'restoreErrors': [], 'inputSent': False, 'featureMutationAttempted': False, 'topologyMutationAttempted': False, 'scope': 'Real GNOME X11 fractional/mixed display layouts, native allocation and AT-SPI popup activation; top Dock and launcher only on both monitors; AT-SPI activation, app shutdown dismisses; no keyboard, bottom or other popup acceptance'}
    report.update(topologyRestored=False, userValueRestored=False, capabilitiesRestored=False)
    out.write_text(json.dumps(report, indent=2))
    try:
        lock = subprocess.check_output(['gdbus', 'call', '--session', '--dest', 'org.gnome.ScreenSaver', '--object-path', '/org/gnome/ScreenSaver', '--method', 'org.gnome.ScreenSaver.GetActive'], text=True, timeout=5)
        assert 'false' in lock
        m.apply(display, before, 0)
        assert before['properties']['renderer'] == 'xrandr' and len(before['logicalMonitors']) == 2
        assert all(monitor['transform'] == 0 and len(monitor['connectors']) == 1 for monitor in before['logicalMonitors']), 'Only two unrotated, unmirrored outputs are supported'
        requested = list(dict.fromkeys(features + [m.FEATURE]))
        if requested != features:
            report['featureMutationAttempted'] = True
            assert settings.set_strv('experimental-features', requested)
            Gio.Settings.sync()
        during = wait(lambda: (lambda s: s if m.fractional_advertised(s) else None)(m.snapshot(display)), 'Fractional support absent')
        report['afterFeature'] = during
        for label, scales in [('125', [1.25, 1.25]), ('150', [1.5, 1.5]), ('mixed', [1, 1.5])]:
            desired = copy.deepcopy(before)
            desired['properties'] = during['properties']
            ordered = sorted(desired['logicalMonitors'], key=lambda x: x['x'])
            x = 0
            ui = math.ceil(max(scales)) if during['properties']['layout-mode'] == 3 else 1
            for logical, scale in zip(ordered, scales):
                logical.update(x=x, y=0, scale=scale)
                mode = next((n for n in desired['monitors'] if n['connector'] == logical['connectors'][0]))['currentModes'][0]
                x += round(mode['width'] * ui / scale)
            m.apply(display, desired, 0)
            report['topologyMutationAttempted'] = True
            m.apply(display, desired, 1)
            time.sleep(2)
            observed = m.snapshot(display)
            assert m.topology(observed) == m.topology(desired), (observed, desired)
            case = {'layout': label, 'requestedScales': scales, 'observed': observed, 'runs': []}
            report['cases'].append(case)
            for logical in ordered:
                connector = logical['connectors'][0]
                for position in ('top',):
                    assert time.monotonic() + 40 < deadline, 'Desktop trial time budget exhausted; restoring baseline'
                    folder = root / (label + '-' + connector + '-' + position)
                    folder.mkdir()
                    env = dict(os.environ, DESKMORPH_DPI_WORKER_ROOT=str(folder))
                    for key in ('GDK_SCALE', 'GDK_DPI_SCALE'):
                        env.pop(key, None)
                    with (folder / 'worker.log').open('w') as log:
                        p = subprocess.run(['/usr/bin/python3', __file__, '--worker', str(folder), connector, position], env=env, stdout=log, stderr=log, timeout=40)
                    r = json.loads((folder / 'result.json').read_text())
                    case['runs'].append(r)
                    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
                    assert p.returncode == 0 and r['passed'], r
                    print(json.dumps({'layout': label, 'monitor': connector, 'position': position, 'passed': True}), flush=True)
            neutral = copy.deepcopy(before)
            neutral['properties'] = during['properties']
            m.apply(display, neutral, 1)
        report['passed'] = True
    except Exception as e:
        report['error'] = repr(e)
    finally:
        for proc in Path('/proc').iterdir():
            if not proc.name.isdigit():
                continue
            try:
                env = (proc / 'environ').read_bytes().split(b'\x00')
                if any((v.startswith(('DESKMORPH_DPI_NATIVE_LAB=' + str(root) + '/').encode()) for v in env)):
                    os.kill(int(proc.name), signal.SIGTERM)
            except (OSError, ProcessLookupError):
                pass
        try:
            if report['featureMutationAttempted']:
                if original is None:
                    settings.reset('experimental-features')
                else:
                    assert settings.set_value('experimental-features', original)
                Gio.Settings.sync()
        except Exception as e:
            report['restoreErrors'].append('Settings: ' + repr(e))
        try:
            after = m.settled(display, before)
            if (report['featureMutationAttempted'] or report['topologyMutationAttempted']) and m.topology(after) != m.topology(before):
                m.apply(display, before, 1)
                after = m.settled(display, before)
            report.update(after=after, topologyRestored=m.topology(after) == m.topology(before), capabilitiesRestored=after['properties'] == before['properties'] and after['monitors'] == before['monitors'])
        except Exception as e:
            report['restoreErrors'].append('Display: ' + repr(e))
        try:
            report['userValueRestored'] = m.same_user_value(settings, original)
        except Exception as e:
            report['restoreErrors'].append('Settings verification: ' + repr(e))
        report['passed'] = report['passed'] and (not report['restoreErrors']) and all((report.get(k) for k in ('topologyRestored', 'userValueRestored', 'capabilitiesRestored')))
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        print(out, flush=True)
    return report
if __name__ == '__main__':
    signal.signal(signal.SIGTERM, m.interrupted)
    signal.signal(signal.SIGINT, m.interrupted)
    if len(sys.argv) > 1 and sys.argv[1] == '--worker':
        sys.exit(0 if worker(Path(sys.argv[2]), sys.argv[3], sys.argv[4])['passed'] else 1)
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true', help='Opt in to reversible host display mutations; requires an agreed idle desktop window')
    if not parser.parse_args().run:
        parser.error('--run is required; no host settings were changed')
    sys.exit(0 if run()['passed'] else 1)
