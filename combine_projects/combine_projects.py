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
    parser.add_argument( "--output", required= True, help="Custom output directory name" )
    args = parser.parse_args()

    files = ["commits.list","issues-github.list"]
    for file in files:
        # extract data
        all_data = extract_data(args.projects, args.resdir, file)
        # merge and update the issue content
        merged_data = merge_data(all_data,file)
        # save merged issues
        save_merged(merged_data, args.resdir, args.output, file)
        log.info(f"{file} data successfully merged!")

def extract_data(project_list, threemonth_dir,type_data):
    """
    Extracts each issues-github.list data from each project and appends to all issues
    """
    all_data = {}
    for project in project_list:
        # Matches the actual path for data: threemonth/<project>/proximity/type_data(commits.list, issues-github.list)
        issues_file = os.path.join(threemonth_dir, project, "proximity", type_data)
        if not os.path.exists(issues_file):
            log.warning(f"File not found: {issues_file}")
            continue

        with open(issues_file, newline="", encoding="utf-8") as f:
            reader = csv.reader(f, delimiter=";")
            rows = [row for row in reader]
        all_data[project] = rows
        log.info(f"Loaded {len(rows)} rows from '{project}'")
    return all_data
      
def merge_data(all_data, file):
    '''
    Merging data based on the file data
    '''
    if file == "commits.list":
        return merge_commits(all_data)
    if file == "issues-github.list":
        return merge_issues(all_data)
    log.error("Incorrect file name!")


def merge_commits(all_commits):
    '''
    All commit data is taken and updated to the required format
    '''
    merged_commits = []
    for project, rows in all_commits.items():
        short_name = project.replace("_proximity","")
        for row in rows:
            if not row:
                continue
            new_row = row.copy()
            new_row[0] = f"{short_name}-{new_row[0]}"
            # update row 12 only if its not empty
            if new_row[12] != "":
                new_row[12] =f"{short_name}/{new_row[12]}"
        merged_commits.append(new_row)

    return merged_commits

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
            new_row[0] = f"{short_name}-{new_row[0]}"
            
            # Checking last row is indeed """issue""" then updating the last but one row: 3885 -> keras-3885
            last_col = new_row[13].strip().strip('"')
            # checking if the 8th Column is "connected"
            connected_col = new_row[8].strip().strip('"')
            sub_issues = new_row[7].strip().strip('"')
            issue_num = new_row[12].strip().strip('"')

            if (last_col.lower() == "issue" or connected_col.lower() == "connected" ) and issue_num.isdigit():
                new_row[12] = f"{short_name}-{issue_num}"
            
            if sub_issues and sub_issues != '[]':
                inner = sub_issues.strip('[]')
                sub_issues_list = [s.strip() for s in inner.split(',')]
                new_row[7] = str([f"{short_name}-{issue}" for issue in sub_issues_list])
            merged.append(new_row)
    log.info(f"Total merged rows: {len(merged)}")
    return merged

def save_merged(merged_rows, resdir, custom_dir, file):
    """
    Saves the merged file to a new directory alongside the input directory.
    """
    # Same directory as input directory with custom name - given by user
    output_dir = os.path.join(os.path.abspath(resdir), custom_dir, "proximity")
    os.makedirs(output_dir, exist_ok=True)

    output_path = os.path.join(output_dir, file)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=";", quoting=csv.QUOTE_ALL)
        writer.writerows(merged_rows)
    log.info(f"Saved to {output_path}")
