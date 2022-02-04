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


from PySide6.QtGui import *
from PySide6.QtCore import *

import traceback, sys

class WorkerSignals(QObject):
  '''
  Defines the signals available from a running worker thread.

  Supported signals are:

  finished
      No data

  error
      tuple (exctype, value, traceback.format_exc() )

  result
      object data returned from processing, anything

  progress
      int indicating % progress

  '''
  finished = Signal()
  error = Signal(tuple)
  result = Signal(object)
  progress = Signal(object)


class Worker(QRunnable):
    '''
    Worker thread

    Inherits from QRunnable to handler worker thread setup, signals and wrap-up.

    :param callback: The function callback to run on this worker thread. Supplied args and
                     kwargs will be passed through to the runner.
    :type callback: function
    :param args: Arguments to pass to the callback function
    :param kwargs: Keywords to pass to the callback function

    '''

    def __init__(self, mutex, wait, killswitch, fn, *args, **kwargs):
      super(Worker, self).__init__()
      self.fn = fn
      self.args = args
      self.kwargs = kwargs
      self.signals = WorkerSignals()
      self.mutex = mutex
      self.wait = wait
      self.killswitch = killswitch

    @Slot()
    def run(self):
      self.mutex.lock()
      try:
        result = self.fn(
          *self.args, **self.kwargs,
          progress=self.signals.progress,
          killswitch=self.killswitch
        )
      except:
        traceback.print_exc()
        exctype, value = sys.exc_info()[:2]
        self.signals.error.emit((exctype, value, traceback.format_exc()))
      else:
        self.signals.result.emit(result)
      finally:
        self.mutex.unlock()
        self.signals.finished.emit()
