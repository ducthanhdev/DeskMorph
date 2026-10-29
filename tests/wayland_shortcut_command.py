#!/usr/bin/python3
"""Record non-secret activation evidence, then exec the real launcher command."""
import json
import os
from pathlib import Path
import sys
root = Path(os.environ['DESKMORPH_COMPOSITOR_LAB'])
assert str(root).startswith('/tmp/deskmorph-wayland-lab-')
assert os.environ['XDG_RUNTIME_DIR'] == str(root / 'runtime') and not os.environ.get('DISPLAY')
binary = Path(__file__).resolve().parents[1] / 'src-tauri/target/agent/debug/deskmorph'
assert binary.is_file()
with (root / 'shortcut-invocations.jsonl').open('a') as output:
    output.write(json.dumps(dict(pid=os.getpid(), xdgActivationTokenPresent=bool(os.environ.get('XDG_ACTIVATION_TOKEN')), desktopStartupIdPresent=bool(os.environ.get('DESKTOP_STARTUP_ID')))) + '\n')
os.execv(str(binary), [str(binary), '--launcher'])
