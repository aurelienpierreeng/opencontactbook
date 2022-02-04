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

from urllib.parse import urlencode
import urllib3
import json
import os
import time
import re


# Configure the cache
home_path = os.path.expanduser('~')
pref_path = os.path.join(home_path, ".opencontactsbook")
cache_path = os.path.join(pref_path, "geocache")

# Create the directory if needed
if(not os.path.isdir(pref_path)):
  os.mkdir(pref_path)

if(not os.path.isdir(cache_path)):
  os.mkdir(cache_path)

class Nominatim:
  def __init__(self):
    self.timer = time.time()

  def fetch_cache_or_web(self, query):
    # Lookup the cache for a query. If not found, fetch it on the server
    all_files = os.listdir(cache_path)
    now = int(time.time())

    # Walk the directory to find all files
    # Look for case-insensitive matches
    for file in sorted(all_files):
      if (file.lower()).startswith(query.lower()):
        """
        # Get the file timestamp
        timestamp = re.search(r"\d+$", file)

        if(now - int(timestamp.group(0)) > 5184000):
          # if the cache is older than 60 days, flush it
          print("Cache flushed for query", query)
          os.remove(file)
        else:
        """
        # the cache is new enough, use it
        # print("Cache used for query", query)
        with open(os.path.join(cache_path, file), "r") as f:
          return json.loads(f.read())

    # No cache found, make it
    http = urllib3.PoolManager(num_pools=1, headers={
      "Accept": "application/json",
      "Content-Type": "application/json",
      "Accept": "text/plain",
      "User-Agent": "Open Contact book experimental"
    })
    url = 'https://nominatim.openstreetmap.org/search?' + query

    # Check if previous request is more than 1 s old
    # To comply with the conditions of use of the API
    now = time.time()
    time_passed = now - self.timer
    if(time_passed < 1.): time.sleep(1. - time_passed)

    r = http.request('GET', url)
    self.timer = now
    output = json.loads(r.data.decode('utf-8'))

    with open(os.path.join(cache_path, query.lower() + "_" + str(int(now))), "w") as file:
      file.write(json.dumps(output))

    print("Server used for query", query)
    return output
