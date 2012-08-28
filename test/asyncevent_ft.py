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

import time
import sys

import add_nebula_path
from nebula import log
from nebula.asyncevent import AsyncEvent, TcpClientDispatcher, TcpServerDispatcher, ScheduledJob

class DemoTestClientDispatcher(TcpClientDispatcher):
    '''
    Use for testing, also for demonstration of the usage of this module.
    '''

    def __init__(self, sock = None, log_handle = None):
        TcpClientDispatcher.__init__(self, sock = sock, log_handle = log_handle)

        self.__request_data = b'''GET /tools/client_address.php HTTP/1.1\r
Host: localhost\r
Accept: text/plain, text/html\r
Accept-Encoding: deflate\r
User-Agent: AsyncEvent-test-py\r
\r
'''

        self.__response_data = b''

        self.__idle_connection = 3.0

    def readable(self):
        self.log_info("func called")
        return True

    def writable(self):
        self.log_info("len(self.__request_data): %d ```%s'''" % (len(self.__request_data), self.__request_data.decode('utf-8')))
        return len(self.__request_data) > 0

    def timeout(self):
        if len(self.__request_data):
            return None
        else:
            return time.time() + self.__idle_connection

    def handle_read(self):
        recv = self._sock.recv(4096)
        if len(recv):
            self.__response_data += recv
            self.log_info("%d bytes recv, %d bytes in total: ```%s'''" % (len(recv),
                                                                          len(self.__response_data),
                                                                          self.__response_data.decode('utf-8')))
        else:
            self.log_info("connection closed by remote node")
            self.handle_close()

    def handle_write(self):
        sent = self._sock.send(self.__request_data)
        self.__request_data = self.__request_data[sent:]
        self.log_info("%d bytes sent, %d bytes remaining" % (sent, len(self.__request_data)))

    def handle_timeout(self):
        if not self.is_connected():
            self.log_notice("connection attempt time out, closing socket ...")
            self.handle_close()
        if not len(self.__request_data):
            self.log_info("all data was sent, connection was idle for a {:.3f} sec, closing ...".format(
                self.__idle_connection))
            self.handle_close()

class DemoTestConnectedClientDispatcher(TcpClientDispatcher):
    '''
    Sent a greeting message to remote client, then close.
    '''

    def __init__(self, sock, max_idle_secs = 5.0, log_handle = None):
        TcpClientDispatcher.__init__(self, sock = sock, log_handle = log_handle)
        self._response = ("hello client %s (server %s)\n" % (self.peer_addr_repr(), self.local_addr_repr())).encode('utf-8')
        self._last_activity_time = time.time()
        self._max_idle_secs = max_idle_secs

    def readable(self):
        return False

    def writable(self):
        return len(self._response) > 0

    def timeout(self):
        return self._last_activity_time + self._max_idle_secs

    def handle_write(self):
        sent = self._sock.send(self._response)
        self.log_info("%d of %d bytes sent to client (local %s <---> peer %s)" % (sent,
                                                                                  len(self._response),
                                                                                  self.local_addr_repr(),
                                                                                  self.peer_addr_repr(),
                                                                                  ))
        self._response = self._response[sent:]
        if len(self._response) == 0:
            self.handle_close()
        else:
            self._last_activity_time = time.time()

    def handle_timeout(self):
        self.log_info("closing idle connection, no activity during last %f secs, sock_fd %d (local %s <---> peer %s)" % \
                      (self._max_idle_secs, self.fileno(), self.local_addr_repr(), self.peer_addr_repr(),)
                      )
        self.handle_close()

class DemoTestServerTimeEvent(ScheduledJob):
    def __init__(self, log_handle = None):
        ScheduledJob.__init__(self, log_handle = log_handle)

        self._count = 0
        self._max_count = 20
        self._interval_sec = 0.1

    def schedule(self):
        if self._count < self._max_count:
            self._count += 1
            return time.time() + self._interval_sec
        else:
            return None

    def handle_job_event(self):
        self.log_info("scheduled sub job %d / %d finished, interval %.3f sec" % \
                      (self._count, self._max_count, self._interval_sec))

class DemoTestAsyncEventInspect(ScheduledJob):
    def __init__(self, log_handle = None):
        ScheduledJob.__init__(self, log_handle = log_handle)

        self._count = 0
        self._max_count = 5
        self._interval_sec = 0.5

    def schedule(self):
        if self._count < self._max_count:
            self._count += 1
            return time.time() + self._interval_sec
        else:
            return None

    def handle_job_event(self):
        self.log_info("inspection %d / %d finished" % (self._count, self._max_count))

class DemoTestServerDispatcher(TcpServerDispatcher):
    '''
    Use for testing, also for demonstration of the usage of this module.
    '''

    def __init__(self, sock = None, log_handle = None):
        TcpServerDispatcher.__init__(self, sock = sock, log_handle = log_handle)

        self._total_connections = 0
        self._num_conns_recently = 0
        self._report_interval = 3
        self._max_idle_report_count = 5
        self._idle_report_count = 0

    def prepare_serving_client(self, conn_sock, conn_addr):
        self._num_conns_recently += 1
        self._total_connections += 1
        if False:
            self.log_info("closing newly accepted connect without serving, fd %d, peer address %s" % \
                          (conn_sock.fileno(), str(conn_addr)))
            conn_sock.close()
        else:
            self.pollster().register(DemoTestConnectedClientDispatcher(conn_sock, log_handle = self.get_log_handle()))

    def timeout(self):
        return time.time() + self._report_interval

    def handle_timeout(self):
        self.log_info("%s.%s handling timeout event!" % (self.__class__.__module__,
                                                         self.__class__.__name__))

        if not self._num_conns_recently:
            self._idle_report_count += 1
        else:
            self.log_info("number of recent connections %d" % self._num_conns_recently)
            self._num_conns_recently = 0
            self._idle_report_count = 0

        if self._idle_report_count == self._max_idle_report_count:
            self.log_info("closing server socket, %d connections in total" % self._total_connections)
            self.handle_close()

def test(test_name, log_level = 'info', event_api = "default"):
    '''
    Use for testing, also for demonstration of the usage of this module.
    '''

    levels = {
              'debug':   log.Logger.DEBUG,
              'info':    log.Logger.INFO,
              'notice':  log.Logger.NOTICE,
              'warning': log.Logger.WARNING,
              'err':     log.Logger.ERR,
              'crit':    log.Logger.CRIT,
              'alert':   log.Logger.ALERT,
              'emerg':   log.Logger.EMERG,
              }

    apis = {
            "default": AsyncEvent.API_DEFAULT,
            "epoll":   AsyncEvent.API_EPOLL,
            "poll":    AsyncEvent.API_POLL,
            "select":  AsyncEvent.API_SELECT,
            }

    if test_name not in ('client', 'server'):
        raise ValueError("invalid parameter `%s' (client|server)" % test_name)
    if log_level not in levels:
        raise ValueError("invalid parameter `%s' (debug|info|notice|warning|err|crit|alert|emerg)" % log_level)
    if event_api not in apis:
        raise ValueError("invalid parameter `%s' (default|epoll|poll|select)" % event_api)

    log_handle = log.ConsoleLogger(log_mask = log.Logger.mask_upto(log.Logger.NOTICE))
    log_handle.set_max_level(levels[log_level])

    ae = AsyncEvent(log_handle = log_handle, api = apis[event_api])
    if test_name == 'client':
        mc = DemoTestClientDispatcher(log_handle = log_handle)
        mc.initialize(peer_addr = ('www.example.com', 80), connect_timeout = 10.0,
                      local_addr = ('0.0.0.0', 0), reuse_addr = True)
        ae.register(mc)
    else:
        ms = DemoTestServerDispatcher(log_handle = log_handle)
        ms.initialize(local_addr = ('0.0.0.0', 8888), reuse_addr = True, listen_backlog = 5)
        ae.register(ms)

        job = DemoTestServerTimeEvent(log_handle = log_handle)
        ae.add_scheduled_job(job)

        job = DemoTestAsyncEventInspect(log_handle = log_handle)
        ae.add_scheduled_job(job)
    ae.loop()
    log_handle.notice("----- Bingo! Test finished successfully! -----")

def main():
    if len(sys.argv) not in (2, 3, 4):
        print('''\
usage: %s client|server [log_level [event_api]]
    log_level: debug, info, notice, warning, err, crit, alert, emerg
    event_api: default, epoll, poll, select
''' % sys.argv[0], file = sys.stderr)

        sys.exit(1)

    if len(sys.argv) == 2:
        test(sys.argv[1])
    elif len(sys.argv) == 3:
        test(sys.argv[1], sys.argv[2])
    else:
        test(sys.argv[1], sys.argv[2], sys.argv[3])

if __name__ == '__main__':
    main()
