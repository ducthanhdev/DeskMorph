import copy
import unittest
from performance_budget import validate


def fixture():
    budgets = dict(phases={p: dict(cpuPercentOfOneCore=20, peakPssMiB=500, maxManagedClients=24)
                          for p in ('studio', 'dock', 'autohidden', 'system', 'many')},
                   startupSeconds=dict(debug=3, release=2))
    runs = []
    for mode in ('debug', 'release'):
        for version in ('before', 'after'):
            for phase in (('studio',) if version == 'before' else budgets['phases']):
                for traced, repeat in ((False, 0), (False, 1), (True, 0)) if phase == 'studio' else ((False, 0), (True, 0)):
                    polls = 0 if phase == 'autohidden' else 18 if version == 'before' else 9
                    runs.append(dict(label=version+'-'+mode, phase=phase, traced=traced, repeat=repeat,
                                     config={}, managedClients=9, sampleSeconds=15,
                                     cpuPercentOfOneCore=10, peakPssMiB=400, startupToAccessibleButtonsSeconds=1,
                                     successfulExecsInSample={'xprop': polls*11} if polls else {},
                                     windowListPollsInSample=polls, windowDetailsQueriesInSample=polls*9,
                                     debugCommandStarts={'is_pointer_over_dock': 58} if phase == 'autohidden' and mode == 'debug' else {}))
    return dict(runs=runs, configRestored=True, allTestPidsExited=True), budgets


class BudgetTest(unittest.TestCase):
    def test_accepts_complete_matrix_and_ignores_trace_cpu(self):
        report, budgets = fixture()
        for run in report['runs']:
            if run['traced']: run['cpuPercentOfOneCore'] = 999
        self.assertEqual(set(validate(report, budgets)), {'debug', 'release'})

    def test_rejects_missing_untraced_overbudget_unmatched_and_spawn_regression(self):
        original, budgets = fixture()
        for change in ('missing', 'cpu', 'clients', 'spawn', 'hidden', 'cleanup'):
            report = copy.deepcopy(original)
            after = next(r for r in report['runs'] if r['label'] == 'after-debug')
            if change == 'missing': report['runs'].remove(after)
            elif change == 'cpu': after['cpuPercentOfOneCore'] = 21
            elif change == 'clients': after['managedClients'] = 10
            elif change == 'spawn':
                next(r for r in report['runs'] if r['label'] == 'after-debug' and r['traced'])['successfulExecsInSample']['xprop'] = 198
            elif change == 'hidden':
                next(r for r in report['runs'] if r['phase'] == 'autohidden' and r['traced'])['successfulExecsInSample'] = {'pactl': 1}
            else: report['configRestored'] = False
            with self.subTest(change=change), self.assertRaises(AssertionError): validate(report, budgets)


if __name__ == '__main__': unittest.main()
