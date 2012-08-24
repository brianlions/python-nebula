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

import errno
import os
import select
import time

from .. import log as _log
from . import _error
from . import _base_dispatcher

class _SelectApiWrapper(object):
    SELECT_IN, SELECT_OUT, SELECT_ERR = 0x01, 0x02, 0x04

    def __init__(self):
        # mapping from fd to events monitored on that fd
        self._monitored = {}

    def register(self, fd, eventmask = (SELECT_IN | SELECT_OUT | SELECT_ERR)):
        '''Register a file descriptor.

        Registering a file descriptor that's already registered is NOT an error.

        Args:
          fd:        (int) file descriptor
          eventmask: (int) optional bitmask of events being waited for
        '''

        self._monitored[fd] = eventmask

    def unregister(self, fd):
        '''Remove a file descriptor being tracked.

        Raises:
          KeyError if fd was never registered.
        '''

        del self._monitored[fd]

    def modify(self, fd, eventmask):
        '''Modifies an already registered fd.

        Raises:
          IOError with errno set to ENOENT, if the fd was never registered.
        '''

        if fd not in self._monitored:
            raise IOError(errno.ENOENT)
        self._monitored[fd] = eventmask

    def poll(self, timeout = None):
        '''Polls the set of registered file descriptors for events.

        Args:
          timeout: timeout in seconds (as float), 0 to return immediately,
                   negative or None to block until at least one event was
                   fired.

        Returns:
          A possibly empty list containing (fd, event) 2-tuples for the
          descriptors that have events or errors to report.
        '''

        rd = []
        wr = []
        exp = []
        for fd, eventmask in self._monitored.items():
            if eventmask & self.SELECT_IN:
                rd.append(fd)
            if eventmask & self.SELECT_OUT:
                wr.append(fd)
            if eventmask & self.SELECT_ERR:
                exp.append(fd)

        # Negative timeout won't be accepted by select.select()!
        if (timeout is not None) and timeout < 0:
            timeout = None
        (rd, wr, exp) = select.select(rd, wr, exp, timeout)

        mapping = {}
        for fd in rd:
            mapping[fd] = self.SELECT_IN
        for fd in wr:
            if fd in mapping:
                mapping[fd] |= self.SELECT_OUT
            else:
                mapping[fd] = self.SELECT_OUT
        for fd in exp:
            if fd in mapping:
                mapping[fd] |= self.SELECT_ERR
            else:
                mapping[fd] = self.SELECT_ERR

        return [(fd, events) for (fd, events) in mapping.items()]

#------------------------------------------------------------------------------ 

class AsyncEvent(_log.WrappedLogger):
    '''Asynchronous events handling, based on Python builtin module `select'.'''

    API_DEFAULT, API_EPOLL, API_POLL, API_SELECT = 0, 1, 2, 3

    __api_names = {API_EPOLL: "epoll", API_POLL: "poll", API_SELECT: "select"}

    def __init__(self, raise_exceptions = True, api = API_DEFAULT,
                 log_handle = None):
        '''Asynchronous event loop.

        Args:
          raise_exceptions: If value of this argument is True, then attempting
                            to register() an already registered dispatcher, or
                            to unregister() a not registered dispatcher, will
                            raise an IOError exception.
          api:              Specifies the event API to be used, valid values
                            are API_DEFAULT, API_EPOLL, API_POLL, API_SELECT.
                            Note that this argument is just a hint, if the
                            specified API is not supported by the operating
                            system, this class will automatically choose an
                            API available.
          log_handle:       A log handle to be used, None to disable logging.
        '''

        _log.WrappedLogger.__init__(self, log_handle = log_handle)

        # poll object for I/O events
        if api <= self.API_EPOLL and hasattr(select, 'epoll'):
            self.__event_api_init(self.API_EPOLL)
        elif api <= self.API_POLL and hasattr(select, 'poll'):
            self.__event_api_init(self.API_POLL)
        elif api <= self.API_SELECT and hasattr(select, 'select'):
            self.__event_api_init(self.API_SELECT)
        else:
            raise ValueError("API {:d} is not supported".format(api))

        #=======================================================================
        # NOTE:
        #   This feature is NOT implemented yet!!!
        #
        # Tips:
        #   Use os.read() & os.write().
        #=======================================================================
        # pipe used by set_stop_flag() to make epoll.poll() return
        self._pipe_rd_end, self._pipe_wr_end = os.pipe()

        self.__set_nonblock_flag(self._pipe_rd_end)
        self.__set_nonblock_flag(self._pipe_wr_end)

        self.log_debug("AsyncEvent initialized, api {:s}{:s}, pipe (r {:d}, w {:d})".format(
            self.event_api_name(),
            self.event_api() == self.API_EPOLL and ", epoll_fd {:d}".format(self._pollster.fileno()) or "",
            self._pipe_rd_end, self._pipe_wr_end))

        # --- file events related ---

        # mapping from fd to dispatcher object
        self._registered_dispatchers = {}
        # mapping from fd to events monitored
        self._monitored_events = {}
        # list of monitored fds with timeout, item is 2-tuple of (timeout, fd)
        self._fds_with_timeout = []

        # --- time events related ---
        self._time_events = []

        # raise an exception in case of error
        self._raise_exceptions = raise_exceptions

        self._stop_flag = False

    def __event_api_init(self, api):
        if api == self.API_EPOLL:
            self._pollster = select.epoll()
            self._event_api = self.API_EPOLL

            self._event_in_mask = select.EPOLLIN
            self._event_pri_mask = select.EPOLLPRI
            self._event_out_mask = select.EPOLLOUT
            self._event_hup_mask = select.EPOLLHUP
            self._event_err_mask = select.EPOLLERR

        elif api == self.API_POLL:
            self._pollster = select.poll()
            self._event_api = self.API_POLL

            self._event_in_mask = select.POLLIN
            self._event_pri_mask = select.POLLPRI
            self._event_out_mask = select.POLLOUT
            self._event_hup_mask = select.POLLHUP
            self._event_err_mask = select.POLLERR

        elif api == self.API_SELECT:
            self._pollster = _SelectApiWrapper()
            self._event_api = self.API_SELECT

            self._event_in_mask = _SelectApiWrapper.SELECT_IN
            self._event_pri_mask = _SelectApiWrapper.SELECT_IN
            self._event_out_mask = _SelectApiWrapper.SELECT_OUT
            self._event_hup_mask = _SelectApiWrapper.SELECT_ERR
            self._event_err_mask = _SelectApiWrapper.SELECT_ERR

        else:
            raise ValueError("API {:d} is not supported".format(api))

    def event_api_name(self):
        "String representation of the event API used."

        return self.__api_names[self._event_api]

    def event_api(self):
        "Event API used."

        return self._event_api

    def set_stop_flag(self):
        '''Try to stop the event loop.

        Notes:
          This method may not work as expected, refer to method loop() for more
          information.
        '''

        self._stop_flag = True

    def get_stop_flag(self):
        '''Check if the stop flag was set.'''

        return self._stop_flag

    def num_of_dispatchers(self):
        '''Returns number of Dispatcher objects being monitored.'''

        return len(self._registered_dispatchers)

    def num_of_scheduled_jobs(self):
        '''Returns number of ScheduledJob scheduled.'''

        return len(self._time_events)

    def __str__(self):
        return "<%s.%s at %s {api: %s%s, pipe_rd:%d, pipe_wr:%d, dispatchers:%d, jobs:%d, stop_flag:%d}>" % \
            (self.__class__.__module__, self.__class__.__name__, hex(id(self)),
             self.event_api_name(),
             self.event_api() == self.API_EPOLL and ", epoll_fd:{:d}".format(self._pollster.fileno()) or "",
             self._pipe_rd_end, self._pipe_wr_end, self.num_of_dispatchers(),
             self.num_of_scheduled_jobs(), self._stop_flag,)

    def register(self, disp_obj):
        '''Register a dispatcher object.

        Returns:
          If registered succesfully, return True. If failed, depends on the
          value of raise_exceptions passed to __init__(), may either return
          False or raise an exception.

        Raises:
          TypeError: if the supplied object is not an instance of Dispatcher.
          IOError:   with errno EEXIST if the dispatcher was already registered.
        '''

        if not isinstance(disp_obj, _base_dispatcher.Dispatcher):
            if self._raise_exceptions:
                raise TypeError('disp_obj {:s} is not an instance of Dispatcher'.format(repr(disp_obj)))
            else:
                return False

        file_number = disp_obj.fileno()

        if file_number not in self._registered_dispatchers:
            flags = 0
            flag_names = []
            if disp_obj.monitor_readable():
                flags |= self._event_in_mask
                flag_names.append("IN")
                if self._event_in_mask != self._event_pri_mask:
                    flags |= self._event_pri_mask
                    flag_names.append("PRI")
            if disp_obj.monitor_writable():
                flags |= self._event_out_mask
                flag_names.append("OUT")

            timeout = disp_obj.monitor_timeout()

            self._pollster.register(file_number, flags)
            self.log_debug("monitored fd {:d}, flags ({:s})".format(file_number,
                " ".join(flag_names)))

            self._registered_dispatchers[file_number] = disp_obj
            # NOTE: a new entry is always created, no matter flag is 0 or not!
            self._monitored_events[file_number] = flags

            if timeout:
                self._fds_with_timeout.append((timeout, file_number))
                self.log_debug("fd {:d}, timeout event at {:s}".format(
                    file_number, _log.Logger.timestamp_str(timeout)))
            else:
                self.log_debug("fd {:d}, no timeout event".format(file_number))

            return True

        elif not self._raise_exceptions:
            return False
        else:
            raise IOError(errno.EEXIST,
                          "fd {:d} was already registered".format(disp_obj.fileno()))

    def unregister(self, disp_obj):
        '''Unregister a dispatcher object.

        Returns:
          If unregistered succesfully, return True. If failed, depends on the
          value of raise_exceptions passed to __init__(), may either return
          False or raise an exception.

        Raises:
          TypeError: if the supplied object is not an instance of Dispatcher.
          IOError:   with errno ENOENT if the dispatcher was already registered.
        '''

        if not isinstance(disp_obj, _base_dispatcher.Dispatcher):
            if self._raise_exceptions:
                raise TypeError('disp_obj {:s} is not an instance of Dispatcher'.format(repr(disp_obj)))
            else:
                return False

        file_number = disp_obj.fileno()

        if file_number in self._registered_dispatchers:
            del self._registered_dispatchers[file_number]
            del self._monitored_events[file_number]
            self.__remove_timeout_fd(file_number)
            self._pollster.unregister(file_number)
            return True
        elif not self._raise_exceptions:
            return False
        else:
            raise IOError(errno.ENOENT,
                          "fd {:d} is not registered".format(disp_obj.fileno()))

    def add_scheduled_job(self, job_obj):
        '''Schedule to execute the job in the future.

        Returns:
          Absolute time (since epoch, as float) the job will be started, or
          None if not scheduled.
        '''

        timeout = job_obj.schedule()
        if timeout:
            self._time_events.append((timeout, job_obj))
            return True
        else:
            return False

    def __set_nonblock_flag(self, fd):
        '''Set O_NONBLOCK flag for the supplied file descriptor.

        Returns:
          True if set, False otherwise.

        Notes:
          Not supported on Windows.
        '''

        try:
            import fcntl

            flags = fcntl.fcntl(fd, fcntl.F_GETFL)
            if flags < 0:
                return False

            flags = fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
            if flags:
                return False

            return True
        except IOError as err:
            self.log_notice("fcntl() failed setting O_NONBLOCK on fd {:d}, exception {:s}".format(fd, err))
            return False
        except ImportError:
            return False

    def __process_fired_events(self, fd, flags):
        disp_obj = self._registered_dispatchers[fd]

        try:
            # We need to check if fd is in self._registered_dispatchers, 'cause
            # those `handle_*' methods might remove `disp_obj' from the
            # AsyncEvent instance (viz. self) used here.

            # 1st: PRI event
            if (self._event_pri_mask != self._event_in_mask) \
            and (flags & self._event_pri_mask) \
            and (fd in self._registered_dispatchers):
                disp_obj.handle_expt_event(self)

            # 2nd: IN event
            if (flags & self._event_in_mask) \
            and (fd in self._registered_dispatchers):
                disp_obj.handle_read_event(self)

            # 3rd: OUT event
            if (flags & self._event_out_mask) \
            and (fd in self._registered_dispatchers):
                disp_obj.handle_write_event(self)

            # 4th: HUP and ERR event
            if (flags & (self._event_hup_mask | self._event_err_mask)) \
            and (fd in self._registered_dispatchers):
                disp_obj.handle_close(self)
        except (_error.ExitNow, KeyboardInterrupt, SystemExit):
            raise
        except Exception as e:
            disp_obj.handle_error(self, e)

    def __loop_step(self):
        nearest_timeout = -1

        now = time.time()

        if len(self._fds_with_timeout):
            self.__sort_timeout_fds()
            nt = self._fds_with_timeout[0][0] - now

            if nt <= 0: # already timed out
                nearest_timeout = 0
            else: # not timed out yet
                if (nearest_timeout < 0) or (nt < nearest_timeout):
                    nearest_timeout = nt

        if len(self._time_events):
            self.__sort_time_events()
            nt = self._time_events[0][0] - now

            if nt <= 0: # already timed out
                nearest_timeout = 0
            else: # not timed out yet
                if (nearest_timeout < 0) or (nt < nearest_timeout):
                    nearest_timeout = nt

        try:
            # NOTE:
            #  select.poll() requires the timeout be specified in milliseconds,
            #  but select.epoll() and select.select() require it specified in
            #  seconds (as float).
            if nearest_timeout \
            and (self.event_api() == self.API_POLL) \
            and (nearest_timeout > 0):
                nearest_timeout = int(nearest_timeout * 1000)
            result = self._pollster.poll(nearest_timeout)
        except (select.error, IOError) as err:
            if err.args[0] != errno.EINTR:
                raise
            result = []

        if len(result):
            for fd, flags in result:
                if self.get_log_handle():
                    flag_names = []
                    if flags & self._event_in_mask:
                        flag_names.append("IN")
                    if flags & self._event_out_mask:
                        flag_names.append("OUT")
                    if (flags & self._event_pri_mask) \
                    and (self._event_pri_mask != self._event_in_mask):
                        flag_names.append("PRI")
                    if (flags & self._event_hup_mask) \
                    and (self._event_hup_mask != self._event_err_mask):
                        flag_names.append("HUP")
                    if flags & self._event_err_mask:
                        flag_names.append("ERR")
                    self.log_debug("events fired, fd {:d}, flags ({:s})".format(
                        fd, " ".join(flag_names)))

                self.__process_fired_events(fd, flags)
                self.__update_associated_events(fd)
        else:
            now = time.time()

            # handle timeout events of file descriptors
            for (timeout, fd) in self._fds_with_timeout:
                if timeout > now:
                    break
                del self._fds_with_timeout[0]

                self._registered_dispatchers[fd].handle_timeout_event(self)
                self.__update_associated_events(fd)

            # handle scheduled jobs
            # TODO: it seems strange to deleting items from iterable while iterating
            for (timeout, job_obj) in self._time_events:
                if timeout > now:
                    break
                del self._time_events[0]
                job_obj.handle_job_event(self)
                new_timeout = job_obj.schedule()
                if new_timeout:
                    self._time_events.append((new_timeout, job_obj))

    def __sort_timeout_fds(self):
        self._fds_with_timeout = sorted(self._fds_with_timeout,
                                        key = lambda item: item[0])

    def __sort_time_events(self):
        self._time_events = sorted(self._time_events,
                                   key = lambda item: item[0])

    def __remove_timeout_fd(self, fd):
        for (idx, (unused_timeout, a_fd)) in enumerate(self._fds_with_timeout):
            if fd == a_fd:
                del self._fds_with_timeout[idx]
                # assume there's no duplicated fd in self._fds_with_timeout[]
                break

    def __update_associated_events(self, fd):
        if fd not in self._registered_dispatchers:
            return

        self.__remove_timeout_fd(fd)

        disp_obj = self._registered_dispatchers[fd]

        flags = 0
        flag_names = []
        if disp_obj.monitor_readable():
            flags |= self._event_in_mask
            flag_names.append("IN")
            if self._event_in_mask != self._event_pri_mask:
                flags |= self._event_pri_mask
                flag_names.append("PRI")
        if disp_obj.monitor_writable():
            flags |= self._event_out_mask
            flag_names.append("OUT")

        if self._monitored_events[fd] != flags:
            self.log_debug("modifying fd {:d}, flags {:d} -> {:d} ({:s})".format(
                fd, self._monitored_events[fd], flags, " ".join(flag_names)))
            self._pollster.modify(fd, flags)
            self._monitored_events[fd] = flags
        else:
            self.log_debug("monitored fd {:d}, flags ({:s})".format(fd,
                " ".join(flag_names)))

        timeout = disp_obj.monitor_timeout()
        if timeout:
            self._fds_with_timeout.append((timeout, fd))
            self.log_debug("fd {:d}, timeout event at {:s}".format(fd,
                _log.Logger.timestamp_str(timeout)))
        else:
            self.log_debug("fd {:d}, no timeout event".format(fd))

    def loop(self):
        '''Starts the event loop

        Event loop will terminate if no Dispatcher or ScheduledJob is available.

        NOTES (or TODOs):
          Sometimes this method might not terminate as you expected, because we
          might be blocked in the call of poll().
        '''

        self.log_notice("starting {:s}".format(self))

        while (not self.get_stop_flag()) \
        and (self.num_of_dispatchers() or self.num_of_scheduled_jobs()):
            self.__loop_step()

        self.log_notice("finishing {:s}".format(self))
