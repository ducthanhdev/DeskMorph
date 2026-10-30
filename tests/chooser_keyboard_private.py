"""Import chooser keyboard route on the runner's owned GNOME/Xvfb only."""
import json
import os
import subprocess
import time
import re
import traceback
from pathlib import Path
from gi.repository import Atspi
from dock_layout_smoke import descendants
from private_keyboard import PrivateKeyboard


def audit(*, app, root, language, pid, **_):
    root = Path(root)
    keyboard = PrivateKeyboard(root)
    binary = Path(__file__).resolve().parents[1] / 'src-tauri/target/agent/debug/deskmorph'
    config = root / 'config/com.ducthanhdev.deskmorph/config.json'
    original = config.read_bytes()
    folder = root / 'chooser-fixture'
    folder.mkdir(exist_ok=True)
    fixture = folder / 'import.json'
    imported = dict(json.loads(original)['config'], iconSpacing=13)
    fixture.write_text(json.dumps(dict(schemaVersion=1, config=imported)))
    routes = []
    assert os.environ['GSETTINGS_BACKEND'] == 'keyfile'
    assert Path(os.environ['XDG_CONFIG_HOME']).resolve().is_relative_to(root.resolve())

    def wait(predicate, message):
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            value = predicate()
            if value:
                return value
            time.sleep(.1)
        raise AssertionError(message)

    def nodes():
        return list(descendants(app))

    def find(name, role='button'):
        return next((n for n in nodes() if n.get_name() == name and n.get_role_name() == role), None)

    def native(title):
        tree = subprocess.check_output(['xwininfo', '-root', '-tree'], text=True, timeout=5)
        for xid in re.findall(r'(0x[0-9a-f]+) "' + re.escape(title) + '"', tree):
            props = subprocess.check_output(['xprop', '-id', xid, '_NET_WM_PID'], text=True, timeout=5)
            info = subprocess.check_output(['xwininfo', '-id', xid], text=True, timeout=5)
            if re.search(r'= ' + str(pid) + r'\b', props) and 'Map State: IsViewable' in info:
                return xid

    def activate(title):
        xid = wait(lambda: native(title), 'Missing owned window: ' + title)
        keyboard.activate(xid, pid)

    def keys(*chord):
        keyboard.keys(keyboard.active(), pid, list(chord))
        time.sleep(.1)

    def focused(node):
        return node.get_state_set().contains(Atspi.StateType.FOCUSED)

    def seed(name):
        node = wait(lambda: find(name), 'Missing Studio control: ' + name)
        assert node.get_component_iface().grab_focus()
        wait(lambda: focused(node), 'Missing seeded focus: ' + name)

    def chooser():
        return find('Select File', 'file chooser')

    labels = dict(system='Hệ thống', trigger='Nhập cấu hình', review='Xem thay đổi trước khi nhập', cancel='Hủy') if language == 'vi' else dict(system='System', trigger='Import configuration', review='Review changes before importing', cancel='Cancel')
    try:
        activate('DeskMorph Context Menu'); keys(0xff1b)
        subprocess.run([str(binary)], env=dict(os.environ, DESKMORPH_CONFIG_HOME=str(root / 'config')), check=True, timeout=8)
        activate('DeskMorph Studio')
        seed(labels['system']); keys(0xff0d)
        for cancel in (True, False):
            seed(labels['trigger']); keys(0xff0d)
            wait(chooser, 'Enter did not open chooser'); activate('Select File')
            if cancel:
                keys(0xff1b)
                wait(lambda: focused(find(labels['trigger'])), 'Chooser Escape lost trigger focus')
                assert config.read_bytes() == original
                continue
            # Fixture setup uses the private GTK cwd preference; no
            # programmatic focus or selection is used inside the chooser.
            def selected(name):
                return any(n.get_name() == name and n.get_state_set().contains(Atspi.StateType.SELECTED) for n in descendants(chooser()))
            wait(lambda: any(n.get_name() == fixture.name for n in descendants(chooser())), 'Private GTK initial fixture folder not shown')
            table = find('Files', 'table')
            for _ in range(32):
                if focused(table):
                    break
                keys(0xff09)
            else:
                raise AssertionError('File table not reachable with Tab')
            keys(0xff50)
            wait(lambda: selected(fixture.name), 'Home did not select fixture')
            for _ in range(32):
                keys(0xff09)
                current = next((n for n in descendants(chooser()) if focused(n)), None)
                assert current is not None, 'Chooser Tab lost accessible focus'
                routes.append(dict(key='Tab', role=current.get_role_name(), name=current.get_name()))
                if current.get_role_name() == 'button' and current.get_name() == 'Open':
                    break
            else:
                raise AssertionError('Open not reachable by Tab: ' + repr(routes))
            # Reverse and forward must return to the same Open control.
            open_button = current
            keys(0xffe1, 0xff09)
            assert not focused(open_button), 'Reverse Tab stuck at Open'
            keys(0xff09)
            wait(lambda: focused(open_button), 'Forward Tab did not return to Open')
            keys(0xff0d)
            wait(lambda: any(n.get_name() == labels['review'] and focused(n) for n in nodes()), 'Open Enter did not focus import review')
            assert config.read_bytes() == original, 'Opening review mutated config'
            keys(0xff09); keys(0xff09)
            wait(lambda: focused(find(labels['cancel'])), 'Review Tab did not reach Cancel')
            keys(0xff0d)
            wait(lambda: focused(find(labels['trigger'])), 'Review Cancel lost trigger focus')
            assert config.read_bytes() == original
        return dict(passed=True, language=language, chooserEscapeReturnsTrigger=True,
                    privateInitialFolder=True, homeSelectsFile=True, tabRoute=routes, reverseForwardOpen=True,
                    enterOpensReview=True, reviewCancelReturnsTrigger=True,
                    configUnchanged=True, scope='AT-SPI seeds Studio controls only; chooser initial fixture folder then Tab/Home/ShiftTab/Open Enter and review Tab/Cancel use owned private XTest')
    except Exception as error:
        from gi.repository import Gdk
        window = Gdk.get_default_root_window()
        image = Gdk.pixbuf_get_from_window(window, 0, 0, window.get_width(), window.get_height())
        image.savev(str(root / 'chooser-failure.png'), 'png', [], [])
        (root / 'chooser-driver-failure.json').write_text(json.dumps(dict(passed=False, error=repr(error), traceback=traceback.format_exc(), routes=routes, nodes=[dict(role=n.get_role_name(), name=n.get_name(), focused=focused(n), text=Atspi.Text.get_text(n, 0, -1) if n.get_text_iface() else '') for n in nodes()]), ensure_ascii=False, indent=2) + '\n')
        raise
    finally:
        fixture.unlink(missing_ok=True)
        folder.rmdir()
