#!/usr/bin/env python3

import os

from gui import gui

# Grab the preferences directory and file
home_path = os.path.expanduser('~')
pref_path = os.path.join(home_path, ".opencontactsbook")
pref_file = os.path.join(pref_path, "config.json")

# Create the directory if needed
if(not os.path.isdir(pref_path)):
  os.mkdir(pref_path)

# Create an empty file if needed
if(not os.path.isfile(pref_file)):
  file = open(pref_file, 'a')
  file.write("{ }")
  file.close()

gui.GUI_Start(pref_file)
