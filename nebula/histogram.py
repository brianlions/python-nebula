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

class Histogram(object):
    __first_group = (0,
                     1, 2, 3, 4, 5)

    __basic_group = (6, 7, 8, 9, 10,
                     12, 14, 16, 18, 20,
                     25, 30, 35, 40, 45, 50)

    __first_count = (0,
                     0, 0, 0, 0, 0)

    __basic_count = (0, 0, 0, 0, 0,
                     0, 0, 0, 0, 0,
                     0, 0, 0, 0, 0, 0,)

    @classmethod
    def first_group(cls):
        return cls.__first_group[:]

    @classmethod
    def basic_group(cls):
        return cls.__basic_group[:]

    def __init__(self, bound = 500000000):
        if type(bound) != int:
            raise TypeError(bound, "value is not integer")
        if bound <= 0:
            raise ValueError(bound, "value must be positive integer")

        self.__min = None
        self.__max = None
        self.__total = 0
        self.__counter = 0

        self.__bound_list = list(self.__first_group)
        self.__count_list = list(self.__first_count)

        last_group = None
        while self.__bound_list[-1] < bound:
            if last_group is None:
                last_group = self.__basic_group[:]
                self.__bound_list.extend(last_group)
            else:
                last_group = [10 * v for v in last_group]
                self.__bound_list.extend(last_group)

            self.__count_list.extend(self.__basic_count)

    def __len__(self):
        return len(self.__bound_list)

    def min(self):
        return self.__min

    def max(self):
        return self.__max

    def total(self):
        return self.__total

    def average(self):
        if self.__counter:
            return self.__total / self.__counter
        else:
            return 0

    def add(self, v):
        if v < 0:
            raise ValueError(v, "value must not be negative")

        if (not self.__min) or (v < self.__min):
            self.__min = v
        if (not self.__max) or (v > self.__max):
            self.__max = v

        self.__total += v
        self.__counter += 1

        max_idx = len(self.__bound_list) - 1
        for idx in range(len(self.__bound_list)):
            if idx == max_idx:
                self.__count_list[-1] += 1
            elif self.__bound_list[idx] <= v < self.__bound_list[idx + 1]:
                self.__count_list[idx] += 1
                break

        return idx

    def report(self, total_marks = 100):
        if type(total_marks) != int:
            raise TypeError("value must be a positive integer")
        if not total_marks:
            raise ValueError("value must be a positive integer")

        rows = []
        rows.append("count: {:d}, min: {:d}, max: {:d}, total: {:d}, avg: {:.6f}".format(
            self.__counter, self.__min, self.__max, self.__total, self.average()))

        if not self.__counter:
            return "\n".join(rows)

        sum_percentage = 0
        for idx in range(len(self.__bound_list)):
            if not self.__count_list[idx]:
                continue

            percentage = self.__count_list[idx] * 100.0 / self.__counter
            sum_percentage += percentage
            hashes = '#' * round(self.__count_list[idx] / self.__counter * total_marks)

            if idx == len(self.__bound_list) - 1:
                row = "[{:10d}, <infinite>) {:10d} {:7.3f}, {:7.3f} {:s}".format(
                    self.__bound_list[idx],
                    self.__count_list[idx], percentage, sum_percentage, hashes)
            else:
                row = "[{:10d}, {:10d}) {:10d} {:7.3f}, {:7.3f} {:s}".format(
                    self.__bound_list[idx], self.__bound_list[idx + 1],
                    self.__count_list[idx], percentage, sum_percentage, hashes)

            rows.append(row)

        return "\n".join(rows)
