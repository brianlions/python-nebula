#!/usr/bin/env python3

from distutils.core import setup

VERSION = '0.1.1'

setup(
    name = 'pyNebula',
    version = VERSION,
    author = 'Brian ZHANG',
    author_email = 'brianlions@gmail.com',
    url = 'https://github.com/brianlions/python-nebula',
    license = 'GPL',

    description = 'A library for developing network applications.',
    long_description = '''\
pyNebula is a library for developing network applications.  Some of
the essential modules are:

**Asynchronous Event Handling**
  Event handling class, and wrapper classes around low level file,
  socket, and SOCKS descriptor etc.. The event handling class can
  utilize platform specific event polling API, e.g. epoll(), poll(),
  or select().

**HTTP and HTTPS**
  HTTPS support is available if the Python interpreter was compiled
  with SSL.

**Histogram**
  Classes to draw a text-based histogram.

**Logging**
  Logging module with time stamp, file name, line number, and method
  name prepended to every log message.
''',
    packages = ['nebula',
                'nebula.asyncevent',
                ],
    data_files = [
                  ['nebula', ['nebula/cacerts_ubuntu.txt']]
                  ],
    platforms = ['any'],
)
