#!/usr/bin/env python3

import json
import os

class OCBPreferences():
  def __init__(self, base_dir=""):
    # Grab the preferences directory and file
    if base_dir == "":
      self.base_dir = os.path.expanduser('~')
    else:
      self.base_dir = os.path.abspath(os.path.normpath(base_dir))

    self.pref_path = os.path.join(self.base_dir, ".opencontactsbook")
    self.pref_file = os.path.join(self.pref_path, "config.json")

    # Create the directory if needed
    if(not os.path.isdir(self.pref_path)):
      os.mkdir(self.pref_path)

    # Create an empty pref file if needed
    if(not os.path.isfile(self.pref_file)):
      file = open(self.pref_file, 'a')
      file.write("{ }")
      file.close()

    # Create the preferences and store them in a dictionnary
    self.dict = dict()
    self.read_preferences()

  def read_preferences(self):
    file = open(self.pref_file, "r")
    self.dict = json.loads(file.read())
    file.close()

  def write_preferences(self):
    file = open(self.pref_file, "w")
    json.dump(self.dict, file)
    file.close()
