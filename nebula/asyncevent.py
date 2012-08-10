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

'''Basic infrastructure for asynchronous event handling.
'''

import errno
import fcntl
import os
import select
import resource
import socket
import sys
import time

# import our own module
from . import debug_info
from . import log

#  -----------------------------------------------------------------------------

def maximize_total_fds():
    '''
    Maximize the total number of opened file descriptors allowed.
    '''

    try:
        (soft, hard) = resource.getrlimit(resource.RLIMIT_NOFILE)
        if soft is not hard:
            resource.setrlimit(resource.RLIMIT_NOFILE, (hard, hard))
    except:
        pass

# AUTOMATICALLY maximize the total number of files allowed to be opened by this
# process.
maximize_total_fds()

#  -----------------------------------------------------------------------------

class Error(Exception):
    pass

class ExitNow(Exception):
    pass

#  -----------------------------------------------------------------------------

class Dispatcher(log.WrappedLogger):
    '''Wrapper around lower level file (or socket) descriptor object.

    This class turns a file (or socket) descriptor into a non-blocking object,
    and when certain low level events fired, the asynchronous loop will detect
    it and calls corresponding handler methods to handle it.
    '''

    def __init__(self, log_handle = None):
        log.WrappedLogger.__init__(self, log_handle)

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
            unused_nil, exp_type, exp_value, exp_traceback = debug_info.compact_traceback()
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

        self.log_info("close, dispatcher {:s}".format(self))
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

class ScheduledJob(log.WrappedLogger):
    '''Base class of scheduled job.'''

    def __init__(self, log_handle = None):
        log.WrappedLogger.__init__(self, log_handle = log_handle)

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

#  -----------------------------------------------------------------------------

class AsyncEvent(log.WrappedLogger):
    '''
    Asynchronous events handling, based on select.epoll().
    '''

    def __init__(self, raise_exceptions = True, log_handle = None):
        '''
        If raise_exceptions is True, raise an exception when failed registering or unregistering new Dispatcher object.
        '''

        log.WrappedLogger.__init__(self, log_handle = log_handle)

        # poll object for I/O events
        self._pollster = select.epoll()

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
        # XXX: do we really needed to set this flag for self._pipe_wr_end?
        self.__set_nonblock_flag(self._pipe_wr_end)
        self.log_warning("@@@@@ FEATURE NEEDS IMPLEMENTATION! neither pipe_rd {:d} nor pipe_wr {:d} is used! @@@@@".format(
            self._pipe_rd_end, self._pipe_wr_end))

        self.log_debug("AsyncEvent instance initialized, epoll_fd {:d}, pipe_rd {:d}, pipe_wr {:d}".format(
            self._pollster.fileno(), self._pipe_rd_end, self._pipe_wr_end))

        # ----- file events related --------------------------------------------

        # mapping from fd to dispatcher object
        self._registered_dispatchers = {}
        # mapping from fd to events monitored
        self._monitored_events = {}
        # list of monitored fds with timeout, every item is a tuple of (timeout, fd)
        self._fds_with_timeout = []

        # ----- time events related --------------------------------------------
        self._time_events = []

        # instead of returning an error code, raise an exception in case of error
        self._raise_exceptions = raise_exceptions

        self._stop_flag = False

    def set_stop_flag(self):
        '''
        Try to stop the event loop.

        Notes:
          This method may not work as expected, refer to method loop() for more information.
        '''

        self._stop_flag = True

    def get_stop_flag(self):
        return self._stop_flag

    def num_of_dispatchers(self):
        '''
        Returns number of Dispatcher objects being monitored by this AsyncEvent instance.
        '''

        return len(self._registered_dispatchers)

    def num_of_scheduled_jobs(self):
        '''
        Returns number of ScheduledJob objects being monitored by this AsyncEvent instance.
        '''
        return len(self._time_events)

    def __str__(self):
        return "<%s.%s at %s {epoll_fd:%d, pipe_rd:%d, pipe_wr:%d, dispatchers:%d, jobs:%d, stop_flag:%d}>" % \
            (self.__class__.__module__, self.__class__.__name__, hex(id(self)),
             self._pollster and self._pollster.fileno() or -1,
             self._pipe_rd_end,
             self._pipe_wr_end,
             self.num_of_dispatchers(),
             self.num_of_scheduled_jobs(),
             self._stop_flag
             )

    def register(self, disp_obj):
        if not isinstance(disp_obj, Dispatcher):
            if self._raise_exceptions:
                raise TypeError('disp_obj {:s} is not an instance of Dispatcher'.format(repr(disp_obj)))
            else:
                return False

        file_number = disp_obj.fileno()

        if file_number not in self._registered_dispatchers:
            flags = 0
            flag_names = []
            if disp_obj.monitor_readable():
                flags |= select.EPOLLIN | select.EPOLLPRI
                flag_names.extend(("EPOLLIN", "EPOLLPRI"))
            if disp_obj.monitor_writable():
                flags |= select.EPOLLOUT
                flag_names.append("EPOLLOUT")

            timeout = disp_obj.monitor_timeout()

            self._pollster.register(file_number, flags)
            self.log_debug("monitored fd %d, flags %d (%s)" % (file_number, flags, " ".join(flag_names)))

            self._registered_dispatchers[file_number] = disp_obj
            # NOTE: a new entry is always created, no matter flag is 0 or not!
            self._monitored_events[file_number] = flags

            if timeout:
                self._fds_with_timeout.append((timeout, file_number))
                self.log_debug("fd %d, timeout event at %s" % (file_number, log.Logger.timestamp_str(timeout)))
            else:
                self.log_debug("fd %d, no timeout event" % file_number)

            return True

        elif not self._raise_exceptions:
            return False
        else:
            raise ValueError("fd %d was already registered" % disp_obj.fileno())

    def unregister(self, disp_obj):
        if not isinstance(disp_obj, Dispatcher):
            if self._raise_exceptions:
                raise TypeError('disp_obj is not an instance of Dispatcher' % repr(disp_obj))
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
            raise ValueError("fd %d is not registered" % disp_obj.fileno())

    def add_scheduled_job(self, job_obj):
        '''
        Adds a ScheduledJob instance.

        Return the absolute time (since epoch, as float) the job will be started if successfully added, None if not added.
        '''

        timeout = job_obj.schedule()
        if timeout:
            self._time_events.append((timeout, job_obj))
            return True
        else:
            return False

    def __set_nonblock_flag(self, fd):
        '''
        Sets the O_NONBLOCK flag for the supplied file descriptor.
        '''

        try:
            flags = fcntl.fcntl(fd, fcntl.F_GETFL)
            if flags < 0:
                return False

            flags = fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
            if flags:
                return False

            return True
        except IOError as err:
            self.log_notice("fcntl() failed setting flag O_NONBLOCK, exception %s" % err)
            return False

    def __process_fired_events(self, fd, flags):
        disp_obj = self._registered_dispatchers[fd]

        try:
            # we need to check whether fd is in self._registered_dispatchers or not, because those `handle_*' methods
            # might remove `disp_obj' from the AsyncEvent instance (viz. self) used here.
            if (flags & select.EPOLLIN) and (fd in self._registered_dispatchers):
                self.log_debug("fd %d, calling handle_read_event()" % fd)
                disp_obj.handle_read_event(self)

            if (flags & select.EPOLLOUT) and (fd in self._registered_dispatchers):
                self.log_debug("fd %d, calling handle_write_event()" % fd)
                disp_obj.handle_write_event(self)

            if (flags & select.EPOLLPRI) and (fd in self._registered_dispatchers):
                self.log_debug("fd %d, calling handle_expt_event()" % fd)
                disp_obj.handle_expt_event(self)

            if (flags & (select.EPOLLHUP | select.EPOLLERR)) and (fd in self._registered_dispatchers):
                self.log_debug("fd %d, calling handle_close()" % fd)
                disp_obj.handle_close(self)
        except (ExitNow, KeyboardInterrupt, SystemExit):
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
            result = self._pollster.poll(timeout = nearest_timeout)
        except (select.error, IOError) as err:
            if err.args[0] != errno.EINTR:
                raise
            self.log_info("interrupted, errno %s" % errno.errorcode[err.args[0]])
            result = []

        if len(result):
            for fd, flags in result:
                if self.get_log_handle():
                    flag_names = []
                    if flags & select.EPOLLIN:
                        flag_names.append("EPOLLIN")
                    if flags & select.EPOLLOUT:
                        flag_names.append("EPOLLOUT")
                    if flags & select.EPOLLPRI:
                        flag_names.append("EPOLLPRI")
                    if flags & select.EPOLLHUP:
                        flag_names.append("EPOLLHUP")
                    if flags & select.EPOLLERR:
                        flag_names.append("EPOLLERR")
                    self.log_debug("events fired, fd %d, flags %d (%s)" % (fd, flags, " ".join(flag_names)))

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
            for (timeout, job_obj) in self._time_events:
                if timeout > now:
                    break
                del self._time_events[0]
                job_obj.handle_job_event(self)
                new_timeout = job_obj.schedule()
                if new_timeout:
                    self._time_events.append((new_timeout, job_obj))

    @classmethod
    def __compare_timeout(cls, va, vb):
        delta = va - vb
        if delta < 0:
            return -1
        elif delta == 0:
            return 0
        else:
            return 1

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
                # we assume that there will be no duplicated fd in self._fds_with_timeout[]
                break

    def __update_associated_events(self, fd):
        if fd not in self._registered_dispatchers:
            return

        self.__remove_timeout_fd(fd)

        disp_obj = self._registered_dispatchers[fd]

        flags = 0
        flag_names = []
        if disp_obj.monitor_readable():
            flags |= select.EPOLLIN | select.EPOLLPRI
            flag_names.extend(("EPOLLIN", "EPOLLPRI"))
        if disp_obj.monitor_writable():
            flags |= select.EPOLLOUT
            flag_names.append("EPOLLOUT")

        if self._monitored_events[fd] != flags:
            self.log_debug("modifying fd %d, flags %d -> %d (%s)" % (fd,
                                                                     self._monitored_events[fd],
                                                                     flags,
                                                                     " ".join(flag_names)))
            self._pollster.modify(fd, flags)
            self._monitored_events[fd] = flags
        else:
            self.log_debug("monitored fd %d, flags %d (%s)" % (fd, flags, " ".join(flag_names)))

        timeout = disp_obj.monitor_timeout()
        if timeout:
            self._fds_with_timeout.append((timeout, fd))
            self.log_debug("fd %d, timeout event at %s" % (fd, log.Logger.timestamp_str(timeout)))
        else:
            self.log_debug("fd %d, no timeout event" % fd)

    def loop(self):
        '''
        Starts the event loop, returns immediately if no Dispatcher or TimeEvents object was being monitored.

        Notes and TODOs:
          Sometimes this method might not return as you expected, because we might be blocked in the call to epoll.poll().
          So this issue should be fixed.
        '''

        self.log_notice("starting %s" % self)
        while (not self.get_stop_flag()) and (self.num_of_dispatchers() or self.num_of_scheduled_jobs()):
            self.__loop_step()
        self.log_notice("finishing %s" % self)

#  -----------------------------------------------------------------------------

class _SocketDispatcher(Dispatcher):
    __socket_family_names = {
                             socket.AF_INET:  "AF_INET",
                             socket.AF_INET6: "AF_INET6",
                             socket.AF_UNIX:  "AF_UNIX",
                             }

    __socket_type_names = {
                           socket.SOCK_STREAM: "SOCK_STREAM",
                           socket.SOCK_DGRAM:  "SOCK_DGRAM",
                           }

    def __init__(self, sock = None, log_handle = None):
        Dispatcher.__init__(self, log_handle = log_handle)
        self._sock = sock
        if sock:
            self.__so_family, self.__so_type = sock.family, sock.type
        else:
            self.__so_family, self.__so_type = None, None
        self.__local_addr = None

    def local_addr(self):
        return self.__local_addr

    def set_local_addr(self, addr):
        self.__local_addr = addr

    def local_addr_repr(self):
        if (not self.__local_addr) or (not self.__so_family):
            return "not_available"
        else:
            if self.__so_family == socket.AF_INET:
                return "{:s}:{:d}".format(self.__local_addr[0], self.__local_addr[1])
            elif self.__so_family == socket.AF_INET6:
                return "[{:s}]:{:d}".format(self.__local_addr[0], self.__local_addr[1])
            else:
                return "unknown_type"

    def peer_addr_repr(self):
        raise NotImplementedError("{:s}.{:s}: peer_addr_repr() not implemented".format(
            self.__class__.__module__, self.__class__.__name__))

    def is_connected(self):
        raise NotImplementedError("{:s}.{:s}: is_connected() not implemented".format(
            self.__class__.__module__, self.__class__.__name__))

    def fileno(self):
        '''File descriptor of the underlying socket object.'''

        return self._sock.fileno()

    def close(self):
        self._sock.close()
        self.log_info("socket closed")

    def socket_family(self):
        return self.__so_family

    def socket_type(self):
        return self.__so_type

    def socket_family_repr(self):
        try:
            return self.__socket_family_names[self.__so_family]
        except KeyError:
            return "unknown"

    def socket_type_repr(self):
        try:
            return self.__socket_type_names[self.__so_type]
        except KeyError:
            return "unknown"

    def socket(self, so_family, so_type):
        '''
        Creates a non-blocking socket object.

        Args:
          so_family: socket.AF_INET, socket.AF_INET6, etc.
          so_type:   socket.SOCK_STREAM, socket.SOCK_DGRAM, etc.
        '''

        self.__so_family = so_family
        self.__so_type = so_type
        self._sock = socket.socket(self.__so_family, self.__so_type)
        self._sock.setblocking(0)

    def bind(self, addr, reuse_addr = False):
        '''Binds to local address.

        Args:
          addr:       local address to bind to
          reuse_addr: if True and addr[0] (viz. port number) is non-zero, set
                      socket option SO_REUSEADDR
        '''

        self.__local_addr = addr
        self.log_info("binding to local address {:s}, SO_REUSEADDR {:d}".format(
            self.local_addr_repr(), reuse_addr))
        if reuse_addr and addr[1]:
            # only if port number is not zero
            self.set_reuse_addr()
        return self._sock.bind(self.__local_addr)

    def set_reuse_addr(self):
        '''Sets socket option SO_REUSEADDR.
        '''

        try:
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        except socket.error:
            self.log_notice("failed setting option SO_REUSEADDR")

#  -----------------------------------------------------------------------------

class TcpClientDispatcher(_SocketDispatcher):
    def __init__(self, sock = None, log_handle = None):
        '''Creates a TCP client socket Dispatcher instance.

        By default the underlying socket object will NOT be created immediately.
        If a socket object is provided, use it instead of creating a new one.

        Args:
          log_handle: used to write log messages
          sock:       used to initialize the socket object used by this Dispatcher
        '''

        _SocketDispatcher.__init__(self, sock = sock, log_handle = log_handle)

        self.__connected = False
        self.__peer_addr = None
        # absolute time in seconds (as float) since the Epoch
        self.__connect_timeout_at = None

        if sock is not None:
            self._sock.setblocking(0)
            try:
                self.__peer_addr = self._sock.getpeername()
                # If the socket is not connected, then getpeername() will raise
                # an exception with ENOTCONN. So the following call (if called)
                # to getsockname() will always return the local address used.
                self.set_local_addr(self._sock.getsockname())
                self.__connected = True
            except socket.error as err:
                if err.args[0] == errno.ENOTCONN:
                    # If we got an unconnected socket
                    self.__connected = False
                else:
                    raise

    def initialize(self, peer_addr = None, connect_timeout = None,
                   local_addr = None, reuse_addr = True):
        '''Creates a non-blocking TCP socket (IPv6 is NOT supported yet).

        Args:
          peer_addr:       remote address to connect to
          connect_timeout: number of seconds (as float) to wait before aborting
                           the connection attempt
          local_addr:      local address to bind to
          reuse_addr:      whether to set socket option SO_REUSEADDR or not,
                           ignored if `local_addr' is not provied
        '''

        self.socket(socket.AF_INET, socket.SOCK_STREAM)
        if local_addr:
            self.bind(local_addr, reuse_addr)
        if peer_addr:
            self.connect(peer_addr, connect_timeout)

    def peer_addr_repr(self):
        # family of __peer_addr and local_addr() are identical
        if (not self.__peer_addr) or (not self.socket_family()):
            return "not_available"
        else:
            if self.socket_family() == socket.AF_INET:
                return "%s:%d" % (self.__peer_addr[0], self.__peer_addr[1])
            elif self.socket_family() == socket.AF_INET6:
                return "[%s]:%d" % (self.__peer_addr[0], self.__peer_addr[1])
            else:
                return "unknown_type"

    def __str__(self):
        return "<%s.%s at %s {sock_fd:%d, sock_family:%s, sock_type:%s, connected:%d, local:%s, peer:%s}>" % (
            self.__class__.__module__, self.__class__.__name__, hex(id(self)),
            self.fileno(), self.socket_family_repr(), self.socket_type_repr(),
            self.__connected, self.local_addr_repr(), self.peer_addr_repr(),)

    def is_connected(self):
        return self.__connected

    def connect(self, addr, timeout = None):
        '''Attempts to make a connection to the specified address.

        Args:
          addr:    address to connect to
          timeout: number of seconds (as float) to wait before aborting the
                   connection attempt
        '''

        # try connect to the remote server, and timeout if required
        self.__peer_addr = addr
        if timeout:
            self.__connect_timeout_at = time.time() + timeout
        err = self._sock.connect_ex(self.__peer_addr)
        if err in (errno.EWOULDBLOCK, errno.EAGAIN, errno.EALREADY, errno.EINPROGRESS):
            self.log_info("fd {:d}, connecting to {:s} in progress, errno {:s}".format(
                self.fileno(), self.peer_addr_repr(), errno.errorcode[err]))
            return err
        elif err in (0, errno.EISCONN):
            self.log_info("fd {:d}, connected to {:s}, errno {:s}".format(
                self.fileno(), self.peer_addr_repr(), errno.errorcode[err]))
            self.__connected = True
            self.set_local_addr(self._sock.getsockname())
            return err
        else:
            raise socket.error(err, errno.errorcode[err])

    def monitor_readable(self, call_user_func = True):
        # if not connected, do not wait for INPUT event
        if not self.__connected:
            return False

        if call_user_func:
            self.log_debug("calling readable()")
            return self.readable()
        else:
            return True

    def monitor_writable(self, call_user_func = True):
        # if not connected, always wait for OUTPUT event
        if not self.__connected:
            return True

        if call_user_func:
            self.log_debug("calling writable()")
            return self.writable()
        else:
            return True

    def monitor_timeout(self, call_user_func = True):
        # if not connected, and a connection timeout was specified, then wait
        # before timeout
        if not self.__connected:
            if self.__connect_timeout_at:
                self.log_info("fd {:d}, connection attempt will be aborted at {:s} unless connected".format(
                    self.fileno(), log.Logger.timestamp_str(self.__connect_timeout_at)))
            return self.__connect_timeout_at

        if call_user_func:
            return self.timeout()
        else:
            return None

    def handle_write_event(self, ae_obj, call_user_func = True):
        if not self.__connected:
            err = self._sock.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
            if err != 0:
                raise socket.error(err, errno.errorcode[err])
            self.log_info("fd {:d}, connected to {:s}".format(self.fileno(),
                                                              self.peer_addr_repr()))
            self.__connected = True
            self.set_local_addr(self._sock.getsockname())
        else:
            if call_user_func:
                self.log_debug("calling handle_write()")
                self.handle_write(ae_obj)

#  -----------------------------------------------------------------------------

class TcpServerDispatcher(_SocketDispatcher):

    def __init__(self, sock = None, log_handle = None):
        '''Creates a TCP server socket Dispatcher instance.

        By default the underlying socket object will NOT be created immediately.
        If a socket object is provided, use it instead of creating a new one.

        Args:
          log_handle: used to write log messages
          sock:       used to initialize the socket object used by this Dispatcher,
                      must be a TCP listening socket if not None!
        '''

        _SocketDispatcher.__init__(self, sock = sock, log_handle = log_handle)

        self._listen_backlog = None
        self._accepting = False

        if sock is not None:
            self._sock.setblocking(0)
            self.set_local_addr(self._sock.getsockname())

    def is_connected(self):
        return False

    def initialize(self, local_addr, reuse_addr = True,
                   listen_backlog = socket.SOMAXCONN):
        '''Creates a non-blocking TCP server socket (IPv6 is NOT supported yet).

        local_addr:
          local address to bind to
        reuse_addr:
          whether to set socket option SO_REUSEADDR or not
        listen_backlog:
          max length of the queue of pending connections
        '''

        self.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.bind(local_addr, reuse_addr)
        self.listen(listen_backlog)

    def __str__(self):
        return "<%s.%s at %s {sock_fd:%d, sock_family:%s, sock_type:%s, accepting:%d, local:%s, backlog:%s}>" % (
            self.__class__.__module__, self.__class__.__name__, hex(id(self)),
            self.fileno(), self.socket_family_repr(), self.socket_type_repr(),
            self._accepting, self.local_addr_repr(),
            self._listen_backlog and str(self._listen_backlog) or "unknown",)

    def listen(self, backlog = socket.SOMAXCONN):
        self._sock.listen(backlog)
        self._listen_backlog = backlog
        self._accepting = True
        self.log_notice("server socket is ready {:s}".format(self))

    def __new_peer_addr(self, conn_sock, conn_addr):
        if conn_sock.family == socket.AF_INET:
            return "{:s}:{:d}".format(conn_addr[0], conn_addr[1])
        elif conn_sock.family == socket.AF_INET6:
            return "[{:s}]:{:d}".format(conn_addr[0], conn_addr[1])
        else:
            return "unknown_type"

    def accept(self):
        try:
            conn_sock, conn_addr = self._sock.accept()
            self.log_info("new connection accepted, fd {:d}, peer address {:s}".format(
                conn_sock.fileno(), self.__new_peer_addr(conn_sock, conn_addr)))
            return conn_sock, conn_addr
        except TypeError as e:
            self.log_notice("caught exception TypeError: {:s}".format(e))
            return None
        except socket.error as why:
            if why.args[0] in (errno.EWOULDBLOCK, errno.EAGAIN, errno.ECONNABORTED):
                return None
            else:
                self.log_warning("caught UNEXPECTED exception socket.error: {:s}".format(e))
                raise

    def prepare_serving_client(self, conn_sock, conn_addr, ae_obj):
        self.log_notice("{:s}.{:s}: using default prepare_serving_client()".format(
            self.__class__.__module__, self.__class__.__name__))
        self.log_info("closing newly accepted connect without serving, fd {:d}, peer address {:s}".format(
            conn_sock.fileno(), str(conn_addr)))
        conn_sock.close()

    def monitor_readable(self):
        return (self._accepting and True or False)

    def monitor_writable(self):
        return False

    def timeout(self):
        return None

    # The reason we re-implement handle_read() instead of handle_read_event() is,
    # user can derive from this class, and use a customized handle_read() with
    # enhanced features (e.g. access control beased on white-list or black-list).
    # It is strange to force the user to re-implement handle_read_event().
    def handle_read(self, ae_obj):
        new_client = self.accept()
        if new_client:
            conn_sock, conn_addr = new_client[0], new_client[1]
            self.prepare_serving_client(conn_sock, conn_addr, ae_obj)
