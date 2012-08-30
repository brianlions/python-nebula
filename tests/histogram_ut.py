#!/usr/bin/env python3
#
# Copyright (c) 2012 Brian Yi ZHANG <brianlions at gmail dot com>
#
# This file is part of pynebula.
#
# pynebula is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# pynebula is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with pynebula. If not, see <http://www.gnu.org/licenses/>.
#

import unittest

import add_nebula_path
import nebula

class HistogramTest(unittest.TestCase):

    def expected_len(self, bound_hint):
        pass

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_len(self):
        bound_and_expected_len = ((1, 6), (2, 6), (3, 6), (4, 6), (5, 6),

                                  (6, 22), (8, 22), (10, 22), (15, 22),
                                  (18, 22), (20, 22), (23, 22), (30, 22),
                                  (31, 22), (40, 22), (41, 22), (47, 22),
                                  (50, 22),

                                  (60, 38), (70, 38), (80, 38), (100, 38),
                                  (105, 38), (137, 38), (200, 38), (290, 38),
                                  (300, 38), (350, 38), (400, 38), (450, 38),
                                  (500, 38),

                                  (501, 54),
                                  )

        for bound, exp_len in bound_and_expected_len:
            histogram = nebula.histogram.Histogram(bound)
            self.assertEqual(exp_len, len(histogram))

    def test_add(self):
        list_a = ((0, 0), (1, 1), (2, 2), (3, 3), (4, 4),
                  (5, 5), (6, 5), (7, 5),
                  )
        list_b = ((0, 0),
                  (1, 1), (2, 2), (3, 3), (4, 4), (5, 5),
                  (6, 6), (7, 7), (8, 8), (9, 9), (10, 10),
                  (11, 10),
                  (12, 11), (13, 11),
                  (14, 12), (15, 12),
                  (16, 13), (17, 13),
                  (18, 14), (19, 14),
                  (20, 15), (24, 15),
                  (25, 16), (29, 16),
                  (30, 17), (34, 17),
                  (35, 18), (39, 18),
                  (40, 19), (44, 19),
                  (45, 20), (49, 20),
                  (50, 21), (60, 21), (70, 21), (10000, 21), (1000000, 21),
                  )
        bound_and_cases = {
                           3: list_a, 5: list_a,
                           10: list_b, 20: list_b, 30: list_b, 40: list_b,
                           50: list_b,
                           }
        for b in bound_and_cases.keys():
            histogram = nebula.histogram.Histogram(b)
            for v, idx in bound_and_cases[b]:
                self.assertEqual(histogram.add(v), idx)

    def test_statistics(self):
        list_a = list(range(1, 10))
        list_b = list(range(10, 50))

        for l in (list_a, list_b):
            hist = nebula.histogram.Histogram()
            for v in l:
                hist.add(v)
            self.assertEqual(hist.min(), min(l))
            self.assertEqual(hist.max(), max(l))
            self.assertEqual(hist.total(), sum(l))
            self.assertEqual(hist.average(), sum(l) / len(l))

#------------------------------------------------------------------------------

if __name__ == '__main__':
    unittest.main()
