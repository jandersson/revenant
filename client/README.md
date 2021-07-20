# Revenant Client

## About

Revenant Client is a rough draft of a front end as well as engine for playing DragonRealms (scripting too, when i get there). 

Its genesis is mostly from my own desire to run Python scripts in a Ruby dominated scripting environment. 

Here's some info on the main components, subject to change on a whim:

* core: Core's objective is to be the engine/middleman between whatever client is running the game. My aim is essentially a lich clone here with more modularity and support for Python scripting. 
* gui: The graphical user interface, using PyQt5 (porting to PyQt6 atm). If you ever played Gemstone on AOL back before wizard or stormfront... the current state is largely reminiscent of that. I'm thinking if you want the cutting edge front end use Frostbite; im just having fun here. At the moment it's basically just a test bench for core.
* tui: A non working draft of a terminal front end. Profanity is your go to here. I'm still not sure what framework to use yet. 

Check out Pylanthia as a great related project!

## Running

As this is a development/hobby project, I'm still running this with a 'if name equals main' in `gui/client_gui.py`.
Going to add a cli tool at some point. 

TODO: Links!