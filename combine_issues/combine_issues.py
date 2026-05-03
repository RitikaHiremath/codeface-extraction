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
# Copyright 2026 by Ritika Hiremath <rihi00002@stud.uni-saarland.de>
# All Rights Reserved.
"""
This file merges different issues_github.list files from different projects.
"""
# coding=utf-8
import os
import csv
import argparse
from pathlib import Path
from logging import getLogger
from codeface_utils.util import setup_logging

# create logger
setup_logging()
log = getLogger(__name__)


def run():
    parser = argparse.ArgumentParser(description="Merge issues-github.list files")
    parser.add_argument( "--resdir", required=True, help="Path to data/results/threemonth/" )
    parser.add_argument( "--projects", nargs="+", required=True, help="One or more project folder names, e.g. vue_proximity keras_proximity" )
    parser.add_argument( "--output", default="merged_issues.list", help="Output CSV file path (default: merged_issues.list)" )
    args = parser.parse_args()

    # extract issues
    all_issues = extract_issues(args.projects, args.resdir)
    # merge and update the issue content
    merged = merge_issues(all_issues)
    # save merged issues
    save_merged(merged, args.output)
    log.info("Issues successfully merged!")

def extract_issues(project_list, threemonth_dir):
    """
    Extracts each issues-github.list data from each project and appends to all issues
    """
    all_issues = {}
    for project in project_list:
        # Matches the actual path for data: threemonth/<project>/proximity/issues-github.list
        issues_file = Path(threemonth_dir) / project / "proximity" / "issues-github.list"
        if not issues_file.exists():
            log.warning(f"File not found: {issues_file}")
            continue

        with issues_file.open(newline="", encoding="utf-8") as f:
            reader = csv.reader(f, delimiter=";")
            rows = [row for row in reader]
        all_issues[project] = rows
        log.info(f"Loaded {len(rows)} rows from '{project}'")
    return all_issues

def merge_issues(all_issues):
    """
    All issues are taken and corrected to the required format
    """
    merged = []
    for project, rows in all_issues.items():
        short_name = project.replace("_proximity","")
        for row in rows:
            if not row:
                continue
            new_row = row.copy()
            # Updating firts row: 1 -> keras-1
            new_row[0] = f"{short_name}_{new_row[0]}"
            
            # Checking last row is indeed """issue""" then updating the last but one row: 3885 -> keras-3885
            last_col = new_row[13].strip().strip('"')
            issue_num = new_row[12].strip().strip('"')

            if last_col.lower() == "issue" and issue_num.isdigit():
                new_row[12] = f"{short_name}-{issue_num}"
            merged.append(new_row)
    log.info(f"Total merged rows: {len(merged)}")
    return merged

def save_merged(merged_rows, output_path):
    """
    Saves the file with the updated contents
    """
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=";", quoting=csv.QUOTE_ALL)
        writer.writerows(merged_rows)
        log.info(f"Saved to {output_path}")
