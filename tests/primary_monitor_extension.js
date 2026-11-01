// GNOME Shell test-only confirmation bridge. It starts only in the private
// compositor lab and never exists in the user's session.
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

const XML = `<node><interface name="org.deskmorph.PrimaryLab">
  <method name="Complete"><arg type="s" direction="in"/><arg type="b" direction="in"/></method>
</interface></node>`;

export default class PrimaryMonitorLab extends Extension {
    enable() {
        const root = GLib.getenv('DESKMORPH_COMPOSITOR_LAB');
        this._token = GLib.getenv('DESKMORPH_PRIMARY_LAB_TOKEN');
        if (!root?.startsWith('/tmp/deskmorph-primary-lab-') || !this._token)
            throw new Error('Primary monitor test extension requires an isolated lab');
        this._root = root;
        this._pending = false;
        this._signal = global.window_manager.connect('confirm-display-change', () => {
            this._pending = true;
            GLib.file_set_contents(`${this._root}/confirmation-pending`, 'pending');
        });
        this._export = Gio.DBusExportedObject.wrapJSObject(XML, this);
        this._export.export(Gio.DBus.session, '/org/deskmorph/PrimaryLab');
        this._owner = Gio.bus_own_name_on_connection(Gio.DBus.session,
            'org.deskmorph.PrimaryLab', Gio.BusNameOwnerFlags.NONE, null, null);
    }

    Complete(token, keep) {
        if (token !== this._token || !this._pending)
            throw new Error('No matching display confirmation');
        this._pending = false;
        global.window_manager.complete_display_change(keep);
        GLib.file_set_contents(`${this._root}/confirmation-result`, keep ? 'kept' : 'reverted');
    }

    disable() {
        if (this._signal) global.window_manager.disconnect(this._signal);
        this._signal = 0;
        this._export?.unexport(); this._export = null;
        if (this._owner) Gio.bus_unown_name(this._owner);
        this._owner = 0; this._pending = false; this._token = null;
    }
}
