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

from PySide6.QtWidgets import *
from PySide6.QtGui import *
from PySide6.QtCore import *

from data.addressbook import addressBook


# Qt Treeview model for a Pandas DataFrame
class TableModel(QAbstractTableModel):

  def __init__(self, addressbook: addressBook):
    super(TableModel, self).__init__()
    self._data = addressbook

  def data(self, index, role):
    if role == Qt.DisplayRole or role == Qt.EditRole:
      value = self._data.addressView.iloc[index.row(), index.column()]
      return str(value)

  def rowCount(self, index):
    return self._data.addressView.shape[0]

  def columnCount(self, index):
    return self._data.addressView.shape[1]

  def headerData(self, section, orientation, role):
    # section is the index of the column/row.
    if role == Qt.DisplayRole:
      if orientation == Qt.Horizontal:
        return str(self._data.addressView.columns[section])

      if orientation == Qt.Vertical:
        return str(self._data.addressView.index[section])

  def flags(self, index):
    return Qt.ItemIsSelectable|Qt.ItemIsEnabled|Qt.ItemIsEditable| \
            Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled

  def setData(self, index, value, role):
    if role == Qt.EditRole:
      # Commit change using keywords to the Pandas DataframeS
      df_col = self._data.addressView.columns[index.column()]
      df_row = self._data.addressView.index[index.row()]
      self._data.set_value(df_row, df_col, value)
      return True
    return False
