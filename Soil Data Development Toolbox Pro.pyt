import os
import sys

from gssurgo.creategssurgobystate import CreategSSURGOByState # pylint:disable=import-error

class Toolbox(object):
    def __init__(self):
        """Define the toolbox (the name of the toolbox is the name of the
        .pyt file)."""
        self.label = 'gSSURGO Tools'
        self.alias = 'gSSURGO Tools'
        self.description = 'gSSURGO'

        self.tools = [CreategSSURGOByState]
