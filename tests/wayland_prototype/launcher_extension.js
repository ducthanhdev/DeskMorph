// Additional lab-only input/inspection for the actual DeskMorph launcher test.
import Base from './base_extension.js';
import Clutter from 'gi://Clutter';
import GLib from 'gi://GLib';
import Meta from 'gi://Meta';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
export default class LauncherLab extends Base {
    enable() {
        super.enable();
        this._keyboard = Clutter.get_default_backend().get_default_seat().create_virtual_device(Clutter.InputDeviceType.KEYBOARD_DEVICE);
    }
    _owned(pid) {
        try {
            const [ok, bytes] = GLib.file_get_contents(`/proc/${pid}/environ`);
            if (ok && new TextDecoder().decode(bytes).split('\0').includes(`DESKMORPH_COMPOSITOR_LAB=${GLib.getenv('DESKMORPH_COMPOSITOR_LAB')}`)) return true;
        } catch (_) { /* Snap confinement can deny environ even to the compositor. */ }
        if (GLib.getenv('DESKMORPH_SNAP_GUI_TEST') !== '1') return false;
        try {
            const root = GLib.getenv('DESKMORPH_COMPOSITOR_LAB');
            const profile = '--user-data-dir=/tmp/deskmorph-snap-probe-' + root.split('/').at(-1).replace('deskmorph-wayland-lab-', '');
            const [ok, bytes] = GLib.file_get_contents(`/proc/${pid}/cmdline`);
            const [labelOk, label] = GLib.file_get_contents(`/proc/${pid}/attr/current`);
            const args = new TextDecoder().decode(bytes).split(/[\0 ]+/).filter(Boolean);
            return ok && labelOk && new TextDecoder().decode(label).startsWith('snap.chromium.chromium (enforce)') &&
                args[0]?.startsWith('/snap/chromium/') && args[0]?.endsWith('/chrome') && args.includes(profile);
        } catch (_) { return false; }
    }
    _windows() {
        return global.get_window_actors().map(a => a.meta_window).filter(w => w.get_pid() === this._pid && this._owned(w.get_pid()));
    }
    Dispatch(token, payload) {
        if (token !== this._token) throw new Error('Invalid lab token');
        const command = JSON.parse(payload);
        if (command.op === 'bindingAvailable') {
            const action = global.display.grab_accelerator('<Control><Super>k', Meta.KeyBindingFlags.NONE);
            if (action) global.display.ungrab_accelerator(action);
            return JSON.stringify({available: action !== 0});
        }
        if (command.op === 'shortcut') {
            // One fixed safe chord, only on the owned headless compositor.
            for (const code of [29, 125, 37]) this._keyboard.notify_key(GLib.get_monotonic_time(), code, Clutter.KeyState.PRESSED);
            for (const code of [37, 125, 29]) this._keyboard.notify_key(GLib.get_monotonic_time(), code, Clutter.KeyState.RELEASED);
            return super.Dispatch(token, '{"op":"state"}');
        }
        if (command.op === 'prepare') {
            Main.overview.hide();
            return super.Dispatch(token, '{"op":"state"}');
        }
        if (command.op === 'target') {
            if (!Number.isInteger(command.pid) || !this._owned(command.pid)) throw new Error('Target is not owned by this lab');
            this._pid = command.pid;
            return super.Dispatch(token, '{"op":"state"}');
        }
        if (command.op === 'key') {
            const allowed = GLib.getenv('DESKMORPH_WALLPAPER_TEST') === '1' ? [1, 14, 15, 28, 44, 57, 102, 103, 107, 108] : [1, 28, 44];
            if (!allowed.includes(command.code) || !this._windows().some(w => w.has_focus())) throw new Error('Only Escape/Enter/Z in a focused lab window are allowed');
            this._keyboard.notify_key(GLib.get_monotonic_time(), command.code, Clutter.KeyState.PRESSED);
            this._keyboard.notify_key(GLib.get_monotonic_time(), command.code, Clutter.KeyState.RELEASED);
            return super.Dispatch(token, '{"op":"state"}');
        }
        return super.Dispatch(token, payload);
    }
    disable() { this._keyboard = null; this._pid = null; super.disable(); }
}
