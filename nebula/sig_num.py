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

import signal

class SignalNumbers(object):
    # mapping, signal number -> signal name
    __sig_names = dict((
                        (sig_num, sig_name)
                        for (sig_name, sig_num) in signal.__dict__.items()
                        if (sig_name.startswith('SIG')
                            and ('_' not in sig_name)
                            and type(sig_num) == int)
                        ))

    @classmethod
    def signal_name(cls, signum, exception = True):
        try:
            return "{:s}".format(cls.__sig_names[signum])
        except KeyError:
            if exception:
                raise KeyError(signum, "unknown signal number")
            return "unknown signal number {:d}".format(signum)

    def items(self):
        '''Yields pair of (sig_num, sig_name) of available signals on this system.
        '''

        for (sig_num, sig_name) in self.__sig_names.items():
            yield (sig_num, sig_name)

#  -----------------------------------------------------------------------------

def main():
    for num, name in SignalNumbers().items():
        print("{:d}\t{:s}".format(num, name))

if __name__ == '__main__':
    main()
