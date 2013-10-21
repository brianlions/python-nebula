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

import os
import sys
import traceback

def callstack(multiline = False, indent = ''):
    '''Return a string representation of current call stack.

    Args:
      multiline: whether to use a single line string or a multiline string
      indent:    indent lines if multiline is True

    Returns:
      String representation of current thread (or process)'s call stack.
    '''

    stacks = traceback.extract_stack()
    stacks = stacks[:-1] # remove last item, this function
    cwd = os.getcwd() + os.path.sep

    list_str = []
    for (file_name, line_num, func_name, unused_text) in stacks:
        if file_name.startswith(cwd):
            file_name = '.' + os.path.sep + file_name[len(cwd):]
        list_str.append('{:s}:{:d}:{:s}'.format(file_name, line_num, func_name))

    if not multiline:
        return '[' + ' -> '.join(list_str) + ']'
    else:
        if len(indent):
            return indent + ('\n' + indent).join(list_str)
        else:
            return '\n'.join(list_str)

def compact_traceback(multiline = False, indent = ''):
    '''Return information about the most recent exception caught.

    Args:
      multiline: whether to use a single line string or a multiline string
      indent:    indent lines if multiline is True

    Returns:
      A tuple of four items:
        1st item is a tuple of three items, are the file name, line number, and
            method name, of the statement that raised the exception;
        2nd item is the type of the exception;
        3rd item is the exception;
        4th item is a string representation of the call stack.
    '''

    exp_type, exp_value, exp_traceback = sys.exc_info()
    if not exp_traceback:
        raise AssertionError("traceback does not exist")

    exp_tb_info = []

    cwd = os.getcwd() + os.path.sep
    while exp_traceback:
        co_name = exp_traceback.tb_frame.f_code.co_filename
        if co_name.startswith(cwd):
            co_name = '.' + os.path.sep + co_name[len(cwd):]
        exp_tb_info.append((
                            co_name,
                            exp_traceback.tb_frame.f_code.co_name,
                            str(exp_traceback.tb_lineno),
                            ))
        exp_traceback = exp_traceback.tb_next

    # just to be safe
    del exp_traceback

    file_name, func_name, line_num = exp_tb_info[-1]
    if not multiline:
        return (file_name, line_num, func_name), exp_type, exp_value, \
          '[' + ' -> '.join(['{:s}:{:s}:{:s}'.format(x[0], x[2], x[1]) for x in exp_tb_info]) + ']'
    else:
        if len(indent):
            return (file_name, line_num, func_name), exp_type, exp_value, \
              indent + ('\n' + indent).join(['{:s}:{:s}:{:s}'.format(x[0], x[2], x[1]) for x in exp_tb_info])
        else:
            return (file_name, line_num, func_name), exp_type, exp_value, \
              '\n'.join(['{:s}:{:s}:{:s}'.format(x[0], x[2], x[1]) for x in exp_tb_info])

def hex_dump(buf, addr_prefix = False, width = 0):
    '''Returns a HEX representation of the `buf'.

    Args:
      addr_prefix prefix each line with the offset in hex decimal if True.
      width       max number of bytes to dump on every line.

    Returns:
      The HEX representation of the buffer `buf'.
    '''

    items = []
    buf_len = len(buf)

    if width:
        for i in range(buf_len):
            if i % width == 0:
                if addr_prefix:
                    items.append('0x{:06x}'.format(i))
                    items.append(' {:02x}'.format(ord(buf[i])))
                else:
                    items.append('{:02x}'.format(ord(buf[i])))
            else:
                items.append(' {:02x}'.format(ord(buf[i])))
            if i != buf_len - 1 and i % width == width - 1:
                items.append('\n')
    else:
        for i in range(buf_len):
            items.append('{:s}{:02x}'.format(i and ' ' or '', ord(buf[i])))

    return ''.join(items)

#===============================================================================
# testing and demonstration
#===============================================================================

def _test_outer_func():
    _test_a()

def _test_a():
    _test_b()

def _test_b():
    _test_c()

def _test_c():
    _test_inner_func()

def _test_inner_func():
    print("--- call stack (one line):\n`%s'" % callstack(multiline = False, indent = '\t'))
    print("--- call stack (multi-line):\n`%s'" % callstack(multiline = True, indent = '\t'))
    raise ValueError('exception for testing purpose')

def test():
    try:
        _test_outer_func()
    except:
        unused_nil, exp_type, exp_value, exp_trace = compact_traceback(multiline = False, indent = '\t')
        print("--- traceback type: %s, value: %s, trace (one line):\n`%s'" % (exp_type, exp_value, exp_trace))
        unused_nil, exp_type, exp_value, exp_trace = compact_traceback(multiline = True, indent = '\t')
        print("--- traceback type: %s, value: %s, trace (multi-line):\n`%s'" % (exp_type, exp_value, exp_trace))

    s = '\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f' + ' abc 123'
    print("--- hex_dump:\n%s" % hex_dump(s, addr_prefix = False, width = 0))
    print("--- hex_dump:\n%s" % hex_dump(s, addr_prefix = True, width = 0))
    print("--- hex_dump:\n%s" % hex_dump(s, addr_prefix = False, width = 12))
    print("--- hex_dump:\n%s" % hex_dump(s, addr_prefix = True, width = 12))
    print("--- hex_dump:\n%s" % hex_dump(s, addr_prefix = False, width = 16))
    print("--- hex_dump:\n%s" % hex_dump(s, addr_prefix = True, width = 16))

if __name__ == '__main__':
    test()
