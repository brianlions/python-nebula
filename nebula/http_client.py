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

import socket
import time
import urllib.parse
import gzip, zlib
import sys
import ssl
import os.path

from ssl import (CERT_NONE, CERT_OPTIONAL, CERT_REQUIRED)

class HttpClientError(Exception):
    pass

class CommonUserAgent(object):
    '''User-Agent of some common well-known browsers.'''

    Default = 'pyNebula/0.1 Python/{:s}'.format(
                  '.'.join([str(n) for n in sys.version_info[:3]]))

    Chrome_21 = ('Mozilla/5.0 (Windows NT 5.1) AppleWebKit/537.1'
                 ' (KHTML, like Gecko) Chrome/21.0.1180.83 Safari/537.1')
    Firefox_14 = ('Mozilla/5.0 (Windows NT 5.1; rv:14.0) Gecko/20100101'
                  ' Firefox/14.0.1')
    IE_8 = ('Mozilla/4.0 (compatible; MSIE 8.0; Windows NT 5.1; Trident/4.0;'
            ' .NET CLR 2.0.50727; .NET CLR 3.0.04506.648; .NET CLR 3.5.21022;'
            ' .NET CLR 3.0.4506.2152; .NET CLR 3.5.30729)')

CA_CERTS = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "cacerts_ubuntu.txt")

class SimpleHttpClient(object):
    '''A simple HTTP client.'''

    _PROLOGUE_ENCODING = 'iso-8859-1'
    _BODY_ENCODING = 'iso-8859-1'
    _HTTP_CLIENT_VERSION = 'HTTP/1.1'
    _HTTP_PORT = 80
    _HTTPS_PORT = 443

    _DEFAULT_ADDITIONAL_HEADERS = {
        'Accept':          'text/html,text/plain;q=0.9, */*;q=0.8',
        'Accept-Encoding': 'gzip;q=0.9, deflate;q=0.5, identity;q=0.3, */*;q=0',
        'Accept-Language': 'zh-cn,zh;q=0.8, en_US;q=0.5, en;q=0.3',
        'Cache-Control':   'max-age=0',
        'Connection':      'close',
        'User-Agent':      CommonUserAgent.Default,
        }

    _REQUEST_LINE_FORMAT = "{method:s} {request_uri:s} {http_version:s}"

    _HEADER_RECV_LEN = 1024
    _CONTENT_RECV_LEN = 8192

    def __init__(self, verbose = False):
        '''Initialize an HTTP client instance.'''

        self._verbose = verbose

        self._socket = None
        # save peer info, in case it's a persistent connection (keep-alive).
        self._peer_name = ''
        self._peer_ip = ''
        self._peer_port = 0

        # request line and headers to send
        self._prologue_rows = []

        # whether SSL was used
        self._ssl_encryption = False
        # status line and headers received
        self._prologue = b''
        # http status line
        self._http_version = None
        self._status_code = None
        self._reason_phrase = None
        # header fields received
        self._response_headers = {}

        # temporary buffer used to save received raw data
        self._pending_blocks = []

        # This is the buffer used to save chunks of the response body. In order
        # to save lots of concatenation operations, we use list here instead of
        # bytes.
        # If `Transfer-Encoding' is `chunked', we have:
        #   1. chunk size indicator are removed;
        #   2. one HTTP chunk might be divied into several items;
        # If `Content-Length' is provided, we have:
        self._chunks = []

        self._shortage = 0

        # content of the web page, decompressed if compression was used while
        # transfering from remote server.
        self._contents = b''
        # content of the web page, never decompressed.
        self._raw_contents = b''

    def _reset(self):
        '''Reset all member variables, if necessary.'''

        self._prologue_rows = []

        self._ssl_encryption = False
        self._prologue = b''
        self._http_version = None
        self._status_code = None
        self._reason_phrase = None
        self._response_headers = {}

        self._pending_blocks = []
        self._chunks = []
        self._shortage = 0

        self._contents = b''
        self._raw_contents = b''

    def _get_verbose(self):
        return self._verbose

    def _set_verbose(self, value):
        self._verbose = value

    verbose = property(_get_verbose, _set_verbose, doc = 'Verbose mode or not.')

    @property
    def http_version(self):
        '''HTTP version from response line.'''
        return self._http_version

    @property
    def status_code(self):
        '''HTTP status code from response line.'''
        return self._status_code

    @property
    def reason_phrase(self):
        '''HTTP reason phrase from response line.'''
        return self._reason_phrase

    @property
    def headers(self):
        '''Dict of headers from response message.'''
        return self._response_headers.copy()

    @property
    def contents(self):
        '''Contents received from remote server, decompress if compressed.'''
        self._join_and_decompress_contents()
        return self._contents

    @property
    def raw_contents(self):
        '''Contents received from remote server, never decompressed.'''
        self._join_and_decompress_contents()
        return self._raw_contents

    def _join_and_decompress_contents(self):
        if not self._chunks:
            if (not self._contents) and (not self._raw_contents):
                return False
            else:
                return True

        if 'content-encoding' not in self._response_headers:
            self._contents = self._raw_contents = b''.join(self._chunks)
            self._chunks = []
            return False

        ce = self._response_headers['content-encoding'].lower()
        if ce in ('gzip', 'x-gzip'):
            self._raw_contents = b''.join(self._chunks)
            self._contents = gzip.decompress(self._raw_contents)
            self._chunks = []
            return True
        elif ce == 'deflate':
            self._raw_contents = b''.join(self._chunks)
            self._contents = zlib.decompress(self._raw_contents)
            self._chunks = []
            return True
        else:
            raise HttpClientError("unknown Content-Encoding `{:s}'".format(ce))

    def log_message(self, message):
        '''Generate a debug message, if verbose mode is enabled.'''

        if self._verbose:
            now = time.time()
            print("{:s}.{:06d}: {:s}".format(
                time.strftime("%Y.%m.%d-%H:%M:%S", time.localtime(now)),
                int((now - int(now)) * 1000000),
                message
                ))

    def _send_prologue(self):
        '''Send request line, and headers.'''

        self._prologue_rows.extend(("", ""))
        self._socket.sendall("\r\n".join(self._prologue_rows).encode(
            self._PROLOGUE_ENCODING))
        self.log_message("request prologue sent:\n```{:s}'''".format(
            "\r\n".join(self._prologue_rows)))

    def _parse_prologue(self):
        '''Parse status line, and headers.'''

        if not self._prologue.startswith(b'HTTP/'):
            raise HttpClientError("Invalid status line, not HTTP/x.y")

        lines = self._prologue.decode(self._PROLOGUE_ENCODING).split('\r\n')
        try:
            self._http_version, self._status_code, self._reason_phrase = \
                                lines[0].split(' ', 2)
            self._status_code = int(self._status_code)
        except ValueError:
            raise HttpClientError("invalid status line: `{:s}'".format(
                lines[0]))

        for header_line in lines[1:]:
            try:
                name, value = [t.strip() for t in header_line.split(':', 1)]
                name = name.lower()
                if name != 'set-cookie':
                    self._response_headers[name] = value
                else:
                    if 'set-cookie' in self._response_headers:
                        self._response_headers['set-cookie'].append(value)
                    else:
                        self._response_headers['set-cookie'] = [value]

            except ValueError:
                raise HttpClientError("invalid header line: `{:s}'".format(
                    header_line))

    def close(self):
        '''Close (keep-alive) connection.'''

        if self._socket:
            self._socket.close()
            self._socket = None
            self._peer_name, self._peer_ip, self._peer_port = '', '', 0

    def fetch_page(self, url, headers = {}, method = 'GET', body = None,
                   keyfile = None, certfile = None,
                   cert_reqs = CERT_NONE, ca_certs = None):
        '''Fetch the specified URL.

        Args:
          url:       resource to fetch
          headers:   user-supplied headers to send
          method:    HTTP request method to use
          body:      additional content to send
          keyfile & certfile:
                     files which contain a certificat to be used to identify
                     the local principle
          cert_reqs: whether a certificate is required from the server, three
                     valid values: ssl.CERT_NONE (default), ssl.CERT_OPTIONAL,
                     and ssl.CERT_REQUIRED
          ca_certs:  a file contains a set of concatenated "CA" certificates
        '''

        self._reset()

        # make all head field names titlecased
        customized_headers = dict([(k.title(), v) for k, v in headers.items()])

        scheme, netloc, path = urllib.parse.urlsplit(url, scheme = 'http')[0:3]
        if not netloc:
            raise HttpClientError("Malformed URL (do not forget the scheme, e.g. `http://')")
        if 'Host' not in customized_headers:
            customized_headers['Host'] = netloc
        if not path:
            request_uri = "/" + url[url.find(netloc) + len(netloc) : ]
        else:
            request_uri = url[url.find(netloc) + len(netloc) : ]

        if (not scheme) or scheme == 'http':
            self._ssl_encryption = False
            port_num = self._HTTP_PORT
        elif scheme == 'https':
            self._ssl_encryption = True
            port_num = self._HTTPS_PORT
        else:
            raise HttpClientError("Unsupported scheme `{:s}'".format(scheme))

        pos_colon = netloc.find(':')
        if pos_colon < 0:
            pass
        elif pos_colon == 0:
            raise HttpClientError("Invalid network location `{:s}'".format(netloc))
        elif pos_colon < len(netloc) - 1:
            port_num = int(netloc[pos_colon + 1 : ])
            netloc = netloc[:pos_colon]
        elif pos_colon == len(netloc) - 1:
            netloc = netloc[:pos_colon]

        # the request line
        self._prologue_rows.append(self._REQUEST_LINE_FORMAT.format(
            method = method, request_uri = request_uri,
            http_version = self._HTTP_CLIENT_VERSION))
        # make `Host:' the first header line
        self._prologue_rows.append("{:s}: {:s}".format('Host',
            customized_headers.pop('Host')))
        # other headers
        for k, v in customized_headers.items():
            self._prologue_rows.append("{:s}: {:s}".format(k, v))
        for k, v in self._DEFAULT_ADDITIONAL_HEADERS.items():
            if k not in customized_headers:
                self._prologue_rows.append("{:s}: {:s}".format(k, v))

        self.log_message("connecting to ``{:s}:{:d}''".format(netloc, port_num))

        # create a new socket, or reuse an existing one
        if (not self._socket) \
        or (netloc not in (self._peer_name, self._peer_ip)) \
        or (port_num != self._peer_port):
            self.close() # different peer node, we can not reuse the socket

            if self._ssl_encryption:
                self._socket = ssl.wrap_socket(socket.socket(),
                    keyfile = keyfile, certfile = certfile,
                    cert_reqs = cert_reqs, ca_certs = ca_certs)
            else:
                self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.connect((netloc, port_num))
            self._peer_name = netloc
            self._peer_ip, self._peer_port = self._socket.getpeername()
            self.log_message("new socket created, fd = {:d}".format(self._socket.fileno()))
        else:
            self.log_message("reuse existing socket, fd = {:d}".format(self._socket.fileno()))

        self._send_prologue()

        # now it's time to receive the response from remote server

        while True:
            # short buf to receive headers, long buf to receive contents
            delta = self._socket.recv(self._response_headers \
                                      and self._CONTENT_RECV_LEN \
                                      or self._HEADER_RECV_LEN)
            if not delta: # closed by peer node
                break

            if not self._response_headers:
                self._prologue += delta
                # search for the delimiter
                pos = self._prologue.find(b'\r\n\r\n')
                if pos < 0:
                    continue
                if pos == 0:
                    # Oops!
                    pass

                if len(self._prologue) >= pos + 4:
                    # 1. value might be empty
                    # 2. `delta' will be appended to `self._chunks' by the
                    #    code several lines after this line.
                    delta = self._prologue[pos + 4 : ]

                self._prologue = self._prologue[:pos] # ``CRLF CRLF'' discarded
                self.log_message("status line and headers:\n```{:s}'''".format(
                    self._prologue.decode(self._PROLOGUE_ENCODING)))
                self._parse_prologue()

            self._pending_blocks.append(delta)
            if self._response_headers.get('transfer-encoding', '').startswith('chunked'):
                if self._extract_all_chunks():
                    break
            elif 'content-length' in self._response_headers:
                if self._extract_all_segments():
                    break
            elif 'close' in self._response_headers.get('connection', ''):
                self._move_all_bytes()

        # close socket if it's necessary
        if 'keep-alive' in self._response_headers.get('connection', '').lower() \
        or 'keep-alive' in self._response_headers:
            self.log_message("Keep-Alive found in response, fd = {:d}".format(
                self._socket.fileno()))
        else:
            self.log_message("Keep-Alive not found in response, closing fd = {:d}".format(
                self._socket.fileno()))
            self.close()

    def _move_all_bytes(self):
        self._chunks.append(self._pending_blocks.pop())

    def _extract_all_segments(self):
        if not self._shortage:
            self._shortage = int(self._response_headers['content-length'])
        self._shortage -= len(self._pending_blocks[0])
        self._chunks.append(self._pending_blocks.pop())
        return (not self._shortage) and True or False

    def _extract_all_chunks(self):
        '''Extract chunks from the receive buffer.

        Returns:
          True:  if the last chunk was received
          False: if the last chunk was NOT received.
        '''

        # this method is called after self._pending_blocks.append(), so we are
        # sure there is at least one item in `self._pending_blocks'.
        if len(self._pending_blocks) > 1:
            self._pending_blocks = [b''.join(self._pending_blocks)]
        # now we have one and only one item in self._pending_blocks

        if self._shortage:
            l = len(self._pending_blocks[0])
            if l < self._shortage + 2:
                # incomplete chunk, 2 bytes for the CRLF
                return False
            else:
                # a complete chunk, possibly followed by several other chunks
                self._chunks.append(self._pending_blocks[0][ : self._shortage])
                self._pending_blocks[0] = self._pending_blocks[0][self._shortage + 2: ]
                self._shortage = 0

        last_chunk = False

        while (not self._shortage) and self._pending_blocks:
            pos = self._pending_blocks[0].find(b'\r\n')
            if pos < 0: # shortage of received data
                return False
            elif pos == 0: # just in case
                raise HttpClientError(
                        "got CRLF while chunk size indicator was excpected")
            else:
                # get chunk size indicator (in hex)
                self._shortage = int(self._pending_blocks[0][:pos], 16)
                # remove the size indicator
                self._pending_blocks[0] = self._pending_blocks[0][pos + 2:]

                l = len(self._pending_blocks[0])
                if l > self._shortage + 2:
                    self._chunks.append(self._pending_blocks[0][ : self._shortage])
                    self._pending_blocks[0] = self._pending_blocks[0][self._shortage + 2 : ]
                    self._shortage = 0
                    # there might be multiple chunks in `self._pending_blocks'
                elif l == self._shortage + 2:
                    if self._shortage == 0:
                        last_chunk = True # the last chunk and CRLF was received
                    self._chunks.append(self._pending_blocks.pop()[ : self._shortage])
                    self._shortage = 0
                    return last_chunk # `self._pending_blocks' is empty
                elif l < self._shortage:
                    self._chunks.append(self._pending_blocks.pop())
                    self._shortage -= l
                    return False # `self._pending_blocks' is empty
                else:
                    # l == self._shortage + 1 or l == self._shortage
                    return False # nothing to do, because `CRLF' is not found

        return False

#===============================================================================

def watch_headers(url, headers = {}, method = 'GET', body = None,
                  verbose = False):
    width_a = 20
    width_b = 10
    print("{mark:s} fetch URL: {url:s} {mark:s}".format(
        url = url, mark = '=' * width_a))

    hc = SimpleHttpClient(verbose = verbose)
    hc.fetch_page(url, headers = headers, method = method, body = body)
    print("{mark:s} request headers:\n{data:s}".format(
        mark = '>' * width_b, data = '\r\n'.join(hc._prologue_rows),
        ))
    print("{mark:s} response headers:\n{data:s}".format(
        mark = '<' * width_b, data = hc._prologue.decode(hc._PROLOGUE_ENCODING),
        ))
    print("{mark:s} response content length: {la:d} (raw {lb:d})".format(
        mark = '-' * width_b, la = len(hc.contents), lb = len(hc.raw_contents),
        ))

    return hc

def print_summary(hc):
    if not isinstance(hc, SimpleHttpClient):
        raise TypeError("not an instance of SimpleHttpClient")

    print("version:\n\t{!s}".format(hc.http_version))
    print("status:\n\t{!s}".format(hc.status_code))
    print("reason:\n\t{!s}".format(hc.reason_phrase))

    max_width = max([len(k) for k in hc.headers.keys()])
    print("headers:\n{!s}".format(
        '\n'.join(['\t{:{:d}s} {!s}'.format(k + ':', max_width + 1, v)
            for k, v in hc.headers.items()])
    ))

    print("content length:\n\t{!s}".format(len(hc.contents)))

if __name__ == '__main__':
    if 0:
        for page in ("http://localhost/", "http://localhost/phpinfo.php"):
            hc = watch_headers(page, verbose = False)
            print()
    else:
        for page in ('http://www.google.com',
                     'http://cn.bing.com',
                     'http://www.baidu.com',
                     'http://www.sina.com.cn',
                     'http://weibo.com',
                     ):
            watch_headers(page,
                          headers = {'user-agent': CommonUserAgent.Firefox_14},
                          verbose = False)
            print()
