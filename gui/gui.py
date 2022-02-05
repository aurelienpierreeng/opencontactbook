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

import random
import sys
import io
import os
import traceback
import threading
import json
import folium
import urllib.request
from pathlib import Path

from PySide6.QtWidgets import *
from PySide6.QtGui import *
from PySide6.QtCore import *
from PySide6.QtWebEngineWidgets import *
from PySide6.QtQml import *
from PySide6.QtQuickWidgets import *

import qtawesome as qta
import pandas as pd

from gui import utils
from gui.workers import *
from gui.table import *
from data import preferences
from data import contact
from data import addressbook as ab

class GuiEvents(QObject):
  DataChanged = Signal()

class AppWindow(QMainWindow):
  def set_address_book(self, data):
    self.addressbook.addressDB = data

    # Raise the signal DataChanged so we can update the Table view
    self.signals.DataChanged.emit()

  def spawn_vcf_files_thread(self):
    # Get the VCF files
    self.startProgress()
    self.event_stop.clear()
    worker = Worker(self.mutex, self.wait, self.event_stop, contact.list_vcf_in_directory, self.preferences.dict["directory"])
    worker.signals.result.connect(self.set_address_book)
    worker.signals.progress.connect(self.updateProgress)
    worker.signals.finished.connect(self.spawn_clean_contacts_db_thread)
    self.threadpool.start(worker)

  def spawn_vcf_update_thread(self):
    # Get the VCF files
    self.startProgress()
    self.event_stop.clear()
    worker = Worker(self.mutex, self.wait, self.event_stop,
                    contact.update_vcf_in_directory,
                    self.preferences.dict["directory"],
                    self.addressbook.addressDB)
    worker.signals.result.connect(self.set_address_book)
    worker.signals.progress.connect(self.updateProgress)
    worker.signals.finished.connect(self.spawn_clean_contacts_db_thread)
    self.threadpool.start(worker)

  def spawn_clean_contacts_db_thread(self):
    self.startProgress()
    self.event_stop.clear()
    worker = Worker(self.mutex, self.wait, self.event_stop, contact.cleanup_contact, self.addressbook.addressDB)
    worker.signals.result.connect(self.set_address_book)
    worker.signals.progress.connect(self.updateProgress)
    worker.signals.finished.connect(self.spawn_geolocation_thread)
    self.threadpool.start(worker)

  def spawn_geolocation_thread(self):
    self.startProgress()
    self.event_stop.clear()
    worker = Worker(self.mutex, self.wait, self.event_stop, contact.get_geoID, self.addressbook.addressDB)
    worker.signals.result.connect(self.set_address_book)
    worker.signals.progress.connect(self.updateProgress)
    self.threadpool.start(worker)

  def build_address_book(self):
    # Look for a cached DB from a previous run
    file_name = os.path.basename(os.path.normpath(self.preferences.dict["directory"]))
    data_path = os.path.join(self.preferences.pref_path, file_name)

    if os.path.isfile(data_path):
      # Load the cached DB
      data = pd.read_pickle(data_path).astype(str)
      self.set_address_book(data)

      # Update files
      self.spawn_vcf_update_thread()
    else:
      self.spawn_vcf_files_thread()

  def make_tree_view(self):
    # Create the data model with the view
    self.model = TableModel(self.addressbook)
    self.table.setModel(self.model)
    self.update()

  def open_local_directory(self):
    self.preferences.dict["directory"] = QFileDialog.getExistingDirectory(self, self.tr("Open Directory"),
                                    "/home",
                                    QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks)
    self.preferences.dict["method"] = "local directory"

  def set_file_menu(self):
    #self.fileMenu.addAction(self.tr("Open a book from a single file (.vcf)"), self.open_local_directory)
    self.fileMenu.addAction(self.tr("Open a book from a local directory"), self.open_local_directory)
    #self.fileMenu.addAction(self.tr("Open a book from a remote directory (CardDAV)"))

  def set_menu(self):
    self.menuBar = QMenuBar()
    self.setMenuBar(self.menuBar)
    self.fileMenu = self.menuBar.addMenu(self.tr("&File"))
    #self.editMenu = self.menuBar.addMenu(self.tr("&Edit"))
    #self.helpMenu = self.menuBar.addMenu(self.tr("&Help"))

    self.set_file_menu()

  def startProgress(self):
    self.progress = QProgressDialog(self)
    self.progress.setWindowModality(Qt.WindowModal)
    self.progress.setMinimumWidth(400)
    self.progress.setMinimumDuration(0)
    self.progress.setAutoClose(True)
    self.progress.canceled.connect(self.event_stop.set)

  def updateProgress(self, progress):
    """
    Update the progress bar
    :param progress: tuple(int, int, int, str, str) containing :
      1. the step number, (to set progress bar current)
      2. the min number of steps, (to set progress bar min)
      3. the max number of steps, (to set progress bar max)
      4. the current step name (to set text label)
      5. the global operation name (to set window title)

    if the current step name is "cancel", the progress bar is cancelled
    if the current step name is "reset", the progress bar is reset
    """
    self.progress.setValue(progress[0])
    self.progress.setMinimum(progress[1])
    self.progress.setMaximum(progress[2])
    self.progress.setLabelText(progress[3])
    self.progress.setWindowTitle(progress[4])

    if(progress[3] == "cancel"):
      self.progress.cancel()
    elif(progress[3] == "reset"):
      self.progress.reset()


  def add_map_markers(self):
    if "geoID" in self.addressbook.addressView.columns:
      coordinate = (48.69, 6.18)
      self.map = folium.Map(
        zoom_start=5,
        location=coordinate,
        prefer_canvas=True
      )

      i = 0
      for index, row in self.addressbook.addressView.iterrows():
        if(i > 1000): break

        results = row['geoID']

        if results != "not found":
          try:
            results = json.loads(results)
          except:
            print(results)
            continue

          for elem in results:
            #elem = json.loads(elem)
            try:
              if(abs(float(elem["lat"]) - coordinate[0]) < 10 and abs(float(elem["lon"]) - coordinate[1]) < 10):
                i += 1
                folium.Marker([elem["lat"], elem["lon"]], popup="%s" % row["fn"]).add_to(self.map)
            except:
              print(elem)

      self.map.save(self.mapBuffer, close_file=False)
      self.webView.setHtml(self.mapBuffer.getvalue().decode())
      self.webView.update()
      self.webView.reload()
      self.update()


  def __init__(self, base_dir=""):
    super().__init__()
    self.setWindowTitle(utils.get_app_name())
    self.setWindowIcon(QIcon(utils.get_app_icon()))
    self.setWindowState(Qt.WindowMaximized)
    self.set_menu()

    self.preferences = preferences.OCBPreferences(base_dir)

    # Threading, mutex and waiting conditions
    # Lock the mutex and wait for it each time you work on the data in a thread
    self.threadpool = QThreadPool()
    self.mutex = QMutex()
    self.wait = QWaitCondition()
    self.event_stop = threading.Event()

    self.centralWidget = QWidget(self)
    self.centralLayout = QVBoxLayout()
    self.centralWidget.setLayout(self.centralLayout)

    # Build the tabs
    self.tabs = QTabWidget(self)
    self.tabList = QWidget()
    self.tabDuplicates = QWidget()
    self.tabMap = QWidget()
    self.tabs.addTab(self.tabList, self.tr("List"))
    self.tabs.addTab(self.tabMap, self.tr("Map"))
    self.centralLayout.addWidget(self.tabs)

    # Create the Table widget
    self.addressbook = ab.addressBook()
    self.table = QTableView()
    self.model = TableModel(self.addressbook)
    self.table.setModel(self.model)
    layout = QVBoxLayout()
    layout.addWidget(self.table)
    self.tabList.setLayout(layout)

    # Create the map view
    layout = QVBoxLayout()
    self.tabMap.setLayout(layout)
    self.webView = QWebEngineView(self.tabMap)
    layout.addWidget(self.webView)

    #self.webView = QQuickWidget()
    #self.webView.setInitialProperties({"myModel": my_model})

    #Load the QML file
    #qml_file = Path(__file__).parent / "view.qml"
    #self.webView.setSource(QUrl.fromLocalFile(qml_file))
    #self.webView.show()

    # save map data to data object
    self.mapBuffer = io.BytesIO()

    # Create global signals and connect their callbacks
    self.signals = GuiEvents()
    self.signals.DataChanged.connect(self.make_tree_view)
    self.signals.DataChanged.connect(self.add_map_markers)

    # Finally, try to load some data
    if "directory" not in self.preferences.dict:
      self.emptyPrompt = QLabel(self.tr("Please open a contact book to start"))
      self.emptyPrompt.setAlignment(Qt.AlignCenter)
      self.setCentralWidget(self.emptyPrompt)
    else:
      self.setCentralWidget(self.centralWidget)
      self.build_address_book()


  def closeEvent(self, event):
    # Save preferences
    self.preferences.write_preferences()

    # Save the dataframe for later use
    file_name = os.path.basename(os.path.normpath(self.preferences.dict["directory"]))
    data_path = os.path.join(self.preferences.pref_path, file_name)
    self.addressbook.addressDB.to_pickle(data_path)


def GUI_Start(base_dir=""):
  app = QApplication([])
  widget = AppWindow(base_dir="")
  widget.show()
  sys.exit(app.exec())
