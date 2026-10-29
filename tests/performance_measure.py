"""Process-tree/PSS samples and execve counts; no argument contents in reports."""
from collections import Counter
import os
from pathlib import Path
import re
import statistics
import time


def process_sample(pid):
    ticks = os.sysconf('SC_CLK_TCK')
    page_kib = os.sysconf('SC_PAGE_SIZE') / 1024
    processes = {}
    for entry in Path('/proc').iterdir():
        if not entry.name.isdecimal():
            continue
        try:
            values = (entry / 'stat').read_text().rsplit(')', 1)[1].split()
            processes[int(entry.name)] = (int(values[1]), sum(int(v) for v in values[11:15]) / ticks, int(values[21]) * page_kib)
        except (OSError, ValueError, IndexError):
            continue
    owned = {pid}
    while True:
        expanded = owned | {child for child, (parent, _, _) in processes.items() if parent in owned}
        if expanded == owned:
            break
        owned = expanded
    assert pid in processes, 'Measured application exited'
    pss = 0
    for child in owned:
        try:
            match = re.search(r'^Pss:\s+(\d+) kB$', Path(f'/proc/{child}/smaps_rollup').read_text(), re.M)
            assert match, 'Missing PSS'
            pss += int(match.group(1))
        except FileNotFoundError:
            if child == pid:
                raise
    return dict(wall=time.time(), monotonic=time.monotonic(), cpuSeconds=sum(processes[p][1] for p in owned),
                rssKiB=sum(processes[p][2] for p in owned), pssKiB=pss, processes=len(owned))


def measure(pid, duration=15, validate=lambda: None):
    validate()
    samples = [process_sample(pid)]
    deadline = time.monotonic() + duration
    while time.monotonic() < deadline:
        time.sleep(min(1, max(.01, deadline - time.monotonic())))
        validate()
        samples.append(process_sample(pid))
    elapsed = samples[-1]['monotonic'] - samples[0]['monotonic']
    cpu = (samples[-1]['cpuSeconds'] - samples[0]['cpuSeconds']) / elapsed * 100
    assert cpu >= 0, 'Process-tree CPU counter went backwards; sample is inconclusive'
    return dict(sampleSeconds=round(elapsed, 3), cpuPercentOfOneCore=round(cpu, 3),
                medianPssMiB=round(statistics.median(s['pssKiB'] for s in samples) / 1024, 2),
                peakPssMiB=round(max(s['pssKiB'] for s in samples) / 1024, 2),
                medianRssMiB=round(statistics.median(s['rssKiB'] for s in samples) / 1024, 2),
                processCounts=sorted(set(s['processes'] for s in samples)), samples=samples)


def exec_counts(lines, begin, end):
    pending, calls = {}, []
    for line in lines:
        match = re.match(r'^(\d+)\s+(\d+\.\d+)\s+(.*)$', line)
        if not match:
            continue
        pid, timestamp, body = match.groups()
        if body.startswith('execve(') and body.endswith('<unfinished ...>'):
            pending[pid] = (float(timestamp), body.removesuffix('<unfinished ...>'))
            continue
        if body.startswith('<... execve resumed>'):
            assert pid in pending, 'execve resumed without its start'
            timestamp, prefix = pending.pop(pid)
            body = prefix + body.removeprefix('<... execve resumed>')
        event = re.match(r'execve\("([^"\\]+)", (.*) = 0$', body)
        if event and begin <= float(timestamp) <= end:
            calls.append((Path(event.group(1)).name, event.group(2)))
    assert not any(begin <= timestamp <= end for timestamp, _ in pending.values()), 'Incomplete execve within sample'
    return dict(successfulExecsInSample=dict(Counter(name for name, _ in calls)),
                windowListPollsInSample=sum(name == 'xprop' and '"-root", "_NET_ACTIVE_WINDOW"' in args for name, args in calls),
                windowDetailsQueriesInSample=sum(name == 'xprop' and '"-id"' in args for name, args in calls))
