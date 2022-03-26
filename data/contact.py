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

import os
import pandas as pd
import re
import unidecode
import requests
import json
import hashlib
import country_list

import vobject as vo
from data.nominatim import Nominatim
from data.spellcheck import GeoSpellChecker
from urllib.parse import urlencode


def hash_file(path):
    """Open a file and compute its hash"""
    BLOCK_SIZE = 65536
    file_hash = hashlib.sha256()

    with open(path, 'rb') as f:
        fb = (f.read(BLOCK_SIZE))
        while len(fb) > 0:
            file_hash.update(fb)
            fb = (f.read(BLOCK_SIZE))

    return file_hash.hexdigest()


def parse_vcf(content, path: str):
    # Remove accentuated characters in vCard tags
    # Otherwise it makes some vobject fail (actually, the codec lib it uses)
    # Also… what stupid vCard app allows them ???
    regex = r"^([A-ZÉÈÊÀÃ\-\;]+):"
    matches = re.finditer(regex, content, re.MULTILINE)

    for matchNum, match in enumerate(matches):
        tag = match.group(1)
        content = content.replace(tag, unidecode.unidecode(tag))

    # Get the inner of the vcard as a Python dict
    parsed = vo.readOne(content).contents
    parsed["z-file"] = path
    parsed["z-hash"] = hash_file(path)
    parsed["z-geoupdate"] = True

    return parsed


def list_vcf_in_directory(directory: str, progress=None, killswitch=None):
    """
    Thread-safe address book building
    :param progress: Qt Worker Signal to emit progress info
    :param killswitch: Thread-safe boolean stopping the process if == True
    """
    contacts = []
    all_files = os.listdir(directory)
    files_number = len(all_files)
    current_file = 0

    # Walk the directory to find al files
    for file in sorted(all_files):

        # Update the progress bar if any
        if progress is not None:
            progress.emit((current_file, 0, files_number,
                          "Parsing files", "Reading directory"))
            current_file += 1

        # Abort and update the progress bar on killswitch
        if killswitch is not None and killswitch.is_set():
            if progress is not None:
                progress.emit((current_file, 0, current_file,
                              files_number, "cancel", "Reading directory"))
            break

        if file.endswith(".vcf"):
            path = os.path.join(directory, file)
            f = open(path, "r")
            content = f.read()
            f.close()
            contacts.append(parse_vcf(content, path))

    if progress is not None:
        progress.emit((current_file, files_number, files_number,
                      "Parsing files", "Reading directory"))

    # Collapse this into a database, aka Pandas DataFrame
    data = pd.DataFrame(contacts)

    return data.astype(str)


def update_vcf_in_directory(directory: str, data: pd.DataFrame, progress=None, killswitch=None):
    """
    Thread-safe address book building
    :param progress: Qt Worker Signal to emit progress info
    :param killswitch: Thread-safe boolean stopping the process if == True
    """
    all_files = os.listdir(directory)
    files_number = len(all_files)
    current_file = 0

    if "z-file" not in data.columns:
        raise ValueError(
            "No file entry was found in the database. This should not happen")

    # Walk the directory to find al files
    for file in sorted(all_files):

        # Update the progress bar if any
        if progress is not None:
            progress.emit((current_file, 0, files_number,
                          "Parsing files", "Reading directory"))
            current_file += 1

        # Abort and update the progress bar on killswitch
        if killswitch is not None and killswitch.is_set():
            if progress is not None:
                progress.emit((current_file, 0, current_file,
                              files_number, "cancel", "Reading directory"))
            break

        if file.endswith(".vcf"):
            path = os.path.join(directory, file)
            f = open(path, "r")
            content = f.read()
            f.close()

            # Look if the file is already in DB
            query = data[data["z-file"] == path]

            if len(query.index) == 1:
                # File already in DB : check for changes
                hash = hash_file(path)
                if(hash != query.iloc[0]["z-hash"]):
                    print("updating", path)

                    # Create a new dataframe with one row at the same index as the DB match
                    new_line = pd.DataFrame(
                        parse_vcf(content, path), index=query.index).astype(str)

                    # Merge the new line within DB: this will not update the actual line
                    # but will add the relevant columns in case your updated entry uses more Vcard tags than the DB
                    data = pd.merge(data, new_line, how="left")

                    # Now, data is guaranteed to have as many cols as new_line
                    # update the line for real
                    data.loc[query.index] = new_line

                else:
                    pass
                    # nothing to do, file didn't change

            elif len(query.index) == 0:
                print("adding", path)
                # File not found in DB : add it now
                # Create a new dataframe with one row and new index
                new_line = pd.DataFrame(parse_vcf(content, path)).astype(str)

                # Append the new line within DB and add a new global column
                # in DB if a new tag is found in the .vcf
                data = pd.concat([data, new_line], axis=0, ignore_index=True)

            else:
                # We have more than one line for this file
                # Someone tampered with our database
                raise ValueError(
                    "Undefined behaviour: we have more than one record in database for %s, this should never happen" % path)

    if progress is not None:
        progress.emit((current_file, files_number, files_number,
                      "Parsing files", "Reading directory"))

    return data


def cleanup_contact(data: pd.DataFrame, progress=None, killswitch=None):
    """
    Thread-safe address book building
    :param progress: Qt Worker Signal to emit progress info
    """

    # Force string type
    data = data.astype(str)

    # Backup the file names as-is
    files = data["z-file"]

    if progress is not None:
        progress.emit((0, 0, 3, "Formatting the database", "Prepare data"))

    # Replace NaN by empty string to not pollute the view
    data.replace(to_replace="nan", value="", inplace=True)

    # Cleanup fully empty columns
    data.dropna(axis=1, how="all", inplace=True)

    if progress is not None:
        progress.emit((1, 0, 3, "Cleaning tags", "Prepare data"))

    # Cleanup the Vcard tags
    # 1. Remove outer brackets : [<fn{} name>] -> <fn{} name>
    data.replace(to_replace="^\[([\s\S]*)\]$",
                 value=r"\1", regex=True, inplace=True)
    # 2. Tags with nested types : [<adr{'TYPE': ['HOME']} value>] -> HOME: value
    data.replace(to_replace="\<[\w\-]+(\{[^\}]*\})([^\>]+)\>\,?",
                 value=r"\1\2;", regex=True, inplace=True)
    # 3. Remove multiple spaces
    data.replace(to_replace="[ ]{2,}", value=" ", regex=True, inplace=True)
    # 4. Remove leading empty elements separated by comas
    data.replace(to_replace="^\s*,\s*[^\S]*",
                 value=" ", regex=True, inplace=True)

    if progress is not None:
        progress.emit((2, 0, 3, "Sorting data", "Prepare data"))

    # Reorder columns in a way that makes sense :
    # 1. start with typical ID and adresses/phone (default vCard fields)
    # 2. end with X-(.*) (custom user-defined fields)
    # 3. fill the middle with the rest of default VCard fields

    original_cols = sorted(list(data.columns.tolist()))
    forced_cols_start = ["categories", "fn", "n",
                         "org", "role", "email", "adr", "tel"]

    for elem in forced_cols_start:
        if elem in original_cols:
            original_cols.remove(elem)

    cols = forced_cols_start + original_cols
    data = data.reindex(columns=cols)

    # Restore files
    data["z-file"] = files

    if progress is not None:
        progress.emit((3, 0, 3, "Sorted", "Prepare data"))

    return data


def get_geoID(data: pd.DataFrame, progress=None, killswitch=None):
    """
    Thread-safe address book building
    :param progress: Qt Worker Signal to emit progress info
    """

    entries = len(data.index)

    if progress is not None:
        progress.emit(
            (0, 0, entries, "Downloading GPS coordinates from nominatim.org…", "Fetch geolocation data"))

    # Try to see if https://nominatim.openstreetmap.org/search is available
    # If not, the DB will be unavailable
    try:
        response = requests.get('https://nominatim.openstreetmap.org/search')
    except:
        if progress is not None:
            progress.emit(
                (0, 0, entries, "nominatim.org can't be reached, geolocation will use the local cache if possible", "Fetch geolocation data"))

    # Get the OSM area ID
    # This can be slow and long since we need to download info from the Nominatim DB
    # However, results are cached, so the next time will run faster
    # To be able to re-use the cache, we actually need to process that single-threaded and sequentially.
    # Also, it wouldn't be nice to DoS the free OSM servers with too many requests per second.
    # See conditions of service use : https://operations.osmfoundation.org/policies/nominatim/
    nominatim = Nominatim()

    # Quick way for reference:
    # Since it's not purely data processing in here, there is no point doing that
    #data['geoID'] = data.apply(lambda row : nominatim.query(re.sub(r"\[[A-Z]+:?\s?\n?([\s\S]*)\]", r"\1", row['adr'].replace("\n", ""))).toJSON(), axis = 1)

    # Get a clean location hint
    data['z-geohint'] = data['adr'].replace(
        to_replace="\{[^\}]+\}", value="", regex=True)

    # Remove content into parenthesis because it's usually precisions and Nominatim will not be able to parse it
    data['z-geohint'].replace(to_replace="(?:\(|\@ESCAPEDLEFTPARENTHESIS\@).*(?:\)|\@ESCAPEDRIGHTPARENTHESIS\@)",
                              value=" ", regex=True, inplace=True)

    # Replace dashes and special characters by spaces
    data['z-geohint'].replace(to_replace="[\-\[\]\{\}]+",
                              value=" ", regex=True, inplace=True)
    data['z-geohint'].replace(to_replace="[\n\r]+",
                              value=", ", regex=True, inplace=True)

    # Factorize multiple spaces
    data['z-geohint'].replace(to_replace="\s+", value=" ", regex=True)

    # Remove leading empty elements separated by comas
    data['z-geohint'].replace(to_replace="^\s*,\s*[^\S]",
                              value="", regex=True, inplace=True)

    # Finally, apply some spell checking
    GeoSpellCheck = GeoSpellChecker(["fr", "en"])

    # Ensure index matches the number of rows, otherwise iterating over rows may not produce the expected result
    data.reset_index(drop=True, inplace=True)

    # Go the slow way to be able to output the progress
    for index, row in data.iterrows():
        if progress is not None:
            progress.emit(
                (index, 0, entries, "Downloading GPS coordinates from nominatim.org…", "Fetch geolocation data"))

        # Abort and update the progress bar on killswitch
        if killswitch is not None and killswitch.is_set():
            if progress is not None:
                progress.emit((index, 0, index, "cancel",
                              "Fetch geolocation data"))
            break

        # If geolocation has already been found
        if "z-geoupdate" in data.columns:
            if data.loc[index, "z-geoupdate"] == "False":
                continue

        result = []

        # Decode Unicode
        decoded = unidecode.unidecode(row['z-geohint'], errors="ignore")

        # Remove illegal characters left-over from bad encodings
        decoded = decoded.replace("\"", "")
        decoded = decoded.replace("(c)", "")
        decoded = decoded.replace("@", "")

        # We may have more than one address per contact (home, office, etc.)
        split = decoded.split(";")

        flag_accurate = False

        for elem in split:
            elem = elem.strip(" \n\r.;,:").lower()

            # Factorize multiple or orphaned commas
            elem = re.sub(r"(\s?\,)+", ",", elem)

            if len(str(elem)) != 0:
                try:
                    query = urlencode({'q': elem,
                                       'format': 'json'})
                    query = re.sub(r"[\+]+", "+", query).strip("+")
                    out = nominatim.fetch_cache_or_web(query)[0]
                    result.append(out)

                    # We found an exact match
                    flag_accurate = True
                except:
                    # Third guess: try to remove the country name and replace it by the ISO code
                    # Nominatim fails if the country name is not in the same language as the rest
                    # of the address,
                    # Note: It's not accurate.
                    # Ex 1: US State "Georgia" may get identified as the country.
                    # Ex 2: If the streetname is a country, the address may also fall in the wrong country
                    (country_code, filtered) = GeoSpellCheck.get_country_code_from_text(
                        elem)

                    try:
                        query = urlencode({'q': filtered,
                                           'countrycodes': country_code,
                                           'format': 'json'})
                        query = re.sub(r"[\+]+", "+", query).strip("+")
                        out = nominatim.fetch_cache_or_web(query)[0]
                        result.append(out)
                    except:
                        # Sometimes, the query fails for being too specific
                        # In that case, we retry all combinations of the n last elements
                        sub_elems = filtered.split(",")
                        found = False
                        for i in range(0, len(sub_elems) - 1, 1):
                            q = sub_elems[-1].strip()
                            # Build sub-query with the n-th last elements
                            # n = length - i > 1
                            for j in range(2, len(sub_elems) - i, +1):
                                q = sub_elems[-j].strip() + "," + q

                            try:
                                query = urlencode({'q': q,
                                                   'countrycodes': country_code,
                                                   'format': 'json'})
                                query = re.sub(r"[\+]+", "+", query).strip("+")
                                out = nominatim.fetch_cache_or_web(query)[0]
                                result.append(out)
                                found = True
                                break
                            except:
                                continue

                        if not found:
                            try:
                                # Try with just the first and last element
                                query = urlencode({'q': sub_elems[0].strip(),
                                                   'countrycodes': country_code,
                                                   'format': 'json'})
                                query = re.sub(r"[\+]+", "+", query).strip("+")
                                out = nominatim.fetch_cache_or_web(query)[0]
                                result.append(out)
                            except:
                                # Just using one element is simply too risky
                                # Abort here
                                print(elem, "not found")
        if result:
            data.loc[index, "z-geoID"] = json.dumps(result)
        else:
            data.loc[index, "z-geoID"] = "not found"
        data.loc[index, "z-exactlocation"] = flag_accurate
        data.loc[index, "z-geoupdate"] = False

    if progress is not None:
        progress.emit((index, entries, entries, "cancel",
                      "Fetch geolocation data"))

    return data
