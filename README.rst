================================
Dragonfly Dictation Mode Grammar
================================

This repository contains a `Dragonfly`_ dictation mode grammar to be used with speech recognition engine back-ends that don't have built-in command-only/dictation-only modes or supply formatted dictation output, i.e. back-ends other than Dragon.

The dictation mode grammar will **not** properly with Dragon's formatted dictation output and will clash with its built-in modes. It is meant to be used with Kaldi, WSR or CMU Pocket Sphinx.

Grammar Command/Dictation Modes
-------------------------------

The dictation mode grammar has three command/dictation modes. These modes can be configured externally by modifying the number in the grammar's status file. The modes and associated status numbers (0-2) are defined as follows:

#. Command-only mode (status no. ``0``).
   Only commands will be recognised in this mode. Dictation on its own will not be recognised, at least not by this grammar.

#. Command and dictation mode (status no. ``1``).
   Both commands and dictation will be recognised in this mode.

#. Dictation-only mode (status no. ``2``).
   Only dictation will be recognised in this mode. This mode sets the grammar grammar as exclusive, so commands defined in other grammars will not be recognised.

Setting the Command/Dictation Mode
----------------------------------

There is a rule for enabling each mode. To enable command-only mode, say "enable command mode". For dictation-only mode, say "enable dictation mode". For command and dictation mode, say "enable command plus dictation mode". These can be configured in the ``_dictation_mode.py`` file. Please see the source code for the other useful commands.

The ``rotate-status-file.sh`` Bash script in this repository can also be used to change the dictation grammar's mode externally. For example, if the current mode is command-only mode, then running the following command will change the status file so that the mode is shifted or "rotated" to command and dictation mode::

  $ ./rotate-status-file.sh 2 .dictation-grammar-status.txt

The status in this case changes from ``0`` to ``1``. Running this command in succession will change the grammar's current dictation mode in a circuit loop between 0 and 2 (inclusive).

The grammar will process the mode change when you start speaking or whenever the grammar's ``_process_begin()`` method is called.


Usage
-----

To use the grammar, download or clone this repository and load the ``_dictation_mode.py`` file as you would load any other Dragonfly command module. You also need to have the required ``text_dictation_formatting.py`` file in the same folder or in a folder Python can import from.

To try the grammar out on its own using `Dragonfly's command-line interface`_, run the following command::

  python -m dragonfly load _dictation_mode.py


.. Links.
.. _Dragonfly: https://github.com/dictation-toolbox/dragonfly
.. _Dragonfly's command-line interface: https://dragonfly2.readthedocs.io/en/latest/cli.html
