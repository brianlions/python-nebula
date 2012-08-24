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

from .. import debug_info as _debug_info
from .. import log as _log

class Dispatcher(_log.WrappedLogger):
    '''Wrapper around lower level file (or socket) descriptor object.

    This class turns a file (or socket) descriptor into a non-blocking object,
    and when certain low level events fired, the asynchronous loop will detect
    it and calls corresponding handler methods to handle it.
    '''

    def __init__(self, log_handle = None):
        _log.WrappedLogger.__init__(self, log_handle)

    # 1. helper methods, implement these methods in derived classes

    def fileno(self):
        '''Returns file descriptor of the open file (or socket).

        NOTES:
          Subclass must override this method.
        '''

        raise NotImplementedError("{:s}.{:s}: fileno() not implemented".format(
            self.__class__.__module__, self.__class__.__name__))

    def close(self):
        '''Closes the underlying file descriptor (or socket).

        NOTES:
          Subclass must override this method.
        '''

        raise NotImplementedError("{:s}.{:s}: close() not implemented".format(
            self.__class__.__module__, self.__class__.__name__))

    # 2. predicate for AsyncEvent, implement these methods in derived classes

    def readable(self):
        '''Determine whether read event on the underlying fd should be waited.

        At the beginning of each round of the asynchronous loop, this method
        will be called.
        '''

        self.log_notice("{:s}.{:s}: using default readable()".format(
            self.__class__.__module__, self.__class__.__name__))
        return True

    def writable(self):
        '''Determine whether write event on the underlying fd should be waited.

        At the beginning of each round of the asynchronous loop, this method
        will be called.
        '''

        self.log_notice("{:s}.{:s}: using default writable()".format(
            self.__class__.__module__, self.__class__.__name__))
        return True

    def timeout(self):
        '''Determine whether timeout event on the underlying fd should be waited.

        At the beginning of each round of the asynchronous loop, this method
        will be called.

        Returns:
          time in seconds (as float) since the Epoch, if interested in timeout
          event; either None or 0, if not interested in timeout event.
        '''

        self.log_notice("{:s}.{:s}: using default timeout()".format(
            self.__class__.__module__, self.__class__.__name__))
        return None

    # 3. methods used for handling of events, implement these methods in derived
    #    classes

    def handle_read(self, ae_obj):
        '''Called when the underlying fd is readable.

        Args:
          ae_obj: the AsyncEvent object this Dispatcher was associated with.
        '''

        self.log_notice("{:s}.{:s}: using default handle_read()".format(
            self.__class__.__module__, self.__class__.__name__))

    def handle_write(self, ae_obj):
        '''Called when the underlying fd is writable.

        Args:
          ae_obj: the AsyncEvent object this Dispatcher was associated with.
        '''

        self.log_notice("{:s}.{:s}: using default handle_write()".format(
            self.__class__.__module__, self.__class__.__name__))

    def handle_timeout(self, ae_obj):
        '''Called when the underlying fd is timed out.

        Args:
          ae_obj: the AsyncEvent object this Dispatcher was associated with.
        '''

        self.log_notice("{:s}.{:s}: using default handle_timeout()".format(
            self.__class__.__module__, self.__class__.__name__))

    def handle_expt(self, ae_obj):
        '''Called when there's out of band (OOB) data for the underlying fd.

        Args:
          ae_obj: the AsyncEvent object this Dispatcher was associated with.
        '''

        self.log_notice("{:s}.{:s}: using default handle_expt()".format(
            self.__class__.__module__, self.__class__.__name__))

    def handle_error(self, ae_obj, exception_obj):
        '''Called when an exception was raised and not handled.

        This default version prints a traceback, then calls `handle_close()',
        in order to dissociate the underlying fd from the AsyncEvent object and
        closes it.

        Args:
          ae_obj: the AsyncEvent object this Dispatcher was associated with.

        NOTES:
          1. there's NO accompanying method `handle_error_event()';
          2. this method calls handle_close()!
          3. Subclass (e.g. D) may do necessary cleanup, and use the `super()'
             method to call this method:
             e.g.
               >>> class Derived(Dispatcher):
               >>>   def handle_error(self, ae_obj, exception_obj):
               >>>      ...
               >>>      # do something
               >>>      ...
               >>>      super(Derived, self).handle_error(ae_obj, exception_obj)
        '''

        if exception_obj:
            unused_nil, exp_type, exp_value, exp_traceback = _debug_info.compact_traceback()
            self.log_notice('error, exception {:s} (type: {:s}, callstack: {:s}), fd {:d}, ae {:s}'.format(
                exp_value, exp_type, exp_traceback, self.fileno(), ae_obj))
        else:
            self.log_notice('error, fd {:d}, ae {:s}'.format(self.fileno(), ae_obj))
        self.handle_close(ae_obj)

    def handle_close(self, ae_obj):
        '''Called when the underlying fd was closed.

        Args:
          ae_obj: the AsyncEvent object this Dispatcher was associated with.

        NOTES:
          1. there's NO accompanying method `handle_close_event()';
          2. this method closes the underlying fd, after dissociate it from
             `ae_obj';
          3. Subclass (e.g. D) may do necessary cleanup, and use the `super()'
             method to call this method:
             e.g.
               >>> class Derived(Dispatcher):
               >>>   def handle_close(self, ae_obj):
               >>>      ...
               >>>      # do something
               >>>      ...
               >>>      super(Derived, self).handle_close(ae_obj)
        '''

        if ae_obj:
            self.log_info("unregister, dispatcher {:s}, ae {:s}".format(self, ae_obj))
            ae_obj.unregister(self)

        self.close()

    # 4. Following methods are called by AsyncEvent directly. These methods are
    #    used when implementing higher level dispatcher classes, in order to do
    #    more sophisticated preparation (e.g. asynchronous TCP connection, SOCKS
    #    connection, etc.), before passing control to thos user implemented
    #    methods, e.g. handle_read(), handle_write(), readable(), writable() etc.

    def handle_read_event(self, ae_obj, call_user_func = True):
        if call_user_func:
            self.handle_read(ae_obj)

    def handle_write_event(self, ae_obj, call_user_func = True):
        if call_user_func:
            self.handle_write(ae_obj)

    def handle_timeout_event(self, ae_obj, call_user_func = True):
        if call_user_func:
            self.handle_timeout(ae_obj)

    def handle_expt_event(self, ae_obj, call_user_func = True):
        if call_user_func:
            self.handle_expt(ae_obj)

    def monitor_readable(self, call_user_func = True):
        if call_user_func:
            return self.readable()
        else:
            return True

    def monitor_writable(self, call_user_func = True):
        if call_user_func:
            return self.writable()
        else:
            return True

    def monitor_timeout(self, call_user_func = True):
        if call_user_func:
            return self.timeout()
        else:
            return None

#  -----------------------------------------------------------------------------

class ScheduledJob(_log.WrappedLogger):
    '''Base class of scheduled job.'''

    def __init__(self, log_handle = None):
        _log.WrappedLogger.__init__(self, log_handle = log_handle)

    # implement these two methods in derived classes

    def schedule(self):
        '''Determine whether we need to schedule this job in the future or not.

        Returns:
          Time in seconds (as float) since the Epoch; or None or 0, if this job
          no longer need to be scheduled in the future.
        '''

        self.log_notice("{:s}.{:s}: schedule() not implement".format(
            self.__class__.__module__, self.__class__.__name__))
        return None

    def handle_job_event(self, ae_obj):
        '''Called to handle the job event.'''

        self.log_notice("{:s}.{:s}: using default handle_timeout()".format(
            self.__class__.__module__, self.__class__.__name__))
