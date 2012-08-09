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

class BlackHoleLogger(nebula.log.Logger):
    def __init__(self, *args, **kwargs):
        super(BlackHoleLogger, self).__init__(*args, **kwargs)

    def output_message(self, level, msg, file_name, line_num, func_name,
                       use_gmtime = None, show_timezone = None):
        '''Do nothing but discards all log messages.'''
        pass

#  -----------------------------------------------------------------------------

class NebulaLogging(unittest.TestCase):
    valid_levels = (nebula.log.Logger.EMERG,
                    nebula.log.Logger.ALERT,
                    nebula.log.Logger.CRIT,
                    nebula.log.Logger.ERR,
                    nebula.log.Logger.WARNING,
                    nebula.log.Logger.NOTICE,
                    nebula.log.Logger.INFO,
                    nebula.log.Logger.DEBUG,)

    invalid_levels = (min(valid_levels) - 1, max(valid_levels) + 1)

    def setUp(self):
        self.handle = BlackHoleLogger()

    def tearDown(self):
        pass

    def test_set_max_level(self):

        for curr_index, curr_level in enumerate(self.valid_levels):
            self.handle.set_max_level(curr_level)

            for idx, lvl in enumerate(self.valid_levels):
                result = self.handle.log(lvl, "foo")
                # check whether the message was logged or not
                if idx <= curr_index:
                    self.assertTrue(result)
                else:
                    self.assertFalse(result)

            for lvl in self.invalid_levels:
                # exception raised for invalid log level
                self.assertRaises(ValueError, self.handle.log, lvl, "foo")

        for level in self.invalid_levels:
            self.assertRaises(ValueError, self.handle.set_max_level, level)

    def test_named_methods(self):
        methods = (self.handle.emerg,
                   self.handle.alert,
                   self.handle.crit,
                   self.handle.err,
                   self.handle.warning,
                   self.handle.notice,
                   self.handle.info,
                   self.handle.debug,)

        for curr_index, curr_level in enumerate(self.valid_levels):
            self.handle.set_max_level(curr_level)
            for idx in range(len(methods)):
                if idx <= curr_index:
                    self.assertTrue(methods[idx]("foo"))
                else:
                    self.assertFalse(methods[idx]("foo"))

    def test_gmtime_timezone(self):
        for gmt, tz in ((True, True), (True, False),
                        (False, True), (False, False)):
            a_handle = BlackHoleLogger(use_gmtime = gmt, show_timezone = tz)
            self.assertEqual(gmt, a_handle.is_use_gmtime())
            self.assertEqual(tz, a_handle.is_show_timezone())

    def test_invalid_levels(self):
        for level in self.invalid_levels:
            self.assertRaises(ValueError, self.handle.log_mask, level)
            self.assertRaises(ValueError, self.handle.mask_upto, level)
            self.assertRaises(ValueError, self.handle.level_name, level)

#  -----------------------------------------------------------------------------

if __name__ == '__main__':
    unittest.main()
