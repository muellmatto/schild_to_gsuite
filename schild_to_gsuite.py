#!/usr/bin/env python3

from argparse import ArgumentParser
import csv
from csv import (
        DictReader,
        DictWriter
        )
from os.path import isfile
from sys import exit


parser = ArgumentParser(description = "takes a SCHILD-file and outputs a csv_file for gsuite")
group = parser.add_mutually_exclusive_group(required=True)
group.add_argument('-t', '--teachers', action="store_true", help="users are added as teachers")
group.add_argument('-s', '--students', action="store_true", help="users are added as students")
parser.add_argument('-p', '--password', required=True, help="Temporary, first password")
parser.add_argument('-d', '--domain', required=True, help="Domain, eg. edu.school.tld")
parser.add_argument('-i', '--input', required=True, help="SCHILD Text (csv) file")
parser.add_argument('-o', '--output', required=True, help="gsuite filename")


def check_input_output(args):
    '''Checks if input exists and output doesnt exist'''
    if not isfile(args.input):
        print(f'{args.input} does not exist')
        exit(1)

    if isfile(args.output):
        print(f"{args.output} does already exist. Choose a diffrent filename.")
        exit(1)


def users_from_schild(schild_file) -> list:
    '''
        takes a SCHILD text-file (csv) and returns a list of dicts.
        The keys are taken from the first csv-row.
    '''
    with open(schild_file, mode = "r", encoding = "utf-8-sig" ) as f:
        reader = DictReader(f, dialect = "excel", delimiter = ';')
        users = list(reader)
    # Check if Schildfile is sufficient
    if args.teachers:
        requirend_keys = ["Vorname", "Nachname", "Interne ID-Nummer", "E-Mail"]
    else:
        requirend_keys = ["Vorname", "Nachname", "Klasse", "Interne ID-Nummer"]
    test_user = users[0]
    if not set(requirend_keys).issubset(set(test_user.keys())):
        print("These Keys are needed: {}".format(requirend_keys))
        exit(1)

    return users


def generate_mail_address(person, add_middle_name):
    '''
        take First name and surname, replaces/strips non-ascii characters
        and white spaces and returns a mailadress.
    '''
    if args.teachers:
        length = 1
    else:
        length = len(person["Vorname"])
    #TODO:
    # - user unicodedata eg to sanitize names!
    # - avoid name clashes!
    return "{}.{}@{}".format(
            person["Vorname"][0:length],
                person["Nachname"],
                args.domain
            )


def user_to_gsuite(user, add_middle_name=False):
    '''
        converts a Schild-dict to a gsuite-dict.
    '''
    mail_address = generate_mail_address(user, add_middle_name)
    if args.teachers:
        org_unit_path = "/Lehrer"
        employee_type = "Lehrer"
        recovery_email = user["E-Mail"]
    else:
        klasse = user["Klasse"]
        if klasse in ["EF", "Q1", "Q2"]:
            jg = "Oberstufe"
        else:
            jg = user["Klasse"][0:2]
        org_unit_path = f"/Schüler/{jg}/{klasse}"
        employee_type = "Schüler"
        recovery_email = "" 
    return {
            "First Name [Required]": user["Vorname"],
            "Last Name [Required]": user["Nachname"],
            "Email Address [Required]": mail_address,
            "Password [Required]": args.password,
            "Org Unit Path [Required]": org_unit_path,
            "Employee ID": user["Interne ID-Nummer"],
            "Employee Type": employee_type,
            "Change Password at Next Sign-In": "true",
            "Recovery Email": recovery_email
            }


def get_duplicate_mailadresses(users):
    '''
        returns a list of users with duplicate mailaddresses 
    '''

    unique_mails = set(
            [
                u["Email Address [Required]"]
                for u in users
            ]
        )
    duplicates = []
    for mail in unique_mails:
        tmp_list = []
        for user in users:
            if user["Email Address [Required]"] == mail:
                tmp_list.append(user)
        if len(tmp_list) > 1:
            duplicates.append(tmp_list)
    return duplicates

def write_gsuite_file(users):
    pass

if __name__ == "__main__":
    args = parser.parse_args()
    check_input_output(args)
    gsuite_list = [
                user_to_gsuite(user)
                for user in users_from_schild(args.input)
            ]
    duplicates = get_duplicate_mailadresses(gsuite_list)
    if len(duplicates) > 0:
        print("CONFLICTS FOUND!!\n")
        for duplicate in duplicates:
            for d in duplicate:
                print("{} - {}\t{}\t{}\t{}".format(
                        d["Employee ID"],
                        d["First Name [Required]"],
                        d["Last Name [Required]"],
                        d["Email Address [Required]"],
                        d["Org Unit Path [Required]"]
                    ))
            print('\n')
        print("ABORT")
        exit(1)

