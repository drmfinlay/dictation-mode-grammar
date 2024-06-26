# coding=utf-8
#
# This file is part of Dragonfly.
# (c) Copyright 2007, 2008 by Christo Butcher
# Licensed under the LGPL.
#
#   Dragonfly is free software: you can redistribute it and/or modify it
#   under the terms of the GNU Lesser General Public License as published
#   by the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   Dragonfly is distributed in the hope that it will be useful, but
#   WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#   Lesser General Public License for more details.
#
#   You should have received a copy of the GNU Lesser General Public
#   License along with Dragonfly.  If not, see
#   <http://www.gnu.org/licenses/>.
#

"""
Dictation formatting for other Dragonfly engines
============================================================================

This module implements dictation formatting for Dragonfly engines that
output plain-text dictated words without formatting information,
i.e. engines other than Natlink. It has been adapted from formatting code
for the Natlink engine.

"""

import logging
import re

from six import string_types


#===========================================================================

class FlagContainer(object):
    """ Container for a predefined set of boolean flags. """

    flag_names = ()

    def __init__(self, *names):
        self._flags_true = set()
        for name in names:
            setattr(self, name, True)

    def flags_string(self):
        flags_true_names = []
        for flag in self.flag_names:
            if flag in self._flags_true:
                flags_true_names.append(flag)
        return u", ".join(flags_true_names)

    def __unicode__(self):
        return u"%s(%s)" % (self.__class__.__name__, self.flags_string())

    def __repr__(self):
        return self.__unicode__()

    def __getattr__(self, name):
        if name not in self.flag_names:
            raise AttributeError("Invalid flag name: %r" % (name,))
        return (name in self._flags_true)

    def __setattr__(self, name, value):
        if name.startswith("_"):
            return object.__setattr__(self, name, value)
        if name not in self.flag_names:
            raise AttributeError("Invalid flag name: received %r, expected"
                                 " one of %r" % (name, self.flag_names))
        if value:
            self._flags_true.add(name)
        else:
            self._flags_true.discard(name)

    def clone(self):
        clone = self.__class__()
        for name in self._flags_true:
            setattr(clone, name, True)
        return clone


#---------------------------------------------------------------------------

class WordFlags(FlagContainer):
    """
        Container for formatting flags associated with DNS words.

        The flags defined by this class are closely related to the
        formatting information provided by DNS.

    """

    flag_names = (
        # Flags related to spacing
        "no_space_before",     # No space before this word (like right-paren)
        "no_space_after",      # No space after this word (like left-paren)
        "two_spaces_after",    # Two spaces after this word (like full-stop)
        "no_space_mode",       # Activate no-spacing mode (like No-Space-On)
        "reset_no_space",      # Reset spacing mode (like No-Space-Off)
        "no_space_reset",      # Don't reset spacing state (like Cap)
        "spacebar",            # Extra space after this word (like spacebar)
        "no_space_between",    # No spaces between adjacent words with this flag (like numbers)

        # Flags related to newlines
        "newline_after",       # One newline after this word (like New-Line)
        "two_newlines_after",  # Two newlines after this word (like New-Paragraph)

        # Flags related to capitalization
        "cap_next",            # Normally capitalize next word (eg full-stop)
        "cap_next_force",      # Always capitalize next word (eg Cap-Next)
        "lower_next",          # Lowercase next word (eg No-Caps-Next)
        "upper_next",          # Uppercase next word (eg All-Caps-Next)
        "cap_mode",            # Activate capitalization mode (like Caps-On)
        "lower_mode",          # Activate lowercase mode (like No-Caps-On)
        "upper_mode",          # Activate uppercase mode (like All-Caps-On)
        "reset_cap",           # Reset capitalization mode (like Caps-Off)
        "no_cap_reset",        # Don't reset the capitalization state (like left-paren)
        "no_title_cap",        # Don't capitalize in title (like and)

        # Miscellaneous flags
        "no_format",           # Don't apply formatting (like Cap)
        "not_after_period",    # Suppress this word after a word ending in period (like full-stop after etc.)
    )


#---------------------------------------------------------------------------

class StateFlags(FlagContainer):
    """
        Container for keeping state for inter-word formatting.

        The flags defined by this class are used by Dragonfly to store
        formatting state between words as a formatter consumes
        consecutive words.

    """

    flag_names = (
        # Flags related to spacing
        "no_space_before",       # No space before next word
        "two_spaces_before",     # Two spaces before next word
        "no_space_between",      # No space before next word if it has no_space_between flag
        "no_space_mode",         # No-spacing mode is active

        # Flags related to capitalization
        "cap_next",              # Normally capitalize next word
        "cap_next_force",        # Always capitalize next word
        "lower_next",            # Lowercase next word
        "upper_next",            # Uppercase next word
        "cap_mode",              # Capitalization mode is active
        "lower_mode",            # Lowercase mode is active
        "upper_mode",            # Uppercase mode is active

        # Miscellaneous flags
        "prev_ended_in_period",  # Previous word ended in period
    )


#===========================================================================

class Word(object):
    """ Word storing written and spoken forms with formatting flags. """

    def __init__(self, written, spoken, flags):
        self.written = written
        self.spoken = spoken
        self.flags = flags

    def __unicode__(self):
        info = [repr(self.written)]
        if self.spoken and self.spoken != self.written:
            info.append(repr(self.spoken))
        flags_string = self.flags.flags_string()
        if flags_string:
            info.append(flags_string)
        return u"%s(%s)" % (self.__class__.__name__, ", ".join(info))

    def __repr__(self):
        return self.__unicode__()


#===========================================================================

class WordParserTextInput(object):
    """
        Dictation results parser for text-input engine.

        Based on the DNS word parser classes.

    """

    _log = logging.getLogger("dictation.word_parser")

    property_map = {
        "new-line":         WordFlags("no_format", "no_space_after", "no_cap_reset", "newline_after"),
        "new-paragraph":    WordFlags("no_format", "no_space_after", "cap_next", "two_newlines_after"),
        "no-space":         WordFlags("no_format", "no_cap_reset", "no_space_after"),
        "no-space-on":      WordFlags("no_format", "no_cap_reset", "no_space_mode"),
        "no-space-off":     WordFlags("no_format", "no_cap_reset", "reset_no_space"),

        "cap":              WordFlags("no_format", "no_space_reset", "cap_next_force"),
        "caps-on":          WordFlags("no_format", "no_space_reset", "reset_cap", "cap_mode"),
        "caps-off":         WordFlags("no_format", "no_space_reset", "reset_cap"),
        "all-caps":         WordFlags("no_format", "no_space_reset", "upper_next"),
        "all-caps-on":      WordFlags("no_format", "no_space_reset", "reset_cap", "upper_mode"),
        "all-caps-off":     WordFlags("no_format", "no_space_reset", "reset_cap"),
        "no-caps":          WordFlags("no_format", "no_space_reset", "lower_next"),
        "no-caps-on":       WordFlags("no_format", "no_space_reset", "reset_cap", "lower_mode"),
        "no-caps-off":      WordFlags("no_format", "no_space_reset", "reset_cap"),

        "space-bar":        WordFlags("no_format", "spacebar", "no_space_after", "no_cap_reset", "no_space_before"),
        "spelling-cap":     WordFlags("no_format", "no_space_reset", "cap_next_force"),
        "letter":           WordFlags("no_space_after"),
        "uppercase-letter": WordFlags("no_space_after"),
        "numeral":          WordFlags("no_space_after"),

        "period":           WordFlags("two_spaces_after", "cap_next", "no_space_before", "not_after_period"),
        "question-mark":    WordFlags("two_spaces_after", "cap_next", "no_space_before"),
        "exclamation-mark": WordFlags("two_spaces_after", "cap_next", "no_space_before"),
        "point":            WordFlags("no_space_after", "no_space_between", "no_space_before"),
        "dot":              WordFlags("no_space_after", "no_space_between", "no_space_before"),
        "ellipsis":         WordFlags("no_space_before", "not_after_period", "cap_next"),
        "comma":            WordFlags("no_space_before"),
        "hyphen":           WordFlags("no_space_before", "no_space_after"),
        "dash":             WordFlags("no_space_before", "no_space_after"),
        "at-sign":          WordFlags("no_space_before", "no_space_after"),
        "colon":            WordFlags("no_space_before"),
        "semicolon":        WordFlags("no_space_before"),
        "apostrophe-s":     WordFlags("no_space_before"),
        "apostrophe-ess":   WordFlags("no_space_before"),
        "left-*":           WordFlags("no_cap_reset", "no_space_after"),
        "right-*":          WordFlags("no_cap_reset", "no_space_before", "no_space_reset"),
        "open-paren":       WordFlags("no_space_after"),
        "close-paren":      WordFlags("no_space_before"),
        "slash":            WordFlags("no_space_after", "no_space_before"),

        # below are two examples of Dragon custom vocabulary with formatting
        # these would have to be added to the Dragon vocabulary for users to use them
        # "len":              WordFlags("no_space_after"), # shorter name for (
        # "ren":              WordFlags("no_space_before"), # shorter name for )
    }

    # Add property aliases.
    property_map["full-stop"] = property_map["period"]
    property_map["enter"] = property_map["new-line"]

    translation_table = {
        "new-line":         "",  # lines and paragraphs are translated into new lines
        "new-paragraph":    "",  # later on.
        "enter":            "",
        "no-space":         "",
        "no-space-on":      "",
        "no-space-off":     "",

        "cap":              "",
        "caps-on":          "",
        "caps-off":         "",
        "all-caps":         "",
        "all-caps-on":      "",
        "all-caps-off":     "",
        "no-caps":          "",
        "no-caps-on":       "",
        "no-caps-off":      "",

        "spelling-cap":     "",
        "space-bar":        " ",

        "tab":              "\t",
        "period":           ".",
        "question-mark":    "?",
        "exclamation-mark": "!",
        "full-stop":        ".",
        "point":            ".",
        "dot":              ".",
        "ellipsis":        u"…",
        "comma":            ",",
        "hyphen":           "-",
        "dash":             "-",
        "em-dash":         u"—",
        "at-sign":          "@",
        "colon":            ":",
        "semicolon":        ";",
        "apostrophe-ess":   "'s",
        "apostrophe-s":     "'s",
        "open-paren":       "(",
        "close-paren":      ")",
        "slash":            "/",
        "forward-slash":    "/",
        "back-slash":       "\\",
        "backslash":        "\\",
    }

    def parse_input(self, word_str):
        spoken = word_str
        written = word_str

        # The written and spoken forms of a word may be different. Use the
        # translation table to translate special words.
        written = self.translation_table.get(word_str, word_str)
        word_flags = self.create_word_flags(word_str)
        word = Word(written, spoken, word_flags)
        # self._log.debug("Parsed input {0!r} -> {1}".format(word_str, word))
        # print ("Parsed input {0!r} -> {1}".format(word_str, word))
        return word

    def create_word_flags(self, property):
        if property in self.property_map:
            flags = self.property_map[property].clone()
        elif property.startswith("left-"):
            flags = self.property_map["left-*"].clone()
        elif property.startswith("right-"):
            flags = self.property_map["right-*"].clone()
        else:
            flags = WordFlags()
        return flags


#===========================================================================

class WordFormatter(object):

    _log = logging.getLogger("dictation.format")

    def __init__(self, state=None, parser=None,
                 two_spaces_after_period=False):
        if state:   self.state = state
        else:       self.state = StateFlags("no_space_before")
        if parser:  self.parser = parser
        else:       self.parser = WordParserTextInput()
        self.two_spaces_after_period = two_spaces_after_period

    def format_dictation(self, input_words):
        if isinstance(input_words, string_types):
            raise ValueError("Argument input_words must be a sequence of"
                             " words, but received a single string: {0!r}"
                             .format(input_words))

        # Pre-process the input words: replace spaces with hyphens for
        # special phrases.
        input_str = " ".join(input_words)
        for key in self.parser.translation_table.keys():
            if "-" in key:
                spaced_key = key.replace("-", " ")  # e.g. "at sign"
                input_str = input_str.replace(spaced_key, key)

        # Get a list again.
        input_words = input_str.split()
        formatted_words = []
        for input_word in input_words:
            word = self.parser.parse_input(input_word)
            formatted_words.append(self.apply_formatting(word))
            new_state = self.update_state(word)
            # self._log.debug("Processing {0}, formatted output: {1!r},"
            #                 " {2} -> {3}"
            #                 .format(word, formatted_words[-1],
            #                         self.state, new_state))
            self.state = new_state
        return u"".join(formatted_words)

    def apply_formatting(self, word):
        state = self.state

        # Determine prefix.
        if   word.flags.no_format:             prefix = ""
        elif state.no_space_mode:              prefix = ""
        elif word.flags.no_space_before:       prefix = ""
        elif state.no_space_before:            prefix = ""
        elif state.no_space_between and word.flags.no_space_between:
                                               prefix = ""
        elif state.two_spaces_before:
            if self.two_spaces_after_period:   prefix = "  "
            else:                              prefix = " "
        else:                                  prefix = " "

        # Determine formatted written form.
        if   word.flags.no_format:         written = word.written
        elif state.cap_mode and not word.flags.no_title_cap:
                                           written = self.capitalize_all(word.written)
        elif state.upper_mode:             written = self.upper_all(word.written)
        elif state.lower_mode:             written = self.lower_all(word.written)
        elif state.cap_next:               written = self.capitalize_first(word.written)
        elif state.cap_next_force:         written = self.capitalize_first(word.written)
        elif state.upper_next:             written = self.upper_first(word.written)
        elif state.lower_next:             written = self.lower_first(word.written)
        else:                              written = word.written

        # Remove first period character if needed.
        if (state.prev_ended_in_period
            and word.flags.not_after_period
            and written.startswith(".")):
            written = written[1:]

        # Determine suffix.
        if   word.flags.newline_after:       suffix = "\n"
        elif word.flags.two_newlines_after:  suffix = "\n\n"
        elif word.flags.spacebar:            suffix = " "
        else:                                suffix = ""

        return prefix + written + suffix

    def update_state(self, word_object):
        word = word_object.flags
        prev = self.state
        state = StateFlags()

        # Update capitalization state.
        state.cap_next_force = word.cap_next_force or (word.no_cap_reset and prev.cap_next_force)
        state.cap_next       = word.cap_next or word.cap_mode or (word.no_cap_reset and prev.cap_next)
        state.upper_next     = word.upper_next     or (word.no_cap_reset and prev.upper_next)
        state.lower_next     = word.lower_next     or (word.no_cap_reset and prev.lower_next)
        state.cap_mode       = word.cap_mode       or (prev.cap_mode   and not word.reset_cap)
        state.upper_mode     = word.upper_mode     or (prev.upper_mode and not word.reset_cap)
        state.lower_mode     = word.lower_mode     or (prev.lower_mode and not word.reset_cap)

        # Update spacing state.
        state.no_space_before   = word.no_space_after   or (prev.no_space_before and word.no_space_reset and word.no_format)
        state.two_spaces_before = word.two_spaces_after or (prev.two_spaces_before and word.no_space_reset and word.no_format)
        state.no_space_between  = word.no_space_between
        state.no_space_mode     = word.no_space_mode    or (prev.no_space_mode and not word.reset_no_space)

        # Record whether this word ended in a period.
        state.prev_ended_in_period = word_object.written.endswith(".")

        # Return newly created state.
        return state

    def capitalize_first(self, written):
        return written.capitalize()

    def _capitalize_all_function(self, match):
        return match.group(1) + match.group(2).upper()

    def capitalize_all(self, written):
        return re.sub(r"(^|\s)(\S)", self._capitalize_all_function, written)

    def upper_first(self, written):
        parts = written.split(" ", 1)
        parts[0] = parts[0].upper()
        return " ".join(parts)

    def lower_first(self, written):
        parts = written.split(" ", 1)
        parts[0] = parts[0].lower()
        return " ".join(parts)

    def upper_all(self, written):
        return written.upper()

    def lower_all(self, written):
        return written.lower()

