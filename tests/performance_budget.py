"""Validate the complete reference matrix; traced CPU is never budget evidence."""
import json
from pathlib import Path
import sys


def validate(report, budgets):
    runs = report['runs']
    assert report['configRestored'] and report['allTestPidsExited'], 'Incomplete cleanup'
    comparisons = {}
    for mode in ('debug', 'release'):
        before = [r for r in runs if r['label'] == 'before-' + mode and r['phase'] == 'studio']
        after = [r for r in runs if r['label'] == 'after-' + mode and r['phase'] == 'studio']
        assert len(before) == len(after) == 3, 'Need two untraced and one traced matched runs'
        assert sum(not r['traced'] for r in before) == 2, 'Missing untraced baseline'
        assert len({json.dumps(r['config'], sort_keys=True) for r in before + after}) == 1, 'Unmatched configuration'
        assert len({r['managedClients'] for r in before + after}) == 1, 'Unmatched client counts'
        old_trace, = [r for r in before if r['traced']]
        new_trace, = [r for r in after if r['traced']]
        old_rate = old_trace['successfulExecsInSample'].get('xprop', 0) / old_trace['sampleSeconds']
        new_rate = new_trace['successfulExecsInSample'].get('xprop', 0) / new_trace['sampleSeconds']
        assert old_rate > 0 and new_rate <= old_rate * .65, 'Shared snapshot spawn regression'
        comparisons[mode] = {'beforeXpropPerSecond': round(old_rate, 3), 'afterXpropPerSecond': round(new_rate, 3)}
        for phase, limits in budgets['phases'].items():
            current = [r for r in runs if r['label'] == 'after-' + mode and r['phase'] == phase]
            untraced = [r for r in current if not r['traced']]
            traced = [r for r in current if r['traced']]
            assert len(untraced) == (2 if phase == 'studio' else 1) and len(traced) == 1, 'Missing native measurement: ' + phase
            assert len({r['managedClients'] for r in current}) == 1, 'Clients changed between CPU and trace runs'
            assert len({json.dumps(r['config'], sort_keys=True) for r in current}) == 1, 'Configuration changed between CPU and trace runs'
            for run in current:
                assert 14.5 <= run['sampleSeconds'] <= 17, 'Invalid reference sample duration'
                assert run['managedClients'] <= limits['maxManagedClients'], 'Outside calibrated client workload'
            for run in untraced:
                for field, maximum in (('cpuPercentOfOneCore', limits['cpuPercentOfOneCore']),
                                       ('peakPssMiB', limits['peakPssMiB']),
                                       ('startupToAccessibleButtonsSeconds', budgets['startupSeconds'][mode])):
                    assert run[field] <= maximum, f'{mode}/{phase}: {field}={run[field]} exceeds {maximum}'
            trace = traced[0]
            polls = trace['windowListPollsInSample']
            maximum = 0 if phase == 'autohidden' else int(trace['sampleSeconds'] / 1.5) + 1
            assert polls <= maximum, f'{phase}: native window polling exceeds budget'
            assert trace['windowDetailsQueriesInSample'] == polls * trace['managedClients'], 'Incomplete detail-query accounting'
            assert trace['successfulExecsInSample'].get('xprop', 0) == polls * (2 + trace['managedClients']), 'Unexpected xprop spawning'
            if phase == 'autohidden':
                assert not trace['successfulExecsInSample'], 'Hidden UI spawned commands'
                starts = trace['debugCommandStarts']
                assert not any(starts.get(k, 0) for k in ('get_open_windows', 'get_system_stats', 'get_system_status')), 'Hidden GUI still polls'
                if mode == 'debug':
                    assert 0 < starts.get('is_pointer_over_dock', 0) <= trace['sampleSeconds'] / .25 + 2, 'Pointer timer outside budget'
    return comparisons


if __name__ == '__main__':
    report = json.loads(Path(sys.argv[1]).read_text())
    budgets = json.loads(Path(sys.argv[2]).read_text())
    print(json.dumps(validate(report, budgets), indent=2))
