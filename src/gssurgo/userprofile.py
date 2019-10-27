"""Define the UserProfile class."""

import os

class UserProfile:
    """Represents the gSSURGO folder in the user's profile (e.g. C:/users/jswise/gSSURGO)."""

    gssurgo_folder = None

    def __init__(self):
        profile = os.path.expanduser('~')
        self.gssurgo_folder = os.path.join(
            profile,
            'gSSURGO'
        )
    
    def get_test_data(self):
        return os.path.join(self.gssurgo_folder, 'TestData')

