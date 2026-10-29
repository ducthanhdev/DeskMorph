"""Real PipeWire/PulseAudio protocol daemons with private sockets and no hardware modules."""
import json
import os
from pathlib import Path
import subprocess
import time


class PrivateAudioServer:
    def __init__(self, root):
        self.root = Path(root).resolve()
        assert str(self.root).startswith('/tmp/deskmorph-')
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        for name in ('runtime', 'pulse'):
            (self.root / name).mkdir(mode=0o700, exist_ok=True)
        self.address = 'unix:' + str(self.root / 'pulse/native')
        self.env = dict(os.environ, DESKMORPH_AUDIO_LAB=str(self.root),
            XDG_RUNTIME_DIR=str(self.root / 'runtime'), PIPEWIRE_RUNTIME_DIR=str(self.root / 'runtime'),
            PIPEWIRE_REMOTE='deskmorph-audio', PULSE_RUNTIME_PATH=str(self.root / 'pulse'),
            PULSE_SERVER=self.address, DBUS_SESSION_BUS_ADDRESS='unix:path=' + str(self.root / 'no-bus'))
        for key in ('DISPLAY', 'WAYLAND_DISPLAY', 'PIPEWIRE_CORE', 'PIPEWIRE_CONFIG_PREFIX', 'PIPEWIRE_CONFIG_DIR', 'PULSE_CLIENTCONFIG'):
            self.env.pop(key, None)
        self.processes = []
        self.core = self.pulse = None
        (self.root / 'core.conf').write_text('''context.properties = { core.daemon = true core.name = deskmorph-audio }
context.spa-libs = { audio.convert.* = audioconvert/libspa-audioconvert support.* = support/libspa-support }
context.modules = [
 { name = libpipewire-module-protocol-native }
 { name = libpipewire-module-spa-node-factory }
 { name = libpipewire-module-client-node }
 { name = libpipewire-module-access args = { access.legacy = true } }
 { name = libpipewire-module-adapter }
 { name = libpipewire-module-metadata }
 { name = libpipewire-module-link-factory }
]
context.objects = [ { factory = metadata args = { metadata.name = default } } ]
''')
        (self.root / 'pulse.conf').write_text('''context.properties = { core.daemon = false core.name = deskmorph-pulse }
context.spa-libs = { audio.convert.* = audioconvert/libspa-audioconvert support.* = support/libspa-support }
context.modules = [
 { name = libpipewire-module-protocol-native }
 { name = libpipewire-module-client-node }
 { name = libpipewire-module-adapter }
 { name = libpipewire-module-metadata }
 { name = libpipewire-module-protocol-pulse }
]
pulse.properties = { server.address = [ "''' + self.address + '''" ] pulse.allow-module-loading = true }
pulse.cmd = []
''')

    def launch(self, binary, config):
        with (self.root / (config + '.log')).open('a') as log:
            process = subprocess.Popen([binary, '-c', str(self.root / config)], env=self.env,
                stdout=log, stderr=log, start_new_session=True)
        self.processes.append(process)
        return process

    def pactl(self, *args):
        assert self.env['PULSE_SERVER'] == self.address
        return subprocess.check_output(['pactl', *args], env=self.env, text=True, stderr=subprocess.PIPE, timeout=6).strip()

    def start(self):
        self.core = self.launch('pipewire', 'core.conf')
        deadline = time.monotonic() + 8
        while not (self.root / 'runtime/deskmorph-audio').exists():
            assert self.core.poll() is None, 'Private PipeWire core exited'
            assert time.monotonic() < deadline, 'Private core socket unavailable'
            time.sleep(.1)
        self.start_pulse()

    def start_pulse(self):
        self.pulse = self.launch('pipewire-pulse', 'pulse.conf')
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            assert self.pulse.poll() is None, 'Private Pulse service exited'
            try:
                info = json.loads(self.pactl('--format=json', 'info'))
                assert info['server_string'] == self.address, info
                return info
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                time.sleep(.1)
        raise AssertionError('Private Pulse service readiness timed out')

    def sink(self, name, description="DeskMorph_Private_Output"):
        assert name.startswith('deskmorph_')
        module = self.pactl('load-module', 'module-null-sink', 'sink_name=' + name,
            'sink_properties=device.description=' + description)
        sinks = json.loads(self.pactl('--format=json', 'list', 'sinks'))
        assert sinks and all(item['properties']['factory.name'] == 'support.null-audio-sink' for item in sinks)
        self.pactl('set-default-sink', name)
        # No session manager is running in this hardware-free lab. Supply the
        # actual default metadata normally published by WirePlumber.
        subprocess.run(['pw-metadata', '-n', 'default', '0', 'default.audio.sink', json.dumps({'name': name}), 'Spa:String:JSON'], env=self.env, check=True, capture_output=True, timeout=5)
        assert json.loads(self.pactl('--format=json', 'info'))['default_sink_name'] == name
        return module

    def stop_process(self, process):
        if process is None or process.poll() is not None: return
        assert f'DESKMORPH_AUDIO_LAB={self.root}'.encode() in Path(f'/proc/{process.pid}/environ').read_bytes().split(b'\0')
        process.terminate()
        try: process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill(); process.wait(timeout=5)

    def stop(self):
        for process in reversed(self.processes): self.stop_process(process)


if __name__ == '__main__':
    import tempfile
    with tempfile.TemporaryDirectory(prefix='deskmorph-audio-probe-') as directory:
        server = PrivateAudioServer(directory)
        try:
            server.start(); server.sink('deskmorph_probe')
            print(server.pactl('--format=json', 'list', 'sinks'), flush=True)
            server.stop_process(server.pulse); server.start_pulse(); server.sink('deskmorph_probe_restart')
            print(server.pactl('--format=json', 'info'), flush=True)
        finally:
            server.stop()
            for config in ('core.conf.log', 'pulse.conf.log'):
                print((server.root / config).read_text()[-2500:])
