"""Trace parsing must not drop split execve or count failed PATH attempts."""
import unittest
from performance_measure import exec_counts


class ExecCountsTest(unittest.TestCase):
    def test_complete_and_split_successes_and_failed_path_search(self):
        records = [
            '12 100.000 execve("/missing/xprop", ["xprop"], 0x0) = -1 ENOENT (No such file)',
            '12 100.001 execve("/usr/bin/xprop", ["xprop", "-root", "_NET_ACTIVE_WINDOW"], 0x0 <unfinished ...>',
            '13 100.002 execve("/usr/bin/xprop", ["xprop", "-id", "0x12"], 0x0) = 0',
            '12 100.003 <... execve resumed>) = 0',
            '14 99.000 execve("/usr/bin/pactl", ["pactl"], 0x0) = 0',
        ]
        result = exec_counts(records, 100, 101)
        self.assertEqual(result['successfulExecsInSample'], {'xprop': 2})
        self.assertEqual(result['windowListPollsInSample'], 1)
        self.assertEqual(result['windowDetailsQueriesInSample'], 1)

    def test_unfinished_interval_or_unpaired_resume_is_not_complete_evidence(self):
        with self.assertRaisesRegex(AssertionError, 'Incomplete'):
            exec_counts(['12 100.000 execve("/usr/bin/xprop", [] <unfinished ...>'], 100, 101)
        with self.assertRaisesRegex(AssertionError, 'without its start'):
            exec_counts(['12 100.001 <... execve resumed>) = 0'], 100, 101)


if __name__ == '__main__':
    unittest.main()
