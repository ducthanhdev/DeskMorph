#!/usr/bin/python3
"""Opt-in Orca speech integration over the owned context keyboard fixtures.

Runs on the unlocked GNOME X11 desktop. Speech uses an owned null sink;
default output/volume and existing screen-reader instances are preserved.
Raw audio and debug logs stay under /tmp, never in the evidence JSON.
"""
import array
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time
import wave


def run():
    repo = Path(__file__).resolve().parents[1]
    navigation = os.environ.get('DESKMORPH_ORCA_NAVIGATION', 'default')
    assert navigation in ('default', 'application', 'bypass-navigation'), 'Unknown Orca navigation profile'
    root = Path(tempfile.mkdtemp(prefix='deskmorph-orca-speech-'))
    sink = 'deskmorph_orca_' + str(os.getpid())
    processes = []
    module = None
    reader = None
    report = dict(passed=False, root=str(root),
        navigationProfileRequested=navigation,
        binarySha256=hashlib.sha256((repo / 'src-tauri/target/agent/debug/deskmorph').read_bytes()).hexdigest(),
        command='/usr/bin/python3 tests/screen_reader_smoke.py',
        scope='Orca speech enabled with native pinned-context keyboard fixtures in vi/en; speech synthesis captured from an owned null sink, no speaker playback or full application certification')

    def pactl(*args):
        return subprocess.check_output(['pactl', *args], text=True, timeout=6).strip()

    def wait(predicate, message, timeout=15):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            value = predicate()
            if value: return value
            time.sleep(.1)
        raise AssertionError(message)

    def launch(command, label, env):
        with (root / (label + '.log')).open('w') as log:
            process = subprocess.Popen(command, env=env, stdout=log, stderr=log, start_new_session=True)
        processes.append(process)
        return process

    # Replacing the user's reader would alter their desktop. This harness
    # deliberately refuses to use --replace or to terminate another instance.
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit(): continue
        try: command = (proc / 'cmdline').read_bytes().split(b'\0')
        except (FileNotFoundError, PermissionError, ProcessLookupError): continue
        assert not any(value in (b'/usr/bin/orca', b'orca') for value in command[:2]), 'An Orca instance is already running'
    lock = subprocess.check_output(['gdbus', 'call', '--session', '--dest', 'org.gnome.ScreenSaver', '--object-path', '/org/gnome/ScreenSaver', '--method', 'org.gnome.ScreenSaver.GetActive'], text=True, timeout=5)
    assert 'false' in lock, 'Unlock the desktop before screen-reader testing'
    before = json.loads(pactl('--format=json', 'info'))['default_sink_name']
    try:
        module = pactl('load-module', 'module-null-sink', 'sink_name=' + sink, 'sink_properties=device.description=DeskMorph_Orca_Capture')
        config = root / 'speech-config'
        (config / 'modules').mkdir(parents=True)
        (config / 'modules/espeak-ng.conf').write_bytes(Path('/etc/speech-dispatcher/modules/espeak-ng.conf').read_bytes())
        (config / 'speechd.conf').write_text('LogLevel 5\nAudioOutputMethod "pulse"\nAudioPulseDevice "' + sink + '"\nAddModule "espeak-ng" "sd_espeak-ng" "espeak-ng.conf"\nDefaultModule espeak-ng\n')
        socket = root / 'speech.sock'
        env = dict(os.environ, SPT_NOENV='1', DESKMORPH_ORCA_PREFS=str(root / 'orca-prefs'), PULSE_SINK=sink, SPEECHD_ADDRESS='unix_socket:' + str(socket), DESKMORPH_SPEECH_LAB=str(root))
        speech = launch(['speech-dispatcher', '-s', '-C', str(config), '-S', str(socket), '-P', str(root / 'speech.pid'), '-L', str(root), '-t', '0'], 'speech-launch', env)
        wait(lambda: socket.exists() or speech.poll() is not None, 'Private speech socket timed out')
        assert speech.poll() is None, 'Private speech daemon exited'
        prefs = root / 'orca-prefs'
        prefs.mkdir()
        navigation_settings = dict(
            caretNavigationEnabled=False, structuralNavigationEnabled=False) if navigation == 'application' else {}
        # Comparison preferences are requests; actual reader state is observed.
        report['navigationSettingsRequested'] = navigation_settings
        # An explicit comparison with Orca's own navigation disabled. This does
        # not change the application or bypass any shared keyboard assertions;
        # success here must not be reported as default-reader compatibility.
        (prefs / 'user-settings.conf').write_text(json.dumps(dict(general=dict(enableSpeech=True, enableBraille=False,
            **navigation_settings,
            speechServerFactory='speechdispatcherfactory', speechServerInfo=['Default Synthesizer', 'default'],
            startingProfile=['Default', 'default']), profiles={'default': dict(profile=['Default', 'default'], pronunciations={}, keybindings={}, **navigation_settings)}, pronunciations={}, keybindings={})))
        raw = root / 'speech.raw'
        with raw.open('wb') as output, (root / 'capture.log').open('w') as errors:
            capture = subprocess.Popen(['parec', '--device=' + sink + '.monitor', '--rate=22050', '--channels=1', '--format=s16le', '--raw'], env=env, stdout=output, stderr=errors, start_new_session=True)
        processes.append(capture)
        debug = root / 'orca-debug.log'
        reader = launch(['orca', '-u', str(prefs), '--enable=speech', '--disable=braille', '--debug-file', str(debug)], 'orca-launch', env)
        wait(lambda: debug.exists() and 'SPEECH: Initialized' in debug.read_text(errors='replace'), 'Orca did not initialize speech')
        assert reader.poll() is None
        # Speech Dispatcher and libespeak both receive PULSE_SINK. Verify all
        # their current playback streams target the owned sink before input.
        sink_id = next(item['index'] for item in json.loads(pactl('--format=json', 'list', 'sinks')) if item['name'] == sink)
        def speech_pids():
            owned_pids = set()
            for proc in Path('/proc').iterdir():
                if not proc.name.isdigit(): continue
                try:
                    if f'DESKMORPH_SPEECH_LAB={root}'.encode() in (proc / 'environ').read_bytes().split(b'\0'): owned_pids.add(proc.name)
                except (FileNotFoundError, PermissionError, ProcessLookupError): pass
            return owned_pids
        def speech_inputs():
            owned_pids = speech_pids()
            return [item for item in json.loads(pactl('--format=json', 'list', 'sink-inputs')) if item.get('properties', {}).get('application.process.id') in owned_pids]
        inputs = wait(speech_inputs, 'Speech playback stream missing')
        report['initialPlaybackTargets'] = dict(expectedSink=sink_id, observed=[dict(index=item['index'], sink=item['sink']) for item in inputs])
        assert all(item['sink'] == sink_id for item in inputs), 'Speech stream escaped the private sink'
        report['playbackStreamsTargetOwnedNullSink'] = True
        command = ['/usr/bin/python3', str(repo / 'tests/desktop_smoke.py'), '--restart', '--context-keyboard-smoke']
        with (root / 'keyboard.log').open('w') as log:
            result = subprocess.run(command, cwd=repo, stdout=log, stderr=log, timeout=240,
                env=dict(os.environ, DESKMORPH_ORCA_DRIVER_ROOT=str(root), DESKMORPH_ORCA_READER_PID=str(reader.pid)))
        report['keyboardExitCode'] = result.returncode
        assert result.returncode == 0, 'Native context keyboard suite failed; see keyboard.log'
        time.sleep(3)
        report['readerExitCodeBeforeCleanup'] = reader.poll()
        assert reader.poll() is None, 'Orca exited during the native keyboard suite'
        assert all(item['sink'] == sink_id for item in speech_inputs())
        capture.terminate(); capture.wait(timeout=5)
        samples = array.array('h', raw.read_bytes())
        assert samples and max(map(abs, samples)) > 500 and sum(value != 0 for value in samples) > 10000, 'Speech capture was silent'
        with wave.open(str(root / 'speech.wav'), 'wb') as output:
            output.setparams((1, 2, 22050, 0, 'NONE', 'not compressed')); output.writeframes(samples.tobytes())
        speech_lines = [line for line in debug.read_text(errors='replace').splitlines() if 'SPEECH OUTPUT:' in line]
        expected = ['DeskMorph Context Keyboard', 'Hủy', 'Cancel', 'Mở ứng dụng', 'Open application',
            'Không mở được ứng dụng', 'Unable to launch application',
            'Buộc đóng có thể', 'Force closing may close']
        observed = {text: any(text in line for line in speech_lines) for text in expected}
        report.update(speechEnabled=True, expectedUtterances=observed, speechOutputLines=len(speech_lines),
            audio=dict(rate=22050, channels=1, samples=len(samples), nonzeroSamples=sum(value != 0 for value in samples), peak=max(map(abs, samples)), sha256=hashlib.sha256(samples.tobytes()).hexdigest()),
            keyboard=json.loads(Path('/tmp/deskmorph-desktop-test/context-keyboard-matrix-result.json').read_text()),
            limits=['No human listening evaluation or certification of intelligibility', 'Whole-application reading order, every live region and other Orca settings remain outside this fixture suite'])
        assert all(observed.values()), 'Orca did not speak all expected context labels'
        report['passed'] = True
    except Exception as error:
        report['error'] = repr(error)
        raise
    finally:
        if reader is not None: report['readerExitCodeBeforeCleanup'] = reader.poll()
        for process in reversed(processes):
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try: process.wait(timeout=5)
                except subprocess.TimeoutExpired: os.killpg(process.pid, signal.SIGKILL); process.wait(timeout=5)
        if module is not None: pactl('unload-module', module)
        raw = root / 'speech.raw'
        if raw.exists():
            samples = array.array('h', raw.read_bytes())
            report['capturedAudio'] = dict(samples=len(samples), nonzeroSamples=sum(value != 0 for value in samples), peak=max(map(abs, samples), default=0))
        debug = root / 'orca-debug.log'
        if debug.exists():
            debug_text = debug.read_text(errors='replace')
            lines = [line for line in debug_text.splitlines() if 'SPEECH OUTPUT:' in line]
            report['speechOutputLines'] = len(lines)
            report['fixtureLabelSpoken'] = any('DeskMorph Context Keyboard' in line for line in lines)
            report['bypassNavigation'] = dict(
                requested=navigation == 'bypass-navigation',
                enabledEvents=sum('DEFAULT: Removing key grabs for deskmorph ' in line and ': bypass mode enabled' in line for line in debug_text.splitlines()),
                disabledEvents=sum('DEFAULT: Adding key grabs for deskmorph ' in line and ': bypass mode disabled' in line for line in debug_text.splitlines()))
            report['applicationCaretNavigationEnabledObserved'] = (
                'Setting enabled state for deskmorph (module=orca.scripts.toolkits.WebKitGTK.script) to True'
                in debug_text)
        launch_log = root / 'orca-launch.log'
        report['orcaSegfaultLogged'] = launch_log.exists() and 'Segmentation fault' in launch_log.read_text(errors='replace')
        report['readerExitCodeAfterCleanup'] = reader.returncode if reader is not None else None
        report['processExitCodesAfterCleanup'] = [process.returncode for process in processes]
        report['defaultOutputPreserved'] = json.loads(pactl('--format=json', 'info'))['default_sink_name'] == before
        report['ownedProcessesExited'] = all(process.poll() is not None for process in processes)
        (root / 'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps(dict(root=str(root), passed=report['passed'], error=report.get('error'))), flush=True)
    assert report['defaultOutputPreserved'] and report['ownedProcessesExited']


if __name__ == '__main__': run()
