import npyscreen


class LoginApp(npyscreen.NPSAppManaged):
    def onStart(self):
        self.login_client = EAccessClient()
        self.addForm("MAIN", LoginForm, name="Login")
        self.addForm("GAME_SELECT", GameForm)
        self.addForm("CHARACTER_SELECT", CharacterForm)


class GameForm(npyscreen.Form):
    def create(self):
        self.game = self.add(
            npyscreen.TitleSelectOne,
            scroll_exit=True,
            max_height=3,
            name="Game",
            values=["DR Prime", "DR Fallen", "DR Platinum"],
        )

    def afterEditing(self):
        self.parentApp.setNextForm("CHARACTER_SELECT")


class CharacterForm(npyscreen.Form):
    def create(self):
        self.character = self.add(npyscreen.TitleText, name="Character Name")

    def afterEditing(self):
        self.parentApp.setNextForm(None)


class LoginForm(npyscreen.Form):
    def create(self):
        super().create()
        self.username = self.add(npyscreen.TitleText, name="Username")
        self.password = self.add(npyscreen.TitlePassword, name="Password")
        self.remember = self.add(npyscreen.RoundCheckBox, name="Remember me")
        self.center_on_display()

    def afterEditing(self):
        self.parentApp.setNextForm("GAME_SELECT")

    def on_ok(self):
        self.parentApp.setNextForm("GAME_SELECT")

    def on_cancel(self):
        self.parentApp.setNextForm(None)
