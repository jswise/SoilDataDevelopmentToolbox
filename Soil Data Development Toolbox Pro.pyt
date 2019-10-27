import os
import sys

project_root = os.path.dirname(__file__)
src = os.path.join(project_root, 'src')
sys.path.append(src)

from gssurgo.creategssurgobystate import CreateGSSURGOByState # pylint:disable=import-error

class Toolbox(object):
    def __init__(self):
        """Define the toolbox (the name of the toolbox is the name of the
        .pyt file)."""
        self.label = 'gSSURGO Tools'
        self.alias = 'gSSURGO Tools'
        self.description = 'gSSURGO'

        self.tools = [CreateGSSURGOByState]
