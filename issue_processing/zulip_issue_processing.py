# new zulip issue processing

"""
This file is able to extract Zulip issue data from json files.
"""

# import argparse
# import httplib
import json
import os
import sys
# import urllib
from datetime import datetime, timedelta
import hashlib
import base64

import operator
from codeface.cli import log
from codeface.cluster.idManager import idManager
from codeface.configuration import Configuration
from codeface.dbmanager import DBManager
from dateutil import parser as dateparser
from datetime import datetime

from csv_writer import csv_writer

# datetime format string
datetime_format = "%Y-%m-%d %H:%M:%S"

def run():
    # get data from zulip api calls . then format it and apply to codeface extraction
    # get all needed paths and arguments for the method call.
    parser = argparse.ArgumentParser(prog='codeface-extraction-issues-zulip', description='Codeface extraction')
    parser.add_argument('-c', '--config', help="Codeface configuration file", default='codeface.conf')
    parser.add_argument('-p', '--project', help="Project configuration file", required=True)
    parser.add_argument('resdir', help="Directory to store analysis results in")

    # parse arguments
    args = parser.parse_args(sys.argv[1:])
    __codeface_conf, __project_conf = map(os.path.abspath, (args.config, args.project))

    # create configuration
    __conf = Configuration.load(__codeface_conf, __project_conf)

    # get source and results folders
    __srcdir = os.path.abspath(os.path.join(args.resdir, __conf['repo'] + "_issues"))
    __resdir = os.path.abspath(os.path.join(args.resdir, __conf['project'], __conf["tagging"]))

    # run processing of issue data:
    # 1) load the list of issues
    issues = load(__srcdir)
    # 2) update missing colums
    issues = update(issues)
    # 3) re-format the issues
    issues = reformat_issues(issues)
    # 5) update user data with Codeface database and dump username-to-name/e-mail list
    issues = insert_user_data(issues, __conf, __resdir)
    # 6) dump result to disk
    print_to_disk(issues, __resdir)

    log.info("Zulip issue processing complete!")



def load(source_folder):
    """Load issues from disk.

    :param source_folder: the folder where to find 'issues.json'
    :return: the loaded issue data
    """

    srcfile = os.path.join(source_folder, "issues.json")
    log.devinfo("Loading Github issues from file '{}'...".format(srcfile))

    # check if file exists and exit early if not
    if not os.path.exists(srcfile):
        log.error("Zulip issue file '{}' does not exist! Exiting early...".format(srcfile))
        sys.exit(-1)

    with open(srcfile) as issues_file:
        issue_data = json.load(issues_file)

    return issue_data

#UPDATED    
def format_time(time):
    """
    Format times from different sources to a consistent time format

    :param time: the time that shall be formatted
    :return: the formatted time
    """

    # empty time would be formatted to current date
    if time == "" or time is None:
        return ""
    else:
        d = datetime.fromtimestamp(time)
        return d.strftime(datetime_format)


def subtract_seconds_from_time(time, seconds):
    """
    Subtract the specified number of seconds from a date string

    :param time: the date string to subtract the specified seconds from
    :param seconds: the number of seconds to subtract from the date string
    :return: the date string after subtracting the specified number of seconds
    """

    new_time = datetime.strptime(time, datetime_format) - timedelta(seconds = seconds)
    return new_time.strftime(datetime_format)


def create_user(name, username, email):
    """
    Creates a user object with all needed information

    :param name: the name the user shall have
    :param username: the username the user shall have
    :param email:  the email the user shall have
    :return: the created user object
    """

    if name is None:
        name = ""
    if username is None:
        username = ""
    if email is None:
        email = ""

    user = dict()
    user["name"] = name
    user["username"] = username
    user["email"] = email

    return user


def create_deleted_user():
    """
    Creates a user object for a deleted user (ghost user)

    :return: the created user object for a deleted user
    """

    return create_user("Deleted user", "ghost", "ghost@github.com")


def lookup_user(user_dict, user):
    """
    Alters a user object in the case that name or email are missing by the corresponding name and email
    from a given user dictionary

    :param user_dict: the user dictionary
    :param user: the user object to lookup in the dictionary
    :return: the altered user object in case of a lookup
             or the unaltered user object otherwise
    """

    # if user is None, replace it by a deleted user
    if user is None:
        user = create_deleted_user()

    if (user["name"] == "" or user["name"] is None or
        user["email"] is None or user["email"] == ""):

        # lookup user only if username is not None and not empty
        if not user["username"] is None and not user["username"] == "":
            user = user_dict[user["username"]]

    return user


def update_user_dict(user_dict, user):
    """
    Adds or updates users to merge GitHub usernames and names and e-mail addresses originating from the git repository

    :param user_dict: the user dictionary
    :param user: the user object to add to or update in the dictionary
    :return: the updated user dictionary
    """

    # if the given user is None, use the deleted user instead
    if user is None:
        user = create_deleted_user()

    if not user["username"] in user_dict.keys():
        if not user["username"] is None and not user["username"] == "":
            user_dict[user["username"]] = user
    else:
        user_in_dict = user_dict[user["username"]]
        if user_in_dict["name"] is None or user_in_dict["name"] == "":
            user_in_dict["name"] = user["name"]
        if user_in_dict["email"] is None or user_in_dict["email"] == "":
            user_in_dict["email"] = user["email"]
        user_dict[user["username"]] = user_in_dict

    return user_dict

def discussion_id_update(issue_data):
    """
    :param issue_data: 
    """
    # Group timestamps by discussion_topic
    grouped = {}

    for item in issue_data:
        topic = item["discusssion_topic"]
        if topic not in grouped:
            grouped[topic] = []
        grouped[topic].append(item)

    # Process each topic group
    for topic, messages in grouped.items():

        # 1. Sort messages by timestamp ASC
        messages.sort(key=lambda m: m["timestamp"])

        # 2. Add sequential discussion_id suffix (#1, #2, #3...)
        for idx, msg in enumerate(messages, start=1):
            msg["discussion_id"] = f'{msg["discussion_id"]}#{idx}'

    return issue_data

def discussion_begin_end_add(issue_data):
    """
    :param issue_data: the issue data where  discussion_begin and discussion_end time is to be added
    :return: the updated data
    """
    # Group timestamps by discussion_topic
    discussion_topics = {}

    for item in issue_data:
        d_topic = item["discussion_topic"]
        ts = item["timestamp"]

        if d_topic not in discussion_topics:
            discussion_topics[d_topic] = []
        discussion_topics[d_topic].append(ts)

    # Compute begin and end for each discussion
    discussion_bounds = {
        d_topic: {
            "discussion_begin": min(times),
            "discussion_end": max(times)
        }
        for d_topic, times in discussion_topics.items()
    }

    # Add begin/end back to each entry
    for item in issue_data:
        d_topic = item["discussion_topic"]
        item["discussion_begin"] = discussion_bounds[d_topic]["discussion_begin"]
        item["discussion_end"] = discussion_bounds[d_topic]["discussion_end"]

    return issue_data

def update(issue_data):
    """
    updates values in the issue data structure as per requirement.
    :params: issue_data: the issue data to be updated.x
    :return: returns the issue data.
    """
    issue_data = discussion_id_update(issue_data)
    issue_data = discussion_begin_end_add(issue_data)

    return issue_data

def reformat_issues(issue_data):
    """
    Re-arrange issue data structure.

    :param issue_data: the issue data to re-arrange
    :return: the re-arranged issue data
    """

    log.devinfo("Re-arranging Github issues...")

    # re-process all issues
    for issue in issue_data:

        # empty container for issue types
        issue["type"] = []

        # empty container for issue resolutions
        issue["resolution"] = []

        # TO DO: Are these column names needed? though they will be empty
        # if an issue has no eventsList, an empty List gets created
        if issue["eventsList"] is None:
            issue["eventsList"] = []

        # if an issue has no commentsList, an empty List gets created
        if issue["commentsList"] is None:
            issue["commentsList"] = []

        # if an issue has no relatedCommits, an empty List gets created
        if issue["relatedCommits"] is None:
            issue["relatedCommits"] = []

        # if an issue has no reviewsList, an empty Listgets created
        if issue["reviewsList"] is None:
            issue["reviewsList"] = []

        # if an issue has no relatedIssues, an empty List gets created
        if "relatedIssues" not in issue:
            issue["relatedIssues"] = []

        # add "closed_at" information if not present yet
        # if issue["closed_at"] is None:
        #     issue["closed_at"] = ""

        # parses the creation time in the correct format
        # issue["created_at"] = format_time(issue["created_at"])

        # parses the close time in the correct format
        # issue["closed_at"] = format_time(issue["closed_at"])

        issue["discussion_begin"] = format_time(issue["discussion_begin"])

        # parses the close time in the correct format
        issue["discussion_end"] = format_time(issue["discussion_end"])

        # checks if the issue is a pull-request or a normal issue and adapts the type
        issue["type"].append("issue")

    return issue_data




def insert_user_data(issues, conf, resdir):
    """
    Insert user data into database and update issue data.
    In addition, dump username-to-user list to file.

    :param issues: the issues to retrieve user data from
    :param conf: the project configuration
    :param resdir: the directory in which the username-to-user-list should be dumped
    :return: the updated issue data
    """

    log.info("Syncing users with ID service...")

    # create buffer for users (key: user id)
    user_buffer = dict()
    # create buffer for user ids (key: user string)
    user_id_buffer = dict()
    # create buffer for usernames (key: username)
    username_id_buffer = dict()
    # open database connection
    dbm = DBManager(conf)
    # open ID-service connection
    idservice = idManager(dbm, conf)

    def get_user_string(name, email):
        if not email or email is None:
            return "{name}".format(name=name)
            # return "{name} <{name}@default.com>".format(name=name)  # for debugging only
        else:
            return "{name} <{email}>".format(name=name, email=email)

    def get_id_and_update_user(user, buffer_db_ids=user_id_buffer, buffer_usernames=username_id_buffer):
        username = unicode(user["username"]).encode("utf-8")

        # fix encoding for name and e-mail address
        if user["name"] is not None:
            name = unicode(user["name"]).encode("utf-8")
        else:
            name = username
        mail = unicode(user["email"]).encode("utf-8")
        # construct string for ID service and send query
        user_string = get_user_string(name, mail)

        # check buffer to reduce amount of DB queries
        if user_string in buffer_db_ids:
            log.devinfo("Returning person id for user '{}' from buffer.".format(user_string))
            if username is not None:
                buffer_usernames[username] = buffer_db_ids[user_string]
            return buffer_db_ids[user_string]

        # get person information from ID service
        log.devinfo("Passing user '{}' to ID service.".format(user_string))
        idx = idservice.getPersonID(user_string)

        # add user information to buffer
        # user_string = get_user_string(user["name"], user["email"]) # update for
        buffer_db_ids[user_string] = idx

        # add id to username buffer
        if username is not None:
            buffer_usernames[username] = idx

        return idx

    def get_user_from_id(idx, buffer_db=user_buffer):

        # check whether user information is in buffer to reduce amount of DB queries
        if idx in buffer_db:
            log.devinfo("Returning user '{}' from buffer.".format(idx))
            return buffer_db[idx]

        # get person information from ID service
        log.devinfo("Passing user id '{}' to ID service.".format(idx))
        person = idservice.getPersonFromDB(idx)
        user = dict()
        user["email"] = person["email1"]  # column "email1"
        user["name"] = person["name"]  # column "name"
        user["id"] = person["id"]  # column "id"

        # add user information to buffer
        buffer_db[idx] = user

        return user


    # check and update database for all occurring users
    for issue in issues:
        # check database for issue author
        issue["user"] = get_id_and_update_user(issue["user"])

        # check database for event authors
        for event in issue["eventsList"]:
            event["user"] = get_id_and_update_user(event["user"])

            # check database for the reference-target user if needed
            if event["ref_target"] != "":
                event["ref_target"] = get_id_and_update_user(event["ref_target"])

    # get all users after database updates having been performed
    for issue in issues:
        # get issue author
        issue["user"] = get_user_from_id(issue["user"])

        # get event authors
        for event in issue["eventsList"]:
            event["user"] = get_user_from_id(event["user"])

            # get the reference-target user if needed
            if event["ref_target"] != "":
                event["ref_target"] = get_user_from_id(event["ref_target"])
                event["event_info_1"] = event["ref_target"]["name"]
                event["event_info_2"] = event["ref_target"]["email"]

    # dump username, name, and e-mail to file
    lines = []
    for username in username_id_buffer:
        user = get_user_from_id(username_id_buffer[username])
        lines.append((
            # username,
            user["name"],
            user["email"]
        ))

    log.info("Dump username list to file...")
    username_dump = os.path.join(resdir, "usernames.list")
    csv_writer.write_to_csv(username_dump, sorted(set(lines), key=lambda line: line[0]))

    return issues


def print_to_disk(issues, results_folder):
    """
    Print issues to file "issues-github.list" in the results folder.

    :param issues: the issues to dump
    :param results_folder: the folder where to place "issues-github.list" output file
    """

    # construct path to output file
    output_file = os.path.join(results_folder, "issues-github.list")
    log.info("Dumping output in file '{}'...".format(output_file))

    # construct lines of output
    lines = []
    for issue in issues:
        for event in issue["eventsList"]:
            lines.append((
                issue["number"],
                issue["title"],
                json.dumps(issue["type"]),
                issue["state_new"],
                json.dumps(issue["resolution"]),
                issue["created_at"],
                issue["closed_at"],
                json.dumps([]),  # components
                event["event"],
                event["user"]["name"],
                event["user"]["email"],
                event["created_at"],
                event["event_info_1"],
                json.dumps(event["event_info_2"])
            ))

    # write to output file
    csv_writer.write_to_csv(output_file, sorted(set(lines), key=lambda line: lines.index(line)))

