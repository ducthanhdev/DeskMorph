"""Input isolation guards; invalid resources must never receive XTest events."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from private_keyboard import PrivateKeyboard


class PrivateInputGuards(unittest.TestCase):
    def test_display_or_marker_mismatch_rejected_before_loading_x11(self):
        with tempfile.TemporaryDirectory(prefix='deskmorph-negative-origin-') as folder:
            root = Path(folder) / 'case'
            root.mkdir()
            (root / 'display').write_text(':999')
            env = dict(DISPLAY=':999', DESKMORPH_GEOMETRY_LAB=str(root))
            for key, value in [('DISPLAY', ':0'), ('DESKMORPH_GEOMETRY_LAB', '/tmp/unowned')]:
                with self.subTest(key=key), patch.dict(os.environ, dict(env, **{key: value}), clear=True), \
                        patch('private_keyboard.ctypes.CDLL') as library:
                    with self.assertRaises(AssertionError):
                        PrivateKeyboard(root)
                    library.assert_not_called()

    def test_wrong_pid_and_lost_activation_send_no_keys(self):
        with tempfile.TemporaryDirectory(prefix='deskmorph-negative-origin-') as folder:
            root = Path(folder) / 'case'
            root.mkdir()
            (root / 'display').write_text(':999')
            for responses in [['_NET_WM_PID(CARDINAL) = 999'],
                              ['_NET_WM_PID(CARDINAL) = 123', '_NET_ACTIVE_WINDOW(WINDOW) = 0x99']]:
                x11, xtst = MagicMock(), MagicMock()
                with self.subTest(responses=responses), \
                        patch.dict(os.environ, dict(DISPLAY=':999', DESKMORPH_GEOMETRY_LAB=str(root)), clear=True), \
                        patch('private_keyboard.ctypes.CDLL', side_effect=[x11, xtst]), \
                        patch('private_keyboard.subprocess.check_output', side_effect=responses):
                    keyboard = PrivateKeyboard(root)
                    with self.assertRaises(AssertionError):
                        keyboard.keys('0x12', 123, [0xff0d])
                    x11.XOpenDisplay.assert_not_called()
                    xtst.XTestFakeKeyEvent.assert_not_called()


if __name__ == '__main__':
    unittest.main()
