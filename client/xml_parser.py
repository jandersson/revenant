import xml.etree.ElementTree as ET


class XMLParser:
    def __init__(self):

        self.server_time = None

        self.room_description = ''
        self.room_name = ''
        self.room_objs = []
        self.room_players = []
        self.compass_dirs = []

        self.cast_time = None
        self.prepared_spell = ''

    def dispatcher(self, text: str):
        """Dispatch a given text string to parsing method"""
        pass

    def perc_window(self) -> list:
        """Handle perc window text"""
        pass


if __name__ == '__main__':
    x = XMLParser()