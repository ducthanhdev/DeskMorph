// Lab only: refuses to start in a normal session. Never installed on the host.
import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import St from 'gi://St';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

const xml = `<node><interface name="org.deskmorph.Lab">
<method name="Dispatch"><arg type="s" direction="in"/><arg type="s" direction="in"/><arg type="s" direction="out"/></method>
</interface></node>`;

export default class Prototype extends Extension {
    enable() {
        const root = GLib.getenv('DESKMORPH_COMPOSITOR_LAB');
        this._token = GLib.getenv('DESKMORPH_PROTOTYPE_TOKEN');
        if (!root?.startsWith('/tmp/deskmorph-wayland-lab-') || !this._token ||
            GLib.getenv('XDG_RUNTIME_DIR') !== `${root}/runtime`)
            throw new Error('DeskMorph prototype requires an isolated lab');
        this._hidden = false;
        this._edge = 'bottom';
        this._dock = new St.Widget({name: 'deskmorph-lab-dock', reactive: true,
            style: 'background-color: #172235; border: 2px solid #77bfff;'});
        Main.layoutManager.addChrome(this._dock, {affectsStruts: false, trackFullscreen: true});
        this._pointer = Clutter.get_default_backend().get_default_seat().create_virtual_device(Clutter.InputDeviceType.POINTER_DEVICE);
        this._place();
        this._timer = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 100, () => {
            const [, y] = global.get_pointer();
            const monitor = Main.layoutManager.primaryMonitor;
            const inside = this._edge === 'bottom' ? y >= monitor.y + monitor.height - 54 : y < monitor.y + 54;
            if (this._hidden === inside) { this._hidden = !inside; this._place(); }
            return GLib.SOURCE_CONTINUE;
        });
        this._export = Gio.DBusExportedObject.wrapJSObject(xml, this);
        this._export.export(Gio.DBus.session, '/org/deskmorph/Lab');
    }

    _place() {
        const m = Main.layoutManager.primaryMonitor;
        const height = this._hidden ? 4 : 54;
        this._dock.set_size(500, height);
        this._dock.set_position(m.x + Math.round((m.width - 500) / 2), this._edge === 'bottom' ? m.y + m.height - height : m.y);
    }

    _windows() {
        return global.get_window_actors().map(a => a.meta_window)
            .filter(w => w.get_gtk_application_id()?.startsWith('org.deskmorph.LabFixture'));
    }

    Dispatch(token, payload) {
        if (token !== this._token) throw new Error('Invalid lab token');
        const command = JSON.parse(payload);
        if (command.op === 'edge') {
            if (!['top', 'bottom'].includes(command.edge)) throw new Error('Invalid edge');
            this._edge = command.edge;
            this._place();
        } else if (command.op === 'pointer') {
            const m = Main.layoutManager.primaryMonitor;
            if (command.x < m.x || command.x >= m.x + m.width || command.y < m.y || command.y >= m.y + m.height)
                throw new Error('Pointer outside lab monitor');
            this._pointer.notify_absolute_motion(GLib.get_monotonic_time(), command.x, command.y);
        } else if (['activate', 'close'].includes(command.op)) {
            const window = this._windows().find(w => w.get_stable_sequence() === command.id && w.get_pid() === command.pid);
            if (!window) throw new Error('Fixture window identity changed');
            if (command.op === 'activate') {
                const workspace = window.get_workspace();
                workspace.activate_with_focus(window, global.get_current_time());
            } else window.delete(global.get_current_time());
        } else if (command.op !== 'state') throw new Error('Unknown lab operation');
        const m = Main.layoutManager.primaryMonitor;
        return JSON.stringify({monitor: {x: m.x, y: m.y, width: m.width, height: m.height},
            dock: {x: this._dock.x, y: this._dock.y, width: this._dock.width, height: this._dock.height, hidden: this._hidden, edge: this._edge},
            actorMapped: this._dock.mapped,
            pointer: global.get_pointer().slice(0, 2), windows: this._windows().map(w => {
                const frame = w.get_frame_rect();
                return {id: w.get_stable_sequence(), pid: w.get_pid(), appId: w.get_gtk_application_id(),
                    title: w.get_title(), focused: w.has_focus(), clientType: w.get_client_type(),
                    frame: {x: frame.x, y: frame.y, width: frame.width, height: frame.height}};
            })});
    }

    disable() {
        this._export?.unexport(); this._export = null;
        if (this._timer) GLib.source_remove(this._timer);
        this._timer = 0;
        if (this._dock) { Main.layoutManager.removeChrome(this._dock); this._dock.destroy(); }
        this._dock = null; this._pointer = null; this._token = null;
    }
}
