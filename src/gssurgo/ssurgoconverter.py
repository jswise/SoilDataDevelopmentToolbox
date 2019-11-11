"""Define the SSURGOConverter class."""

import csv
import datetime
import json
import locale
from operator import itemgetter, attrgetter
import os
import string
import sys
import time
import traceback
import xml.etree.cElementTree as ET

import arcpy
from arcpy import env

from gssurgo.core.thing import Thing

class SSURGOConverter(Thing):
    """Allow batch appending of SSURGO soil shapefiles and soil attribute tables into a single file geodatabase.

    Based on code by Steve Peaslee, National Soil Survey Center, Lincoln, Nebraska.

    Requires input dataset structure to follow the NRCS standard for Geospatial data (eg. soil_ne109/spatial and soil_ne109/tabular).

    Merge order is based upon sorted extent coordinates

    For the attribute data, we use an XML workspace document to define FGDB schema and read the tables from the SSURGO template database.
    These xml files should reside in the same folder as this script. See the GetML function for more info.
    
    Things yet to do:
    
    1. Update metadata for each XML workspace document
    2. Test implementation of ITRF00 datum transformation
    """

    def Number_Format(self, num, places=0, bCommas=True):
        try:
        # Format a number according to locality and given places
            locale.setlocale(locale.LC_ALL, "")
            if bCommas:
                theNumber = locale.format("%.*f", (places, num), True)

            else:
                theNumber = locale.format("%.*f", (places, num), False)
            return theNumber

        except Exception as e:
            self.raise_error(str(e))
        
    
    def CreateSSURGO_DB(self, outputWS, inputXML, areasymbolList, aliasName):
        # Create new 10.0 File Geodatabase using XML workspace document
        #
        try:
            if not arcpy.Exists(inputXML):
                self.raise_error(" \nMissing input file: " + inputXML)

            outputFolder = os.path.dirname(outputWS)
            gdbName = os.path.basename(outputWS)

            if arcpy.Exists(os.path.join(outputFolder, gdbName)):
                arcpy.Delete_management(os.path.join(outputFolder, gdbName))

            self.info(" \nCreating new geodatabase (" + gdbName + ") in " + outputFolder)

            env.XYResolution = "0.001 Meters"
            env.XYTolerance = "0.01 Meters"

            arcpy.CreateFileGDB_management(outputFolder, gdbName, "10.0")

            # The following command will fail when the user only has a Basic license
            arcpy.ImportXMLWorkspaceDocument_management(os.path.join(outputFolder, gdbName), inputXML, "SCHEMA_ONLY")

            # Create indexes for cointerp here.
            # If it works OK, incorporate these indexes into the xml workspace document
            try:
                pass

            except:
                self.warning(" \nUnable to index the cointerp table")

            if not arcpy.Exists(os.path.join(outputFolder, gdbName)):
                self.raise_error("Failed to create new geodatabase")

            env.workspace = os.path.join(outputFolder, gdbName)
            tblList = arcpy.ListTables()

            if len(tblList) < 50:
                self.raise_error("Output geodatabase has only " + str(len(tblList)) + " tables")

            # Alter aliases for featureclasses
            if aliasName != "":
                try:
                    arcpy.AlterAliasName("MUPOLYGON", "Map Unit Polygons - " + aliasName)
                    arcpy.AlterAliasName("MUPOINT", "Map Unit Points - " + aliasName)
                    arcpy.AlterAliasName("MULINE", "Map Unit Lines - " + aliasName)
                    arcpy.AlterAliasName("FEATPOINT", "Special Feature Points - " + aliasName)
                    arcpy.AlterAliasName("FEATLINE", "Special Feature Lines - " + aliasName)
                    arcpy.AlterAliasName("SAPOLYGON", "Survey Boundaries - " + aliasName)

                except:
                    pass

            # arcpy.RefreshCatalog(outputFolder)

            return True

        except Exception as e:
            self.raise_error(str(e))
    
    def GetTableList(self, outputWS):
        # Query mdstattabs table to get list of input text files (tabular) and output tables
        # This function assumes that the MDSTATTABS table is already present and populated
        # in the output geodatabase per XML Workspace Document.
        #
        # Skip all 'MDSTAT' tables. They are static.
        #
        try:
            tblList = list()
            mdTbl = os.path.join(outputWS, "mdstattabs")

            if not arcpy.Exists(outputWS):
                self.raise_error("Missing output geodatabase: " + outputWS)

            if not arcpy.Exists(mdTbl):
                self.raise_error("Missing mdstattabs table in output geodatabase")

            else:
                # got the mdstattabs table, create list
                #mdFields = ('tabphyname','iefilename')
                mdFields = ('tabphyname')

                with arcpy.da.SearchCursor(mdTbl, mdFields) as srcCursor: # pylint:disable=no-member
                    for rec in srcCursor:
                        tblName = rec[0]
                        if not tblName.startswith('mdstat') and not tblName in ('mupolygon', 'muline', 'mupoint', 'featline', 'featpoint', 'sapolygon'):
                            tblList.append(rec[0])

            return tblList

        except Exception as e:
            self.raise_error(str(e))
    
    def GetTemplateDate(self, newDB, areaSym):
        # Get SAVEREST date from previously existing Template database
        # Use it to compare with the date from the WSS dataset
        # If the existing database is same or newer, it will be kept and the WSS version skipped.
        # This function is also used to test the output geodatabase to make sure that
        # the tabular import process was successful.
        #
        try:
            if not arcpy.Exists(newDB):
                return 0

            saCatalog = os.path.join(newDB, "SACATALOG")
            dbDate = 0
            whereClause = "UPPER(AREASYMBOL) = '" + areaSym.upper() + "'"

            if arcpy.Exists(saCatalog):
                with arcpy.da.SearchCursor(saCatalog, ("SAVEREST"), where_clause=whereClause) as srcCursor: # pylint:disable=no-member
                    for rec in srcCursor:
                        dbDate = str(rec[0]).split(" ")[0]

                del saCatalog
                del newDB
                return dbDate

            else:
                # unable to open SACATALOG table in existing dataset
                return 0

        except Exception as e:
            self.raise_error('GetTemplateDate: {}'.format(str(e)))

    def SSURGOVersionTxt(self, tabularFolder):
        # For future use. Should really create a new table for gSSURGO in order to implement properly.
        #
        # Get SSURGO version from the Template database "SYSTEM Template Database Information" table
        # or from the tabular/version.txt file, depending upon which is being imported.
        # Compare the version number (first digit) to a hardcoded version number which should
        # be theoretically tied to the XML workspace document that accompanies the scripts.

        try:
            # Get SSURGOversion number from version.txt
            versionTxt = os.path.join(tabularFolder, "version.txt")

            if arcpy.Exists(versionTxt):
                # read just the first line of the version.txt file
                fh = open(versionTxt, "r")
                txtVersion = int(fh.readline().split(".")[0])
                fh.close()
                return txtVersion

            else:
                # Unable to compare vesions. Warn user but continue
                self.warning("Unable to find tabular file: version.txt")
                return 0

        except Exception as e:
            self.raise_error(str(e))
    
    def SSURGOVersionDB(self, templateDB):
        # For future use. Should really create a new table for gSSURGO in order to implement properly.
        #
        # Get SSURGO version from the Template database "SYSTEM Template Database Information" table

        try:
            if not arcpy.Exists(templateDB):
                self.raise_error("Missing input database (" + templateDB + ")")

            systemInfo = os.path.join(templateDB, "SYSTEM - Template Database Information")

            if arcpy.Exists(systemInfo):
                # Get SSURGO Version from template database
                dbVersion = 0

                with arcpy.da.SearchCursor(systemInfo, "*", "") as srcCursor: # pylint:disable=no-member
                    for rec in srcCursor:
                        if rec[0] == "SSURGO Version":
                            dbVersion = int(str(rec[2]).split(".")[0])

                del systemInfo
                del templateDB
                return dbVersion

            else:
                # Unable to open SYSTEM table in existing dataset
                # Warn user but continue
                self.raise_error("Unable to open 'SYSTEM - Template Database Information'")


        except Exception as e:
            self.raise_error(str(e))

    def GetTableInfo(self, newDB):
        # Adolfo's function
        #
        # Retrieve physical and alias names from MDSTATTABS table and assigns them to a blank dictionary.
        # Stores physical names (key) and aliases (value) in a Python dictionary i.e. {chasshto:'Horizon AASHTO,chaashto'}
        # Fieldnames are Physical Name = AliasName,IEfilename

        try:
            tblInfo = dict()

            # Open mdstattabs table containing information for other SSURGO tables
            theMDTable = "mdstattabs"
            env.workspace = newDB


            # Establishes a cursor for searching through field rows. A search cursor can be used to retrieve rows.
            # This method will return an enumeration object that will, in turn, hand out row objects
            if arcpy.Exists(os.path.join(newDB, theMDTable)):

                fldNames = ["tabphyname","tablabel","iefilename"]
                with arcpy.da.SearchCursor(os.path.join(newDB, theMDTable), fldNames) as rows: # pylint:disable=no-member

                    for row in rows:
                        # read each table record and assign 'tabphyname' and 'tablabel' to 2 variables
                        physicalName = row[0]
                        aliasName = row[1]
                        importFileName = row[2]

                        # i.e. {chaashto:'Horizon AASHTO',chaashto}; will create a one-to-many dictionary
                        # As long as the physical name doesn't exist in dict() add physical name
                        # as Key and alias as Value.
                        #if not physicalName in tblAliases:
                        if not importFileName in tblInfo:
                            tblInfo[importFileName] = physicalName, aliasName

                del theMDTable

                return tblInfo

            else:
                # The mdstattabs table was not found
                self.raise_error("Missing mdstattabs table")
                # return tblInfo


        except Exception as e:
            self.raise_error(str(e))

    def ImportMDTables(self, newDB, dbList):
        # Import as single set of metadata tables from first survey area's Access database
        # These tables contain table information, relationship classes and domain values
        # They have tobe populated before any of the other tables
        #
        # mdstatdomdet
        # mdstatdommas
        # mdstatidxdet
        # mdstatidxmas
        # mdstatrshipdet
        # mdstatrshipmas
        # mdstattabcols
        # mdstattabs

        try:
            # Create list of tables to be imported
            tables = ['mdstatdommas', 'mdstatidxdet', 'mdstatidxmas', 'mdstatrshipdet', 'mdstatrshipmas', 'mdstattabcols', 'mdstattabs', 'mdstatdomdet']

            accessDB = dbList[0] # source database for metadata table data

            # Process list of text files
            # 
            for table in tables:
                arcpy.SetProgressorLabel("Importing " + table + "...")
                inTbl = os.path.join(accessDB, table)
                outTbl = os.path.join(newDB, table)

                if arcpy.Exists(inTbl) and arcpy.Exists(outTbl):
                    # Create cursor for all fields to populate the current table
                    #
                    # For a geodatabase, I need to remove OBJECTID from the fields list
                    fldList = arcpy.Describe(outTbl).fields
                    fldNames = list()
                    fldLengths = list()

                    for fld in fldList:
                        if fld.type != "OID":
                            fldNames.append(fld.name.lower())

                            if fld.type.lower() == "string":
                                fldLengths.append(fld.length)

                            else:
                                fldLengths.append(0)

                    if len(fldNames) == 0:
                        self.raise_error("Failed to get field names for " + outTbl)

                    with arcpy.da.InsertCursor(outTbl, fldNames) as outcur: # pylint:disable=no-member
                        incur = arcpy.da.SearchCursor(inTbl, fldNames) # pylint:disable=no-member
                        # counter for current record number
                        iRows = 0

                        #try:
                        # Use csv reader to read each line in the text file
                        for row in incur:
                            # replace all blank values with 'None' so that the values are properly inserted
                            # into integer values otherwise insertRow fails
                            # truncate all string values that will not fit in the target field
                            newRow = list()
                            fldNo = 0

                            for val in row:  # mdstatdomdet was having problems with this 'for' loop. No idea why.
                                fldLen = fldLengths[fldNo]

                                if fldLen > 0 and not val is None:
                                    val = val[0:fldLen]

                                newRow.append(val)

                                fldNo += 1

                            try:
                                outcur.insertRow(newRow)

                            except:
                                self.raise_error("Error handling line " + self.Number_Format(iRows, 0, True) + " of " + inTbl)

                            iRows += 1

                        if iRows < 63:
                            # the smallest table (msrmas.txt) currently has 63 records.
                            self.raise_error(table + " has only " + str(iRows) + " records")

                else:
                    self.raise_error("Required table '" + table + "' not found in " + newDB)

            return True

        except Exception as e:
            self.raise_error(str(e))

    def ImportMDTabular(self, newDB, tabularFolder, codePage):
        # Import a single set of metadata text files from first survey area's tabular
        # These files contain table information, relationship classes and domain values
        # They have tobe populated before any of the other tables
        #
        # mdstatdomdet
        # mdstatdommas
        # mdstatidxdet
        # mdstatidxmas
        # mdstatrshipdet
        # mdstatrshipmas
        # mdstattabcols
        # mdstattabs
        #codePage = 'cp1252'

        try:
            # Create list of text files to be imported
            txtFiles = ['mstabcol', 'msrsdet', 'mstab', 'msrsmas', 'msdommas', 'msidxmas', 'msidxdet',  'msdomdet']

            # Create dictionary containing text filename as key, table physical name as value
            tblInfo = {u'mstabcol': u'mdstattabcols', u'msrsdet': u'mdstatrshipdet', u'mstab': u'mdstattabs', u'msrsmas': u'mdstatrshipmas', u'msdommas': u'mdstatdommas', u'msidxmas': u'mdstatidxmas', u'msidxdet': u'mdstatidxdet', u'msdomdet': u'mdstatdomdet'}

            csv.field_size_limit(128000)

            # Process list of text files
            for txtFile in txtFiles:

                # Get table name and alias from dictionary
                if txtFile in tblInfo:
                    tbl = tblInfo[txtFile]

                else:
                    self.raise_error("Required input textfile '" + txtFile + "' not found in " + tabularFolder)

                arcpy.SetProgressorLabel("Importing " + tbl + "...")

                # Full path to SSURGO text file
                txtPath = os.path.join(tabularFolder, txtFile + ".txt")

                # continue import process only if the target table exists

                if arcpy.Exists(tbl):
                    # Create cursor for all fields to populate the current table
                    #
                    # For a geodatabase, I need to remove OBJECTID from the fields list
                    fldList = arcpy.Describe(os.path.join(newDB, tbl)).fields
                    fldNames = list()
                    fldLengths = list()

                    for fld in fldList:
                        if fld.type != "OID":
                            fldNames.append(fld.name)

                            if fld.type.lower() == "string":
                                fldLengths.append(fld.length)

                            else:
                                fldLengths.append(0)

                    if len(fldNames) == 0:
                        self.raise_error("Failed to get field names for " + tbl)

                    with arcpy.da.InsertCursor(os.path.join(newDB, tbl), fldNames) as cursor: # pylint:disable=no-member
                        # counter for current record number
                        iRows = 1  # input textfile line number

                        if os.path.isfile(txtPath):

                            # Use csv reader to read each line in the text file
                            for rowInFile in csv.reader(open(txtPath, newline=''), delimiter='|'):
                                # , quotechar="'"
                                # replace all blank values with 'None' so that the values are properly inserted
                                # into integer values otherwise insertRow fails
                                # truncate all string values that will not fit in the target field
                                newRow = list()
                                fldNo = 0
                                fixedRow = rowInFile # For Python 3, don't fix it.
                                # fixedRow = [x.decode(codePage) for x in rowInFile]  # handle non-utf8 characters
                                #.decode('iso-8859-1').encode('utf8')
                                #fixedRow = [x.decode('iso-8859-1').encode('utf8') for x in rowInFile]
                                #fixedRow = [x.decode('iso-8859-1') for x in rowInFile]

                                for val in fixedRow:  # mdstatdomdet was having problems with this 'for' loop. No idea why.
                                    fldLen = fldLengths[fldNo]

                                    if val == '':
                                        val = None

                                    elif fldLen > 0:
                                        val = val[0:fldLen]

                                    newRow.append(val)

                                    fldNo += 1

                                try:
                                    cursor.insertRow(newRow)

                                except:
                                    self.raise_error("Error handling line " + self.Number_Format(iRows, 0, True) + " of " + txtPath)

                                iRows += 1

                            if iRows < 63:
                                # msrmas.txt has the least number of records
                                self.raise_error(tbl + " has only " + str(iRows) + " records. Check 'md*.txt' files in tabular folder")

                        else:
                            self.raise_error("Missing tabular data file (" + txtPath + ")")

                else:
                    self.raise_error("Required table '" + tbl + "' not found in " + newDB)

            return True

        except Exception as e:
            self.raise_error(str(e))

    def ImportTables(self, outputWS, dbList, dbVersion):
        #
        # Import tables from an Access Template database. Does not require text files, but
        # the Access database must be populated and it must reside in the tabular folder and
        # it must be named 'soil_d_<AREASYMBOL>.mdb'
        # Origin: SSURGO_Convert_to_Geodatabase.py

        try:
            tblList = self.GetTableList(outputWS)

            # Something is slowing up the CONUS gSSURGO database creation at the end of this function. Could it be the
            # relationshipclasses triggering new indexes?
            arcpy.SetProgressorLabel("\tAdding additional relationships for sdv* tables...")

            if len(tblList) == 0:
                self.raise_error("No tables found in " +  outputWS)

            # Set up enforcement of unique keys for SDV tables
            #
            dIndex = dict()  # dictionary storing field index for primary key of each SDV table
            dKeys = dict()  # dictionary containing a list of key values for each SDV table
            # dFields = dict() # dictionary containing list of fields for eacha SDV table

            # keyIndx = dict()  # dictionary containing key field index number for each SDV table
            keyFields = dict() # dictionary containing a list of key field names for each SDV table
            keyFields['sdvfolderattribute'] = "attributekey"
            keyFields['sdvattribute'] = "attributekey"
            keyFields['sdvfolder'] = "folderkey"
            keyFields['sdvalgorithm'] = "algorithmsequence"
            sdvTables = ['sdvfolderattribute', 'sdvattribute', 'sdvfolder', 'sdvalgorithm']

            for sdvTbl in sdvTables:

                keyField = keyFields[sdvTbl]

                fldList = arcpy.Describe(os.path.join(outputWS, sdvTbl)).fields
                fldNames = list()

                for fld in fldList:
                    if fld.type != "OID":
                        fldNames.append(fld.name.lower())

                #dFields[sdvTbl] = fldNames                 # store list of fields for this SDV table
                dIndex[sdvTbl] = fldNames.index(keyField)  # store field index for primary key in this SDV table
                dKeys[sdvTbl] = []                         # initialize key values list for this SDV table

            # End of enforce unique keys setup...


            self.info(" \nImporting tabular data from SSURGO Template databases...")
            iCntr = 0

            for inputDB in dbList:
                iCntr += 1

                # Check SSURGO version in the Template database and make sure it matches this script
                ssurgoVersion = self.SSURGOVersionDB(inputDB)

                if ssurgoVersion != dbVersion:
                    self.raise_error("Tabular data in " + inputDB + " (SSURGO Version " + str(ssurgoVersion) + ") is not supported")

                # Check the input Template database to make sure it contains data from the Import process
                # Really only checking last record (normally only one record in table). Multiple surveys would fail.
                saCatalog = os.path.join(inputDB, "SACATALOG")

                if arcpy.Exists(saCatalog):
                    # parse Areasymbol from database name. If the geospatial naming convention isn't followed,
                    # then this will not work.
                    fnAreasymbol = inputDB[-9:][0:5].upper()
                    dbAreaSymbol = ""

                    with arcpy.da.SearchCursor(saCatalog, ("AREASYMBOL")) as srcCursor: # pylint:disable=no-member
                        for rec in srcCursor:
                            # Get Areasymbol from SACATALOG table, assuming just one survey is present in the database
                            dbAreaSymbol = rec[0]

                    if dbAreaSymbol != fnAreasymbol:
                        if dbAreaSymbol != "":
                            self.raise_error("Survey data in " + os.path.basename(inputDB) + " does not match filename")

                        else:
                            self.raise_error("Unable to get survey area information from " + os.path.basename(inputDB))

                else:
                    # unable to open SACATALOG table in existing dataset
                    # return False which will result in the existing dataset being overwritten by a new WSS download
                    self.raise_error("SACATALOG table not found in " + os.path.basename(inputDB))

                arcpy.SetProgressor("step", "Importing " +  dbAreaSymbol + " tabular data (" + self.Number_Format(iCntr, 0, True) + " of " + self.Number_Format(len(tblList), 0, True) + ")", 0, (len(tblList)) + 1, 1)

                for tblName in tblList:
                    outputTbl = os.path.join(outputWS, tblName)
                    inputTbl = os.path.join(inputDB, tblName)

                    if arcpy.Exists(inputTbl):
                        if tblName != "month" or (tblName == "month" and int(arcpy.GetCount_management(outputTbl).getOutput(0)) < 12):
                            arcpy.SetProgressorLabel("Importing " +  dbAreaSymbol + " tabular data (" + self.Number_Format(iCntr, 0, True) + " of " + self.Number_Format(len(dbList), 0, True) + ") : " + tblName)
                            mdbFields = arcpy.Describe(inputTbl).fields
                            mdbFieldNames = list()

                            for inFld in mdbFields:
                                if not inFld.type == "OID":
                                    mdbFieldNames.append(inFld.name.upper())

                            if not tblName in sdvTables:
                                # Import all tables except SDV*

                                with arcpy.da.SearchCursor(inputTbl, mdbFieldNames) as inCursor: # pylint:disable=no-member
                                    #outFields = inCursor.fields

                                    with arcpy.da.InsertCursor(outputTbl, mdbFieldNames) as outCursor: # pylint:disable=no-member
                                        for inRow in inCursor:
                                            outCursor.insertRow(inRow)

                            else:
                                # Import SDV tables while enforcing unique key values
                                # 'sdvfolderattribute', 'sdvattribute', 'sdvfolder', 'sdvalgorithm'
                                #
                                with arcpy.da.SearchCursor(inputTbl, mdbFieldNames) as inCursor: # pylint:disable=no-member

                                    with arcpy.da.InsertCursor(outputTbl, mdbFieldNames) as outCursor: # pylint:disable=no-member
                                        for inRow in inCursor:
                                            keyVal = inRow[dIndex[tblName]]

                                            if not keyVal in dKeys[tblName]:
                                                dKeys[tblName].append(keyVal)
                                                outCursor.insertRow(inRow)

                                if inputTbl == "sdvattribute":
                                    # Check to see if sainterp contains anything that is not in sdvattribute.nasisrulename.
                                    # If so, try to get it from os.path.join(os.path.dirname(sys.argv[0]), MissingInterps.gdb)
                                    pass

                    else:
                        err = "\tMissing input table: " + inputTbl
                        self.raise_error(err)

                    arcpy.SetProgressorPosition()

                arcpy.ResetProgressor()

            # Add attribute index for each SDV table
            self.warning(" \nSkipping indexes for sdv tables")

            return True

        except Exception as e:
            self.raise_error(str(e))

    def ImportTabular(self, newDB, dbList, dbVersion, codePage):
        # Use csv reader method of importing text files into geodatabase for those
        # that do not have a populated SSURGO database
        #
        # 2015-12-16 Need to eliminate duplicate records in sdv* tables. Also need to index primary keys
        # for each of these tables.
        #
        try:
            # new code from ImportTables
            #codePage = 'cp1252'

            tblList = self.GetTableList(newDB)

            if len(tblList) == 0:
                self.raise_error("No tables found in " +  newDB)

            self.info(" \nImporting tabular data...")
            
            iCntr = 0

            # Set up enforcement of unique keys for SDV tables
            #
            sdvTables = ['sdvfolderattribute', 'sdvattribute', 'sdvfolder', 'sdvalgorithm']
            dIndex = dict()  # dictionary storing field index for primary key of each SDV table
            dKeys = dict()  # dictionary containing a list of key values for each SDV table
            dFields = dict() # dictionary containing list of fields for eacha SDV table

            # keyIndx = dict()  # dictionary containing key field index number for each SDV table
            keyFields = dict() # dictionary containing a list of key field names for each SDV table
            keyFields['sdvfolderattribute'] = "attributekey"
            keyFields['sdvattribute'] = "attributekey"
            keyFields['sdvfolder'] = "folderkey"
            keyFields['sdvalgorithm'] = "algorithmsequence"

            for sdvTbl in sdvTables:
                #sdvTbl = os.path.join(outputWS, "sdvfolderattribute")
                #indx = keyIndx[sdvTbl]
                keyField = keyFields[sdvTbl]

                fldList = arcpy.Describe(os.path.join(newDB, sdvTbl)).fields
                fldNames = list()

                for fld in fldList:
                    if fld.type != "OID":
                        fldNames.append(fld.name.lower())

                dFields[sdvTbl] = fldNames                 # store list of fields for this SDV table
                dIndex[sdvTbl] = fldNames.index(keyField)  # store field index for primary key in this SDV table
                dKeys[sdvTbl] = []                         # initialize key values list for this SDV table

            
            # Add SDV* table relationships. These aren't part of the XML workspace doc as of FY2018 gSSURGO
            # Not normally necessary, but useful for diagnostics

            for inputDB in dbList:
                iCntr += 1
                newFolder = os.path.dirname(os.path.dirname(inputDB)) # survey dataset folder

                # parse Areasymbol from database name. If the geospatial naming convention isn't followed,
                # then this will not work.
                soilsFolder = os.path.dirname(os.path.dirname(inputDB))

                fnAreasymbol = soilsFolder[(soilsFolder.rfind("_") + 1):].upper()
                newFolder = os.path.dirname(os.path.dirname(inputDB)) # survey dataset folder

                # get database name from file listing in the new folder
                env.workspace = newFolder

                # move to tabular folder
                env.workspace = os.path.join(newFolder, "tabular")

                # Using Adolfo's csv reader method to import tabular data from text files...
                tabularFolder = os.path.join(newFolder, "tabular")

                # if the tabular directory is empty return False
                if len(os.listdir(tabularFolder)) < 1:
                    self.raise_error("No text files found in the tabular folder")

                # Make sure that input tabular data has the correct SSURGO version for this script
                ssurgoVersion = self.SSURGOVersionTxt(tabularFolder)

                if ssurgoVersion != dbVersion:
                    self.raise_error("Tabular data in " + tabularFolder + " (SSURGO Version " + str(ssurgoVersion) + ") is not supported")

                # Create a dictionary with table information
                tblInfo = self.GetTableInfo(newDB)

                # Create a list of textfiles to be imported. The import process MUST follow the
                # order in this list in order to maintain referential integrity. This list
                # will need to be updated if the SSURGO data model is changed in the future.
                #
                txtFiles = ["distmd","legend","distimd","distlmd","lareao","ltext","mapunit", \
                "comp","muaggatt","muareao","mucrpyd","mutext","chorizon","ccancov","ccrpyd", \
                "cdfeat","cecoclas","ceplants","cerosnac","cfprod","cgeomord","chydcrit", \
                "cinterp","cmonth", "cpmatgrp", "cpwndbrk","crstrcts","csfrags","ctxfmmin", \
                "ctxmoicl","ctext","ctreestm","ctxfmoth","chaashto","chconsis","chdsuffx", \
                "chfrags","chpores","chstrgrp","chtext","chtexgrp","chunifie","cfprodo","cpmat","csmoist", \
                "cstemp","csmorgc","csmorhpp","csmormr","csmorss","chstr","chtextur", \
                "chtexmod","sacatlog","sainterp","sdvalgorithm","sdvattribute","sdvfolder","sdvfolderattribute"]
                # Need to add featdesc import as a separate item (ie. spatial\soilsf_t_al001.txt: featdesc)

                # Static Metadata Table that records the metadata for all columns of all tables
                # that make up the tabular data set.
                # mdstattabsTable = os.path.join(env.workspace, "mdstattabs")

                # set progressor object which allows progress information to be passed for every merge complete
                #arcpy.SetProgressor("step", "Importing " +  fnAreasymbol + " tabular  (" + self.Number_Format(iCntr, 0, True) + " of " + self.Number_Format(len(dbList), 0, True) + ")" , 0, len(txtFiles) + 1, 1)

                #csv.field_size_limit(sys.maxsize)
                csv.field_size_limit(512000)

                # For cointerp, adjust for missing columns
                #  x = fldNames[0:7]
                #  y = fldNames[12:14]
                #  z = fldNames[16:20]

                # Need to import text files in a specific order or the MS Access database will
                # return an error due to table relationships and key violations
                for txtFile in txtFiles:

                    # Get table name and alias from dictionary
                    if txtFile in tblInfo:
                        tbl, _ = tblInfo[txtFile]

                    else:
                        self.raise_error("Textfile reference '" + txtFile + "' not found in 'mdstattabs table'")

                    arcpy.SetProgressorLabel("Importing " +  fnAreasymbol + " tabular data  (" + self.Number_Format(iCntr, 0, True) + " of " + self.Number_Format(len(dbList), 0, True) + ") :   " + tbl)

                    # Full path to SSURGO text file
                    txtPath = os.path.join(tabularFolder, txtFile + ".txt")

                    # continue if the target table exists
                    if arcpy.Exists(tbl):
                        # Create cursor for all fields to populate the current table
                        #
                        # For a geodatabase, I need to remove OBJECTID from the fields list
                        fldList = arcpy.Describe(tbl).fields
                        fldNames = list()
                        #fldLengths = list()

                        for fld in fldList:
                            if fld.type != "OID":
                                fldNames.append(fld.name)

                        if len(fldNames) == 0:
                            self.raise_error("Failed to get field names for " + tbl)

                        if not tbl in ['sdvfolderattribute', 'sdvattribute', 'sdvfolder', 'sdvalgorithm']:
                            # Import all tables except SDV
                            #
                            time.sleep(0.05)  # Occasional write errors
                            
                            if tbl.endswith("text"):
                                with arcpy.da.InsertCursor(os.path.join(newDB, tbl), fldNames) as cursor: # pylint:disable=no-member
                                    # counter for current record number
                                    iRows = 1  # input textfile line number

                                    #if os.path.isfile(txtPath):
                                    if arcpy.Exists(txtPath):

                                        try:
                                            # Use csv reader to read each line in the text file
                                            time.sleep(0.5)  # trying to prevent error reading text file

                                            for rowInFile in csv.reader(open(txtPath, newline=''), delimiter='|', quotechar='"'):
                                                # replace all blank values with 'None' so that the values are properly inserted
                                                # into integer values otherwise insertRow fails
                                                fixedRow = rowInFile # For Python 3, don't fix it.
                                                # fixedRow = [x.decode(codePage) if x else None for x in rowInFile]  # handle non-utf8 characters
                                                #fixedRow = [x if x else None for x in rowInFile]  # figure out which tables have non-utf8 characters
                                                cursor.insertRow(fixedRow) # was fixedRow
                                                iRows += 1

                                        except:
                                            self.warning(" \n" + str(fixedRow))
                                            err = "1: Error writing line " + self.Number_Format(iRows, 0, True) + " from " + txtPath
                                            self.raise_error(err)

                                    else:
                                        self.raise_error("Missing tabular data file (" + txtPath + ")")

                            elif tbl == "cointerp":

                                with arcpy.da.InsertCursor(os.path.join(newDB, tbl), fldNames) as cursor: # pylint:disable=no-member
                                    # counter for current record number
                                    iRows = 1  # input textfile line number

                                    #if os.path.isfile(txtPath):
                                    if arcpy.Exists(txtPath):

                                        try:
                                            # Use csv reader to read each line in the text file
                                            time.sleep(0.5)  # trying to prevent error reading text file

                                            for rowInFile in csv.reader(open(txtPath, newline=''), delimiter='|', quotechar='"'):
                                                # replace all blank values with 'None' so that the values are properly inserted
                                                # into integer values otherwise insertRow fails
                                                #fixedRow = [x.decode(codePage) if x else None for x in rowInFile]  # handle non-utf8 characters
                                                r1 = rowInFile[0:7]
                                                r2 = rowInFile[11:13]
                                                r3 = rowInFile[15:19]
                                                r1.extend(r2)
                                                r1.extend(r3)
                                                # fixedRow = rowInFile # For Python 3, don't fix it.
                                                fixedRow = [x if x else None for x in r1]  # figure out which tables have non-utf8 characters
                                                #mrulekey = fixedRow[1]
                                                #ruledepth = fixedRow[6]
                                                
                                                if (fixedRow[6] == '0') or (fixedRow[1] == '54955'):
                                                    # NCCPI or ruledepth zero
                                                    # should I make the 54955 a dynamic variable?
                                                    cursor.insertRow(fixedRow) # was fixedRow
                                                iRows += 1

                                        except:
                                            self.warning(str(fixedRow))
                                            err = "2: Error writing line " + self.Number_Format(iRows, 0, True) + " from " + txtPath
                                            self.raise_error(err)

                                    else:
                                        self.raise_error("Missing tabular data file (" + txtPath + ")")

                            
                            else:
                                with arcpy.da.InsertCursor(os.path.join(newDB, tbl), fldNames) as cursor: # pylint:disable=no-member
                                    # counter for current record number
                                    iRows = 1  # input textfile line number

                                    #if os.path.isfile(txtPath):
                                    if arcpy.Exists(txtPath):

                                        try:
                                            # Use csv reader to read each line in the text file
                                            time.sleep(0.5)  # trying to prevent error reading text file

                                            for rowInFile in csv.reader(open(txtPath, newline=''), delimiter='|', quotechar='"'):
                                                # replace all blank values with 'None' so that the values are properly inserted
                                                # into integer values otherwise insertRow fails
                                                #fixedRow = [x.decode(codePage) if x else None for x in rowInFile]  # handle non-utf8 characters
                                                # fixedRow = rowInFile # For Python 3, don't fix it.
                                                fixedRow = [x if x else None for x in rowInFile]  # figure out which tables have non-utf8 characters
                                                cursor.insertRow(fixedRow) # was fixedRow
                                                iRows += 1

                                        except Exception as e:
                                            self.warning(" \n" + str(fixedRow))
                                            err = "3: Error writing line " + self.Number_Format(iRows, 0, True) + " from " + txtPath
                                            err += '\n'
                                            err += str(e)
                                            err += '\n'
                                            err += 'fields: {}'.format(fldNames)
                                            self.raise_error(err)

                                    else:
                                        self.raise_error("Missing tabular data file (" + txtPath + ")")

                        else:
                            # Import SDV tables while enforcing unique key constraints
                            # 'sdvfolderattribute', 'sdvattribute', 'sdvfolder', 'sdvalgorithm'
                            #
                            with arcpy.da.InsertCursor(os.path.join(newDB, tbl), fldNames) as cursor: # pylint:disable=no-member
                                # counter for current record number
                                iRows = 1

                                if os.path.isfile(txtPath):

                                    try:
                                        # Use csv reader to read each line in the text file
                                        time.sleep(0.5)  # trying to prevent error reading text file
                                        
                                        for rowInFile in csv.reader(open(txtPath, newline=''), delimiter='|', quotechar='"'):
                                            newRow = list()
                                            # fldNo = 0
                                            keyVal = int(rowInFile[dIndex[tbl]])

                                            if not keyVal in dKeys[tbl]:
                                                # write new record to SDV table
                                                dKeys[tbl].append(keyVal)
                                                newRow = [x if x else None for x in rowInFile]
                                                cursor.insertRow(newRow)  # was newRow
                                            iRows += 1

                                    except:
                                        err = "Error importing line " + self.Number_Format(iRows, 0, True) + " from " + txtPath + " \n " + str(newRow)
                                        self.warning(err)
                                        self.raise_error("4: Error writing line " + self.Number_Format(iRows, 0, True) + " of " + txtPath)

                                else:
                                    self.raise_error("Missing tabular data file (" + txtPath + ")")

                        # Check table count
                        # This isn't correct. May need to look at accumulating total table count in a dictionary
                        #if int(arcpy.GetCount_management(os.path.join(newDB, tbl)).getOutput(0)) != iRows:
                        #    self.raise_error(tbl + ": Failed to import all " + self.Number_Format(iRows, 0, True) + " records into "
                        #

                    else:
                        self.raise_error("Required table '" + tbl + "' not found in " + newDB)

                #arcpy.SetProgressorPosition()


                # Populate the month table (pre-populated in the Access Template database, no text file)
                #
                monthList = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
                monthTbl = os.path.join(newDB, "month")
                
                if int(arcpy.GetCount_management(monthTbl).getOutput(0)) < 12:
                    arcpy.SetProgressorLabel("Importing " +  fnAreasymbol + " tabular  (" + self.Number_Format(iCntr, 0, True) + " of " + self.Number_Format(len(dbList), 0, True) + ") :   " + monthTbl)
                    
                    with arcpy.da.InsertCursor(monthTbl, ["monthseq", "monthname"]) as cur: # pylint:disable=no-member
                        for seq, month in enumerate(monthList):
                            rec = [(seq + 1), month]
                            cur.insertRow(rec)
                
                # Import feature description file. Does this file exist in a NASIS-SSURGO download?
                # soilsf_t_al001.txt
                spatialFolder = os.path.join(os.path.dirname(tabularFolder), "spatial")
                txtFile ="soilsf_t_" + fnAreasymbol
                txtPath = os.path.join(spatialFolder, txtFile + ".txt")
                tbl = "featdesc"

                if arcpy.Exists(txtPath):
                    # For a geodatabase, I need to remove OBJECTID from the fields list
                    fldList = arcpy.Describe(tbl).fields
                    fldNames = list()
                    for fld in fldList:
                        if fld.type != "OID":
                            fldNames.append(fld.name)

                    if len(fldNames) == 0:
                        self.raise_error("Failed to get field names for " + tbl)

                    # Create cursor for all fields to populate the featdesc table
                    with arcpy.da.InsertCursor(tbl, fldNames) as cursor: # pylint:disable=no-member
                        # counter for current record number
                        iRows = 1
                        arcpy.SetProgressorLabel("Importing " +  fnAreasymbol + "  (" + self.Number_Format(iCntr, 0, True) + " of " + self.Number_Format(len(dbList), 0, True) + "):   " + tbl)

                        try:
                            # Use csv reader to read each line in the text file
                            for rowInFile in csv.reader(open(txtPath, newline=''), delimiter='|', quotechar='"'):
                                # replace all blank values with 'None' so that the values are properly inserted
                                # into integer values otherwise insertRow fails
                                newRow = [None if value == '' else value for value in rowInFile]
                                cursor.insertRow(newRow)
                                iRows += 1

                        except:
                            self.raise_error("Error loading line no. " + self.Number_Format(iRows, 0, True) + " of " + txtFile + ".txt")

                    arcpy.SetProgressorPosition()  # for featdesc table
                    time.sleep(1.0)

                # Check the database to make sure that it completed properly, with at least the
                # SAVEREST date populated in the SACATALOG table. Featdesc is the last table, but not
                # a good test because often it is not populated.
                dbDate = self.GetTemplateDate(newDB, fnAreasymbol)

                if dbDate == 0:
                    # With this error, it would be best to bailout and fix the problem before proceeding
                    self.raise_error("Failed to get Template Date for " + fnAreasymbol)

                # Set the Progressor to show completed status
                arcpy.ResetProgressor()

            # Check mapunit and sdvattribute tables. Get rid of certain records if there is no data available.
            # iacornsr IS NOT NULL OR nhiforsoigrp IS NOT NULL OR vtsepticsyscl IS NOT NULL

            # 'Soil-Based Residential Wastewater Disposal Ratings (VT)'  [vtsepticsyscl]

            # 'Iowa Corn Suitability Rating CSR2 (IA)'   [iacornsr]

            # 'NH Forest Soil Group'  [nhiforsoigrp]

            # tblIndexes = GetTableIndexes(newDB)  # using mdstatidxdet table

            bCorn = False
            bNHFor = False
            bVTSeptic = False
            wc = "iacornsr IS NOT NULL"
            with arcpy.da.SearchCursor(os.path.join(newDB, "mapunit"), ["OID@"], where_clause=wc) as cur: # pylint:disable=no-member
                for rec in cur:
                    bCorn = True
                    break

            wc = "vtsepticsyscl IS NOT NULL"
            with arcpy.da.SearchCursor(os.path.join(newDB, "mapunit"), ["OID@"], where_clause=wc) as cur: # pylint:disable=no-member
                for rec in cur:
                    bVTSeptic = True
                    break

            wc = "nhiforsoigrp IS NOT NULL"
            with arcpy.da.SearchCursor(os.path.join(newDB, "mapunit"), ["OID@"], where_clause=wc) as cur: # pylint:disable=no-member
                for rec in cur:
                    bNHFor = True
                    break

            if not bCorn:
                # Next open cursor on the sdvattribute table and delete any unneccessary records
                wc = "attributecolumnname = 'iacornsr'"
                with arcpy.da.UpdateCursor(os.path.join(newDB, "sdvattribute"), ["attributecolumnname"], where_clause=wc) as cur: # pylint:disable=no-member
                    for rec in cur:
                        cur.deleteRow()

            if not bVTSeptic:
                # Next open cursor on the sdvattribute table and delete any unneccessary records
                wc = "attributecolumnname = 'vtsepticsyscl'"
                with arcpy.da.UpdateCursor(os.path.join(newDB, "sdvattribute"), ["attributecolumnname"], where_clause=wc) as cur: # pylint:disable=no-member
                    for rec in cur:
                        cur.deleteRow()                

            if not bNHFor:
                # Next open cursor on the sdvattribute table and delete any unneccessary records
                wc = "attributecolumnname = 'nhiforsoigrp'"
                with arcpy.da.UpdateCursor(os.path.join(newDB, "sdvattribute"), ["attributecolumnname"], where_clause=wc) as cur: # pylint:disable=no-member
                    for rec in cur:
                        cur.deleteRow()

            arcpy.SetProgressorLabel("Adding attribute index for cointerp table")

            try:
                indxName = "Indx_CointerpRulekey"
                indxList = arcpy.ListIndexes(os.path.join(newDB, "cointerp"), indxName)
                
                if len(indxList) == 0: 
                    arcpy.SetProgressorLabel("\tAdding attribute index on rulekey for cointerp table")
                    # Tried to add this Cointerp index to the XML workspace document, but slowed down data import.
                    arcpy.AddIndex_management(os.path.join(newDB, "COINTERP"), "RULEKEY", indxName)
                    arcpy.SetProgressorPosition()

            except:
                self.raise_error(" \nUnable to create new rulekey index on the cointerp table")
                
            arcpy.SetProgressorLabel("Tabular import complete")

            return True

        except Exception as e:
            self.raise_error(str(e))


    def AppendFeatures(self, outputWS, AOI, mupolyList, mulineList, mupointList, sflineList, sfpointList, sapolyList, featCnt):
        # Merge all spatial layers into a set of file geodatabase featureclasses
        # Compare shapefile feature count to GDB feature count
        # featCnt:  0 mupoly, 1 muline, 2 mupoint, 3 sfline, 4 sfpoint, 5 sapoly
        try:
            # Set output workspace
            env.workspace = outputWS

            # Put datum transformation methods in place
            #AOI = "CONUS"
            self.info(" \nImporting spatial data...")

            # Problem if soil polygon shapefile has MUNAME column or other alterations
            # Need to use fieldmapping parameter to fix append error.
            fieldmappings = arcpy.FieldMappings()
            fieldmappings.addTable(os.path.join(outputWS, "MUPOLYGON"))
            fieldmappings.addTable(os.path.join(outputWS, "MULINE"))
            fieldmappings.addTable(os.path.join(outputWS, "MUPOINT"))
            fieldmappings.addTable(os.path.join(outputWS, "FEATLINE"))
            fieldmappings.addTable(os.path.join(outputWS, "FEATPOINT"))
            fieldmappings.addTable(os.path.join(outputWS, "SAPOLYGON"))

            # Assuming input featureclasses from Web Soil Survey are GCS WGS1984 and that
            # output datum is either NAD 1983 or WGS 1984. Output coordinate system will be
            # defined by the existing output featureclass.

            # WITH XML workspace method, I need to use Append_management

            # Merge process MUPOLYGON
            if len(mupolyList) > 0:
                self.info(" \n\tAppending " + str(len(mupolyList)) + " soil mapunit polygon shapefiles to create new featureclass: " + "MUPOLYGON")
                arcpy.SetProgressorLabel("Appending features to MUPOLYGON layer")
                arcpy.Append_management(mupolyList,  os.path.join(outputWS, "MUPOLYGON"), "NO_TEST", fieldmappings )
                mupolyCnt = int(arcpy.GetCount_management(os.path.join(outputWS, "MUPOLYGON")).getOutput(0))

                if mupolyCnt != featCnt[0]:
                    self.raise_error("MUPOLYGON imported only " + self.Number_Format(mupolyCnt, 0, True) + " polygons, should be " + self.Number_Format(featCnt[0], 0, True))

                # Add spatial index
                arcpy.AddSpatialIndex_management (os.path.join(outputWS, "MUPOLYGON"))
                arcpy.AddIndex_management(os.path.join(outputWS, "MUPOLYGON"), "AREASYMBOL", "Indx_MupolyAreasymbol")

            # Merge process MULINE
            if len(mulineList) > 0:
                self.info(" \n\tAppending " + str(len(mulineList)) + " soil mapunit line shapefiles to create new featureclass: " + "MULINE")
                arcpy.SetProgressorLabel("Appending features to MULINE layer")
                arcpy.Append_management(mulineList,  os.path.join(outputWS, "MULINE"), "NO_TEST", fieldmappings)
                mulineCnt = int(arcpy.GetCount_management(os.path.join(outputWS, "MULINE")).getOutput(0))

                if mulineCnt != featCnt[1]:
                    self.raise_error("MULINE short count")

                # Add spatial index
                arcpy.AddSpatialIndex_management (os.path.join(outputWS, "MULINE"))

                # Add attribute indexes
                arcpy.AddIndex_management(os.path.join(outputWS, "MULINE"), "AREASYMBOL", "Indx_MulineAreasymbol")

            # Merge process MUPOINT
            if len(mupointList) > 0:
                self.info(" \n\tAppending " + str(len(mupointList)) + " soil mapunit point shapefiles to create new featureclass: " + "MUPOINT")
                arcpy.SetProgressorLabel("Appending features to MUPOINT layer")
                arcpy.Append_management(mupointList,  os.path.join(outputWS, "MUPOINT"), "NO_TEST", fieldmappings)
                mupointCnt = int(arcpy.GetCount_management(os.path.join(outputWS, "MUPOINT")).getOutput(0))

                if mupointCnt != featCnt[2]:
                    self.raise_error("MUPOINT short count")

                # Add spatial index
                arcpy.AddSpatialIndex_management (os.path.join(outputWS, "MUPOINT"))

                # Add attribute indexes
                arcpy.AddIndex_management(os.path.join(outputWS, "MUPOINT"), "AREASYMBOL", "Indx_MupointAreasymbol")

            # Merge process FEATLINE
            if len(sflineList) > 0:
                self.info(" \n\tAppending " + str(len(sflineList)) + " special feature line shapefiles to create new featureclass: " + "FEATLINE")
                arcpy.SetProgressorLabel("Appending features to FEATLINE layer")
                arcpy.Append_management(sflineList,  os.path.join(outputWS, "FEATLINE"), "NO_TEST", fieldmappings)
                sflineCnt = int(arcpy.GetCount_management(os.path.join(outputWS, "FEATLINE")).getOutput(0))

                if sflineCnt != featCnt[3]:
                    self.raise_error("FEATLINE short count")

                # Add spatial index
                arcpy.AddSpatialIndex_management (os.path.join(outputWS, "FEATLINE"))

                # Add attribute indexes
                arcpy.AddIndex_management(os.path.join(outputWS, "FEATLINE"), "AREASYMBOL", "Indx_SFLineAreasymbol")

            # Merge process FEATPOINT
            if len(sfpointList) > 0:
                self.info(" \n\tAppending " + str(len(sfpointList)) + " special feature point shapefiles to create new featureclass: " + "FEATPOINT")
                arcpy.SetProgressorLabel("Appending features to FEATPOINT layer")
                arcpy.Append_management(sfpointList,  os.path.join(outputWS, "FEATPOINT"), "NO_TEST", fieldmappings)
                sfpointCnt = int(arcpy.GetCount_management(os.path.join(outputWS, "FEATPOINT")).getOutput(0))

                if sfpointCnt != featCnt[4]:
                    self.warning(" \nWA619 SF Points had 3136 in the original shapefile")
                    self.warning("featCnt is " + str(featCnt[4]))
                    self.warning(" \nExported " + str(sfpointCnt) + " points to geodatabase")
                    self.raise_error("FEATPOINT short count")

                # Add spatial index
                arcpy.AddSpatialIndex_management (os.path.join(outputWS, "FEATPOINT"))

                # Add attribute indexes
                arcpy.AddIndex_management(os.path.join(outputWS, "FEATPOINT"), "AREASYMBOL", "Indx_SFPointAreasymbol")

            # Merge process SAPOLYGON
            if len(sapolyList) > 0:
                self.info(" \n\tAppending " + str(len(sapolyList)) + " survey boundary shapefiles to create new featureclass: " + "SAPOLYGON")
                arcpy.SetProgressorLabel("Appending features to SAPOLYGON layer")
                arcpy.Append_management(sapolyList,  os.path.join(outputWS, "SAPOLYGON"), "NO_TEST", fieldmappings)
                sapolyCnt = int(arcpy.GetCount_management(os.path.join(outputWS, "SAPOLYGON")).getOutput(0))

                if sapolyCnt != featCnt[5]:
                    self.raise_error("SAPOLYGON short count")

                # Add spatial index
                arcpy.AddSpatialIndex_management (os.path.join(outputWS, "SAPOLYGON"))


            # arcpy.RefreshCatalog(outputWS)

            if not arcpy.Exists(outputWS):
                self.raise_error(outputWS + " not found at end of AppendFeatures...")

            return True

        except Exception as e:
            self.raise_error(str(e))

    def StateNames(self):
        # Create dictionary object containing list of state abbreviations and their names that
        # will be used to name the file geodatabase.
        # For some areas such as Puerto Rico, U.S. Virgin Islands, Pacific Islands Area the
        # abbrevation is

        # NEED TO UPDATE THIS FUNCTION TO USE THE LAOVERLAP TABLE AREANAME. AREASYMBOL IS STATE ABBREV

        try:
            stDict = dict()
            stDict["AL"] = "Alabama"
            stDict["AK"] = "Alaska"
            stDict["AS"] = "American Samoa"
            stDict["AZ"] = "Arizona"
            stDict["AR"] = "Arkansas"
            stDict["CA"] = "California"
            stDict["CO"] = "Colorado"
            stDict["CT"] = "Connecticut"
            stDict["DC"] = "District of Columbia"
            stDict["DE"] = "Delaware"
            stDict["FL"] = "Florida"
            stDict["GA"] = "Georgia"
            stDict["HI"] = "Hawaii"
            stDict["ID"] = "Idaho"
            stDict["IL"] = "Illinois"
            stDict["IN"] = "Indiana"
            stDict["IA"] = "Iowa"
            stDict["KS"] = "Kansas"
            stDict["KY"] = "Kentucky"
            stDict["LA"] = "Louisiana"
            stDict["ME"] = "Maine"
            stDict["MD"] = "Maryland"
            stDict["MA"] = "Massachusetts"
            stDict["MI"] = "Michigan"
            stDict["MN"] = "Minnesota"
            stDict["MS"] = "Mississippi"
            stDict["MO"] = "Missouri"
            stDict["MT"] = "Montana"
            stDict["NE"] = "Nebraska"
            stDict["NV"] = "Nevada"
            stDict["NH"] = "New Hampshire"
            stDict["NJ"] = "New Jersey"
            stDict["NM"] = "New Mexico"
            stDict["NY"] = "New York"
            stDict["NC"] = "North Carolina"
            stDict["ND"] = "North Dakota"
            stDict["OH"] = "Ohio"
            stDict["OK"] = "Oklahoma"
            stDict["OR"] = "Oregon"
            stDict["PA"] = "Pennsylvania"
            stDict["PRUSVI"] = "Puerto Rico and U.S. Virgin Islands"
            stDict["RI"] = "Rhode Island"
            stDict["Sc"] = "South Carolina"
            stDict["SD"] ="South Dakota"
            stDict["TN"] = "Tennessee"
            stDict["TX"] = "Texas"
            stDict["UT"] = "Utah"
            stDict["VT"] = "Vermont"
            stDict["VA"] = "Virginia"
            stDict["WA"] = "Washington"
            stDict["WV"] = "West Virginia"
            stDict["WI"] = "Wisconsin"
            stDict["WY"] = "Wyoming"
            return stDict

        except:
            self.raise_error("\tFailed to create list of state abbreviations (CreateStateList)")

    def GetXML(self, AOI):
        # Set appropriate XML Workspace Document according to AOI
        # The xml files referenced in this function must all be stored in the same folder as the
        # Python script and toolbox
        #
        # FY2016. Discovered that my MD* tables in the XML workspace documents were out of date.
        # Need to update and figure out a way to keep them updated
        #
        try:
            # Set folder path for workspace document (same as script)
            script_folder = os.path.dirname(__file__)
            xmlPath = os.path.join(script_folder, 'templates')

            # Changed datum transformation to use ITRF00 for ArcGIS 10.1
            # FYI. Multiple geographicTransformations would require a semi-colon delimited string
            tm = "WGS_1984_(ITRF00)_To_NAD_1983"

            # Input XML workspace document used to create new gSSURGO schema in an empty geodatabase
            if AOI == "Lower 48 States":
                #inputXML = os.path.join(xmlPath, "gSSURGO_CONUS_AlbersNAD1983.xml")
                inputXML = os.path.join(xmlPath, "gSSURGO_CONUS_AlbersNAD1983.xml")
                tm = "WGS_1984_(ITRF00)_To_NAD_1983"

            elif AOI == "Hawaii":
                inputXML = os.path.join(xmlPath, "gSSURGO_Hawaii_AlbersWGS1984.xml")
                tm = ""

            elif AOI == "American Samoa":
                inputXML = os.path.join(xmlPath, "gSSURGO_Hawaii_AlbersWGS1984.xml")
                tm = ""

            elif AOI == "Alaska":
                inputXML = os.path.join(xmlPath, "gSSURGO_Alaska_AlbersWGS1984.xml")
                tm = ""

            elif AOI == "Puerto Rico and U.S. Virgin Islands":
                inputXML = os.path.join(xmlPath, "gSSURGO_CONUS_AlbersNAD1983.xml")
                tm = "WGS_1984_(ITRF00)_To_NAD_1983"

            elif AOI == "Pacific Islands Area":
                inputXML = os.path.join(xmlPath, "gSSURGO_PACBasin_AlbersWGS1984.xml")
                # No datum transformation required for PAC Basin data
                tm = ""

            elif AOI == "World":
                self.info(" \nOutput coordinate system will be Geographic WGS 1984")
                inputXML = os.path.join(xmlPath, "gSSURGO_Geographic_WGS1984.xml")
                tm = ""

            else:
                self.warning(" \nNo projection is being applied")
                inputXML = os.path.join(xmlPath, "gSSURGO_GCS_WGS1984.xml")
                tm = ""

            arcpy.env.geographicTransformations = tm

            return inputXML

        except Exception as e:
            self.raise_error('GetXML: {}'.format(e))

    def gSSURGO(self, inputFolder, surveyList, outputWS, AOI, tileInfo, useTextFiles, bClipped, areasymbolList):
        # main function

        try:
            # Creating the file geodatabase uses the ImportXMLWorkspaceDocument command which requires
            #
            # ArcInfo: Advanced license
            # ArcEditor: Standard license
            # ArcView: Basic license
            licenseLevel = arcpy.ProductInfo().upper()
            if licenseLevel == "BASIC":
                self.raise_error("ArcGIS License level must be Standard or Advanced to run this tool")

            env.overwriteOutput= True
            codePage = 'iso-8859-1'  # allow csv reader to handle non-ascii characters
            # According to Gary Spivak, SDM downloads are UTF-8 and NASIS downloads are iso-8859-1
            # cp1252 also seemed to work well
            #codePage = 'utf-16' this did not work
            #
            # http://stackoverflow.com/questions/6539881/python-converting-from-iso-8859-1-latin1-to-utf-8
            # Next need to try: string.decode('iso-8859-1').encode('utf8')

            dbVersion = 2  # This is the SSURGO version supported by this script and the gSSURGO schema (XML Workspace document)

            # Make sure that the env.scratchGDB is NOT Default.gdb. This can cause problems for
            # some unknown reason.
            #if (os.path.basename(env.scratchGDB).lower() == "default.gdb") or \
            #(os.path.basename(env.scratchWorkspace).lower() == "default.gdb") or \
            #(os.path.basename(env.scratchGDB).lower() == outputWS):
                        
            #if SetScratch() == False:
            #    self.raise_error("Invalid scratch workspace setting (" + env.scratchWorkspace + ")"


            # Problem when scratchGDB or scratchFolder no longer exist
            # scratchFolder = env.scratchFolder # pylint:disable=no-member
            
            if not arcpy.Exists(env.scratchFolder): # pylint:disable=no-member
                # try to create it
                arcpy.CreateFolder(env.scratchFolder) # pylint:disable=no-member

            if not arcpy.Exists(env.scratchGDB): # pylint:disable=no-member
                arcpy.management.CreateFileGDB(os.path.dirname(env.scratchGDB), os.path.basename(env.scratchGDB), "10.0") # pylint:disable=no-member

            # Import script to generate relationshipclasses and associated attribute indexes
            # import gssurgo.Create_SSURGO_RelationshipClasses
            
            # get the information from the tileInfo
            # if type(tileInfo) == tuple:
            #     if bClipped:
            #         # Set the aliasname when this is a clipped layer
            #         aliasName = ""
            #         description = tileInfo[1]

            #     else:
            #         # Try leaving the aliasname off of the regular layers.
            #         aliasName = tileInfo[0]
            #         description = tileInfo[1]

            # else:
            #     stDict = self.StateNames()
            #     aliasName = tileInfo

            #     if aliasName in stDict:
            #         description = stDict[aliasName]

            #     else:
            #         description = tileInfo

            aliasName = ""

            # Get the XML Workspace Document appropriate for the specified AOI
            inputXML = self.GetXML(AOI)

            if inputXML == "":
                self.raise_error("Unable to set input XML Workspace Document")

            if len(surveyList) == 0:
                self.raise_error("At least one soil survey area input is required")

            extentList = list()
            mupolyList = list()
            mupointList = list()
            mulineList = list()
            sflineList = list()
            sfpointList = list()
            sapolyList = list()
            dbList = list()

            if len(areasymbolList) == 0:
                # The 'Create gSSURGO DB by Map' tool will skip this section because the SortSurveyAreas function
                # has already generated a spatial sort for the list of survey areas.
                #
                iSurveys = len(surveyList)
                self.info(" \nCreating spatially sorted list for " + str(iSurveys) + " selected surveys...")
            
                for subFolder in surveyList:

                    # Perform spatial import
                    # Req: inputFolder, subFolder
                    # build the input shapefilenames for each SSURGO featureclass type using the
                    # AREASYMBOL then confirm shapefile existence for each survey and append to final input list
                    # used for the Append command. Use a separate list for each featureclass type so
                    # that missing or empty shapefiles will not be included in the Merge. A separate
                    # Append process is used for each featureclass type.

                    #areaSym = subFolder[-5:].encode('ascii')
                    areaSym = subFolder[(subFolder.rfind("_") + 1):].lower()  # STATSGO mod
                    env.workspace = os.path.join( inputFolder, os.path.join( subFolder, "spatial"))
                    mupolyName = "soilmu_a_" + areaSym + ".shp"
                    gsmupolyName = "gsmsoilmu_a_" + areaSym + ".shp"
                    mulineName = "soilmu_l_" + areaSym + ".shp"
                    mupointName = "soilmu_p_" + areaSym + ".shp"
                    sflineName = "soilsf_l_" + areaSym + ".shp"
                    sfpointName = "soilsf_p_" + areaSym + ".shp"
                    sapolyName = "soilsa_a_" + areaSym + ".shp"
                    arcpy.SetProgressorLabel("Getting extent for " + areaSym.upper() + " survey area")

                    if arcpy.Exists(mupolyName):
                        # Found soil polygon shapefile...
                        # Calculate the product of the centroid X and Y coordinates
                        desc = arcpy.Describe(mupolyName)
                        shpExtent = desc.extent
                        
                        if shpExtent is None:
                            self.raise_error("Corrupt soil polygon shapefile for " + areaSym.upper() + "?")

                        # XCntr = ( shpExtent.XMin + shpExtent.XMax) / 2.0
                        # YCntr = ( shpExtent.YMin + shpExtent.YMax) / 2.0
                        #sortValue = (areaSym, round(XCntr, 1),round(YCntr, 1))  # center of survey area
                        sortValue = (areaSym, round(shpExtent.XMin, 1), round(shpExtent.YMax, 1)) # upper left corner of survey area
                        extentList.append(sortValue)
                        areasymbolList.append(areaSym.upper())

                    elif arcpy.Exists(gsmupolyName):
                        # Found STATSGO soil polygon shapefile...
                        # Calculate the product of the centroid X and Y coordinates
                        desc = arcpy.Describe(gsmupolyName)
                        shpExtent = desc.extent
                        
                        if shpExtent is None:
                            self.raise_error("Corrupt soil polygon shapefile for " + areaSym.upper() + "?")

                        # XCntr = ( shpExtent.XMin + shpExtent.XMax) / 2.0
                        # YCntr = ( shpExtent.YMin + shpExtent.YMax) / 2.0
                        #sortValue = (areaSym, round(XCntr, 1),round(YCntr, 1))  # center of survey area
                        sortValue = (areaSym, round(shpExtent.XMin, 1), round(shpExtent.YMax, 1)) # upper left corner of survey area
                        extentList.append(sortValue)
                        areasymbolList.append(areaSym.upper())
                        
                    else:
                        # Need to remove this if tabular-only surveys are allowed
                        self.raise_error("Error. Missing soil polygon shapefile: " + mupolyName + " in " + os.path.join( inputFolder, os.path.join( subFolder, "spatial")))

                # Make sure that the extentList is the same length as the surveyList. If it is
                # shorter, there may have been a duplicate sortKey which would result in a
                # survey being skipped in the merge
                env.workspace = inputFolder

                if len(extentList) < len(surveyList):
                    self.raise_error("Problem with survey extent sort key")

                # Sort the centroid coordinate list so that the drawing order of the merged layer
                # is a little more efficient
                extentList.sort(key=itemgetter(1), reverse=False)
                extentList.sort(key=itemgetter(2), reverse=True)


                areasymbolList = list()
                cnt = 0
                
                for sortValu in extentList:
                    cnt += 1
                    areasym = sortValu[0]
                    areasymbolList.append(areasym)

            else:
                # Spatial sort has already been handled using the soil survey boundary layer.
                pass
            
            # Save the total featurecount for all input shapefiles
            mupolyCnt = 0
            mulineCnt = 0
            mupointCnt = 0
            sflineCnt = 0
            sfpointCnt = 0
            sapolyCnt = 0

            # Create a series of lists that contain the found shapefiles to be merged
            self.info(" \nCreating list of shapefiles to be imported for each of " + self.Number_Format(len(areasymbolList), 0, True) + " survey area...")
            arcpy.SetProgressor("step", "Adding surveys to merge list", 1, len(areasymbolList))
            
            for areaSym in areasymbolList:
                #areaSym = sortValue[0]
                subFolder = "soil_" + areaSym
        
                shpPath = os.path.join( inputFolder, os.path.join( subFolder, "spatial"))

                badShps = list()

                # soil polygon shapefile
                mupolyName = "soilmu_a_" + areaSym + ".shp"
                # gsmpolyName = "gsmsoilmu_a_" + areaSym + ".shp"
                muShp = os.path.join(shpPath, mupolyName)
                gsmuShp = os.path.join(shpPath, mupolyName)

                if arcpy.Exists(muShp):

                    cnt = int(arcpy.GetCount_management(muShp).getOutput(0))

                    if cnt > 0:
                        if not muShp in mupolyList:
                            mupolyCnt += cnt
                            mupolyList.append(muShp)
                            arcpy.SetProgressorLabel("Adding " + areaSym.upper() + " survey to merge list")

                    else:
                        badShps.append(muShp)
                        #self.raise_error("No features found in " + shpFile

                elif arcpy.Exists(gsmuShp):

                    cnt = int(arcpy.GetCount_management(gsmuShp).getOutput(0))

                    if cnt > 0:
                        if not gsmuShp in mupolyList:
                            mupolyCnt += cnt
                            mupolyList.append(gsmuShp)
                            arcpy.SetProgressorLabel("Adding " + areaSym.upper() + " survey to merge list")

                    else:
                        badShps.append(gsmuShp)
                        #self.raise_error("No features found in " + gsmuShp

                else:
                    self.raise_error("Shapefile " + muShp + " not found")

                # input soil polyline shapefile
                mulineName = "soilmu_l_" + areaSym + ".shp"
                shpFile = os.path.join(shpPath, mulineName)

                if arcpy.Exists(shpFile):
                    cnt = int(arcpy.GetCount_management(shpFile).getOutput(0))

                    if cnt > 0:
                        if not shpFile in mulineList:
                            mulineCnt += cnt
                            mulineList.append(shpFile)

                # input soil point shapefile
                mupointName = "soilmu_p_" + areaSym + ".shp"
                shpFile = os.path.join(shpPath, mupointName)

                if arcpy.Exists(shpFile):
                    cnt = int(arcpy.GetCount_management(shpFile).getOutput(0))

                    if cnt > 0:
                        mupointCnt += cnt
                        mupointList.append(shpFile)

                # input specialfeature polyline shapefile name
                sflineName = "soilsf_l_" + areaSym + ".shp"
                shpFile = os.path.join(shpPath, sflineName)

                if arcpy.Exists(shpFile):
                    cnt = int(arcpy.GetCount_management(shpFile).getOutput(0))

                    if cnt > 0:
                        if not shpFile in sflineList:
                            sflineCnt += cnt
                            sflineList.append(shpFile)

                # input special feature point shapefile
                sfpointName = "soilsf_p_" + areaSym + ".shp"
                shpFile = os.path.join(shpPath, sfpointName)

                if arcpy.Exists(shpFile):
                    cnt = int(arcpy.GetCount_management(shpFile).getOutput(0))

                    if cnt > 0:
                        if not shpFile in sfpointList:
                            sfpointCnt += cnt
                            sfpointList.append(shpFile)

                # input soil survey boundary shapefile name
                sapolyName = "soilsa_a_" + areaSym + ".shp"
                shpFile = os.path.join(shpPath, sapolyName)

                if arcpy.Exists(shpFile):
                    cnt = int(arcpy.GetCount_management(shpFile).getOutput(0))
                    
                    if cnt > 0:
                        if not shpFile in sapolyList:
                            cnt = int(arcpy.GetCount_management(shpFile).getOutput(0))
                            sapolyCnt += cnt
                            sapolyList.append(shpFile)

                # input soil survey Template database
                if useTextFiles == True:
                    # use database path, even if it doesn't exist. It will be used
                    # to actually define the location of the tabular folder and textfiles
                    # probably need to fix this later
                    dbPath = os.path.join( inputFolder, os.path.join( subFolder, "tabular"))
                    dbName = "soil_d_" + areaSym + ".mdb"
                    dbFile = os.path.join(dbPath, dbName)
                    
                    if not dbFile in dbList:
                        dbList.append(dbFile)

                else:
                    dbPath = os.path.join( inputFolder, os.path.join( subFolder, "tabular"))
                    dbName = "soil_d_" + areaSym + ".mdb"
                    dbFile = os.path.join(dbPath, dbName)

                    if arcpy.Exists(dbFile) and not dbFile in dbList:
                        dbList.append(dbFile)

                    else:
                        self.raise_error("Missing Template database (" + dbName + ")")

                arcpy.SetProgressorPosition()

            if len(badShps) > 0:
                self.raise_error("Found " + self.Number_Format(len(badShps), 0, True) + " soil polygon shapefiles with no data: " + "\n".join(badShps))
            
            time.sleep(1)
            arcpy.ResetProgressor()

            if len(mupolyList) > 0:
                # Create file geodatabase for output data
                # Remove any dashes in the geodatabase name. They will cause the
                # raster conversion to fail for some reason.
                gdbName = os.path.basename(outputWS)
                outFolder = os.path.dirname(outputWS)
                gdbName = gdbName.replace("-", "_")
                outputWS = os.path.join(outFolder, gdbName)
                featCnt = (mupolyCnt, mulineCnt, mupointCnt, sflineCnt, sfpointCnt, sapolyCnt)  # 0 mupoly, 1 muline, 2 mupoint, 3 sfline, 4 sfpoint, 5 sapoly

                bGeodatabase = self.CreateSSURGO_DB(outputWS, inputXML, areasymbolList, aliasName)

                if bGeodatabase:
                    # Successfully created a new geodatabase
                    # Merge all existing shapefiles to file geodatabase featureclasses
                    #
                    bSpatial = self.AppendFeatures(outputWS, AOI, mupolyList, mulineList, mupointList, sflineList, sfpointList, sapolyList, featCnt)

                    # Append tabular data to the file geodatabase
                    #
                    if bSpatial == True:
                        if not arcpy.Exists(outputWS):
                            self.raise_error("Could not find " + outputWS + " to append tables to")

                        if useTextFiles:
                            bMD = self.ImportMDTabular(outputWS, dbPath, codePage)  # new, import md tables from text files of last survey area

                            if bMD == False:
                                self.raise_error("")

                            # import attribute data from text files in tabular folder
                            bTabular = self.ImportTabular(outputWS, dbList, dbVersion, codePage)

                        else:
                            bMD = self.ImportMDTables(outputWS, dbList)

                            if bMD == False:
                                self.raise_error("")

                            # import attribute data from Template database tables
                            bTabular = self.ImportTables(outputWS, dbList, dbVersion)

                        if bTabular == True:
                            # Successfully imported all tabular data (textfiles or Access database tables)
                            self.info(" \nAll spatial and tabular data imported")

                        else:
                            self.raise_error("Failed to export all data to gSSURGO. Tabular export error.")

                    else:
                        self.raise_error("Failed to export all data to gSSURGO. Spatial export error")

                else:
                    return False

                # In October 2018 it was reported that two of the DHS interps were missing from the sdv tables
                # This is a patch to replace the 4 missing records
                #bFixed = IdentifyNewInterps(outputWS)

                # Create table relationships and indexes
                # bRL = CreateTableRelationships(outputWS)

                # Query the output SACATALOG table to get list of surveys that were exported to the gSSURGO
                #
                saTbl = os.path.join(outputWS, "sacatalog")
                expList = list()
                queryList = list()

                with arcpy.da.SearchCursor(saTbl, ["AREASYMBOL", "SAVEREST"]) as srcCursor: # pylint:disable=no-member
                    for rec in srcCursor:
                        expList.append(rec[0] + " (" + str(rec[1]).split()[0] + ")")
                        queryList.append("'" + rec[0] + "'")

                # surveyInfo = ", ".join(expList)
                queryInfo = ", ".join(queryList)

                # Update metadata for the geodatabase and all featureclasses
                self.info(" \nUpdating metadata...")
                arcpy.SetProgressorLabel("Updating metadata...")
                # mdList = [outputWS, os.path.join(outputWS, "FEATLINE"), os.path.join(outputWS, "FEATPOINT"), \
                # os.path.join(outputWS, "MUPOINT"), os.path.join(outputWS, "MULINE"), os.path.join(outputWS, "MUPOLYGON"), \
                # os.path.join(outputWS, "SAPOLYGON")]
                gssurgo_dir = os.path.dirname(__file__)
                remove_gp_history_xslt = os.path.join(gssurgo_dir, "remove geoprocessing history.xslt")

                if not arcpy.Exists(remove_gp_history_xslt):
                    self.raise_error("Missing required file: " + remove_gp_history_xslt)

                # for target in mdList:
                #     bMetadata = UpdateMetadata(outputWS, target, surveyInfo, description, remove_gp_history_xslt)

                # Check scratchfolder for xxImport*.log files
                # For some reason they are being put in the folder above env.scratchFolder (or is it one above scratchworkspace?)
                
                env.workspace = os.path.dirname(env.scratchFolder)

                logFiles = arcpy.ListFiles("xxImport*.log")

                if len(logFiles) > 0:
                    for logFile in logFiles:
                        arcpy.Delete_management(logFile)

                self.info(" \nSuccessfully created a geodatabase containing the following surveys: " + queryInfo)

            self.info(" \nOutput file geodatabase:  " + outputWS + "  \n ")

            return True

        except Exception as e:
            self.raise_error(str(e))

    def SortSurveyAreaLayer(self, ssaLayer, surveyList):
        # For the 'Create gSSURGO DB by Map' sort the polygons by extent and use that to regenerate the surveyList
        #
        try:
            # first reformat the surveyList (soil_areasymbol.lower())
            newSurveyList = list()
            areasymList = [s[5:].upper() for s in surveyList]
            sortedSSA = os.path.join(env.scratchGDB, "sortedSSA") # pylint:disable=no-member
            desc = arcpy.Describe(ssaLayer)
            shapeField = desc.featureclass.shapeFieldName

            if arcpy.Exists(sortedSSA):
                arcpy.Delete_management(sortedSSA)
                
            arcpy.Sort_management(ssaLayer, sortedSSA, shapeField, "UR")

            if arcpy.Exists(sortedSSA):
                with arcpy.da.SearchCursor(sortedSSA, "areasymbol", ) as cur: # pylint:disable=no-member
                    for rec in cur:
                        areaSym = rec[0].encode('ascii')
                        
                        if areaSym in areasymList and not areaSym in newSurveyList:
                            newSurveyList.append(areaSym)

            else:
                self.raise_error("Failed to produce spatial sort on survey areas")

            return newSurveyList
                                            

        except Exception as e:
            self.raise_error(str(e))
