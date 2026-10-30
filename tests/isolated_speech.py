"""Owned Orca/SD/null-sink fixture for the private Xvfb native runner.

No host display or accessibility bus is used. Debug/audio stay in the lab root.
Orca's debug tail is buffered: stop the reader gracefully before deciding which
labels were spoken, while the app and audio capture are still alive.
"""
import array
import json
import os
from pathlib import Path
import signal
import subprocess
import time


class PrivateSpeech:
    def __init__(self, root):
        self.root = Path(root)
        self.host = os.environ['DESKMORPH_PRIVATE_SPEECH_HOST_PULSE']
        self.sink = 'deskmorph_isolated_speech_' + str(os.getpid())
        self.module = self.reader = self.before = None
        self.processes = []

    def pactl(self, *args):
        return subprocess.check_output(['pactl', '--server=' + self.host, *args], text=True, timeout=5).strip()

    def launch(self, command, name, env):
        with (self.root / (name + '.log')).open('w') as log:
            process = subprocess.Popen(command, env=env, stdout=log, stderr=log, start_new_session=True)
        self.processes.append(process)
        return process

    @staticmethod
    def wait(predicate, seconds=12):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            value = predicate()
            if value:
                return value
            time.sleep(.1)
        raise AssertionError('Private speech readiness timeout')

    @staticmethod
    def stop(process):
        if process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                # Orca has its own five-second shutdown watchdog. Let it
                # finish (and flush diagnostics) before harness escalation.
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait(timeout=5)

    def streams(self):
        owned = set()
        for proc in Path('/proc').iterdir():
            if not proc.name.isdigit():
                continue
            try:
                if f'DESKMORPH_ISOLATED_READER_LAB={self.root}'.encode() in (proc / 'environ').read_bytes().split(b'\0'):
                    owned.add(proc.name)
            except (FileNotFoundError, PermissionError, ProcessLookupError):
                pass
        return [stream for stream in json.loads(self.pactl('--format=json', 'list', 'sink-inputs'))
                if stream.get('properties', {}).get('application.process.id') in owned]

    def start(self):
        assert os.environ['DISPLAY'] == (self.root / 'display').read_text()
        assert os.environ['AT_SPI_BUS_ADDRESS'].startswith('unix:path=' + str(self.root))
        # Orca CLI's single-instance check is per Unix user, across all buses.
        # Never use --replace: that could terminate a user's reader.
        existing = subprocess.run(['pgrep', '-u', str(os.getuid()), '-x', 'orca'],
            capture_output=True, text=True, timeout=5)
        assert existing.returncode == 1, 'An Orca reader already exists; run speech fixtures sequentially'
        self.before = json.loads(self.pactl('--format=json', 'info'))['default_sink_name']
        self.module = self.pactl('load-module', 'module-null-sink', 'sink_name=' + self.sink,
            'sink_properties=device.description=DeskMorph_Isolated_Speech')
        config = self.root / 'speech-config'
        (config / 'modules').mkdir(parents=True)
        (config / 'modules/espeak-ng.conf').write_bytes(Path('/etc/speech-dispatcher/modules/espeak-ng.conf').read_bytes())
        (config / 'speechd.conf').write_text('LogLevel 5\nAudioOutputMethod "pulse"\nAudioPulseDevice "' + self.sink + '"\nAddModule "espeak-ng" "sd_espeak-ng" "espeak-ng.conf"\nDefaultModule espeak-ng\n')
        sock = self.root / 'speech.sock'
        env = dict(os.environ, SPT_NOENV='1', PULSE_SERVER=self.host, PULSE_SINK=self.sink,
            SPEECHD_ADDRESS='unix_socket:' + str(sock), DESKMORPH_ISOLATED_READER_LAB=str(self.root))
        daemon = self.launch(['speech-dispatcher', '-s', '-C', str(config), '-S', str(sock),
            '-P', str(self.root / 'speech.pid'), '-L', str(self.root), '-t', '0'], 'speech-launch', env)
        self.wait(lambda: sock.exists() or daemon.poll() is not None)
        assert daemon.poll() is None
        prefs = self.root / 'orca-prefs'
        prefs.mkdir()
        (prefs / 'user-settings.conf').write_text(json.dumps(dict(general=dict(enableSpeech=True,
            enableBraille=False, speechServerFactory='speechdispatcherfactory',
            speechServerInfo=['Default Synthesizer', 'default'], startingProfile=['Default', 'default']),
            profiles={'default': dict(profile=['Default', 'default'], pronunciations={}, keybindings={})},
            pronunciations={}, keybindings={})))
        self.raw = self.root / 'speech.raw'
        with self.raw.open('wb') as output, (self.root / 'capture.log').open('w') as errors:
            capture = subprocess.Popen(['parec', '--server=' + self.host, '--device=' + self.sink + '.monitor',
                '--rate=22050', '--channels=1', '--format=s16le', '--raw'],
                env=env, stdout=output, stderr=errors, start_new_session=True)
        self.processes.append(capture)
        self.debug = self.root / 'orca-debug.log'
        self.reader = self.launch(['orca', '-u', str(prefs), '--enable=speech', '--disable=braille',
            '--debug-file', str(self.debug)], 'orca-launch', env)
        def initialized():
            assert self.reader.poll() is None, 'Private reader exited during startup; see orca-launch.log'
            return self.debug.exists() and 'SPEECH: Initialized' in self.debug.read_text(errors='replace')
        self.wait(initialized)
        self.sink_id = next(sink['index'] for sink in json.loads(self.pactl('--format=json', 'list', 'sinks')) if sink['name'] == self.sink)
        def routed():
            streams = self.streams()
            return streams if streams and all(stream['sink'] == self.sink_id for stream in streams) else None
        # PipeWire can initially publish index 4294967295 until routing resolves.
        self.wait(routed)
        time.sleep(1)

    def observe(self, expected, seconds=8):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            assert self.reader.poll() is None, 'Private reader exited before observation ended'
            if any(expected in line and 'SPEECH OUTPUT:' in line for line in self.debug.read_text(errors='replace').splitlines()):
                break
            time.sleep(.1)
        # Let the short fixture utterance finish before reader shutdown.
        time.sleep(3)
        assert self.reader.poll() is None, 'Private reader exited during speech drain'
        streams = self.streams()
        assert streams and all(stream['sink'] == self.sink_id for stream in streams)
        # Ask the reader's private session service to quit on its GLib loop.
        # A POSIX handler can arrive during synchronous AT-SPI cache work.
        quit_result = subprocess.run(['gdbus', 'call', '--session', '--dest',
            'org.gnome.Orca.Service', '--object-path', '/org/gnome/Orca/Service',
            '--method', 'org.gnome.Orca.Service.Quit'], capture_output=True,
            text=True, timeout=5)
        assert quit_result.returncode == 0 and 'true' in quit_result.stdout, quit_result.stderr
        self.reader.wait(timeout=8)
        time.sleep(.2)
        lines = [line for line in self.debug.read_text(errors='replace').splitlines() if 'SPEECH OUTPUT:' in line]
        samples = array.array('h', self.raw.read_bytes())
        spoken = any(expected in line for line in lines)
        peak = max(map(abs, samples), default=0)
        nonzero = sum(sample != 0 for sample in samples)
        return dict(passed=spoken and self.reader.returncode == 0 and peak > 500 and nonzero > 10000,
            expected=expected, spoken=spoken, speechOutputLines=len(lines), readerAliveBeforeStop=True,
            readerExitCodeAfterObservation=self.reader.returncode, speechLogReadAfterReaderStop=True,
            speechDrainSeconds=3, samples=len(samples), nonzeroSamples=nonzero, peak=peak,
            playbackStreamsTargetOwnedNullSink=True)

    def close(self):
        errors = []
        for process in reversed(self.processes):
            try:
                self.stop(process)
            except Exception as error:
                errors.append(repr(error))
        if self.module is not None:
            try:
                self.pactl('unload-module', self.module)
            except Exception as error:
                errors.append(repr(error))
        if self.before is not None:
            try:
                assert json.loads(self.pactl('--format=json', 'info'))['default_sink_name'] == self.before
            except Exception as error:
                errors.append(repr(error))
        assert not errors, errors
