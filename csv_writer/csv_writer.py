# coding=utf-8
# This file is part of codeface-extraction, which is free software: you
# can redistribute it and/or modify it under the terms of the GNU General
# Public License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright 2017 by Claus Hunsen <hunsen@fim.uni-passau.de>
# Copyright 2018 by Anselm Fehnker <fehnker@fim.uni-passau.de>
# Copyright 2020-2021 by Thomas Bock <bockthom@cs.uni-saarland.de>
# Copyright 2025 by Maximilian Löffler <s8maloef@stud.uni-saarland.de>
# All Rights Reserved.
"""
This file provides the needed functions for standardized CSV writing
"""

import csv


def write_to_csv(file_path, lines, append=False):
    """
    Write the given lines to the file with the given file path.

    :param file_path: The path where the file shall be written
    :param lines: The lines that shall be written in the file
    :param append: Flag if lines shall be appended to file or overwrite file
    """

    open_mode = "a" if append else "w"

    with open(file_path, mode=open_mode, encoding="utf-8") as csv_file:
        wr = csv.writer(csv_file, delimiter=';', lineterminator='\n', quoting=csv.QUOTE_NONNUMERIC)
        # encode in proper UTF-8 before writing to file
        for line in lines:
            wr.writerow(line)

def read_from_csv(file_path, delimiter=";"):
    """
    Read lines from a given csv file.

    :param file_path: The path of the file to read from
    :param delimiter: The delimiter of the columns in the csv file to read

    :return: A list containing the lines of the read file
    """
    content = csv.reader(open(file_path), delimiter=delimiter)
    return list(content)
