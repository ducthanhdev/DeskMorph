"""Safety guards: reject host resources before launching Shell or sending keys."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from private_gnome_wm import private_gnome_wm


class PrivateWmGuards(unittest.TestCase):
    def test_host_display_bus_settings_or_xdg_never_launch_shell(self):
        with tempfile.TemporaryDirectory(prefix='deskmorph-negative-origin-') as folder:
            root = Path(folder) / 'case'
            root.mkdir()
            (root / 'display').write_text(':999')
            env = dict(DESKMORPH_GEOMETRY_LAB=str(root), DISPLAY=':999',
                GSETTINGS_BACKEND='keyfile',
                DBUS_SYSTEM_BUS_ADDRESS='unix:path=' + str(root / 'no-system-bus'),
                DBUS_SESSION_BUS_ADDRESS='unix:path=/tmp/dbus-owned-fixture',
                **{key: str(root / key) for key in ('XDG_RUNTIME_DIR',
                    'XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'XDG_CACHE_HOME')})
            for key, value in (
                ('DESKMORPH_GEOMETRY_LAB', '/tmp/unowned'),
                ('DISPLAY', ':0'),
                ('GSETTINGS_BACKEND', 'dconf'),
                ('DBUS_SYSTEM_BUS_ADDRESS', 'unix:path=/run/dbus/system_bus_socket'),
                ('DBUS_SESSION_BUS_ADDRESS', 'unix:path=/run/user/1000/bus'),
                ('XDG_CONFIG_HOME', '/tmp/outside-lab'),
            ):
                with self.subTest(key=key), patch.dict(os.environ, dict(env, **{key: value}), clear=True), \
                        patch('private_gnome_wm.subprocess.Popen') as launch:
                    with self.assertRaises(AssertionError):
                        with private_gnome_wm(root):
                            self.fail('Invalid host resource was accepted')
                    launch.assert_not_called()


if __name__ == '__main__':
    unittest.main()
