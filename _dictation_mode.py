import os

from dragonfly import (Grammar, Choice, Key, Text, FuncContext, IntegerRef,
                       CompoundRule, Dictation, Window)

from text_dictation_formatting import WordFormatter, StateFlags

class DictationModeGrammar(Grammar):

    status_file_path = ".dictation-grammar-status.txt"

    # Define the initial word formatter state flags.
    _initial_state_flags = StateFlags(
        "no_space_before", "cap_next", "prev_ended_in_period"
    )

    def __init__(self):
        Grammar.__init__(self, self.__class__.__name__)
        self._window_stacks = {}
        self._current_window_handle = -1
        self._dictation_mode_enabled = False  # CHANGE DEFAULT ENABLED STATE HERE
        self._set_status_from_file()
        self._word_formatter = WordFormatter()

    def _write_status_to_file(self, value):
        with open(self.status_file_path, 'w+') as f:
            f.write(value)

    def _set_status_from_file(self):
        try:
            with open(self.status_file_path, 'r+') as f:
                value = True if f.read().strip() == '1' else False
        except (IOError, OSError):
            self._write_status_to_file('1')
            value = True

        self._dictation_mode_enabled = value
        if self.loaded:
            self.set_exclusiveness(value)

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

    def load(self):
        Grammar.load(self)
        self.set_exclusiveness(self._dictation_mode_enabled)

    def _process_begin(self, executable, title, handle):
        self._current_window_handle = handle

        # Enable / disable dictation mode according to the status file.
        self._set_status_from_file()

    @property
    def dictation_mode_enabled(self):
        return self._dictation_mode_enabled

    @dictation_mode_enabled.setter
    def dictation_mode_enabled(self, value):
        self._dictation_mode_enabled = value
        file_value = "1" if value else "0"
        self._write_status_to_file(file_value)
        if self.loaded:
            self.set_exclusiveness(value)

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
enabled_context = FuncContext(lambda: grammar.dictation_mode_enabled)
disabled_context = FuncContext(lambda: not grammar.dictation_mode_enabled)


class EnableRule(CompoundRule):
    context = disabled_context
    spec = "enable dictation"

    def _process_recognition(self, node, extras):
        self.grammar.dictation_mode_enabled = True


class DisableRule(CompoundRule):
    context = enabled_context
    spec = "disable dictation"

    def _process_recognition(self, node, extras):
        self.grammar.dictation_mode_enabled = False


class DictationRule(CompoundRule):
    context = enabled_context
    spec = "[<modifier>] <text>"
    extras = [
        Choice("modifier", {
            "cap": ("cap",),
            "no space": ("no-space",),
        }, default=()),
        Dictation("text", default="")
    ]

    def _process_recognition(self, node, extras):
        # Process recognized words.
        words = extras["modifier"] + extras["text"].words
        self.grammar.type_dictated_words(words)


class ScratchRule(CompoundRule):
    context = enabled_context
    spec = "scratch [that] [<n>] [times]"
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
    context = enabled_context
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


grammar.add_rule(EnableRule())
grammar.add_rule(DisableRule())
grammar.add_rule(DictationRule())
grammar.add_rule(ScratchRule())
grammar.add_rule(ScratchAndReplaceRule())
grammar.add_rule(ResetDictationRule())
grammar.load()


def unload():
    global grammar
    if grammar:
        grammar.unload()
    grammar = None

