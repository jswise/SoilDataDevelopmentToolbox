import arcpy
import os, sys, locale, traceback
from arcpy import env

class ToolValidator(object):
  """Class for validating a tool's parameter values and controlling
  the behavior of the tool's dialog."""

  def __init__(self):
    """Setup arcpy and the list of tool parameters."""
    self.params = arcpy.GetParameterInfo()

  def initializeParameters(self):
    """Refine the properties of a tool's parameters.  This method is
    called when the tool is opened."""
    return

  def updateParameters(self):
    # Modify the values and properties of parameters before internal
    # validation is performed.  This method is called whenever a parameter
    # has been changed.

    try:
      # Query the database (param 1) to get a list of AREASYMBOLS
      # Get a list of valid SSURGO subfolders within (param 0) and make
      # sure there is a shapefile available for each AREASYMBOL.

      # Handle choice list according to the first two parameter values
      clearChoices = False
      refreshChoices = False

      if self.params[0].value is None or self.params[1].value is None:
        # One or more required parameters is missing, clear everything
        clearChoices = True
        refreshChoices = False

      else:
        # param 0 or param 1 has just been changed to a new value
        if (self.params[0].altered and not self.params[0].hasBeenValidated) or (self.params[1].altered and not self.params[1].hasBeenValidated):
          clearChoices = True
          refreshChoices = True

      if clearChoices:
        # Clear the choice list
        self.params[2].filter.list = []
        self.params[2].values = []

      if refreshChoices:
        # Clear the choice list and create a new one
        self.params[2].filter.list = []
        self.params[2].values = []

        # use searchcursor on survey boundary layer to generate list of Areasymbol values
        inputFolder = self.params[0].value.value
        surveyLayer = self.params[1].value
        queryList = list()
        surveyList = list()
        env.workspace = inputFolder

        with arcpy.da.SearchCursor(surveyLayer, ["AREASYMBOL"]) as cursor:
          for row in cursor:
            if not row[0].upper() in queryList:
              queryList.append(row[0].upper())  # for uppercase match with folder names

        selCnt = len(queryList) # number of selected surveys in the map

        # get a list of all folders under the input folder, assuming 'soil_' naming convention
        folderList = arcpy.ListWorkspaces("soil_*", "Folder")

        # check each subfolder to make sure it is a valid SSURGO dataset
        # validation: has 'soil_' prefix and contains a spatial folder and a soilsmu_a shapefile
        # and matches one of the AREASYMBOL values in the legend table

        for subFolder in folderList:
          shpAS = os.path.basename(subFolder)[5:].upper()  # uppercase match

          if shpAS in queryList:
            # this should be one of the target SSURGO dataset folder
            # add it to the choice list
            shpName = "soilmu_a_" + shpAS.lower() + ".shp"
            shpPath = os.path.join( os.path.join( inputFolder, os.path.join( subFolder, "spatial")), shpName)

            if arcpy.Exists(shpPath):
              surveyList.append(os.path.basename(subFolder))

              if len(surveyList) == selCnt:
                # found all we need, stop looking
                break

        if len(surveyList)  > 0:
          self.params[2].filter.list = surveyList
          self.params[2].values = surveyList

      if self.params[3].value:
        if not self.params[3].hasBeenValidated:
          db = self.params[3].value.value
          path = os.path.dirname(db)
          dbName = os.path.basename(db)
          fn, ext = os.path.splitext(dbName)

          if ext == "":
            ext = ".gdb"

          elif ext != ".gdb":
            ext = ".gdb"

          dbName = fn + ext
          db = os.path.join(path, dbName)
          self.params[3].value = db

      return

    except:
      tb = sys.exc_info()[2]
      tbinfo = traceback.format_tb(tb)[0]
      theMsg = tbinfo + " \n" + str(sys.exc_type)+ ": " + str(sys.exc_value) + " \n"
      #self.params[6].value = theMsg
      return

  def updateMessages(self):
    """Modify the messages created by internal validation for each tool
    parameter.  This method is called after internal validation."""

    try:
      mxd = arcpy.mapping.MapDocument("CURRENT")

    except:
      self.params[1].value = "ArcMap layers only"
      self.params[1].setErrorMessage("This ArcTool should only be run from ArcMap")
      return

    try:
      if self.params[0].value:
        if self.params[0].hasBeenValidated:

          if self.params[1].value:
            surveyLayer = self.params[1].value

            if not self.params[1].hasBeenValidated:
              if not self.params[2].filter.list:
                self.params[0].setErrorMessage("No soil survey datasets matching the boundary layer were found under the " + self.params[0].value.value + " folder")

              else:
                # warn the user if the number of surveys selected in the input layer does not match the
                # number in the choice list. This would mean that some SSURGO downloads are missing.
                queryList = list()

                with arcpy.da.SearchCursor(surveyLayer, ["AREASYMBOL"]) as cursor:
                  for row in cursor:
                    if not row[0] in queryList:
                      queryList.append(row[0])


                # compare the number in the choice list with the queryList
                if len(queryList) != len(self.params[2].filter.list):
                  missingList = list()

                  for f in queryList:
                    folder = "soil_" + f.lower()

                    if not folder in self.params[2].filter.list:
                        missingList.append(f.upper())

                  if len(missingList) == 1:
                    self.params[2].setWarningMessage("One selected survey area has no matching dataset within the downloaded SSURGO (" + ", ".join(missingList)+ ")")

                  else:
                    self.params[2].setWarningMessage(str(len(missingList)) + " selected survey areas have no matching dataset within the downloaded SSURGO (" + ", ".join(missingList)+ ")")

      if self.params[3].value:
        # determine what type of output workspace is being specified
        outputWS = self.params[3].value.value

        if not outputWS.endswith('.gdb'):
          self.params[3].setErrorMessage("Output workspace must be a file geodatabase (.gdb)")

        if (os.path.basename(outputWS).find(" ") >= 0):
          self.params[3].setErrorMessage("Illegal geodatabase name (contains a space)")

        if (os.path.basename(outputWS).find("-") >= 0):
          self.params[3].setErrorMessage("Illegal geodatabase name (contains a dash)")

        firstChar = os.path.basename(outputWS)[0:1]

        if firstChar in "1234567890":
          self.params[3].setErrorMessage("Illegal geodatabase name begins with a number (" + str(firstChar) + ")")

        if os.path.dirname(outputWS).find("-") >= 0:
          self.params[3].setErrorMessage("Illegal path contains a dash (-)")

      return

    except:
      tb = sys.exc_info()[2]
      tbinfo = traceback.format_tb(tb)[0]
      theMsg = tbinfo + " \n" + str(sys.exc_type)+ ": " + str(sys.exc_value) + " \n"
      #self.params[6].value = theMsg
      #self.params[3].value = subFolder
      return
