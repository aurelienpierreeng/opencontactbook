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

import re
from collections import Counter
from collections import defaultdict
from country_list import countries_for_language
from country_list import available_languages
import unidecode

# Adapted from Peter Norvig
# http://norvig.com/spell-correct.html

class GeoSpellChecker:
  def rebuild_dict(self, languages):
    # Build a dictionnary with:
    # key : ISO country code
    # values : list of all country names in all available languages

    # Phase 1: gather all country names in all requested languages
    DB = []
    for lang in languages:
      DB.append(dict(countries_for_language(lang)))

    # Phase 2: merge all names in all languages that have the same country code (key)
    # Remove dashes, non-unicode chars and so on because we do machine detection, not actual spell checking
    self.countries = defaultdict(list)
    for i in range(len(DB)):
      current = DB[i]
      for key, value in current.items():
        self.countries[key].append(unidecode.unidecode(value.lower()).replace("-", " "))

    # Phase 3 : Extract all unique names and find their frequency
    # This will be to compute the probability of the spell corrections
    self.WORDS = Counter()
    for key, value in self.countries.items():
      self.WORDS.update(value)

  def __init__(self, languages=["en"]):
    self.rebuild_dict(languages)

  def words(text):
    return re.findall(r'\w+', text.lower())

  def P(self, word):
      "Probability of `word`."
      return self.WORDS[word] / sum(self.WORDS.values())

  def correction(self, word):
      "Most probable spelling correction for word."
      return max(self.candidates(word), key=self.P)

  def candidates(self, word):
      "Generate possible spelling corrections for word."
      return (self.known([word]) or self.known(self.edits1(word)) or self.known(self.edits2(word)) or [word])

  def known(self, words):
      "The subset of `words` that appear in the dictionary of WORDS."
      return set(w for w in words if w in self.WORDS)

  def edits1(self, word):
      "All edits that are one edit away from `word`."
      letters    = 'abcdefghijklmnopqrstuvwxyz'
      splits     = [(word[:i], word[i:])    for i in range(len(word) + 1)]
      deletes    = [L + R[1:]               for L, R in splits if R]
      transposes = [L + R[1] + R[0] + R[2:] for L, R in splits if len(R)>1]
      replaces   = [L + c + R[1:]           for L, R in splits if R for c in letters]
      inserts    = [L + c + R               for L, R in splits for c in letters]
      return set(deletes + transposes + replaces + inserts)

  def edits2(self, word):
      "All edits that are two edits away from `word`."
      return (e2 for e1 in self.edits1(word) for e2 in self.edits1(e1))

  def get_country_code_from_spell_check(self, word):
    "Perform a spell check and fetch the country code"
    guess = self.correction(word.lower())
    for key, value in self.countries.items():
      if guess in value or guess in key:
        return key

  def get_country_code_from_text(self, text):
    """
    Try to identify a country name in text
    If found, output the ISO 3166-1 country code and remove the country name from the text
    We parse the text from the end since the country is generally
    written last in an address
    """
    clean_text = unidecode.unidecode(text.lower())

    tokens = clean_text.split(",")
    for word in reversed(tokens):
      guess = self.get_country_code_from_spell_check(word.strip())
      if guess is not None:
        filtered = clean_text.replace(word, "").strip(" ,")
        return (guess, filtered)

    return (None, clean_text)

  def spell_check_countries(self, text):
    """
    Try to identify a country name in text and correct it
    """
    clean_text = unidecode.unidecode(text.lower())

    # Tokenize with comma
    tokens = clean_text.split(",")
    for word in reversed(tokens):
      stripped = word.strip()
      guess = self.correction(stripped)
      clean_text = clean_text.replace(stripped, guess)

    return clean_text
