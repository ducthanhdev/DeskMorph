"""Procfs observations for an owned native test instance and its descendants."""
from pathlib import Path
import statistics
import time


class NativeResources:
    def __init__(self, pid, config_home):
        self.pid = pid
        assert f'DESKMORPH_CONFIG_HOME={config_home}'.encode() in Path(f'/proc/{pid}/environ').read_bytes().split(b'\0')
        self.started = time.monotonic()
        self.samples = []
        self.identities = {}

    def sample(self):
        pending, seen, rows = [self.pid], set(), []
        while pending:
            pid = pending.pop()
            if pid in seen: continue
            seen.add(pid)
            proc = Path(f'/proc/{pid}')
            try:
                stat = (proc / 'stat').read_text().rsplit(')', 1)[1].split()
                if stat[0] == 'Z': continue
                for children in (proc / 'task').glob('*/children'):
                    try: pending.extend(map(int, children.read_text().split()))
                    except FileNotFoundError: pass
                status = dict(line.split(':', 1) for line in (proc / 'status').read_text().splitlines() if ':' in line)
                try: fds = len(list((proc / 'fd').iterdir()))
                except PermissionError:
                    if pid == self.pid: raise
                    fds = None  # Sandboxed WebKit children can deny fd inspection.
                row = dict(pid=pid, name=status['Name'].strip(), rssKiB=int(status.get('VmRSS', '0 kB').split()[0]),
                    threads=int(status['Threads']), fds=fds)
                rows.append(row)
                self.identities[pid] = stat[19]  # /proc stat field 22: starttime.
            except FileNotFoundError:
                if pid == self.pid: raise AssertionError('Owned native app exited during soak')
        assert any(row['pid'] == self.pid for row in rows), 'Native app missing from resource sample'
        value = dict(seconds=round(time.monotonic() - self.started, 3), processes=rows)
        self.samples.append(value)
        return value

    def summary(self):
        assert len(self.samples) >= 12, 'Too few samples for resource trend comparison'
        # Skip the first third for lazy WebKit initialization. Compare medians
        # over the middle and last thirds rather than two noisy endpoints.
        size = len(self.samples) // 3
        def median(group, field):
            return statistics.median(next(row[field] for row in sample['processes'] if row['pid'] == self.pid) for sample in group)
        middle, last = self.samples[size:2 * size], self.samples[-size:]
        deltas = {field: median(last, field) - median(middle, field) for field in ('rssKiB', 'threads', 'fds')}
        deltas['treeRssKiB'] = statistics.median(sum(row['rssKiB'] for row in sample['processes']) for sample in last) - statistics.median(sum(row['rssKiB'] for row in sample['processes']) for sample in middle)
        deltas['treeProcesses'] = statistics.median(len(sample['processes']) for sample in last) - statistics.median(len(sample['processes']) for sample in middle)
        # Conservative alarms for sustained growth, not a proof of zero leaks.
        limits = dict(rssKiB=32768, threads=4, fds=8, treeRssKiB=131072, treeProcesses=2)
        return dict(sampleCount=len(self.samples), elapsedSeconds=self.samples[-1]['seconds'],
            first=self.samples[0], last=self.samples[-1], medianGrowth=deltas, alarmLimits=limits,
            withinGrowthLimits=all(deltas[key] <= limits[key] for key in limits),
            peakTreeRssKiB=max(sum(row['rssKiB'] for row in sample['processes']) for sample in self.samples))

    def survivors(self):
        live = []
        for pid, starttime in self.identities.items():
            try:
                stat = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
                if stat[0] != 'Z' and stat[19] == starttime: live.append(pid)
            except FileNotFoundError: pass
        return live
