#!/usr/bin/env python3

from argparse import ArgumentParser
import csv
from csv import (
        DictReader,
        DictWriter
        )
from os.path import isfile
from sys import exit
import unicodedata


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
        requirend_keys = ["Vorname", "Nachname", "E-Mail (Dienstlich)", "eindeutige Nummer (GUID)"]
    else:
        requirend_keys = ["Vorname", "Nachname", "Klasse", "Interne ID-Nummer"]
    test_user = users[0]
    if not set(requirend_keys).issubset(set(test_user.keys())):
        print("These Keys are needed: {}".format(requirend_keys))
        exit(1)

    # filter test-users, etc.
    def _is_testuser(user):
        return all(
                [
                    user["Vorname"] != '',
                    user["Nachname"] != ''
                ]
            )

    users = [user for user in filter(_is_testuser, users)]
    return users

## begin tryouts
def sanitize_username(name):
    REPLACE_MAP = {
            " ": "-",
            "ß": "ss",
            "ä": "ae",
            "ö": "oe",
            "ü": "ue",
            "æ": ""
        }
    TARGET_CHARS = "abcdefghijklmnopqrstuvwxyz0123456789._-"
    username = ''
    def _char_translate(c):
        base = unicodedata.decomposition(c).split(" ")[0].strip('0')
        return bytes.fromhex(base).decode("utf-8")
    for c in name.lower():
        if c in TARGET_CHARS:
            username += c
        elif c in REPLACE_MAP:
            username += REPLACE_MAP[c]
        else:
            username += _char_translate(c)
    return username
    # unused ....
    def _string_translate(s):
        return unicodedata.normalize('NFKD', s).encode('ascii','ignore')

def generate_mail_address(person, add_middle_name):
    '''
        take First name and surname, replaces/strips non-ascii characters
        and white spaces and returns a mailaddress.
    '''
    if args.teachers:
        length = 1
    else:
        length = len(person["Vorname"])
    raw_username = ".".join([person["Vorname"], person["Nachname"]])
    username = sanitize_username(raw_username) 
    mail_address = "{}@{}".format(
                username,
                args.domain
            ).lower()
    return mail_address


def user_to_gsuite(user, add_middle_name=False):
    '''
        converts a Schild-dict to a gsuite-dict.
    '''
    mail_address = generate_mail_address(user, add_middle_name)
    if args.teachers:
        org_unit_path = "/Lehrer"
        employee_type = "Lehrer"
        recovery_email = user["E-Mail (Dienstlich)"]
        # strip '{' and '}'
        user["Interne ID-Nummer"] = user["eindeutige Nummer (GUID)"][1:-1]
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


def fix_duplicates(gsuite_users, duplicates):
    for duplicate in duplicates:
        print("\nCONFLICTS FOUND!!")
        for num, d in enumerate(duplicate, start=1):
            print("{} - {}\t{}\t{}\t{}".format(
                    d["Employee ID"],
                    d["First Name [Required]"],
                    d["Last Name [Required]"],
                    d["Email Address [Required]"],
                    d["Org Unit Path [Required]"]
                ))
        print("... solving ...")
        for num, d in enumerate(duplicate, start=1):
            index = gsuite_users.index(d)
            mail = d["Email Address [Required]"]
            username, domain = mail.split('@')
            username += str(num)
            mail = '@'.join([username, domain])
            gsuite_users[index]["Email Address [Required]"] = mail
            # check
            user = gsuite_users[index]
            print("{} - {}\t{}\t{}\t{}".format(
                    user["Employee ID"],
                    user["First Name [Required]"],
                    user["Last Name [Required]"],
                    user["Email Address [Required]"],
                    user["Org Unit Path [Required]"]
                ))
        print('\n')

    return gsuite_users

def write_gsuite_file(users, gsuite_file):
    '''
        write a gsuite csv file.
    '''
    # get csv-filednames from first user
    fieldnames = list(users[0].keys())
    with open(gsuite_file, "w") as f:
        writer = DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(users)



if __name__ == "__main__":
    args = parser.parse_args()
    check_input_output(args)
    gsuite_users = [
                user_to_gsuite(user)
                for user in users_from_schild(args.input)
            ]
    duplicates = get_duplicate_mailadresses(gsuite_users)
    if len(duplicates) > 0:
        # fix duplicates
        gsuite_users = fix_duplicates(gsuite_users=gsuite_users, duplicates=duplicates)

    write_gsuite_file(gsuite_users, args.output)

