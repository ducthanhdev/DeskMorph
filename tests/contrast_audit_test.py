"""Validate alpha/luminance math independently of the CSS fixture results."""
import unittest
from contrast_audit import over, contrast, background_bounds, contrast_lower_bound

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

    def test_gradient_alpha_bounds_and_unsupported_layers(self):
        layer = dict(background=[9,13,22,1], opacity=1,
            image='radial-gradient(at 10% 10%, rgba(72,185,199,0.06) 0%, rgba(0,0,0,0) 40%)')
        lower, upper = background_bounds([layer])
        self.assertEqual(lower, [9,13,22,1])
        for actual, expected in zip(upper, [12.78,23.32,32.62,1]):
            self.assertAlmostEqual(actual, expected)
        for unsupported in (dict(layer, opacity=.5), dict(layer, image='url(asset.png)'),
                            dict(layer, image='linear-gradient(in oklab, rgb(0,0,0), rgb(255,255,255))')):
            with self.assertRaises(AssertionError): background_bounds([unsupported])

    def test_gradient_floor_covers_continuous_samples_and_luminance_crossing(self):
        layer = dict(background=[0,0,0,1], opacity=1,
            image='linear-gradient(rgb(80,10,40), rgb(10,80,20))')
        lower, upper = background_bounds([layer])
        foreground = [241,245,249,1]
        bound = contrast_lower_bound(foreground, lower, upper)
        for step in range(101):
            t = step / 100
            actual = [80*(1-t)+10*t, 10*(1-t)+80*t, 40*(1-t)+20*t, 1]
            self.assertLessEqual(bound, contrast(foreground, actual) + 1e-12)
        self.assertEqual(contrast_lower_bound([118,118,118,1], [0,0,0,1], [255,255,255,1]), 1)

if __name__ == '__main__':
    unittest.main()
