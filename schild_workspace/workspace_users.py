from __future__ import print_function
from collections import UserDict
import pickle
import os.path
import unicodedata

from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

from .wordlist import generate_password


def sanitize_username(name):
    REPLACE_MAP = {" ": "-", "ß": "ss", "ä": "ae", "ö": "oe", "ü": "ue", "æ": ""}
    TARGET_CHARS = "abcdefghijklmnopqrstuvwxyz0123456789._-"
    username = ""

    def _char_translate(c):
        base = unicodedata.decomposition(c).split(" ")[0].strip("0")
        return bytes.fromhex(base).decode("utf-8")

    for c in name.lower():
        if c in TARGET_CHARS:
            username += c
        elif c in REPLACE_MAP:
            username += REPLACE_MAP[c]
        else:
            username += _char_translate(c)
    return username


class User(UserDict):
    def __init__(self, userdata, workspace=None):
        super().__init__(userdata)
        self.workspace = workspace

    def __repr__(self):
        output = self["primaryEmail"] + " - " + self["orgUnitPath"]
        if "externalIds" in self:
            output += " - " + self["externalIds"][0]["value"]
        return output

    @property
    def schildId(self):
        if "externalIds" in self:
            return self["externalIds"][0]["value"]
        return None

    @schildId.setter
    def schildId(self, value):
        if "externalIds" in self:
            self["externalIds"][0]["value"] = str(value)
        else:
            self["externalIds"] = [{"value": str(value), "type": "organization"}]

    def set_password(self, password):
        self["password"] = password
        print(self["primaryEmail"], password)
        return self.save()

    def generate_new_password(self):
        new_password = generate_password()
        return self.set_password(new_password)

    def is_student(self):
        return self["orgUnitPath"].startswith("/Schüler")

    def save(self):
        if self.organization:
            self.organization.update_user(self)
            return True
        else:
            print("FAILED: No organization set")
            return False

    def save(self):
        if isinstance(self.workspace, WorkspaceUsers):
            print("saving ...")
            return self.workspace.update_user(self)
        else:
            print("no workspace available...")
            return False


class WorkspaceUsers(object):
    def __init__(self, domain):
        self.domain = domain
        self.creds = self._get_credentials()
        self.users = self._get_users()

    def __str__(self):
        return "\n".join([user["primaryEmail"] for user in self.users])

    def _get_credentials(self):
        """load or request creds"""
        creds = None
        if os.path.exists("secret/token.pickle"):
            with open("secret/token.pickle", "rb") as token:
                creds = pickle.load(token)
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    "secret/credentials.json",
                    ["https://www.googleapis.com/auth/admin.directory.user"],
                )
                creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open("secret/token.pickle", "wb") as token:
                pickle.dump(creds, token)
        return creds

    def _get_users(self):
        """returns a list of all users"""
        users = []
        service = build("admin", "directory_v1", credentials=self.creds)
        request = service.users().list(
            customer="my_customer", maxResults=200, orderBy="email"
        )
        while request is not None:
            result = request.execute()
            users += result.get("users", [])
            request = service.users().list_next(request, result)
        # apply custom dicts for better console output
        return [User(user, workspace=self) for user in users]

    def get_user_by_schild_id(self, schild_id):
        result = None
        for user in self.users:
            if "externalIds" in user:
                if user["externalIds"][0]["value"] == str(schild_id):
                    # heißt im deutschen UI "Mitarbeiter-ID" und in der csv "interne ID-Nummer"
                    result = user
                    break
        return result

    def get_user_by_mail(self, mail):
        result = None
        for user in self.users:
            if user["primaryEmail"] == mail:
                result = user
                break
        return result

    def get_students_without_schild_id(self):
        result = []
        for user in self.users:
            if not "externalIds" in user and user["orgUnitPath"].startswith("/Schüler"):
                result.append(user)
        return result

    def query(self, name="", school_class=""):
        return [
            user
            for user in self.users
            if name.casefold() in user["name"]["fullName"].casefold()
            and school_class.casefold() in user["orgUnitPath"]
        ]

    def move_to_next_year(self, i_really_know_what_i_am_doing=False):
        if not i_really_know_what_i_am_doing:
            print("think again!")
            return None
        for user in self.users:
            print(user)
            update = True
            if user["orgUnitPath"].startswith("/Lehrer"):
                update = False
                print("skipping Lehrer:", user)
            elif user["orgUnitPath"].startswith("/Schüler/Ehemalige"):
                self.delete_user(user)
                update = False
                # implement deleting
            elif user["orgUnitPath"].startswith("/Schüler/Oberstufe"):
                if user["orgUnitPath"] == "/Schüler/Oberstufe/Q2":
                    user["orgUnitPath"] = "/Schüler/Ehemalige_S2"
                elif user["orgUnitPath"] == "/Schüler/Oberstufe/Q1":
                    user["orgUnitPath"] = "/Schüler/Oberstufe/Q2"
                elif user["orgUnitPath"] == "/Schüler/Oberstufe/EF":
                    user["orgUnitPath"] = "/Schüler/Oberstufe/Q1"
                else:
                    Print("\n========\nerr - who is this")
                    print(user)
                    Print("========\n")
                    update = False
            elif user["orgUnitPath"].startswith("/Schüler/10"):
                user["orgUnitPath"] = "/Schüler/Ehemalige_S1"
            elif user["orgUnitPath"].startswith("/Schüler/0"):
                jg, schoolclass = map(int, user["orgUnitPath"].split("/")[2:4])
                jg += 1
                schoolclass += 10
                user["orgUnitPath"] = f"/Schüler/{jg:02d}/{schoolclass:03d}"
            else:
                update = False
            if update:
                print(
                    "key:",
                    user["primaryEmail"],
                    "body:",
                    f"{{'orgUnitPath': '{user['orgUnitPath']}'}}",
                )
                updated_user = self.update_user(user)
                print("updated:", updated_user)
        # get a fresh userlist
        self.users = self._get_users()

    def delete_user(self, user):
        service = build("admin", "directory_v1", credentials=self.creds)
        request = service.users().delete(userKey=user["primaryEmail"])
        result = request.execute()
        return result

    def _insert_user(self, user, password):
        service = build("admin", "directory_v1", credentials=self.creds)
        # "externalIds": [{'value': '7618', 'type': 'organization'}]
        body = {
            "primaryEmail": user["primaryEmail"],
            "password": password,
            "changePasswordAtNextLogin": user[
                "changePasswordAtNextLogin"
            ],  # True or False
            "orgUnitPath": user["orgUnitPath"],
            "name": user["name"],
        }
        if "externalIds" in user:
            body["externalIds"] = user["externalIds"]
        request = service.users().insert(body=body)
        result = request.execute()
        self.users.append(User(result, workspace=self))
        # print(result)
        return User(result, workspace=self)

    def add_user(
        self,
        first_name,
        last_name,
        recoveryEmail=None,
        schild_id=None,
        password=None,
        teacher=False,
        schoolclass=None,
        changePasswordAtNextLogin=False,
    ):
        """
        add_user(
            first_name,
            last_name,
            recoveryEmail=None,
            schild_id=None,
            password=None,
            teacher=False,
            schoolclass=None,
            changePasswordAtNextLogin=False
        ):

        returns a tuple (User, password)
        """
        if not teacher and not schoolclass:
            print("you need to proivide a schoolclass for students")
            return None

        user = User({}, workspace=self)
        user["name"] = {
            "givenName": first_name,  # First Name
            "fullName": f"{first_name} {last_name}",  # Full Name
            "familyName": last_name,  # Last Name
        }
        if teacher:
            length = 1
            user["orgUnitPath"] = "/Lehrer"
            user["organizations"] = [
                {"primary": True, "customType": "", "description": "Lehrer"}
            ]
            if recoveryEmail:
                user["recoveryEmail"] = recoveryEmail
        else:
            length = len(first_name)
            if type(schoolclass) == int:
                schoolclass = str(schoolclass)
            if not schoolclass.startswith("/"):
                if len(schoolclass) < 3:
                    schoolclass = "0" + schoolclass
                schoolclass = "/Schüler/{}/{}".format(schoolclass[0:2], schoolclass)
            user["orgUnitPath"] = schoolclass
            user["organizations"] = [
                {"primary": True, "customType": "", "description": "Schüler"}
            ]
            if schild_id:
                user["externalIds"] = [
                    {"value": str(schild_id), "type": "organization"}
                ]
        raw_username = ".".join([first_name[0:length], last_name])
        username = sanitize_username(raw_username).lower()
        primaryEmail = f"{username}@{self.domain}"
        # is primaryEmail still available?
        counter = 0
        while self.get_user_by_mail(primaryEmail):
            counter += 1
            primaryEmail = f"{username}{counter}@{self.domain}"
        user["primaryEmail"] = primaryEmail
        user["changePasswordAtNextLogin"] = changePasswordAtNextLogin
        if self.get_user_by_schild_id(schild_id):
            print(
                "already exists! UPDATE! (please reload users when done. Hint: .refresh() method)"
            )
            user["primaryEmail"] = self.get_user_by_schild_id(schild_id)["primaryEmail"]
            return self.update_user(user), None
        if not password:
            password = generate_password()
        return self._insert_user(user, password), password

    def add_user_interactive(self):
        print("is teacher? [n]/y\n > ", end="")
        _input = input()
        teacher = _input == "y"
        print("first name?\n > ", end="")
        first_name = input()
        print("last name?\n > ", end="")
        last_name = input()
        if teacher:
            print("recovery mail?\n > ", end="")
            recoveryEmail = input()
            return self.add_user(
                first_name=first_name,
                last_name=last_name,
                recoveryEmail=recoveryEmail,
                teacher=True,
                changePasswordAtNextLogin=True,
            )
        else:
            print("Schild ID?\n > ", end="")
            schildId = input()
            print("School class?\n > ", end="")
            schoolclass = input()
            return self.add_user(
                first_name=first_name,
                last_name=last_name,
                schild_id=schildId,
                teacher=False,
                schoolclass=schoolclass,
                changePasswordAtNextLogin=False,
            )

    def add_schild_students(
        self, schild_users, onboarding=False, write_existing_users_too=False
    ):
        requirend_keys = ["Vorname", "Nachname", "Klasse", "Interne ID-Nummer"]
        test_user = schild_users[0]
        if not set(requirend_keys).issubset(set(test_user.keys())):
            print("Err - These Keys are needed: {}".format(requirend_keys))
            return None
        amount_users = len(schild_users)
        for i, user in enumerate(schild_users):
            base_org_unit = "/Schüler"
            if onboarding:
                base_org_unit += "/onboarding"
            with open(f"passwords_{user['Klasse']}.csv", "a") as log:
                if user["Klasse"] in ["EF", "Q1", "Q2"]:
                    schoolclass = f"{base_org_unit}/Oberstufe/{user['Klasse']}"
                elif user["Klasse"] == "IPD":
                    schoolclass = f"{base_org_unit}/{user['Klasse']}"
                else:
                    schoolclass = (
                        f"{base_org_unit}/{user['Klasse'][:2]}/{user['Klasse']}"
                    )
                workspace_user, pw = self.add_user(
                    first_name=user["Vorname"],
                    last_name=user["Nachname"],
                    schild_id=user["Interne ID-Nummer"],
                    teacher=False,
                    schoolclass=schoolclass,
                )
                # default: write only new users to file
                if write_existing_users_too:
                    if not pw:
                        pw = "****"
                if pw:
                    log.write(
                        "{};{};{};{}\n".format(
                            workspace_user["name"]["givenName"],
                            workspace_user["name"]["familyName"],
                            workspace_user["primaryEmail"],
                            pw,
                        )
                    )
                print(
                    f"processing no. {i+1} / {amount_users} - {workspace_user['primaryEmail']}"
                )
        self.users = self._get_users()

    def refresh(self):
        self.users = self._get_users()

    def update_user(self, user):
        service = build("admin", "directory_v1", credentials=self.creds)
        body = {"orgUnitPath": user["orgUnitPath"], "name": user["name"]}
        if "externalIds" in user:
            body["externalIds"] = user["externalIds"]
        if "password" in user:
            body["password"] = user["password"]
        request = service.users().update(userKey=user["primaryEmail"], body=body)
        result = request.execute()
        return User(result, workspace=self)

    def get_not_agreed_users(self):
        not_agreed = [user for user in self.users if user["agreedToTerms"] == False]
        return not_agreed

    def get_former_students(self, schild_object):
        former_users = []
        active_schild_ids = [user.schildID for user in schild_object.users]
        for user in self.users:
            if user.is_student():
                if not user.schildId in active_schild_ids:
                    former_users.append(user)
        return former_users


if __name__ == "__main__":
    print("this is a module")
