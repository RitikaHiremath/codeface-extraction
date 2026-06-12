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
This file merges different commits.list files and issues_github.list files from different projects.
"""
# coding=utf-8
import os
import re
import csv
import argparse
import subprocess
import sys
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
    parser.add_argument( "--gitauthority", required= True, help = "path to the cloned gitauthoirty")
    args = parser.parse_args()
 
    files = ["commits.list","issues-github.list","bots.list"]
    for file in files:
        # extract data
        all_data = extract_data_per_project(args.projects, args.resdir, file)
        # merge and update the issue content
        merged_data = merge_data(all_data,file)
        # if merged_data is None:
        #     continue
        # save merged issues
        save_merged(merged_data, args.resdir, args.output, file)
        log.info(f"{file} data successfully merged!")
    # extracts all usernames.list and authors.list to a single user_data
    user_data = extract_user_data(args.projects, args.resdir)
    # save user_data to users.list in the output directory
    output_dir = os.path.join(os.path.abspath(args.resdir), args.output, "proximity")
    os.makedirs(output_dir, exist_ok=True)
    users_list_path = os.path.join(output_dir, "users.list")
    with open(users_list_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerows(user_data)
    log.info(f"Saved users.list to {users_list_path}")

    # save combined authors.list (id;name;email) for post-GitAuthority dedup
    authors_data = extract_authors_for_list(args.projects, args.resdir)
    authors_list_path = os.path.join(output_dir, "authors.list")
    with open(authors_list_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerows(authors_data)
    log.info(f"Saved authors.list to {authors_list_path}")

    # run gitauthority and save the csv file
    run_gitauthority(args.gitauthority, output_dir, args.output)

    # update saved files("commits.list","issues-github.list","bots.list", "authors.list") and resave them
    update(output_dir, args.output)


def extract_data_per_project(project_list, dir,type_data):
    """
    Extracts each (issues-github.list or commits.list) data from each project and appends to all issues
    """
    all_data = {}
    for project in project_list:
        # Matches the actual path for data: threemonth/<project>/proximity/type_data(commits.list, issues-github.list)
        issues_file = os.path.join(dir, project, "proximity", type_data)
        if not os.path.exists(issues_file):
            log.warning(f"File not found: {issues_file}")
            continue

        with open(issues_file, newline="", encoding="utf-8") as f:
            reader = csv.reader(f, delimiter=";")
            rows = [row for row in reader]
        all_data[project] = rows
        log.info(f"Loaded {len(rows)} rows from '{project}'")
    return all_data

def extract_user_data(project_list, dir):
    """
    extracts data from authors.list and usernames.list
    The data in all_data contains each row in the format [usernmae,name,email]
    """
    all_data = []
    author_data_files = ["authors.list","usernames.list"]
    for type_data in author_data_files:
        for project in project_list:
            # Matches the actual path for data: threemonth/<project>/proximity/type_data(commits.list, issues-github.list)
            user_file = os.path.join(dir, project, "proximity", type_data)
            if not os.path.exists(user_file):
                log.warning(f"File not found: {user_file}")
                continue

            with open(user_file, newline="", encoding="utf-8") as f:
                # [ "Hakim El Hattab", "hakim.elhattab@gmail.com", ""] for authors.list
                reader = csv.reader(f, delimiter=";")
                if type_data == "authors.list":
                    rows = [[row[1], row[2],""] for row in reader if row]
                else:
                    rows = [[row[1], row[2], row[0]] for row in reader if row]
            all_data.extend(rows)
            log.info(f"Loaded {len(rows)} rows from '{project}'")
    return all_data


def extract_authors_for_list(project_list, dir):
    """
    Collect unique (name, email) pairs from all projects' authors.list files and
    assign new sequential numeric IDs.  Returns rows as [id, name, email].
    """
    seen = {}  # (name, email) → assigned id
    for project in project_list:
        author_file = os.path.join(dir, project, "proximity", "authors.list")
        if not os.path.exists(author_file):
            log.warning(f"File not found: {author_file}")
            continue
        with open(author_file, newline="", encoding="utf-8") as f:
            reader = csv.reader(f, delimiter=";")
            for row in reader:
                if row and len(row) >= 3:
                    key = (row[1].strip(), row[2].strip())
                    if key not in seen:
                        seen[key] = len(seen) + 1
    return [[str(aid), name, email] for (name, email), aid in seen.items()]
      
def merge_data(all_data, file):
    """
    Merging data based on the file data
    """
    if file == "commits.list":
        return merge_commits(all_data)
    if file == "issues-github.list":
        return merge_issues(all_data)
    if file == "bots.list":
        return merge_bots(all_data)
    log.error("Incorrect file name!")


def run_gitauthority(script: str, dir: str, project_name: str):
    """
    Running the gitauthority script with all required files/data
    """
    script_path = Path(os.path.join(script, "gitAuthority.py"))
    input_file = os.path.join(dir, "users.list")
    Path(dir).mkdir(parents=True, exist_ok=True)
    clean_name = Path(project_name).stem 
    cmd = [sys.executable, str(script_path),
           "--file", str(input_file),
           "--name", clean_name,
           "--output-dir", str(dir),
           "--drop-boolean-column"]
    print(f"[gitauthority] Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True, cwd=str(script_path.parent))


def merge_commits(all_commits):
    """
    All commit data is taken and updated to the required format
    """
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

def merge_bots(all_bots):
    """
    Combines bots.list rows from all projects, deduplicating by entire row.
    """
    seen = set()
    merged = []
    for rows in all_bots.values():
        for row in rows:
            if not row:
                continue
            key = tuple(row)
            if key not in seen:
                seen.add(key)
                merged.append(row)
    log.info(f"Total merged bot rows: {len(merged)}")
    return merged

def parse_name_email(value):
    """
    Parse a gitAuthority identity string like:
        'Firstname Lastname <email@domain.com>'
    Returns (name, email) or (value, "") if format is unexpected.
    """
    value = value.strip().strip('"')
    match = re.match(r'^(.*?)\s*<([^>]+)>\s*$', value)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return value, ""


def parse_gitauthority_csv(rows):
    """
    Parse the gitAuthority CSV with format:
        project ; original_author_id ; dealialized_author_id

    Returns:
        identity_map : dict[(str, str), (str, str)]
        (orig_name, orig_email) → (canon_name, canon_email)
        Only contains entries where original and canonical differ.
    """
    identity_map = {}

    for row in rows:
        if len(row) < 3 or row[1].strip().strip('"') == "original_author_id":
            continue  # skip header or malformed rows

        original  = row[1].strip().strip('"')
        canonical = row[2].strip().strip('"')

        orig_name,  orig_email  = parse_name_email(original)
        canon_name, canon_email = parse_name_email(canonical)

        if orig_name != canon_name or orig_email != canon_email:
            identity_map[(orig_name, orig_email)] = (canon_name, canon_email)

    return identity_map


def update_issues_github(git_authority_csv, issues_github_rows):
    """
    Update col 9 (name) and col 10 (email) in issues-github.list
    using canonical identities from gitAuthority CSV.
    """
    identity_map = parse_gitauthority_csv(git_authority_csv)

    updated_rows  = []
    updated_count = 0

    for row in issues_github_rows:
        if not row or len(row) < 11:
            updated_rows.append(row)
            continue

        new_row = row.copy()
        canon = identity_map.get(row[9].strip().strip('"'), row[10].strip().strip('"'))
        if canon:
            new_row[9]  = canon[0]
            new_row[10] = canon[1]
            updated_count += 1

        updated_rows.append(new_row)

    log.info(f"update_issues_github: {updated_count}/{len(updated_rows)} rows updated")
    return updated_rows


def update_commits(git_authority_csv, commits_rows):
    """
    Update the two set of user data (cols 2, 3), (cols 5, 6) in commits.list
    using canonical identities from gitAuthority CSV.
    """
    identity_map = parse_gitauthority_csv(git_authority_csv)

    updated_rows  = []
    updated_count = 0

    for row in commits_rows:
        if not row or len(row) < 7:
            updated_rows.append(row)
            continue

        new_row = row.copy()

        canon = identity_map.get(row[2].strip().strip('"'), row[3].strip().strip('"'))
        if canon:
            new_row[2] = canon[0]
            new_row[3] = canon[1]
            updated_count += 1

        canon = identity_map.get(row[5].strip().strip('"'), row[6].strip().strip('"'))
        
        if canon:
            new_row[5] = canon[0]
            new_row[6] = canon[1]

        updated_rows.append(new_row)

    log.info(f"update_commits: {updated_count}/{len(updated_rows)} rows updated")
    return updated_rows

def update_bots(git_authority_csv, bots_rows):
    """
    Update the user data (cols 0, 1) in bots.list
    using canonical identities from gitAuthority CSV.
    """
    identity_map = parse_gitauthority_csv(git_authority_csv)

    updated_rows  = []
    updated_count = 0

    for row in bots_rows:
        if not row or len(row) < 7:
            updated_rows.append(row)
            continue

        new_row = row.copy()

        canon = identity_map.get(row[0].strip().strip('"'), row[1].strip().strip('"'))
        
        if canon:
            new_row[0] = canon[0]
            new_row[1] = canon[1]

        updated_rows.append(new_row)

    log.info(f"update_commits: {updated_count}/{len(updated_rows)} rows updated")
    return updated_rows

def update(output_dir, project_name):
    """
    Fetches the dealialized user data (merged_authors_{project_name}.csv).
    Checks and updates each exisiting files with this dealialized user data.
    """
    ga_filename = f"merged_authors_{project_name}.csv"
    ga_path = os.path.join(os.path.abspath(output_dir), ga_filename)
    if not os.path.exists(ga_path):
        log.error(f"gitAuthority CSV not found: {ga_path}")
        return

    with open(ga_path, newline="", encoding="utf-8") as f:
        git_authority_csv = list(csv.reader(f, delimiter=";"))

    def update_file(path, updater, label):
        """
        checks if the file exists then runs the command to update the files with dealialized user data.
        """
        if os.path.exists(path):
            with open(path, newline="", encoding="utf-8") as f:
                rows = list(csv.reader(f, delimiter=";"))
            updated = updater(git_authority_csv, rows)
            with open(path, "w", newline="", encoding="utf-8") as f:
                csv.writer(f, delimiter=";", quoting=csv.QUOTE_ALL).writerows(updated)
            log.info(f"{label} saved")
        else:
            log.warning(f"{label} not found in {output_dir}")

    update_file(os.path.join(output_dir, "issues-github.list"), update_issues_github, "issues-github.list")
    update_file(os.path.join(output_dir, "commits.list"), update_commits, "commits.list")
    update_file(os.path.join(output_dir, "bots.list"), update_bots, "bots.list")

    log.info("update complete!")
    
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
