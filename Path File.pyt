import distutils.sysconfig
import os
import site

import arcpy

class Toolbox(object):
    def __init__(self):
        """Define the toolbox (the name of the toolbox is the name of the
        .pyt file)."""
        self.label = "Toolbox"
        self.alias = ""

        # List of tool classes associated with this toolbox
        self.tools = [CreatePathFile]

class CreatePathFile(object):

    file_path = None

    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "Create Path File"
        self.description = ""
        self.canRunInBackground = False

    def getParameterInfo(self):
        """Define parameter definitions"""
        params = None
        return params

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""
        return

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        return

    def check(self):
        file_path = self.get_file_path()
        exists = os.path.exists(file_path)
        if exists:
            arcpy.AddMessage('Path file exists at {}.'.format(file_path))
            with open(file_path) as f:
                content = f.read()
            arcpy.AddMessage('Contents:\n  {}'.format(content))
        else:
            arcpy.AddMessage("The path file doesn't exist yet.")
            arcpy.AddMessage('Suggested location: {}'.format(file_path))
            arcpy.AddMessage('Suggested content: {}'.format(self.get_src()))
        return exists

    def execute(self, parameters, messages):
        file_path = self.get_file_path()
        if os.path.exists(file_path):
            arcpy.AddMessage('Path file exists ({})'.format(file_path))
            arcpy.AddMessage('Leaving existing path file in place.')
            return file_path
        src = self.get_src()
        arcpy.AddMessage('Writing "{}" to {}.'.format(src, file_path))
        with open(file_path, 'w') as f:
            f.write(src)

    def get_file_path(self):
        if not self.file_path:
            site_packages = distutils.sysconfig.get_python_lib()
            self.file_path = os.path.join(site_packages, 'gssurgo.pth')
        return self.file_path
    
    def get_src(self):
        project_root = os.path.dirname(__file__)
        return os.path.join(project_root, 'src')
