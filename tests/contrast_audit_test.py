"""Validate alpha/luminance math independently of the CSS fixture results."""
import unittest
from contrast_audit import over, contrast

class ContrastMath(unittest.TestCase):
    def test_reference_ratios(self):
        self.assertAlmostEqual(contrast([0,0,0,1], [255,255,255,1]), 21)
        self.assertAlmostEqual(contrast([255,255,255,1], [0,0,0,1]), 21)
        self.assertAlmostEqual(contrast([100,120,140,1], [100,120,140,1]), 1)
        # WCAG reference: #767676 on white passes normal text, #777777 fails.
        self.assertGreater(contrast([118]*3+[1], [255]*3+[1]), 4.5)
        self.assertLess(contrast([119]*3+[1], [255]*3+[1]), 4.5)
    def test_alpha_composition(self):
        self.assertEqual(over([255,0,0,.5], [0,0,255,1]), [127.5,0,127.5,1])
        self.assertEqual(over([255,0,0,0], [0,0,255,1]), [0,0,255,1])
        self.assertEqual(over([255,0,0,0], [0,0,255,0]), [0,0,0,0])
        # A black group at half opacity on white must become middle gray.
        self.assertEqual(over([0,0,0,.5], [255,255,255,1]), [127.5]*3+[1])

if __name__ == '__main__':
    unittest.main()
