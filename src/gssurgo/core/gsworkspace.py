"""Define the GSWorkspace class."""

import os

from gssurgo.core.thing import Thing

class GSWorkspace(Thing):
    """Represents the gSSURGO folder in the user's profile (e.g. C:/users/jswise/gSSURGO)."""

    def get_path(self):
        """Return the path to the gSSURGO workspace.

        :return: The path to a folder in the user's profile
        """

        # Assume that the gSSURGO folder is the parent of the log folder.
        log_folder = self.reporter.get_log_folder()
        kp_folder = os.path.dirname(log_folder)

        # Find or create the "Workspace" folder.
        ws_folder = os.path.join(kp_folder, 'Workspace')
        os.makedirs(ws_folder, exist_ok=True)
        
        return ws_folder