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
import traceback
import os

class Logger(object):
    '''
    '''

    EMERG, ALERT, CRIT, ERR, WARNING, NOTICE, INFO, DEBUG = range(0, 8)

    LOG_LEVELS = frozenset((EMERG, ALERT, CRIT, ERR, WARNING, NOTICE, INFO, DEBUG))

    __level_names = {
                     EMERG:   ('eme', 'emerg'),
                     ALERT:   ('ale', 'alert'),
                     CRIT:    ('cri', 'crit'),
                     ERR:     ('err', 'err'),
                     WARNING: ('war', 'warning'),
                     NOTICE:  ('not', 'notice'),
                     INFO:    ('inf', 'info'),
                     DEBUG:   ('deb', 'debug'),
                     }

    @classmethod
    def log_mask(cls, level):
        '''Returns log mask for the specified log level.

        Args:
          level: one of the constants in Logger.LOG_LEVELS.

        Returns:
          An integer which can be passed to set_log_mask() etc.
        '''

        if level not in cls.__level_names:
            raise ValueError("invalid log level: {:d}".format(level))
        return (1 << level)

    @classmethod
    def mask_upto(cls, level):
        '''Returns log mask for all levels through level.

        Args:
          level: one of the constants in Logger.LOG_LEVELS.

        Returns:
          An integer which can be passed to set_log_mask() etc.
        '''

        if level not in cls.__level_names:
            raise ValueError("invalid log level: {:d}".format(level))
        return (1 << (level + 1)) - 1

    @classmethod
    def level_name(cls, level, abbr = False):
        '''Returns name of the specified log level.

        Args:
          level: one of the constants in Logger.LOG_LEVELS.
          abbr:  whether to use the abbreviated name or not.

        Returns:
          Human-readable string representation of the log level.'''

        if level not in cls.__level_names:
            raise ValueError("invalid log level: {:d}".format(level))
        return cls.__level_names[level][(not abbr) and 1 or 0]

    @classmethod
    def timestamp_str(cls, now = None, use_gmtime = False, show_timezone = False):
        '''Format and return current date and time.

        Args:
          now:           seconds (as float) since the unix epoch, use current
                         time stamp if value is false.
          use_gmtime:    whether to use GMT time or not.
          show_timezone: whether to display the time zone or not.

        Returns:
          String representation of date & time, the format of the returned
          value is "YYYY.mm.dd-HH:MM:SS.ssssss-ZZZ".
        '''

        if not now:
            now = time.time()

        if show_timezone:
            tz_format = use_gmtime and '-GMT' or '-%Z'
        else:
            tz_format = ''

        return time.strftime('%Y.%m.%d-%H:%M:%S' + ('.%06d' % ((now - int(now)) * 1000000)) + tz_format,
                             use_gmtime and time.gmtime(now) or time.localtime(now))

    def __init__(self, log_mask = None, use_gmtime = False, show_timezone = True):
        self.__log_mask = log_mask and log_mask or self.mask_upto(self.INFO)
        self.__use_gmtime = use_gmtime and True or False
        self.__show_timezone = show_timezone and True or False

    def set_log_mask(self, new_mask):
        '''Set log mask, and return previous log mask.

        Args:
          new_mask: the new log mask to be set to.

        Returns:
          Previous log mask (as integer).
        '''

        if new_mask < self.mask_upto(self.EMERG) or new_mask > self.mask_upto(self.DEBUG):
            raise ValueError("invalid log mask: {:d}".format(new_mask))

        old_mask = self.__log_mask
        self.__log_mask = new_mask
        return old_mask

    def set_max_level(self, max_level):
        '''Log all messages through max_level.

        Args:
          max_level: one of the constants in Logger.LOG_LEVELS.

        Returns:
          Previous log mask (as integer).
        '''

        return self.set_log_mask(Logger.mask_upto(max_level))

    def is_use_gmtime(self):
        '''Whether we are using GMT time representation of not.

        Returns:
          True if using GMT, False otherwise.
        '''

        return self.__use_gmtime

    def is_show_timezone(self):
        '''Whether we are printing the time zone of not.

        Returns:
          True if printing time zone, False otherwise.
        '''

        return self.__show_timezone

    def log(self, level, msg, use_gmtime = None, show_timezone = None,
            stack_limit = 2):
        '''Generate one log message.

        Args:
          level:         level of the message
          msg:           string message to be logged
          use_gmtime:    whether to use GMT or not, if value is None, use the
                         value passed to __init__()
          show_timezone: whether to log time zone or not, if value is None, use
                         the value passed to __init__()
          stack_limit:   passed to traceback.extract_stack(), in order to get
                         the correct file name, line number, and method name.

        Returns:
          True if the message was logged, False otherwise.
        '''

        if self.log_mask(level) & self.__log_mask:
            file_name, line_num, func_name = traceback.extract_stack(limit = stack_limit)[0][:3]
            # remove current working directory if it is prefix of the file name
            cwd = os.getcwd() + os.path.sep
            if file_name.startswith(cwd):
                file_name = '.' + os.path.sep + file_name[len(cwd):]

            if use_gmtime is None:
                use_gmtime = self.is_use_gmtime()
            if show_timezone is None:
                show_timezone = self.is_show_timezone()
            self.output_message(level, msg, file_name, line_num, func_name,
                                use_gmtime = use_gmtime,
                                show_timezone = show_timezone)
            return True
        else:
            return False

    def debug(self, msg, stack_limit = 3):
        return self.log(self.DEBUG, msg, use_gmtime = self.__use_gmtime,
                        show_timezone = self.__show_timezone,
                        stack_limit = stack_limit)

    def info(self, msg, stack_limit = 3):
        return self.log(self.INFO, msg, use_gmtime = self.__use_gmtime,
                        show_timezone = self.__show_timezone,
                        stack_limit = stack_limit)

    def notice(self, msg, stack_limit = 3):
        return self.log(self.NOTICE, msg, use_gmtime = self.__use_gmtime,
                        show_timezone = self.__show_timezone,
                        stack_limit = stack_limit)

    def warning(self, msg, stack_limit = 3):
        return self.log(self.WARNING, msg, use_gmtime = self.__use_gmtime,
                        show_timezone = self.__show_timezone,
                        stack_limit = stack_limit)

    def err(self, msg, stack_limit = 3):
        return self.log(self.ERR, msg, use_gmtime = self.__use_gmtime,
                        show_timezone = self.__show_timezone,
                        stack_limit = stack_limit)

    def crit(self, msg, stack_limit = 3):
        return self.log(self.CRIT, msg, use_gmtime = self.__use_gmtime,
                        show_timezone = self.__show_timezone,
                        stack_limit = stack_limit)

    def alert(self, msg, stack_limit = 3):
        return self.log(self.ALERT, msg, use_gmtime = self.__use_gmtime,
                        show_timezone = self.__show_timezone,
                        stack_limit = stack_limit)

    def emerg(self, msg, stack_limit = 3):
        return self.log(self.EMERG, msg, use_gmtime = self.__use_gmtime,
                        show_timezone = self.__show_timezone,
                        stack_limit = stack_limit)

    def output_message(self, level, msg, file_name, line_num, func_name,
                       use_gmtime = None, show_timezone = None):
        '''Method subclass MUST implement.

        Args:
          level:         (int)  level of the message
          msg:           (str)  message to be logged
          file_name:     (str)  in which file the message was generated
          line_num:      (int)  at which line the message was generated
          func_name:     (str)  in which method (or function) the message was
                                generated
          use_gmtime:    (bool) whether to use GMT or not
          show_timezone: (bool) whether to log the time zone or not

        Returns:
          (not required)
        '''

        raise NotImplementedError("{:s}.{:s}: output_message() not implemented".format(self.__class__.__module__,
                                                                                       self.__class__.__name__))

#-------------------------------------------------------------------------------

class ConsoleLogger(Logger):
    '''Logger which log messages to console (stdout).'''

    def __init__(self, *args, **kwargs):
        super(ConsoleLogger, self).__init__(*args, **kwargs)

    def output_message(self, level, msg, file_name, line_num, func_name,
                       use_gmtime = None, show_timezone = None):
        '''Implements the abstract method defined in parent class.'''

        if use_gmtime is None:
            use_gmtime = self.is_use_gmtime()
        if show_timezone is None:
            show_timezone = self.is_show_timezone()

        # time, log level, file name, line number, method name, log message
        print("[{:s} {:s} {:s}:{:d}:{:s}] {:s}".format(self.timestamp_str(use_gmtime, show_timezone),
                                                       self.level_name(level, abbr = True),
                                                       file_name, line_num, func_name, msg))

#-------------------------------------------------------------------------------

class WrappedLogger(object):

    def __init__(self, log_handle = None):
        self.__log_handle = None
        self.set_log_handle(log_handle)

    def set_log_handle(self, log_handle):
        '''Set new log handle to be used.
        
        Args:
          log_handle: new log handle to be used
        Returns:
          Previous log handle, value might be None.
        '''

        if (log_handle is not None) and (not isinstance(log_handle, Logger)):
            raise TypeError("log_handle {:s} is not an instance of {:s}.Logger".format(repr(log_handle),
                                                                                       self.__class__.__module__))

        prev_handle = self.__log_handle
        self.__log_handle = log_handle
        return prev_handle

    def get_log_handle(self):
        '''Get current log handle current in use.
        
        Returns:
          Current log handle in use, value might be None.
        '''
        return self.__log_handle

    def log_debug(self, msg):
        if self.__log_handle:
            self.__log_handle.debug(msg, stack_limit = 4)

    def log_info(self, msg):
        if self.__log_handle:
            self.__log_handle.info(msg, stack_limit = 4)

    def log_notice(self, msg):
        if self.__log_handle:
            self.__log_handle.notice(msg, stack_limit = 4)

    def log_warning(self, msg):
        if self.__log_handle:
            self.__log_handle.warning(msg, stack_limit = 4)

    def log_err(self, msg):
        if self.__log_handle:
            self.__log_handle.err(msg, stack_limit = 4)

    def log_crit(self, msg):
        if self.__log_handle:
            self.__log_handle.crit(msg, stack_limit = 4)

    def log_alert(self, msg):
        if self.__log_handle:
            self.__log_handle.alert(msg, stack_limit = 4)

    def log_emerg(self, msg):
        if self.__log_handle:
            self.__log_handle.emerg(msg, stack_limit = 4)

#-------------------------------------------------------------------------------

def demo():
    logger = ConsoleLogger(show_timezone = True)
    for max_level in (Logger.DEBUG, Logger.INFO, Logger.NOTICE, Logger.WARNING, Logger.ERR):
        print("max log level: %s" % Logger.level_name(max_level))
        logger.set_log_mask(Logger.mask_upto(max_level))
        for level in (Logger.DEBUG, Logger.INFO, Logger.NOTICE, Logger.WARNING, Logger.ERR):
            logger.log(level, "message level %s" % Logger.level_name(level, abbr = False))
        print()

    print("max log level: %s" % Logger.level_name(Logger.DEBUG))
    logger.set_log_mask(Logger.mask_upto(logger.DEBUG))
    logger.debug("debug()")
    logger.info("info()")
    logger.notice("notice()")
    logger.warning("wanring()")
    logger.err("err()")

if __name__ == '__main__':
    demo()
