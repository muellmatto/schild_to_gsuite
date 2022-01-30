from csv import (
        DictReader,
        )
from os.path import isfile


class SchildUser(dict):
    def __repr__(self):
        return f"{self['Vorname']} {self['Nachname']} - {self['Klasse']} - {self['Interne ID-Nummer']}"
    @property
    def schildID(self):
        return self['Interne ID-Nummer']


class SchildUsers(object):

    def __init__(self, schild_file=None, teachers=False):
        self.users = []
        self.teachers = teachers
        self.schild_file = schild_file
        if schild_file:
            self.users = self._users_from_schild()

    def _users_from_schild(self) -> list:
        '''
            takes a SCHILD text-file (csv) and returns a list of dicts.
            The keys are taken from the first csv-row.
        '''
        if not self.schild_file:
            print("load schild file first")
            return None
        if not isfile(self.schild_file):
            print(f"{self.schild_file} does not exist!")
            return None
        self.users = []
        with open(self.schild_file, mode = "r", encoding = "utf-8-sig" ) as f:
            reader = DictReader(f, dialect = "excel", delimiter = ';')
            users = list(reader)
        # Check if Schildfile is sufficient
        if self.teachers:
            requirend_keys = ["Vorname", "Nachname", "E-Mail (Dienstlich)", "eindeutige Nummer (GUID)"]
        else:
            requirend_keys = ["Vorname", "Nachname", "Klasse", "Interne ID-Nummer"]
        test_user = users[0]
        if not set(requirend_keys).issubset(set(test_user.keys())):
            print("Err - These Keys are needed: {}\nmake sure to use ; as delimiter".format(requirend_keys))
            return None

        # filter test-users, etc.
        def _is_testuser(user):
            return all(
                    [
                        user["Vorname"] != '',
                        user["Nachname"] != ''
                    ]
                )

        return [SchildUser(user) for user in filter(_is_testuser, users)]


    def find_users(self, string):
        for i, user in enumerate(self.users):
            if f"{user['Vorname']} {user['Nachname']}".casefold().find(string) >= 0:
                yield i, user

