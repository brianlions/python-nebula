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
import socket
import time

from .. import log as _log
from . import _base_dispatcher

#------------------------------------------------------------------------------ 

class _SocketDispatcher(_base_dispatcher.Dispatcher):
    __socket_family_names = {
                             socket.AF_INET:  "AF_INET",
                             socket.AF_INET6: "AF_INET6",
                             }

    __socket_type_names = {
                           socket.SOCK_STREAM: "SOCK_STREAM",
                           socket.SOCK_DGRAM:  "SOCK_DGRAM",
                           }

    def __init__(self, sock = None, log_handle = None):
        _base_dispatcher.Dispatcher.__init__(self, log_handle = log_handle)
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
        '''Creates a non-blocking socket object.

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
        '''Sets socket option SO_REUSEADDR.'''

        try:
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        except socket.error:
            self.log_notice("failed setting option SO_REUSEADDR")

#------------------------------------------------------------------------------ 

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
            self.__connected, self.local_addr_repr(), self.peer_addr_repr(),
            )

    def is_connected(self):
        return self.__connected

    def connect(self, addr, timeout = None):
        '''Attempts to make a connection to the specified address.

        Args:
          addr:    address to connect to
          timeout: number of seconds (as float) to wait before aborting the
                   connection attempt

        NOTES:
          Beware that if the supplied `addr' is a domain name instead of an IP,
          then this method will use DNS to lookup the host IP, which might block
          the calling thread for a while.
        '''

        # try connect to the remote server, and timeout if required
        self.__peer_addr = addr
        err = self._sock.connect_ex(self.__peer_addr)
        if timeout:
            self.__connect_timeout_at = time.time() + timeout
        if err in (errno.EWOULDBLOCK, errno.EAGAIN, errno.EALREADY, errno.EINPROGRESS):
            self.log_info("fd {:d}, connecting to {:s}, errno {:s}".format(
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
            return self.readable()
        else:
            return True

    def monitor_writable(self, call_user_func = True):
        # if not connected, always wait for OUTPUT event
        if not self.__connected:
            return True

        if call_user_func:
            return self.writable()
        else:
            return True

    def monitor_timeout(self, call_user_func = True):
        # if not connected, and a connection timeout was specified, then wait
        # before timeout
        if not self.__connected:
            if self.__connect_timeout_at:
                self.log_info("fd {:d}, connection attempt will be aborted at {:s}".format(
                    self.fileno(), _log.Logger.timestamp_str(self.__connect_timeout_at)))
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
                self.handle_write(ae_obj)

    def handle_timeout_event(self, ae_obj, call_user_func = True):
        '''Generates a log message if the connect attempt timed out.

        Notes:
          It is the derived class' responsibility to decide what to do when the
          connect attempt failed.
        '''
        if self.__connect_timeout_at and not self.__connected:
            self.log_info("fd {:d}, connection to {:s} timedout".format(
                self.fileno(), self.peer_addr_repr()))
        if call_user_func:
            self.handle_timeout(ae_obj)

#------------------------------------------------------------------------------ 

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
