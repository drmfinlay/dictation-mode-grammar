"""
Dictation & command mode Dragonfly grammar
============================================================================

This module defines a configurable grammar for using three different
command/dictation modes. The modes can be configured externally by modifying
the number in the grammar's status file. The modes and associated status
numbers (0-2) are defined as follows:

 0. Command-only mode.
    Only commands will be recognised in this mode. Dictation on its own will
    not be recognised, at least not by this grammar.
 1. Command and dictation mode.
    Both commands and dictation will be recognised in this mode.
 2. Dictation-only mode.
    Only dictation will be recognised in this mode. This mode sets the
    grammar as exclusive, so commands defined in other grammars will not be
    recognised.

It should be noted that this module and grammar is only intended to be used
with engines such as Kaldi, WSR or CMU Pocket Sphinx that yield lowercase
text dictation output. It will *not* properly with Dragon's formatted
dictation and will clash with its built-in modes.

"""

import os

from dragonfly import (Grammar, Choice, Key, Text, FuncContext, IntegerRef,
                       CompoundRule, Dictation, Window)

from text_dictation_formatting import WordFormatter, StateFlags


class DictationModeGrammar(Grammar):

    # Set the status file path.
    status_file_path = ".dictation-grammar-status.txt"

    # Define the initial word formatter state flags.
    _initial_state_flags = StateFlags(
        "no_space_before", "cap_next", "prev_ended_in_period"
    )

    def __init__(self):
        Grammar.__init__(self, self.__class__.__name__)
        self._window_stacks = {}
        self._current_window_handle = -1
        self._status = 0  # CHANGE DEFAULT STATE HERE
        self._set_status_from_file()
        self._word_formatter = WordFormatter()

    def _write_status_to_file(self, value):
        with open(self.status_file_path, 'w+') as f:
            f.write(value)

    def _get_status_from_file(self):
        try:
            with open(self.status_file_path, 'r+') as f:
                return int(f.read().strip())
        except (IOError, OSError):
            self._write_status_to_file('1')
            return 1

    def _set_status_from_file(self):
        self._status = self._get_status_from_file()
        if self.loaded:
            self.set_exclusiveness(self._status == 2)

    def _get_window_stack(self):
        handle = self._current_window_handle
        stack = self._window_stacks.get(handle)
        if stack is None:
            stack = []
            self._window_stacks[handle] = stack
        return stack

    def _set_formatting_state_flags(self):
        handle = self._current_window_handle
        stack = self._window_stacks.get(handle)
        if not stack:
            state = self._initial_state_flags
        else:
            state = stack[len(stack) - 1][1]

        # Set the formatter flags for the latest utterance sent to the
        # current window.
        self._word_formatter.state = state.clone()

    def push_window_stack_frame(self, frame):
        self._get_window_stack().append(frame)

    def load(self):
        Grammar.load(self)
        self.set_exclusiveness(self._status == 2)

    def _process_begin(self, executable, title, handle):
        self._current_window_handle = handle

        # Enable / disable dictation mode according to the status file.
        self._set_status_from_file()

    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, value):
        value = int(value)
        self._status = value
        self._write_status_to_file(str(value))
        if self.loaded:
            self.set_exclusiveness(value == 2)

    def type_dictated_words(self, words):
        # Set the formatting state for the current window.
        self._set_formatting_state_flags()

        # Format the words and type them.
        text = self._word_formatter.format_dictation(words)
        Text(text).execute()

        # Save the utterance state.
        current_state = self._word_formatter.state.clone()
        frame = (len(text), current_state)
        self._get_window_stack().append(frame)

    def do_scratch_n_times(self, n):
        for _ in range(n):
            try:
                # Get the number of characters to delete from the current
                # window's stack. Discard the state flags.
                scratch_number, _ = self._get_window_stack().pop()
                Key("backspace:%d" % scratch_number).execute()
            except IndexError:
                handle = self._current_window_handle
                window = Window.get_window(handle)
                exe = os.path.basename(window.executable)
                title = window.title
                print("Nothing in scratch memory for %r window "
                      "(title=%r, id=%d)" % (exe, title, handle))
                break

    def clear_formatting_state(self, option):
        if option == "current":
            stack = self._get_window_stack()
            while stack:
                stack.pop()
        elif option == "all":
            self._window_stacks.clear()


# Initialize the grammar here so we can use it to keep track of state.
grammar = DictationModeGrammar()
enabled_context = FuncContext(lambda: grammar.status)
disabled_context = FuncContext(lambda: not grammar.status)


class EnableRule(CompoundRule):
    spec = "enable <mode>"
    extras = [
        Choice("mode", {
            "command [only] mode": 0,
            "dictation plus command mode": 1,
            "command plus dictation mode": 1,
            "dictation [only] mode ": 2,
        }, default=1)
    ]

    def _process_recognition(self, node, extras):
        self.grammar.status = extras["mode"]


class DisableRule(CompoundRule):
    context = enabled_context
    spec = "disable dictation"

    def _process_recognition(self, node, extras):
        self.grammar.status = 0


class DisabledDictationRule(CompoundRule):
    context = disabled_context
    spec = "dictation <text>"
    extras = [Dictation("text", default="")]

    def _process_recognition(self, node, extras):
        print("\n\n----DICTATION MODE IS DISABLED----\n\n")
        self.grammar.type_dictated_words(extras["text"].words)


class DictationRule(CompoundRule):
    context = enabled_context
    spec = "[<modifier>] <text> [mimic <mimic_text>]"
    extras = [
        Choice("modifier", {
            "dictation": (),
            "cap": ("cap",),
            "no space": ("no-space",),
        }, default=()),
        Dictation("text", default=""),
        Dictation("mimic_text", default="")
    ]

    def _process_recognition(self, node, extras):
        # Process recognized words.
        words = extras["modifier"] + extras["text"].words
        self.grammar.type_dictated_words(words)
        mimic_text = extras["mimic_text"].format()
        if mimic_text:
            self.grammar.engine.mimic(mimic_text)


class ScratchRule(CompoundRule):
    context = enabled_context
    spec = "(scratch | scratch that [<n> times])"
    extras = [
        IntegerRef("n", 1, 20, default=1)
    ]

    def _process_recognition(self, node, extras):
        self.grammar.do_scratch_n_times(extras["n"])


class ScratchAndReplaceRule(CompoundRule):
    context = enabled_context
    spec = "make that <text>"
    extras = [
        Dictation("text", default="")
    ]

    def _process_recognition(self, node, extras):
        self.grammar.do_scratch_n_times(1)
        self.grammar.type_dictated_words(extras["text"].words)


class ResetDictationRule(CompoundRule):
    spec = "reset dictation [<option>]"
    extras = [
        Choice("option", {
            "all": "all",
            "current": "current",
        }, default="all")
    ]

    def _process_recognition(self, node, extras):
        option = extras["option"]
        self.grammar.clear_formatting_state(option)


class StateChangeRule(CompoundRule):
    context = enabled_context
    spec = "<state_change>"
    extras = [
        Choice("state_change", {
            "[start] new sentence": ("cap_next", "prev_ended_in_period"),
            "[start] new paragraph": ("no_space_before", "cap_next", "prev_ended_in_period"),
        })
    ]

    def _process_recognition(self, node, extras):
        # Append the new state flags to the current window's stack using length 0.
        frame = (0, StateFlags(*extras["state_change"]))
        self.grammar.push_window_stack_frame(frame)


grammar.add_rule(EnableRule())
grammar.add_rule(DisableRule())
grammar.add_rule(DisabledDictationRule())
grammar.add_rule(DictationRule())
grammar.add_rule(ScratchRule())
grammar.add_rule(ScratchAndReplaceRule())
grammar.add_rule(ResetDictationRule())
grammar.add_rule(StateChangeRule())
grammar.load()


def unload():
    global grammar
    if grammar:
        grammar.unload()
    grammar = None
