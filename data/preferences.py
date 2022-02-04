#!/usr/bin/env python3

import json


def read_preferences(pref_file):
  file = open(pref_file, "r")
  preferences = json.loads(file.read())
  file.close()
  return preferences


def write_preferences(pref_file, json_string):
  file = open(pref_file, "w")
  json.dump(json_string, file)
  file.close()
  return
