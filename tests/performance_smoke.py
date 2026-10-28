"""Reference debug-build measurements; traces are separate from idle CPU samples."""
from collections import Counter
import json
import os
from pathlib import Path
import re
import statistics
import subprocess
import time


def run(app, config_home, startup_seconds, traced):
    root = Path('/tmp/deskmorph-desktop-test')
    pid = app.get_process_id()
    assert b'DESKMORPH_CONFIG_HOME=' + config_home.encode() in Path(f'/proc/{pid}/environ').read_bytes().split(b'\0')
    config = json.loads((Path(config_home) / 'com.ducthanhdev.deskmorph/config.json').read_text())['config']
    assert config['enabled'] and config['showApps'] and config['showStats'] and not config['autoHide'], 'Baseline requires visible Dock/apps/stats and autoHide off'
    assert startup_seconds is not None and startup_seconds > 0
    ticks = os.sysconf('SC_CLK_TCK')
    page_kib = os.sysconf('SC_PAGE_SIZE') / 1024

    def sample():
        processes = {}
        for entry in Path('/proc').iterdir():
            if not entry.name.isdecimal(): continue
            try:
                fields = (entry / 'stat').read_text().rsplit(')', 1)[1].split()
                processes[int(entry.name)] = (int(fields[1]), sum(int(v) for v in fields[11:15]) / ticks, int(fields[21]) * page_kib)
            except (OSError, ValueError, IndexError): continue
        owned = {pid}
        while True:
            expanded = owned | {child for child, (parent, _, _) in processes.items() if parent in owned}
            if expanded == owned: break
            owned = expanded
        assert pid in processes, 'Measured app exited'
        pss = 0
        for child in owned:
            try:
                match = re.search(r'^Pss:\s+(\d+) kB$', Path(f'/proc/{child}/smaps_rollup').read_text(), re.M)
                assert match, 'Missing PSS'
                pss += int(match.group(1))
            except FileNotFoundError:
                if child == pid: raise
        return dict(wall=time.time(), cpuSeconds=sum(processes[p][1] for p in owned), rssKiB=sum(processes[p][2] for p in owned), pssKiB=pss, processes=len(owned))

    time.sleep(3)  # Separate startup work from the steady-state sample.
    begin = time.time()
    samples = [sample()]
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        time.sleep(min(1, max(.01, deadline - time.monotonic())))
        samples.append(sample())
    end = time.time()
    elapsed = samples[-1]['wall'] - samples[0]['wall']
    report = dict(pid=pid, build='debug/custom-protocol', traced=traced, startupToAccessibleButtonsSeconds=round(startup_seconds, 3), sampleSeconds=round(elapsed, 3),
        config={key: config[key] for key in ('enabled', 'autoHide', 'showApps', 'showStats', 'showAudio', 'showClock', 'showBattery', 'showNetwork')},
        cpuPercentOfOneCore=round((samples[-1]['cpuSeconds'] - samples[0]['cpuSeconds']) / elapsed * 100, 3),
        medianPssMiB=round(statistics.median(s['pssKiB'] for s in samples) / 1024, 2), peakPssMiB=round(max(s['pssKiB'] for s in samples) / 1024, 2),
        medianRssMiB=round(statistics.median(s['rssKiB'] for s in samples) / 1024, 2), processCounts=sorted(set(s['processes'] for s in samples)))
    clients = subprocess.check_output(['xprop', '-root', '_NET_CLIENT_LIST'], text=True)
    report['managedClientCountAtEnd'] = len(re.findall(r'0x[0-9a-fA-F]+', clients))
    if traced:
        calls = []
        trace_lines = (root / 'performance-execve.log').read_text().splitlines()
        assert not any('<unfinished ...>' in line or '<... execve resumed>' in line for line in trace_lines), 'Split execve records require a per-PID trace parser; no complete-count claim'
        for line in trace_lines:
            match = re.search(r'\s(\d+\.\d+) execve\("([^"]+)", (.*) = 0$', line)
            if match and begin <= float(match.group(1)) <= end: calls.append((Path(match.group(2)).name, match.group(3)))
        report['successfulExecsInSample'] = dict(Counter(name for name, _ in calls))
        report['windowListPollsInSample'] = sum(name == 'xprop' and '"-root", "_NET_ACTIVE_WINDOW"' in argv for name, argv in calls)
        report['windowDetailsQueriesInSample'] = sum(name == 'xprop' and '"-id"' in argv for name, argv in calls)
        assert report['windowListPollsInSample'] > 0, 'strace did not capture real window polls'
        report['windowListPollsPerSecond'] = round(report['windowListPollsInSample'] / (end - begin), 3)
    output = root / ('performance-trace-result.json' if traced else 'performance-idle-result.json')
    payload = json.dumps(dict(report=report, samples=samples), indent=2)
    output.write_text(payload)
    (root / f'performance-{"trace" if traced else "idle"}-{pid}.json').write_text(payload)
    print(json.dumps(report), flush=True)
