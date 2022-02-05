#!/usr/bin/env python3
#
# Copyright © Aurélien Pierre - 2022
#
# This file is part of the Open Contact Book project.
#
# Open Contact Book is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Open Contact Book is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
# or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

# You should have received a copy of the GNU General Public License along with Open Contact Book.
# If not, see <https://www.gnu.org/licenses/>.

import pandas as pd

class addressDB(pd.DataFrame):
  def __init__(self, *args, **kargs):
    super().__init__()


class addressBook():
  def __init__(self, *args, hidden_cols=[], **kargs):
    # addressDB contains the whole contacts book as fetched on disk
    self._addressDB = addressDB(*args, **kargs)

    # Add a column to track user edits in line
    self._addressDB["changed"] = False

    # addressView contains a subset of addressDB extracted by query and manipulated in GUI
    self._addressView = self._addressDB

    # text query to build the view
    self._query = ""

    # columns to hide in the view
    self.hidden_cols = hidden_cols

  def make_view(self):
    try:
      self._addressView = self.addressDB[self._query].drop(self.hidden_cols, axis = 1)
    except:
      self._addressView = self.addressDB.drop(self.hidden_cols, axis = 1)

  # Getters/Setters for addressDB
  def get_addressDB(self):
    return self._addressDB

  def set_addressDB(self, data):
    # addressDB should always be set from existing data (disk or network)
    # user interactions should only use the view
    self._addressDB = data

    # Add a column to track user edits in line
    self._addressDB["changed"] = False

    # Build the view
    self.make_view()

  def del_addressDB(self):
    del self._addressDB

  addressDB = property(get_addressDB, set_addressDB, del_addressDB)

  # Getter for addressView
  def get_addressView(self):
    return self._addressView

  def set_addressView(self, data):
    self._addressView = data

  addressView = property(get_addressView, set_addressView)

  # Getters/Setters for query
  def get_query(self):
    return self._query

  def set_query(self, query):
    self._query = query
    self.make_view()

  def del_query(self):
    del self._query

  query = property(get_query, set_query, del_query)

  def set_value(self, row, col, value):
    # set both view and data
    self._addressView._set_value(row, col, value)
    self._addressDB._set_value(row, col, value)

    # set the changed flag on the row
    self._addressView._set_value(row, "changed", True)
    self._addressDB._set_value(row, "changed", True)
