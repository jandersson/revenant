import struct
import re
import getpass
from telnetlib import Telnet
import npyscreen

GAME_CODE = b'DR'
# Protocol Actions - Sending to server (summary only):
# K - Server responses with Key (to encrypt password with)
# The server response, will always be 32 characters, then 0x0a
# A - This action tells the server what user/pass you're dealing with
# M - Asks the server for a list of games
# N - Asks server for game capabilities
# G - Tells the server what game you want, server responds with some details
# C - Asks the server for a list of characters specifically, other stuff included
# L - Tells the server you want to play a character, server responds with connection info
# F - (Unknown) SGE Sends it... Server response: NORMAL
# B - (Unknown) zMUD Sends it... Server response: UNKNOWN
# P - (Unknown) SGE Sends it w/ gamecode.. Server response: ?God knows what?


class LoginError(Exception):
    def __init__(self, message):
        super().__init__(message)


class EAccessClient:
    # TODO: consider subclassing Telnet
    def __init__(self, host='eaccess.play.net', port=7900):
        self.host = host
        self.port = port
        self.client = Telnet()

    def connect(self):
        self.client.open(self.host, self.port)

    def a_action(self, credentials):
        """Inform the server of the user/pass, return what appears to be a login key?"""
        hashed_password = self.encrypt_password(credentials['password'], credentials['hashkey'])
        self.client.write(b'A\t' + credentials['username'] + b'\t' + hashed_password + b'\n')
        a_response = self.client.read_until(b'\n').decode()
        if 'PASSWORD' in a_response:
            raise LoginError('Bad Password')
        elif 'NORECORD' in a_response:
            raise LoginError('Bad Username')
        elif 'REJECTED' in a_response:
            raise LoginError('Account suspended? Login Rejected')
        elif 'KEY' in a_response:
            key = re.compile(".*\tKEY\t(.+)\t").match(a_response).group(1)
            return key
        else:
            raise LoginError('Something went wrong while trying to log in')


    def k_action(self):
        """Sends request for key to encrypt password with"""
        self.client.write(b'K\n')
        return self.client.read_until(b'\n')


    def g_action(self):
        """Tell the server what game you want"""
        self.client.write(b'G\t' + GAME_CODE + b'\n')
        return self.client.read_until(b'\n')


    def c_action(self, character_name):
        """Poll server for list of characters, return character code"""
        self.client.write(b'C\n')
        c_response = self.client.read_until(b'\n')
        character_code = re.compile("C\t\d\t\d\t\d\t\d\t(.+)\t" + character_name).match(c_response.decode()).group(1)
        return character_code


    def l_action(self, character_code):
        """Inform server of which character to play, return the server response with connection info"""
        self.client.write(b'L\t' + character_code.encode('ASCII') + b'\t' + b'STORM\n')
        l_response = self.client.read_until(b'\n').decode()
        login_key = re.compile(".+KEY=(.+)\n").match(l_response).group(1)
        self.client.close()
        return login_key


    def encrypt_password(self, password, hashkey):
        """Encrypt the password with the supplied hash from the server"""
        password = list(password)
        hashkey = list(hashkey[:32])
        return b''.join([struct.pack('B', ((char - 32) ^ hashkey[i]) + 32) for i, char in enumerate(password)])


def get_credentials():
    return {
        'username': input('Username: ').encode('ASCII'),
        'password': getpass.getpass().encode('ASCII'),
        'character': input('Character name: ').capitalize(),
    }


def eaccess_protocol(login_info):
    try:
        login_client = EAccessClient()
        login_client.connect()
        login_info['hashkey'] = login_client.k_action()
        login_client.a_action(login_info)
        login_client.g_action()
        character_code = login_client.c_action(login_info['character'])
        l_response = login_client.l_action(character_code)
        login_client.client.close()
        print(l_response)
    except LoginError as e:
        login_client.client.close()
        print(e)
    # TODO: Persist key


class LoginApp(npyscreen.NPSAppManaged):
    def onStart(self):
        self.addForm("MAIN", LoginForm, name='Login')
        self.addForm("GAME_SELECT", GameForm)
        self.addForm("CHARACTER_SELECT", CharacterForm)


class GameForm(npyscreen.Form):
    def create(self):
        self.game = self.add(npyscreen.TitleSelectOne, scroll_exit=True, max_height=3, name='Game', values=['DR Prime', 'DR Fallen', 'DR Platinum'])

    def afterEditing(self):
        self.parentApp.setNextForm("CHARACTER_SELECT")


class CharacterForm(npyscreen.Form):
    def create(self):
        self.character = self.add(npyscreen.TitleText, name='Character Name')

    def afterEditing(self):
        self.parentApp.setNextForm(None)


class LoginForm(npyscreen.Form):
    def create(self):
        super().create()
        self.username = self.add(npyscreen.TitleText, name='Username').encode('ASCII')
        self.password = self.add(npyscreen.PasswordEntry, name='Password').encode('ASCII')

    def afterEditing(self):

        self.parentApp.setNextForm("GAME_SELECT")


if __name__ == '__main__':
    creds = get_credentials()
    eaccess_protocol(creds)
    # TestApp = LoginApp().run()
