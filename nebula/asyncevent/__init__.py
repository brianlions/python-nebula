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

'''Basic infrastructure for asynchronous event handling.'''

__all__ = [
           "maximize_total_fds",
           "Dispatcher", "ScheduledJob",
           "AsyncEvent",
           "Error", "ExitNow",
           "TcpClientDispatcher", "TcpServerDispatcher",
           ]

from ._base_dispatcher import Dispatcher, ScheduledJob
from ._asyncevent import AsyncEvent
from ._error import Error, ExitNow
from ._socket_dispatcher import TcpClientDispatcher, TcpServerDispatcher

def maximize_total_fds():
    '''
    Maximize the total number of opened file descriptors allowed.
    '''

    try:
        import resource
        (soft, hard) = resource.getrlimit(resource.RLIMIT_NOFILE)
        if soft is not hard:
            resource.setrlimit(resource.RLIMIT_NOFILE, (hard, hard))
    except ImportError:
        pass
    except:
        pass

# AUTOMATICALLY maximize the total number of files allowed to be opened by this
# process.
maximize_total_fds()
