#!/usr/bin/python
"""
This program facilitates the inventorizing of an Oracle database object structures.
It extracts such information from the oracle data dictionary and stores the SQL
scripts to re-create the objects in an GIT repository. Relevant object types
for this workflow is typically the following:
* PL/SQL stored procedures such as packages, types, triggers, procedures, functions
* Views
* Tables, whereby the logical structure is in focus
* Synonyms

Other object types requires further analysis. Candidates are materialized views,
scheduler jobs, user profiles for example.

Object types which should definitely excluded are users and DB links as these would
contain login information which must not enter a versioning repository.

Since GIT use file tree structure, it is practical to have the directory hierarchy below:

+<Global database name of source database>
	+<Schema name>
		+<object type>

Beneath <object type> directories, we store the extracted scripts per object. Since 
Oracle ensures the uniqueness of object names, this hiararchy is safe from naming 
conflicts.

When this program is used to access multiple databases which are fundamentally
simular such as a production and integration database, the next logical use case is to 
compile a diff report. This information can be very helpful both for release management
team and developers. Different ways of storing the extracted scripts for 
a diff operation are conceivable:

* both versions are only stored as files in the described hierarchy (not checked-in)
* both versions have been checked in. 
* one version is checked in, the other one is not.

Evolving further on this fundament of methods to perform the tasks laid out, it 
is also possible to compare to versions which both have been checked in.

Configuration:
The program reads from a config file the following settings:

INCLUDE_SCHEMAS
INCLUDE_OBJECT_TYPES
(at a later stage) EXCLUDE_TRIPLETS: schema, object type, regexp to be applied on object names for exclusion

Below is an examplary command to extract the specified objects and check the result into GIT:

./gitWatchOra.py -a checkin -f my_input.txt -O IOS_APP_DATA -D sfwbe_2_xe -u dummySvnUser --keep_work_area --use_default_svn_auth y -r $HOME/testGitRepo

"""

import argparse
import difflib
import getpass
import glob
import inspect
import re
import os
import shutil
import subprocess
import svnHelper
import sys
import tempfile
import time

g_revision = "$Revision: 28066 $"
g_myBaseName = os.path.basename( sys.argv[0] )

g_userHome= os.path.expanduser( '~' )
g_workAreaRoot = "%s/%s_%s_%d" % ( '/tmp', g_myBaseName[0:8], time.strftime("%Y%m%d_%H%M%S") , os.getpid () )
g_queryDbName= "select dbms_standard.database_name n from dual;"
g_useDbaView=None

g_supportedObjectTypes= [ 
	  'FUNCTION' 
	, 'PACKAGE' 
	, 'PROCEDURE' 
	, 'TABLE' 
	, 'SEQUENCE' 
	, 'SYNONYM' 
	, 'TYPE' 
	, 'VIEW' 
	]

g_spoolTargetMarker = '#+?Sp00lTargetMark3r:'

g_envVarNamePrimarySecret  = 'PRIMARY_SECRET' 
g_envVarNameSecondarySecret= 'SECONDARY_SECRET' 

g_primaryOraPassword= None
g_primaryOraUser= None
g_primaryConnectString= None

g_secondaryOraPassword= None
g_secondaryOraUser= None
g_secondaryConnectString= None

g_maxDiffLines= 50

cfgParamKeyIncludeSchema        = 'INCLUDE_SCHEMA'
cfgParamKeyIncludeObjectType    = 'INCLUDE_OBJECT_TYPE'

cfgParamKeyPrimaryConnectString = 'PRIMARY_CONNECT_STRING'
cfgParamKeyPrimaryOraUser       = 'PRIMARY_ORA_USER'

cfgParamKeySecondaryConnectString = 'SECOND_CONNECT_STRING'
cfgParamKeySecondaryOraUser       = 'SECOND_ORA_USER'

g_validFilterNames = [cfgParamKeyIncludeSchema, cfgParamKeyIncludeObjectType
	, cfgParamKeyPrimaryConnectString, cfgParamKeyPrimaryOraUser
	]
g_standardCommitMessage = ""
g_dbxCnt = 1
g_maxDbxMsg = 999

def _dbx ( text ):
	global g_dbxCnt
	print( 'dbx: %s - Ln%d: %s' % ( inspect.stack()[1][3], inspect.stack()[1][2], text ) )
	g_dbxCnt += 1
	if g_dbxCnt > g_maxDbxMsg:
		_errorExit( "g_maxDbxMsg of %d exceeded" % g_maxDbxMsg )

def _infoTs ( text , withTs = False ):
	if withTs :
		print( '%s (Ln%d) %s' % ( time.strftime("%H:%M:%S"), inspect.stack()[1][2], text ) )
	else :
		print( '(Ln%d) %s' % ( inspect.stack()[1][2], text ) )

def _errorExit ( text ):
	print( 'ERROR raised from %s - Ln%d: %s' % ( inspect.stack()[1][3], inspect.stack()[1][2], text ) )
	sys.exit(1)

def getTextSize ( lines ):
	rc = 0
	for line in lines:
		rc += len( line )
	return rc	

def parseCmdLine() :

	global g_primaryConnectString
	global g_primaryOraUser

	global g_secondaryConnectString
	global g_secondaryOraUser

	global g_useDbaViews

	parser = argparse.ArgumentParser()
	# lowercase shortkeys
	parser.add_argument( '-a', '--action', help='which action applies', choices=['checkin', 'diff-db-db', 'diff-db-repo', 'diff-repo-repo', 'extract-as-zip' ], required= True)
	parser.add_argument( '-f', '--config_file' , help='Read configuration from this file', required= True )
	parser.add_argument( '-m', '--mail_recipient' , help="recipient of diff ouptut" )
	parser.add_argument( '-d', '--secondary_connect_string', help='Oracle connect string to the secondary Database to extract scripts from' )
	parser.add_argument( '-D', '--primary_connect_string', help='Oracle connect string to the primary Database to extract scripts from' )
	parser.add_argument( '-o', '--secondary_ora_user')
	parser.add_argument( '-O', '--primary_ora_user')
	parser.add_argument( '-r', '--checkin_target_url', help= "Target URL within the GIT repository to import/commit the scripts to")
	parser.add_argument( '-t', '--tag_comment', help="a free text message that will be appended to the commit message for GIT check-in. " )
	parser.add_argument( '-u', '--svn_user', help= "Whenever access to GIT is required, specify the user name. The password will be prompted interactively or passed as environment variable. Provide dummies if credentials not strictly required" )
	# long keywords only
	parser.add_argument( '--batch_mode', dest='batch_mode', action='store_true', help= "Run in batch mode. Interactive prompts will be suppressed" )
	parser.add_argument( '--keep_work_area', dest='keep_work_area', action='store_true', help= "Do not remove work area after run. This would be for diagnosis" )
	parser.add_argument( '--repo_url1', help= "repository URL if a diff is requested against the database or another URL" )
	parser.add_argument( '--repo_url2', help= "2nd repository URL for diff-repo-repo" )
	parser.add_argument( '--use_dba_views', help= "Does the Oracle user have SELECT_CATALOG_ROLE or equivalent? If no, this program may only works for the schema which is the same as --primary_ora_user or --secondary_ora_user", choices=[ 'y', 'n'], default= 'y' )
	parser.add_argument( '--use_default_svn_auth', help= "Do not prompt for GIT authentication" , choices=[ 'y', 'n'], default= 'n' )

	parser.set_defaults( batch_mode= False)
	parser.set_defaults( keep_work_area= False)

	result= parser.parse_args()

	# for (k, v) in vars( result ).iteritems () : print( "%s : %s" % (k, v) )

	if result.primary_connect_string != None: 
		g_primaryConnectString=  result.primary_connect_string
	if result.primary_ora_user != None: g_primaryOraUser=  result.primary_ora_user

	if result.secondary_connect_string != None: 
		g_secondaryConnectString=  result.secondary_connect_string
	if result.secondary_ora_user != None: g_secondaryOraUser=  result.secondary_ora_user

	g_useDbaViews = True if result.use_dba_views == 'y' else False

	return result

def parseCfgFileAndSetGlobals( path ):
	global g_primaryConnectString
	global g_primaryOraUser
	global g_secondaryConnectString
	global g_secondaryOraUser

	includeSchemas= []
	includeObjectTypes= []

	lineNo= 0
	lines= open( path, 'r' ).readlines()
	for line in lines:
		lineNo += 1
		line = line.strip() # remove leading, trailing whitespaces
		if line.startswith( '#' ) or line == None or len( line ) == 0 : None
		else:
			value=  line.split( '::' )[1]
			if line.startswith( cfgParamKeyIncludeSchema ) : 
				if value == None:
					_errorExit( "Ln %d of %s does not contain any schema" % ( lineNo, path ) )
				includeSchemas.append( value )
			elif line.startswith( cfgParamKeyIncludeObjectType ) : 
				if value == None:
					_errorExit( "Ln %d of %s does not contain any object type" % ( lineNo, path ) )
				includeObjectTypes.append( value )

			elif line.startswith( cfgParamKeyPrimaryConnectString ) : 
				if g_primaryConnectString != None:
					_info( "WARNING: %s in %s will be ignored since the command line argument takes higher precedence!" % ( cfgParamKeyPrimaryConnectString, path) )	
				else:
					if value == None:
						_errorExit( "Ln %d of %s does not contain any connect string" % ( lineNo, path ) )
					g_primaryConnectString= value
			elif line.startswith( cfgParamKeyPrimaryOraUser ) : 
				if g_primaryOraUser != None:
					_info( "WARNING: %s in %s will be ignored since the command line argument takes higher precedence!" % ( cfgParamKeyPrimaryOraUser, path) )	
				else: 
					if value == None:
						_errorExit( "Ln %d of %s does not contain any Oracle user" % ( lineNo, path ) )
					g_primaryOraUser= value

			elif line.startswith( cfgParamKeySecondaryConnectString ) : 
				if g_secondaryConnectString != None:
					_info( "WARNING: %s in %s will be ignored since the command line argument takes higher precedence!" % ( cfgParamKeySecondaryConnectString, path) )	
				else:
					if value == None:
						_errorExit( "Ln %d of %s does not contain any connect string" % ( lineNo, path ) )
					g_secondaryConnectString= value
			elif line.startswith( cfgParamKeySecondaryOraUser ) : 
				if g_secondaryOraUser != None:
					_info( "WARNING: %s in %s will be ignored since the command line argument takes higher precedence!" % ( cfgParamKeySecondaryOraUser, path) )	
				else: 
					if value == None:
						_errorExit( "Ln %d of %s does not contain any Oracle user" % ( lineNo, path ) )
					g_secondaryOraUser= value

			else:
				_errorExit( "Ln %d of %s does not contain a valid keyword" % ( lineNo, path ) )

	# _dbx( len( includeObjectTypes ) )

	distinctSchemaCnt=  len( set( includeSchemas ) ) 
	if len( includeSchemas ) > distinctSchemaCnt:
		_errorExit( "Please elimenate duplicate schemas. %d given and %d are unique!" % ( len( includeSchemas ), distinctSchemaCnt ) )

	distinctObjectTypeCnt=  len( set( includeObjectTypes ) ) 
	if len( includeObjectTypes ) > distinctObjectTypeCnt:
		_errorExit( "Please elimenate duplicate object types. %d given and %d are unique!" % ( len( includeObjectTypes ), distinctObjectTypeCnt ) )

	if len( includeObjectTypes ) == 0:
		_infoTs( "WARNING: No object types are specified so we default to all supported types!" )
		includeObjectTypes= g_supportedObjectTypes
	
	return includeSchemas, includeObjectTypes

def getOraPassword ( oraUser, oraPasswordEnvVar, batchMode ):
	"""Prompt for Oracle password if it is not found from environment variable. 
	Password entered will be hidden.
	"""
	passwordEnv= None
	if oraPasswordEnvVar in os.environ:
		passwordEnv= os.environ[ oraPasswordEnvVar ]
		if passwordEnv:
			print('INFO: Found a value from the environment varable %s. Will use it if you just hit Enter on the password prompt' % oraPasswordEnvVar )
			if batchMode:
				return passwordEnv
	else:
		print('INFO: Password could be passed as environment variable %s however it is not set.' % oraPasswordEnvVar )
	hiddenPassword = getpass.getpass('Enter password for Oracle user %s. (The input will be hidden if supported by the OS platform)' % oraUser )
	if hiddenPassword == "" :
		if passwordEnv:
			hiddenPassword= passwordEnv
	return hiddenPassword

def validateSettings ( argObject ):
	checkSvnUser = False if argObject.use_default_svn_auth else True

	printErrorIfValueNone = {}

	if argObject.action == 'diff-db-db' :
		printErrorIfValueNone ['primary connect string'] = g_primaryConnectString
		printErrorIfValueNone ['secondary connect string'] = g_secondaryConnectString
		printErrorIfValueNone ['primary oracle user'] = g_primaryOraUser
		printErrorIfValueNone ['secondary oracle user'] = g_secondaryOraUser
		# printErrorIfValueNone ['mail recipient'] = argObject.mail_recipient
	elif argObject.action == 'diff-db-repo' :
		printErrorIfValueNone ['primary connect string'] = g_primaryConnectString
		printErrorIfValueNone ['primary oracle user'] = g_primaryOraUser
		printErrorIfValueNone ['repo url1'] = argObject.repo_url1
		if checkSvnUser: printErrorIfValueNone ['GIT user'] = argObject.svn_user
	elif argObject.action == 'diff-repo-repo' :
		printErrorIfValueNone ['1st repo url'] = argObject.repo_url1
		printErrorIfValueNone ['2nd repo url'] = argObject.repo_url2
		printErrorIfValueNone ['GIT user'] = argObject.svn_user
	elif argObject.action == 'checkin' :
		printErrorIfValueNone ['primary connect string'] = g_primaryConnectString
		printErrorIfValueNone ['primary oracle user'] = g_primaryOraUser
		printErrorIfValueNone ['GIT target URL'] = argObject.checkin_target_url
		if checkSvnUser: printErrorIfValueNone ['GIT user'] = argObject.svn_user
	else:
		_errorExit( "Check is not yet implemented for action %s!" % argObject.action )
		
	# now simply loop and check for None!
	for key in printErrorIfValueNone.keys():
		if printErrorIfValueNone[ key ] == None:
			_errorExit( "For action %s, '%s' is required!" % ( argObject.action, key ) )
			

def containsForeignCharacters( inputString, localCharacters ):
	"""Return True if inputString contains characters which are not within the set
	of localCharacters. If inputString or standardCharacters is None, return True anyway.
	Otherwise return False
	"""
	if inputString == None or localCharacters == None: 
		return False
	for c in inputString:
		if not c in localCharacters:
			return True
	
	return False

def fuzzyNormalizeOutputMessages ( stream ):
	"""subprocess returns an outputstream which appends a new line after each single character. 
	To be able to interpret the output message in a sensible way, we need to convert this 
	stream back to "normal". We check if the first N lines are indeed one character long. If
	yes, we join the complete list with ''. Then split on newline.
	"""
	rc = []
	""" we used to check 4 lines, but in case the query is to retrieve the database name 
	and the result is XE, we will have only 2 lines
	"""
	if len( stream ) > 1:
		line1, line2 = stream[0:2]
		if len( line1 ) == 1 and len( line2 ) == 1 :
			temp = ''.join( stream )
			# _dbx( temp )
			rc = temp.split( '\n' )
	else:
		rc = stream # no conversion 
	return rc


def tokenizeProxyUserConnectUser( oraUserString ):
	"""To connect via proxy user via SQLPLUS, the user name string is e.g. JOHNSON[SALES]
	This method checks the user name string for occurrence of embracing square brackets 
	at the right side of the string. If the pair of brackets is found, the value inside
	is returned as connectUser, the left side is returned as proxyUser
	"""
	match = re.search( r"(.*)\[(.*)\]", oraUserString )
	if match != None:
		proxyUser= match.group( 1 )
		connectUser= match.group( 2 )
	else:
		proxyUser= None
		connectUser= oraUserString
	return proxyUser, connectUser
	
def composeConnectCommand( oraUserString, oraPassword, hostPortServiceName ) :
	""" hostPortServiceName is given as host:port:serviceName
	example connect string without TNSNAMEE.ORA: 
	(DESCRIPTION=(ADDRESS_LIST=(ADDRESS=(PROTOCOL=TCP)(HOST=localhost.localdomain)(PORT=1521)))(CONNECT_DATA=(SERVER=DEDICATED)(SERVICE_NAME=ora9ir2.kyte.com)))
	"""
	
	oraIdStandardChars = 'abcdefghijklmnopqrstuvwxyz_0123456789'
	
	host, port, serviceName = hostPortServiceName.split(":")
	_dbx( host ); _dbx( serviceName)
	connectString = "\(DESCRIPTION=\(ADDRESS_LIST=\(ADDRESS=\(PROTOCOL=TCP\)\(HOST=(host)\)\(PORT=(port)\)\)\)\(CONNECT_DATA=\(SERVER=DEDICATED\)\(SERVICE_NAME=(serviceName)\)\)\)".format( host= host, port= port, serviceName= serviceName )
	_dbx( connectString )
	
	proxyUser, connectUser= tokenizeProxyUserConnectUser( oraUserString )

	if containsForeignCharacters( inputString= connectUser.lower(), localCharacters= oraIdStandardChars ):
		connectUser= '"' + connectUser + '"'

	if proxyUser == None:
		connectCommand = 'connect {connectUser}/"{password}"@{connectString}'.format( connectUser= connectUser, password= oraPassword, connectString= connectString )
	else:
		if containsForeignCharacters( inputString= proxyUser.lower(), localCharacters= oraIdStandardChars ):
			proxyUser= '"' + proxyUser + '"'
		connectCommand = 'connect {proxyUser}[{connectUser}]/"{password}"@{connectString}'.format( connectUser= connectUser
			, proxyUser= proxyUser
			, password= oraPassword
			, connectString= connectString )

	return connectCommand
	
def testOracleConnect( oraUser, oraPassword, connectString ) :
	connectCommand=  composeConnectCommand( oraUser, oraPassword, connectString ) 
	# _dbx( connectCommand )
	proc= subprocess.Popen( ['sqlplus', '-s', '/nolog'] ,stdin=subprocess.PIPE ,stdout=subprocess.PIPE ,stderr=subprocess.PIPE)
	msgLines, errLines= proc.communicate( connectCommand )
	if len( msgLines ) > 0 or len( errLines ) > 0 :
		print( sys.stderr, ''.join( msgLines ) )
		print( sys.stderr, ''.join( errLines  ) )

		_errorExit( "Oracle test connect on %s@%s failed! Check the credentials" % ( oraUser, connectString ) )


def getMultipleRowsSingleColumn( oraUser, oraPassword, connectString, queryWithColon ) :
	"""This method retrieves one column from a query which may return 0 
	to many rows because we start a sqlplus process each time. For occasional use it 
	should be ok but definitely not suitable for use within loops with many, many iterations.
	Also the query must not contain newlines since if it does the user has no means to 
	tell how many rows have been retrieved
	"""
	connectCommand=  composeConnectCommand( oraUser, oraPassword, connectString ) 
	formatOutputSettings= "set pagesize 0 linesize 1000 trimspool on head off echo off verify off feedback off"

	script = "\n".join ( [ connectCommand, formatOutputSettings, queryWithColon, 'exit' ] )
	# _dbx( script )
	proc= subprocess.Popen( ['sqlplus', '-s', '/nolog'] ,stdin=subprocess.PIPE ,stdout=subprocess.PIPE ,stderr=subprocess.PIPE)
	msgLines, errLines= proc.communicate( script )
	if len( errLines ) > 0 :
		print( sys.stderr, ''.join( msgLines ) )
		print( sys.stderr, ''.join( errLines  ) )

		_errorExit( "Query returns errors %s:\n\t" % "\t\n".join( errLines ) )

	msgLines = fuzzyNormalizeOutputMessages( msgLines )
	if len( msgLines ) > 1 :
		lastLine= msgLines[ len( msgLines ) - 1 ]
		if lastLine.strip() == lastLine:
			msgLines= msgLines[0 :  len( msgLines ) - 1 ]
	# _dbx(  msgLines ) ; _dbx( len( msgLines ) )
	return msgLines

def expensiveGetOneColumnValue( oraUser, oraPassword, connectString, queryWithColon ) :
	"""This is an expensive operation to retrieve one column from a query which must return
	a single row because we start a sqlplus process each time. For occasional use it 
	should be ok but definitely not suitable for high volumn usage
  
	"""
	connectCommand=  composeConnectCommand( oraUser, oraPassword, connectString ) 
	formatOutputSettings= "set pagesize 0 linesize 1000 trimspool on head off echo off verify off feedback off"

	script = "\n".join ( [ connectCommand, formatOutputSettings, queryWithColon, 'exit' ] )
	# _dbx( script )
	proc= subprocess.Popen( ['sqlplus', '-s', '/nolog'] ,stdin=subprocess.PIPE ,stdout=subprocess.PIPE ,stderr=subprocess.PIPE)
	msgLines, errLines= proc.communicate( script )
	if len( errLines ) > 0 :
		print( sys.stderr, ''.join( msgLines ) )
		print( sys.stderr, ''.join( errLines  ) )

		_errorExit( "Query returns errors %s:\n\t" % "\t\n".join( errLines ) )

	msgLines = fuzzyNormalizeOutputMessages( msgLines )
	# if there are more than one line and the last line is empty, we may remove it
	if len( msgLines ) > 1 :
		lastLine= msgLines[ len( msgLines ) - 1 ]
		if lastLine.strip() == lastLine:
			msgLines= msgLines[0 :  len( msgLines ) - 1 ]
	# _dbx( "=>\n".join( msgLines ) )
	if len( msgLines ) == 0 :
		_errorExit( "Query returns no result" )
	elif len( msgLines ) > 1 :
		_errorExit( "Query returns more than one line. Could it be that Newline characters are inside the retrieved column?" )
	return msgLines[0]



def composePath4DatabaseObject( rootPath, dbName, schema= None, objectType= None, objectName= None ):
	"""Example for the input '/tmp', 'CRMDB', 'SALES_DATA', 'TABLE', 'SALES_REGION'
	the following string would be returned:
	'/tmp/crmdb/sales_data/tables/sales_region.sql'

	If root == '', the path would be relative:
	'crmdb/sales_data/tables/sales_region.sql'
	"""

	dirPath= rootPath

	if dbName != None:
		dirPath= os.path.join( dirPath, dbName.lower() )

	if schema != None:
		dirPath= os.path.join( dirPath, schema.lower() )

	if objectType != None:
	
		if objectType not in g_supportedObjectTypes:
			_errorExit( "Object type '%s' is not supported!" % objectType )
		dir4ObjectType = objectType.lower() +'s'
		dirPath= os.path.join( dirPath, dir4ObjectType )

	if objectName != None:
		fullPath= os.path.join( dirPath, objectName.lower() ) + '.sql'
	else:
		fullPath= dirPath

	return fullPath, dirPath

def composeSpoolScripts4ObjectType( oraUser, oraPassword, connectString, dbName, schema, objectType):
	"""Query the Oracle DB dictionary to generated SELECT DBMS_META.GET_DDL queries.
	Also wrap each query within proper spooling commands so that the extracted code 
	is stored at the intended locatioan such as /tmp/crmdb/sales_data/tables/sales_region.sql
	"""
	connectCommand=  composeConnectCommand( oraUser, oraPassword, connectString ) 
	formatOutputSettings= "set pagesize 0 linesize 1000 trimspool on head off echo off verify off feedback off long 100000 longchunksize 100000"

	transformCommand = configureTransformation4ObjectType( objectType )
	entityDelim = '<#314Del1m$>'
	condensedObjectType= objectType #fixme

	objectsView = 'dba_objects' if g_useDbaViews else 'all_objects'
	queryGenGetDdl = """
with my_objs as (
    select object_name
    from {objectsView}
    where 1=1
      and object_type = '{objectType}'
      and owner = '{schema}'
)
 SELECT '{replaceSpoolTargetFor}{schema}{entityDelim}{condensedObjectType}{entityDelim}'||object_name
||chr(10)
||'SELECT DBMS_METADATA.GET_DDL(object_type=> ''{objectType}'', name=>'''||object_name||''' , SCHEMA=>''{schema}'' ) AS q FROM dual;'
||chr(10)||'spool off'
 cmd
 from my_objs
;
	""".format( replaceSpoolTargetFor= g_spoolTargetMarker
		, objectType= objectType
		, condensedObjectType= condensedObjectType
		, schema= schema
		, entityDelim= entityDelim
		, objectsView= objectsView
	)
	
	_script = "\n".join ( [ connectCommand, formatOutputSettings, queryGenGetDdl, 'exit' ] )
	proc= subprocess.Popen( ['sqlplus', '-s', '/nolog'] ,stdin=subprocess.PIPE ,stdout=subprocess.PIPE ,stderr=subprocess.PIPE ) # universal_newlines= True  seems to have no effect!
	getDdlCodeBlocks, errLines= proc.communicate( _script )
	if len( errLines ) > 0 :
		print( sys.stderr, ''.join( getDdlCodeBlocks ) )
		print( sys.stderr, ''.join( errLines  ) )

		_errorExit( "Query returns errors %s:\n\t" % "\t\n".join( errLines ) )

	getDdlCodeBlocks= fuzzyNormalizeOutputMessages( getDdlCodeBlocks ) 
	# replace g_spoolTargetMarker but also return set of directories for the spool files
	spoolDirs = []
	markerLen= len( g_spoolTargetMarker )
	cntObject= 0
	for i, line in enumerate( getDdlCodeBlocks ):
		if line.startswith( 'ORA-' ):
			_infoTs( 'Found error whiling checking DDL extraction command: --> %s' % line ) 
			_errorExit( 'Exit due to previous error' )
		elif line.startswith( g_spoolTargetMarker ):
			payload= line[ markerLen : ]
			schema, objectType, objectName= payload.split( entityDelim )
			fullPath, dirPath=  composePath4DatabaseObject( rootPath= g_workAreaRoot
				, dbName = dbName, schema= schema, objectType= objectType
				, objectName= objectName )
			cntObject += 1
			# _dbx( spoolFilePath )
			if dirPath not in spoolDirs:
				spoolDirs.append( dirPath )
			getDdlCodeBlocks[i] = 'spool ' + fullPath
				
	outputScript = connectCommand + "\n" +  \
		formatOutputSettings + "\n" +  \
		transformCommand + "\n" +  \
		"\n".join( getDdlCodeBlocks )
		
	return outputScript, spoolDirs, cntObject

def sqlplusNologRunHereDoc ( hereDoc ):
	""" invoke "sqlplus /nolog" to execute a script in memory
	We pipe the hereDoc to sqlplus process. 
	""" 

	errLines = []

	commandArgs= ['sqlplus', '-s', '/nolog' ]
	# _dbx( hereDoc )
	proc= subprocess.Popen( commandArgs, stdin=subprocess.PIPE ,stdout=subprocess.PIPE ,stderr=subprocess.PIPE, universal_newlines= True )
	msgLines, errLines= proc.communicate( hereDoc.encode('utf-8') )

	stdoutErrFile= fileSqlplusOutputIfErrorsFound( msgLines )

	if stdoutErrFile != None:
		_errorExit( "Check sqlplus error in file %s" % stdoutErrFile)

	stderrErrFile= fileSqlplusOutputIfErrorsFound( errLines )
	if stderrErrFile != None:

		_errorExit( "Check sqlplus error in file %s" % stderrErrFile)

	return msgLines

def fileSqlplusOutputIfErrorsFound ( msgLines ):
	logFile= None
	if msgLines != None :
		for line in msgLines:
			# _dbx( line )
			if line.startswith( 'ORA-' ) or line.startswith( 'SP2-' ):
				logFile = tempfile.mktemp()
				fh = open( logFile, 'w' )
				fh.writelines( msgLines )
				fh.close()
				break
	# _dbx( logFile )
	return logFile

def saveLinesToTempFile ( msgLines ):
	if msgLines != None :
		logFile = tempfile.mktemp()
		fh = open( logFile, 'w' )
		lno= 0
		for line in msgLines: 
			lno += 1
			if line.rstrip() == line: # there is no endOfLine respectively newline
				line = line + '\n'
			fh.write( line )
		fh.close()

		return logFile
	else:
		 return None

def saveStringToTempFile ( string ):
	if string != None :
		logFile = tempfile.mktemp()
		fh = open( logFile, 'w' )
		fh.write( string )
		fh.close()

		return logFile
	else:
		 return None

def configureTransformation4ObjectType ( objectType ):
	"""In general it is better to have a more compact DDL script 
	The default behaviour of DBMS_METADATA however is to return 
	the most verbose version of the script so we need to offset 
	this behaviour according to the object type
	"""

	if objectType == "TABLE":
		rc = """begin 
	DBMS_METADATA.SET_TRANSFORM_PARAM(TRANSFORM_HANDLE=>
		DBMS_METADATA.SESSION_TRANSFORM, name=>'STORAGE', value=>false);
	DBMS_METADATA.SET_TRANSFORM_PARAM(TRANSFORM_HANDLE=>
		DBMS_METADATA.SESSION_TRANSFORM, name=>'SQLTERMINATOR', value=>true);
	DBMS_METADATA.SET_TRANSFORM_PARAM(TRANSFORM_HANDLE=>
		DBMS_METADATA.SESSION_TRANSFORM,name=>'SEGMENT_ATTRIBUTES', value=>false);
end;
/
		"""
	else:
		rc= ''

	return rc

def extractScriptsFromDatabase( includeSchemas, includeObjectTypes,  oraUser, oraPassword, connectString, dbName ):
	"""Extract DDL scripts for the given schemas and object types from the given database
	"""
	statsMsgs= []
	if len( includeSchemas ) == 0:
		_errorExit( "No schemas have been specified from which objects are to be extracted!"  )
	if len( includeObjectTypes ) == 0:
		_errorExit( "No object types have been specified for which scripts are to be extracted" ) 

	statsMsgs.append("Scripts are to be extracted for the following %d schemas at '%s':" % ( len( includeSchemas ), dbName) ) 
	for schema in includeSchemas: 
		statsMsgs.append( "\t" + schema )
	statsMsgs.append("And for the following %d object types:" % len( includeObjectTypes ) ) 
	for objectType in includeObjectTypes: 
		statsMsgs.append( "\t" + objectType )

	# _dbx( len( includeObjectTypes ) )
	for schema in includeSchemas:
		dbSchemaDir= composePath4DatabaseObject( g_workAreaRoot, dbName= dbName, schema= schema ) [0]
		os.makedirs( dbSchemaDir )
		schemaStats= []
		for objectType in includeObjectTypes:
			bigSpoolScript, objectTypeSubDirs, cntObject= composeSpoolScripts4ObjectType(  oraUser= oraUser
				, oraPassword= oraPassword, connectString= connectString
				, dbName= dbName, schema= schema, objectType= objectType )
			# append a string element like 'Tables: 3' or 'Packages: 1'
			schemaStats.append( "%s: %d" % ( objectType.title(), cntObject ) )
			# create the directories as SQLPLUS SPOOL does not create the parent directories to a spool file
			for dir in objectTypeSubDirs: 
				os.makedirs( dir )
			# _dbx( bigSpoolScript ); _errorExit( "test" )

			_infoTs( "Extracting %s scripts for schema %s from database %s..." % ( objectType, schema, dbName ), True )
			sqlplusNologRunHereDoc( bigSpoolScript )
		statsMessage=  "\nObjects found in schema %s@%s:\n\t%s" % ( schema, dbName, ' '.join( schemaStats ) ) 
		statsMsgs.append( statsMessage )

	_infoTs( statsMessage )

	return '\n'.join( statsMsgs )

def chdirAndGetFindOutput ( path ):
	"""Calls the unix find command and returns its output to the calling function
	bomb out if any error was detected but only displayed upto 10 lines of the stderr
	"""
	
	savedWorkDir = os.getcwd() ; os.chdir( path )

	findCmdArgsUnix= [ 'find', '.' ]
	
	proc= subprocess.Popen( findCmdArgsUnix, stdin=subprocess.PIPE, stdout=subprocess.PIPE ,stderr=subprocess.PIPE) # universal_newlines= True  has no effect
	unixOutMsgs, errMsgs= proc.communicate()

	if len( errMsgs ) > 0 : # got error, return immediately
		_errorExit( 'got error from find. Only first 10 lines are shown:\n%s ' % '\n'.join( errMsgs [ 0: 10]  ) )
	unixOutMsgs= fuzzyNormalizeOutputMessages( unixOutMsgs )
	# _dbx( "->".join( unixOutMsgs ) )# ; _errorExit( "test" )
	os.chdir( savedWorkDir )

	return unixOutMsgs 

def genUnixDiff ( oldPath, newPath, recursive= False ):
	"""Calls the unix diff command and returns its output to the calling function
	bomb out if any error was detected but only displayed upto 10 lines of the stderr
	"""
	diffCmdArgsUnix= [ 'diff', '-b', oldPath, newPath ]
	if recursive: diffCmdArgsUnix.insert( 1, '-r' )
	
	# for a in diffCmdArgsUnix: _dbx( a ); _errorExit( 'test' )
	proc= subprocess.Popen( diffCmdArgsUnix, stdin=subprocess.PIPE, stdout=subprocess.PIPE ,stderr=subprocess.PIPE, universal_newlines= True )
	unixOutMsgs, errMsgs= proc.communicate()

	if len( errMsgs ) > 0 : # got error, return immediately
		_errorExit( 'got error from diff. Only first 10 lines are shown:\n%s ' % '\n'.join( errMsgs [ 0: 10]  ) )

	# _dbx(  len( unixOutMsgs ) )
	return unixOutMsgs 

def genDiffAndOverwriteOldFile ( oldFile, newFile ):
	""" Unix line command diff can produce only plaintext output and it fails to ignore GIT keywords.
	It also shows removed lines sometimes in a crammed (the lines) fashion.
	"svn diff" can ignore GIT keywords but it is bad at ignoring whitespaces even with -x -b!

	If both old and new file exist, do a unix diff then do a svn diff 
	So we do both and pick the one with more compact output in terms of character count
	"""
	
	unixOutMsg= genUnixDiff ( oldFile, newFile )
	unixDiffSize = getTextSize( unixOutMsg )

	# Now overwrite the checke -out version
	shutil.copyfile( newFile, oldFile )

	diffCmdArgsSvn= [ 'svn', 'diff', oldFile, '-x', '-b' ]
	# _dbx ( ' '.join( diffCmdArgsSvn ) )
	proc= subprocess.Popen( diffCmdArgsSvn, stdin=subprocess.PIPE, stdout=subprocess.PIPE ,stderr=subprocess.PIPE)
	svnOutMsgs, errMsgs= proc.communicate()

	if len( errMsgs ) > 0 : # got error, return immediately
		_infoTs(  errMsgs.split( '\n' ) )
		_errorExit( 'Aborted due to preceding errors' )
	else: # note empty svn diff output is legal!
		svnDiffSize = getTextSize( svnOutMsgs )

	if svnDiffSize <= unixDiffSize:
		cmdString =  ' '.join( diffCmdArgsSvn )
		outputText = "\"%s\" produced the follwing output\n%s\n%s" % ( cmdString ,  '_' * 80 ,  svnOutMsgs ) 
	else:
		cmdString =  ' '.join( diffCmdArgsUnix )
		outputText = "\"%s\" produced the follwing output\n%s\n%s" % ( cmdString ,  '_' * 80 ,  unixOutMsg ) 
	
	return ( outputText .split( '\n' ) )

def compareTwoTreesReturnFile( treeA, treeB, expressiveNameA, expressiveNameB, copyBFilesToAAndDiff = False ):
	buddyFileMatches = []
	diffOutputsByNode = {}
	buddyADoesNotExist = []
	buddyBDoesNotExist = []
	buddyIsNotDir = []
	buddyIsNotFile = []

	_infoTs( "Comparing two trees:\n  A: '%s', expressiveName: '%s'\n  B: '%s' expressiveName: '%s' " % ( treeA, expressiveNameA, treeB, expressiveNameB ) ) 

	diffOutputFile = tempfile.mktemp()
	outputFH = open( diffOutputFile, 'w' )

	# while walking tree A, we check if the buddy in B exists and has the same node kind.
	# if both nodes exist and are a file, we also perform a diff.
	fileDiffCnt= 0
	for root, dirs, files in os.walk( treeA ):
		for dir in dirs:
			fullPathA = os.path.join( root, dir )
			relPath = os.path.relpath( fullPathA, treeA )
			if relPath.startswith( '.svn' ) or  relPath.endswith( '.svn' ) or  '/.svn/' in relPath :
				None
			else:
				# _dbx( relPath )
				fullPathB = os.path.join( treeB, relPath )
				if os.path.isfile( fullPathB ):
					buddyIsNotDir.append( relPath )
				elif not os.path.exists( fullPathB ):
					buddyBDoesNotExist.append( relPath )
		# for "svn diff", we need to change to sandbox dir
		if copyBFilesToAAndDiff:
			os.chdir( treeA )
		for file in files:
			fullPathA = os.path.join( root, file )
			relPath = os.path.relpath( fullPathA, treeA )
			if relPath.startswith( '.svn' ) or  relPath.endswith( '.svn' ) or  '/.svn/' in relPath :
				None
			else:
				# _dbx( relPath )
				fullPathB = os.path.join( treeB, relPath )
				if os.path.isdir( fullPathB ):
					buddyIsNotFile.append( relPath )
				elif not os.path.exists( fullPathB ):
					buddyBDoesNotExist.append( relPath )
				elif os.path.isfile( fullPathB ):
					if copyBFilesToAAndDiff:
						shutil.copyfile( fullPathB, fullPathA )
						svnRc, msgLines, errLinesFromSvn = svnHelper.svnQuery ( ['diff', relPath ] )
						if svnRc != 0 :
							_infoTs( "Function %s got error code %d from svn." % ( _func_(), svnRc ) )
							if len( errLinesFromSvn ) > 0:
								_infoTs( "Error output:" )
								for errLine in errLinesFromSvn: print(  errLine )
							_errorExit( 'aborting due to previous error' )
					else:
						msgLines= genUnixDiff( oldPath= fullPathA, newPath= fullPathB )

					if len( msgLines ) == 0:
							buddyFileMatches.append( relPath )
					else:
						fileDiffCnt += 1
						# _dbx( relPath ); _dbx( "type: %s, len: %d" % (type( msgLines ), len( msgLines ) ) )
						if type( msgLines ) == str: 
							msgLines= msgLines .split( '\n' )
							#_dbx( "type: %s, len: %d" % (type( msgLines ), len( msgLines ) ) )

						if  len( msgLines ) <= g_maxDiffLines:
							diffOutputsByNode[ relPath ] =   '\n'.join( msgLines )
						else:
 							excerpt= msgLines [ 0 : g_maxDiffLines - 1] 
							# _dbx( "type: %s, len: %d" % (type( excerpt ), len( excerpt ) ) )
							excerpt.append( "\n... diff output contained %d lines. The rest has been suppressed " % len( msgLines ) )
							diffOutputsByNode[ relPath ] = '\n'.join( excerpt )

						# _dbx( "type: %s, len: %d" % (type( diffOutputsByNode[ relPath ] ), len( diffOutputsByNode[ relPath ] ) ) )
						

			# if fileDiffCnt > 4: _errorExit( "test" )
	# while walking tree B, we check only if any node in B does not have a buddy in A
	for root, dirs, files in os.walk( treeB ):
		for dir in dirs:
			fullPathB = os.path.join( root, dir )
			relPath = os.path.relpath( fullPathB, treeB )
			if relPath.startswith( '.svn' ) or  relPath.endswith( '.svn' ) or  '/.svn/' in relPath :
				None
			else:
				fullPathA = os.path.join( treeA, relPath )
				if not os.path.exists( fullPathA ):
					buddyADoesNotExist.append( relPath )
		for file in files:
			fullPathB = os.path.join( root, file )
			relPath = os.path.relpath( fullPathB, treeB )
			if relPath.startswith( '.svn' ) or  relPath.endswith( '.svn' ) or  '/.svn/' in relPath :
				None
			else:
				fullPathA = os.path.join( treeA, relPath )
				if not os.path.exists( fullPathA ):
					buddyADoesNotExist.append( relPath )

	outputFH.write("*" * 80 + '\n' + '** Result of comparing ' + '\n** ' + expressiveNameA + '\n** ' + expressiveNameB + '\n'*2 )

	if len( buddyFileMatches ) > 0:
		outputFH.write("Following files match:\n" )
		for relPath in buddyFileMatches: 
			outputFH.write( '-> ' + relPath + "\n")

	if len( buddyIsNotFile ) > 0:
		outputFH.write("\nFollowing nodes exist as files in \n\t%s\nbut but the buddies are directories in \n\t%s:\n" % ( expressiveNameA, expressiveNameB ) )
		for relPath in buddyIsNotFile: 
			outputFH.write( '-> ' + relPath + "\n")

	if len( buddyIsNotDir ) > 0:
		outputFH.write("\nFollowing nodes exist as directories in \n\t%s\nbut but the buddies are files in \n\t%s:\n" % ( expressiveNameA, expressiveNameB ) )
		for relPath in buddyIsNotDir: 
			outputFH.write( '-> ' + relPath + "\n")

	if len( buddyBDoesNotExist ) > 0:
		outputFH.write("\nFollowing nodes exist in \n\t%s\nbut NOT in \n\t%s:\n" % ( expressiveNameA, expressiveNameB ) )
		for relPath in buddyBDoesNotExist: 
			outputFH.write( '-> ' + relPath + "\n")

	if len( buddyADoesNotExist ) > 0:
		outputFH.write("\nFollowing nodes exist in \n\t%s\nbut NOT in \n\t%s:\n" % ( expressiveNameB, expressiveNameA ) )
		for relPath in buddyADoesNotExist: 
			outputFH.write( '-> ' + relPath + "\n")

	if len( diffOutputsByNode ) > 0:
		for relPath, diffOutput in diffOutputsByNode.iteritems() : 
			urlNodeA = os.path.join( expressiveNameA, relPath )
			urlNodeB = os.path.join( expressiveNameB, relPath )
			outputFH.write( "\n%s \nsvn_diff result on the following files:\n\t%s and \n\t%s\n%s\n" % ( '-'*80, urlNodeA, urlNodeB , '-'*80) )
			outputFH.write( "".join( diffOutput )  + "\n" )

	outputFH.close()

	return diffOutputFile

def diffTwoTexts( text1, text2 ):
	file1= saveLinesToTempFile( text1 )
	file2= saveLinesToTempFile( text2 )
	result = genUnixDiff( file1, file2 )
	# _dbx( file1 ); _dbx( file2 )
	# diffFile= saveLinesToTempFile( result ); _errorExit( diffFile )
	return result 
	
def sendMimeText ( recipients, subject, asciiText, htmlText= None, zipAttachment = None ):
	from email.mime.text import MIMEText
	from email.mime.base import MIMEBase
	from email.mime.multipart import MIMEMultipart
	from email import encoders
	
	import smtplib
	import socket
	
	# Create message container - the correct MIME type is multipart/alternative.
	
	hostname = socket.gethostname()
	me = 'donotreply@' + hostname
	
	msg = MIMEMultipart()
	msg['Subject'] = subject
	msg['From'] = me
	msg['To'] = recipients
	
	# Create the body of the message (a plain-text and an HTML version).
	

	# Inline attach plain text
	part1 = MIMEText(asciiText, 'plain')
	msg.attach(part1)

	# Inline attach html version
	if htmlText != None:
		part2 = MIMEText(htmlText, 'html')
		# According to RFC 2046, the last part of a multipart message, in this case
		# the HTML message, is best and preferred.
		msg.attach(part2)
	
	if zipAttachment != None:
		fh = open( zipAttachment, 'r' )
		part3 = MIMEBase( 'application', 'zip' ) 
		part3.set_payload( fh.read() )
		encoders.encode_base64( part3 )
		zipBaseName = os.path.basename( zipAttachment )
		part3.add_header( 'Content-Disposition', 'attachment; filename="%s"' % zipBaseName )
		msg.attach( part3 )
	
	# Send the message via local SMTP server.
	s = smtplib.SMTP('localhost')
	# sendmail function takes 3 arguments: sender's address, recipient's address
	# and message to send - here it is sent as one string.
	s.sendmail(me, recipients, msg.as_string())

	s.quit()

def performActionDiffDbDb ( argObject, includeSchemas, includeObjectTypes) :
	""" extract DDL scripts from database A and B which match the specified patterns
	 (schemas and object types), store the scripts underneath the
	sandbox root and perform a recursive diff on each scripts from both databases.
	"""
	global g_primaryOraPassword
	global g_secondaryOraPassword

	validateSettings( argObject )

	g_primaryOraPassword   = getOraPassword( oraUser= g_primaryOraUser  , oraPasswordEnvVar= g_envVarNamePrimarySecret
		, batchMode= argObject.batch_mode )
	g_secondaryOraPassword = getOraPassword( oraUser= g_secondaryOraUser, oraPasswordEnvVar= g_envVarNameSecondarySecret
		, batchMode= argObject.batch_mode )

	# ping the primary DB
	_infoTs( 'Testing oracle DB connection to %s' % g_primaryConnectString, True )
	testOracleConnect(  oraUser= g_primaryOraUser, oraPassword= g_primaryOraPassword, connectString= g_primaryConnectString )
	primaryDbName= expensiveGetOneColumnValue( oraUser= g_primaryOraUser
		, oraPassword= g_primaryOraPassword, connectString= g_primaryConnectString
		, queryWithColon = g_queryDbName ) 

	# ping the secondary DB
	# _dbx( "'%s'" % g_secondaryOraPassword ) ; _errorExit( "test" )
	_infoTs( 'Testing oracle DB connection to %s' % g_secondaryConnectString, True )
	testOracleConnect(  oraUser= g_secondaryOraUser, oraPassword= g_secondaryOraPassword, connectString= g_secondaryConnectString )
	secondaryDbName= expensiveGetOneColumnValue( oraUser= g_secondaryOraUser
		, oraPassword= g_secondaryOraPassword, connectString= g_secondaryConnectString
		, queryWithColon = g_queryDbName ) 

	primarySandboxPath= composePath4DatabaseObject( g_workAreaRoot, primaryDbName ) [0]
	secondarySandboxPath= composePath4DatabaseObject( g_workAreaRoot, secondaryDbName ) [0]
	os.makedirs( primarySandboxPath ) # make sure the path does exist even if no script will be extracted
	os.makedirs( secondarySandboxPath ) # make sure the path does exist even if no script will be extracted

	if True: # make it easier to skip while testing
		statusMsgPrimary = extractScriptsFromDatabase( includeSchemas= includeSchemas, includeObjectTypes= includeObjectTypes 
			,  oraUser= g_primaryOraUser, oraPassword= g_primaryOraPassword, connectString= g_primaryConnectString \
			, dbName= primaryDbName)
			
		statusMsgSecondary= extractScriptsFromDatabase( includeSchemas= includeSchemas, includeObjectTypes= includeObjectTypes 
			,  oraUser= g_secondaryOraUser, oraPassword= g_secondaryOraPassword, connectString= g_secondaryConnectString \
			, dbName= secondaryDbName)
			
	mailTextLines= []	
	mailTextLines.append( statusMsgPrimary + '\n' + '*'*80 )
	mailTextLines.append( statusMsgSecondary + '\n' + '*'*80 )

	for schema in includeSchemas:
		treeA=  composePath4DatabaseObject( g_workAreaRoot, primaryDbName, schema ) [0]
		treeB=  composePath4DatabaseObject( g_workAreaRoot, secondaryDbName, schema ) [0]
		diffTreeOutputFile= compareTwoTreesReturnFile( treeA= treeA, treeB= treeB
			, expressiveNameA= schema+'@'+ primaryDbName , expressiveNameB= schema+'@'+ secondaryDbName
			, copyBFilesToAAndDiff = False )
	
		diffOutput= open( diffTreeOutputFile, 'r' ).readlines()
		mailTextLines.extend( diffOutput )

	textSize= getTextSize( mailTextLines )
	if argObject.mail_recipient != None:
		_infoTs( "Sending diff output to %s (text size: %d)" % ( argObject.mail_recipient, textSize) )
		sendMimeText ( recipients= argObject.mail_recipient, subject= "Diff for specified database objects"
			, asciiText= ''.join( mailTextLines ) )
	else:
		tempFile= saveLinesToTempFile( mailTextLines )
		_infoTs( "diff output stored to %s (text size: %d)" % ( tempFile, textSize) )


def addNewNodesToSvn( sandbox ):
	""" cd to the sandbox and run "svn status" to see which nodes are not yet scheduled.
	Add them
	"""
	savedWorkDir = os.getcwd(); os.chdir( sandbox )

	rc, msgLines, errLines = svnHelper.svnQuery ( queryArgs= ['status'] )
	if errLines != None and len( errLines ) > 0: 
		_infoTs( ''.join( errLines ) )
		_errorExit( "svn checkin failed due to previous issues" )
	
	newNodes= []
	for line in msgLines :
		if line.startswith( '? '):
			node= line[1:].strip()
			# _dbx( node )
			newNodes.append( node )

	svnAddCmdArgs= ['add']
	if len( newNodes ) > 0:
		svnAddCmdArgs.extend( newNodes )
		rc, msgLines, errLines = svnHelper.svnQuery ( queryArgs= svnAddCmdArgs )
		if errLines != None and len( errLines ) > 0: 
			_infoTs( ''.join( errLines ) )
			_errorExit( "svn add failed due to previous issues" )

	os.chdir( savedWorkDir )

def mergeTreeWithDeleteCheck ( sourceTree, targetTree, deleteCheckObjectTypes ):
	"""When the scripts are extracted into a tree and the tree is supposed 
	to overwrite the checked-in versions, what happens with those object 
	which have once been checked in but no longer exist and hence are not
	estracted? Because of this reason, we want to visualiz these "obsolete" 
	nodes by optionally creating a trash bin subfolder in the same
	directory as the obsolete file node. Note we assume that in the "new"
	tree, at least the object type folder is created if no object of the type
	exists. This task is called "delete check"
	
	The delete check is only applied to the given deleteCheckObjectTypes
	"""

	trashDirFixName= '_trashbin'

	_infoTs( "merging with delete check: '%s' --> '%s'" % (  sourceTree, targetTree  ) )
	# walk from source tree and copy
	for root, dirs, files in os.walk( sourceTree ):
		""" fore directory nodes in the source tree, we only need to ensure
		it exists also in the destination tree
		"""
		for dir in dirs:
			fullPathA = os.path.join( root, dir )
			relPath = os.path.relpath( fullPathA, sourceTree )
			if relPath.startswith( '.svn' ) or  relPath.endswith( '.svn' ) or  '/.svn/' in relPath :
				None
			else:
				# _dbx( relPath )
				fullPathB = os.path.join( targetTree, relPath )
				if os.path.isfile( fullPathB ):
					_errorExit( "Node '%s' is a directory in '%s' but a file in '%s'!" % ( relPath, sourceTree, targetTree ) )
				elif not os.path.exists( fullPathB ):
					os.makedirs( fullPathB ) # make sure the path does exist even if no script will be extracted

		for file in files:
			fullPathA = os.path.join( root, file )
			relPath = os.path.relpath( fullPathA, sourceTree )
			if relPath.startswith( '.svn' ) or  relPath.endswith( '.svn' ) or  '/.svn/' in relPath :
				None
			else:
				fullPathB = os.path.join( targetTree, relPath )
				if os.path.isdir( fullPathB ):
					_errorExit( "Node '%s' is a file in '%s' but a directory in '%s'!" % ( relPath, sourceTree, targetTree ) )
				else:
					# _dbx( "copying %s to %s " % ( fullPathA , fullPathB ) )
					shutil.copyfile( fullPathA, fullPathB )

	fullPathA= None; fullPathB= None; 

	# walk from target and move obsolete nodes into trash bin 

	relevantFolderNames= [] # pre-compute parent folder names of file node which are relevant
	for type in deleteCheckObjectTypes :
		relevantFolderNames.append( type.lower() + 's' )  # not very clean solution!
	# _dbx( "relevant folders:\n%s" % "\n".join( relevantFolderNames ) )

	for root, dirs, files in os.walk( targetTree ):
		if root.startswith( '.svn' ) or  root.endswith( '.svn' ) or  '/.svn/' in root :
			continue
		elif os.path.basename( root ) == trashDirFixName:
			continue
		elif root == trashDirFixName:
			continue

		# tricky solution: only do delete check if the parent node of the file indicates 
		# a relevant object type
		dummyRoot, typeFolderName= os.path.split( root )
		# _dbx( dummyRoot ); _dbx( typeFolderName )
		if not typeFolderName in relevantFolderNames : 
			#_dbx( "skipping type folder %s" % typeFolderName )

			continue
		
		# _dbx( "doing dlete check for folder %s" % typeFolderName )
		for dir in dirs:
			if dir in ('.svn', trashDirFixName ):

				continue

			fullDirPathSandbox = os.path.join( root, dir )
			relPath = os.path.relpath( fullDirPathSandbox, targetTree )

			fullDirPathExtract = os.path.join( sourceTree, relPath )
			if not os.path.exists( fullDirPathExtract ):
				# _dbx( "fullDirPathExtract does not exist: %s" % fullDirPathExtract )
				assertSvnSubDir( parentPath= fullDirPathSandbox, subDir= trashDirFixName )
				localSvnMove( sandboxPath= fullDirPathSandbox, sourceNode= dir, targetNode= trashDirFixName )

		for file in files:
			if file == trashDirFixName:
				_errorExit( "Invalid structure detected. '%s' exists as file node in '%s'!" % ( trashDirFixName, fullFilePathSandbox ) )
			else:
				fullFilePathSandbox = os.path.join( root, file )
				relPath = os.path.relpath( fullFilePathSandbox, targetTree )
				fullFilePathExtract = os.path.join( sourceTree, relPath )
				fileExists= os.path.isfile( fullFilePathExtract )
				# _dbx( fullFilePathExtract + ' exists in extracted tree?' );  _dbx( fileExists )	
				if fileExists:
					None # this may well be our copy from source tree
				elif os.path.isdir( fullFilePathExtract ):
					_errorExit( "Node '%s' is a file in '%s' but a directory in '%s'!" % ( relPath, targetTree, sourceTree ) )
				else :
					fullDirPathSandbox= os.path.split( fullFilePathSandbox )[0]
					trashbinDir= assertSvnSubDir( parentPath= fullDirPathSandbox, subDir= trashDirFixName )
					_dbx( "trashbinDir: " + trashbinDir )
					trashbinFileNode= os.path.join( trashbinDir, file )
					if os.path.isfile( trashbinFileNode ):
						localSvnDelete( trashbinFileNode )
					else:
						localSvnMove( sandboxPath= fullDirPathSandbox, sourceNode= file, targetNode= trashDirFixName )

def  localSvnDelete( node ):
	""" need to do this for example we want to move an object into _trashbin but that object 
	is already present there. In this case it is ok to svn delete it (without commit) yet
	and do the actual svn move
	"""
	# _dbx( node )

	parentPath = os.path.split( node ) [0]
	savedWorkDir = os.getcwd(); os.chdir( parentPath )

	svnCmdArgs= ['delete',  node]
	rc, msgLines, errLines = svnHelper.svnQuery ( queryArgs= svnCmdArgs )
	if msgLines != None: 
		_infoTs ( "Output from svn DELETE:\n%s" % ''.join( msgLines ) )
	if errLines != None and len( errLines ) > 0 : 
		_infoTs( ''.join( errLines ) )
		_errorExit( "svn DELETE failed due to previous issues" )

def  localSvnMove( sandboxPath, sourceNode, targetNode ):
	"""chdir to sandboxPath and schedules a add + delete (move)
	"""

	# _dbx( sandboxPath ); _dbx( sourceNode + ' --> ' +  targetNode )

	savedWorkDir = os.getcwd(); os.chdir( sandboxPath )

	svnCmdArgs= ['move',  sourceNode, targetNode]
	rc, msgLines, errLines = svnHelper.svnQuery ( queryArgs= svnCmdArgs )
	if msgLines != None: 
		_infoTs ( "Output from svn MOVE:\n%s" % ''.join( msgLines ) )
	if errLines != None and len( errLines ) > 0 : 
		_infoTs( ''.join( errLines ) )
		_errorExit( "svn MOVE failed due to previous issues" )

	os.chdir( savedWorkDir )

def  assertSvnSubDir( parentPath, subDir ):
	"""Make sure a GIT directory exists (at least locally added) under the parent 
	as the current working directory
	"""
	# _dbx( parentPath + ' subdir: ' + subDir )
	savedWorkDir = os.getcwd(); os.chdir( parentPath )
	if not os.path.isdir( subDir ):
		os.makedirs( subDir ) 

		svnCmdArgs= ['add', subDir]
		rc, msgLines, errLines = svnHelper.svnQuery ( queryArgs= svnCmdArgs )
		if msgLines != None: 
			_infoTs (''.join( msgLines ) )
		if errLines != None and len( errLines ) > 0 : 
			_infoTs( ''.join( errLines ) )
			_errorExit( "svn checkin failed due to previous issues" )

	os.chdir( savedWorkDir )
	return os.path.join(  parentPath, subDir )

def promptAndSetSvnPasswor( svnUser, batchMode ):
	_dbx( "batch_mode" if batchMode else "interactive" )
	svnHelper.g_svnUser= svnUser
	secret= svnHelper.getSvnPassword( svnUser, batchMode= batchMode )
	svnHelper.g_svnAuth= secret

def forceCopyTree ( src, dst ):
	"""since shutil plays safe and does not provide any API to force copy a tree
	we will use the OS "cp -r" for this purpose
	"""
	subprocess.check_call( [ 'cp', '-r', src, dst ] )

def performActionDiffDbRepo ( argObject, includeSchemas, includeObjectTypes) :
	""" checkout a repository tree from the given URL and extract DDL scripts 
	from given database, store the scripts underneath the sandbox root and 
	perform a recursive diff 
	"""
	global g_primaryOraPassword

	validateSettings( argObject )

	if argObject.repo_url1.startswith( 'file:///' ) : # file protocol needs no credentials?
		svnHelper.g_needCredentials= False 
	else: 
		promptAndSetSvnPasswor (argObject.svn_user, batchMode= argObject.batch_mode)

	g_primaryOraPassword   = getOraPassword( oraUser= g_primaryOraUser  , oraPasswordEnvVar= g_envVarNamePrimarySecret
		, batchMode= argObject.batch_mode )

	# ping the primary DB
	_infoTs( 'Testing oracle DB connection to %s' % g_primaryConnectString, True )
	testOracleConnect(  oraUser= g_primaryOraUser, oraPassword= g_primaryOraPassword, connectString= g_primaryConnectString )
	# get the DB name since we need it as part of the os path for the scripts
	dbName= expensiveGetOneColumnValue( oraUser= g_primaryOraUser
		, oraPassword= g_primaryOraPassword, connectString= g_primaryConnectString
		, queryWithColon = g_queryDbName ) 
	
	extractedScriptsRoot= composePath4DatabaseObject( g_workAreaRoot, dbName ) [0]
	os.makedirs( extractedScriptsRoot ) # make sure the path does exist even if no script will be extracted

	if True: # make it easier to skip while testing
		statusMsgPrimary = extractScriptsFromDatabase( includeSchemas= includeSchemas, includeObjectTypes= includeObjectTypes 
			,  oraUser= g_primaryOraUser, oraPassword= g_primaryOraPassword, connectString= g_primaryConnectString \
			, dbName= dbName)
			
	mailTextLines= []	
	mailTextLines.append( statusMsgPrimary + '\n' + '*'*80 )

	# diff schema-wise
	relevantDbSchemaPathsInWorkArea= []
	relevantDbSchemaUrls=     []
	for schema in includeSchemas:
		schemaUrl= composePath4DatabaseObject(  rootPath= argObject.repo_url1, dbName= None # we may be compare checked-in stuff from database A with stuff extracted directly from database B, so we have to omit dbName
			, schema= schema )[0]
		relevantDbSchemaUrls.append( schemaUrl )
		
	#_dbx( "Urls: \n%s" % "\n".join( relevantDbSchemaUrls ) )

	for i, schema in enumerate( includeSchemas ):
		workAreaSchemaPath= composePath4DatabaseObject(  rootPath= g_workAreaRoot, dbName= dbName, schema= schema )[0]

		schemaUrl= relevantDbSchemaUrls [i]
		svnSandbox= svnHelper.checkoutToTempDir( schemaUrl )

		# since the helper returns a path which does not contain the parent node, we need to fix it
		parentNodeName= os.path.basename( schemaUrl )
		tempDir= tempfile.mkdtemp()
		svnPathCorrected = os.path.join( tempDir , parentNodeName )
		# _dbx( svnPathCorrected )
		shutil.move( svnSandbox, svnPathCorrected )
		
		diffTreeOutputFile= compareTwoTreesReturnFile( treeA= svnPathCorrected, treeB= workAreaSchemaPath
			, expressiveNameA= schemaUrl, expressiveNameB= "Schema %s at database %s" % ( schema, dbName )
			, copyBFilesToAAndDiff = True )
	
		diffOutput= open( diffTreeOutputFile, 'r' ).readlines()
		mailTextLines.extend( diffOutput )

	textSize= getTextSize( mailTextLines )
	if argObject.mail_recipient != None:
		_infoTs( "Sending diff output to %s (text size: %d)" % ( argObject.mail_recipient, textSize) )
		sendMimeText ( recipients= argObject.mail_recipient, subject= "Diff for specified database objects"
			, asciiText= ''.join( mailTextLines ) )
	else:
		tempFile= saveLinesToTempFile( mailTextLines )
		_infoTs( "diff output stored to %s (text size: %d)" % ( tempFile, textSize) )


def assertDbSchemas ( connectUser, connectPassword, connectString, schemas ):
	"""Make sure that the specified schemas do exists either in all_users
	"""
	quotedSchemas= []
	for schema in schemas:
		quotedSchemas.append( "'" + schema + "'" )
	singleQuotedCsv= ",".join( quotedSchemas )
	querySchemas= """select username from all_users where username in ( {singleQuotedCsv} );
	""" .format ( singleQuotedCsv= singleQuotedCsv )

	existingSChemas= getMultipleRowsSingleColumn( oraUser= g_primaryOraUser
		, oraPassword= g_primaryOraPassword, connectString= g_primaryConnectString
		, queryWithColon = querySchemas ) 

	if len( existingSChemas ) == len ( schemas ):
		None # it is ok
	else: 
		missingSchemas= []
		for schema in schemas:
			if schema not in existingSChemas:
				missingSchemas.append( schema )
		
		_errorExit( "Following schemas do not exist at %s: %s" % ( connectString, ','.join( missingSchemas ) ) )

def performActionCheckin ( argObject, includeSchemas, includeObjectTypes) :
	""" extract DDL scripts from the primary database for the given schema, 
	store the scripts underneath the sandbox root and import or commit them 
	to the given repository URL
	"""
	global g_primaryOraPassword

	g_primaryOraPassword   = getOraPassword( oraUser= g_primaryOraUser  , oraPasswordEnvVar= g_envVarNamePrimarySecret 
		, batchMode= argObject.batch_mode )

	validateSettings( argObject )

	if argObject.checkin_target_url.startswith( 'file:///' ) or argObject.use_default_svn_auth == 'y' :  # file protocol needs no credentials?
		svnHelper.g_needCredentials= False 
	else: 
		promptAndSetSvnPasswor (argObject.svn_user, batchMode= argObject.batch_mode)

	nodeKind=  svnHelper.getUrlNodeKind( argObject.checkin_target_url )
	_dbx( nodeKind )
	rootDboNodeExists= False
  
	if "skip_repo_validation_for_now" == "y":
		if nodeKind == None:
			_errorExit( "GIT URL: %s does not exist. Make sure it exists and is a directory" % argObject.checkin_target_url )
		elif nodeKind == 'file':
			_errorExit( "GIT URL: %s is a file! Make sure it is a directory" % argObject.checkin_target_url )
		else:
			rootDboNodeExists= True
	
	# ping the primary DB
	_infoTs( 'Testing oracle DB connection to %s' % g_primaryConnectString, True )
	testOracleConnect(  oraUser= g_primaryOraUser, oraPassword= g_primaryOraPassword, connectString= g_primaryConnectString )
	primaryDbName= expensiveGetOneColumnValue( oraUser= g_primaryOraUser
		, oraPassword= g_primaryOraPassword, connectString= g_primaryConnectString
		, queryWithColon = g_queryDbName ) 
	assertDbSchemas(  connectUser= g_primaryOraUser, connectPassword= g_primaryOraPassword, connectString= g_primaryConnectString
		, schemas= includeSchemas )
	url4DbNameNode= composePath4DatabaseObject( rootPath= argObject.checkin_target_url, dbName= primaryDbName )[0]
	# _dbx( url4DbNameNode )

	statusMsgPrimary = extractScriptsFromDatabase( includeSchemas= includeSchemas, includeObjectTypes= includeObjectTypes 
		,  oraUser= g_primaryOraUser, oraPassword= g_primaryOraPassword, connectString= g_primaryConnectString \
		, dbName= primaryDbName)

	checkInMessage= "Extraced at " + time.strftime("%Y.%m.%d %H:%M") 
	"""We should have created <dbName>/<Schema> directories as configured and 
	populated them with script files extracted from the database. The directories
	are logically derived from the checkin URL target. 
	To perform merge back into the repository with "delete check", if we were to
	proceed also on the the node <checkin URL target>, we would be checking out
	directories which are not part of desired configuration at all. For example
	if the configuration only includes schema B and D for database X, 
	but the repository has directories for schema A - F for database X, plus
	schema A - H for database Y, we must only perform "delete check" on the 
	A@x and D@X, NOT on the others!
	To this end, we must check out only the relevant <dbName>/<Schema> directories
	and operate on them.	
	"""
	relevantDbSchemaPathsInWorkArea= []
	relevantDbSchemaUrls=     []
	for schema in includeSchemas:
		path= composePath4DatabaseObject(  rootPath= g_workAreaRoot, dbName= primaryDbName, schema= schema )[0]
		relevantDbSchemaPathsInWorkArea.append( path )

		targetUrl= composePath4DatabaseObject(  rootPath= argObject.checkin_target_url, dbName= primaryDbName, schema= schema )[0]
		relevantDbSchemaUrls.append( targetUrl )
		
	#_dbx( "Urls: \n%s" % "\n".join( relevantDbSchemaUrls ) )
	#_dbx( "Paths: \n%s" % "\n".join( relevantDbSchemaPathsInWorkArea ) )

	for i, dbSchemaPath in enumerate( relevantDbSchemaPathsInWorkArea ):
		checkinTarget= relevantDbSchemaUrls[ i ]
		nodeKind=  svnHelper.getUrlNodeKind( checkinTarget )
		# _dbx( nodeKind )

		schemaNodeExists= False
		if nodeKind == None:
			_infoTs( "GIT URL %s will be created." % checkinTarget )
		elif nodeKind == 'file':
			_errorExit( "GIT URL: %s is a file! Make sure it is a directory" %cckinTarget )
		else:
			schemaNodeExists= True

		if not schemaNodeExists:
			svnCmdArgs= [ 'import', dbSchemaPath, checkinTarget ]
		else:
			# of course we need to check out before before checkin
			checkedOutToPath=  svnHelper.checkoutToTempDir( checkinTarget ) 
			mergeTreeWithDeleteCheck ( sourceTree= dbSchemaPath, targetTree= checkedOutToPath 
				, deleteCheckObjectTypes= includeObjectTypes )
	
			addNewNodesToSvn( checkedOutToPath )
			svnCmdArgs= [ "commit", checkedOutToPath ]
				
		svnCmdArgs.extend( [ '-m', checkInMessage ] )
		
		_infoTs( "Submitting Svn request: %s " % ' '.join( svnCmdArgs ) )
		# _errorExit( "test" )
		rc, msgLines, errLines = svnHelper.svnQuery ( queryArgs= svnCmdArgs )
		if msgLines != None: 
			_infoTs ( "Output from svn COMMIT:\n%s" % ''.join( msgLines ) )
		if errLines != None and len( errLines ) > 0 : 
			_infoTs( ''.join( errLines ) )

			_errorExit( "svn commit failed due to previous issues" )

def getListOfRelevantSubfolders ( rootPath, dbName, includeSchemas, includeObjectTypes ):
	""" we only want to perform certain tasks ("delete check" for example) on relevant
	subfolders. This method returns the list of such subfolders
	"""
	subFolders= []
	for schema in  includeSchemas : 
		for objectType in includeObjectTypes : 
			path= composePath4DatabaseObject( rootPath= rootPath
				, dbName= dbName, schema= schema, objectType= objectType ) [0]
			subFolders.append( path )

	return subFolders

def performActionDiffRepoRepo ( argObject, includeSchemas= None, includeObjectTypes= None ) :
	""" export scripts from the given repo URL's and perform a diff on each file node
	Since we want to choose the "best" diff from both Unix and GIT diff, we need one file 
	tree with GIT metadata (checkou) and one without (export). We do the unix diff first
	between the sandboxed version and exported version. Then we overwrite the sandboxed version
	with the exported version for a GIT diff.
	"""
	validateSettings( argObject )

	if argObject.repo_url1 == argObject.repo_url2:
		_errorExit( "repo_urlr1 and repo_url2 must not be identical!" )

	if argObject.repo_url1.startswith( 'file:///' ) or argObject.repo_url1.startswith( 'file:///' ) :  # file protocol needs no credentials?
		svnHelper.g_needCredentials= False 

	nodeKind1=  svnHelper.getUrlNodeKind( argObject.repo_url1 )
	if nodeKind1 == None:
		_errorExit( "GIT URL: %s does not exist. Make sure it exists and is a directory" % argObject.repo_url1 )
	elif nodeKind1 == 'file':
		_errorExit( "GIT URL: %s is a file! Make sure it is a directory" % argObject.repo_url1 )
	
	nodeKind2=  svnHelper.getUrlNodeKind( argObject.repo_url2 )
	if nodeKind2 == None:
		_errorExit( "GIT URL: %s does not exist. Make sure it exists and is a directory" % argObject.repo_url2 )
	elif nodeKind2 == 'file':
		_errorExit( "GIT URL: %s is a file! Make sure it is a directory" % argObject.repo_url2 )
	
	repo1CheckedOutPath= svnHelper.checkoutToTempDir( argObject.repo_url1 )

	tempDirMeaningfullName= g_myBaseName[0:8] + '_repo2' 
	repo2ExportedPath= svnHelper.exportToTempDir( argObject.repo_url2 , tempDirMeaningfullName )
	# _dbx( repo2ExportedPath )

	diffTreeOutputFile= compareTwoTreesReturnFile( treeA= repo1CheckedOutPath, treeB= repo2ExportedPath
		, expressiveNameA= argObject.repo_url1, expressiveNameB= argObject.repo_url2
		, copyBFilesToAAndDiff = True )
	#_dbx( diffTreeOutputFile )

	mailTextLines= []

	diffOutput= open( diffTreeOutputFile, 'r' ).readlines()
	mailTextLines.extend( diffOutput )

	textSize= getTextSize( mailTextLines )
	if argObject.mail_recipient != None:
		_infoTs( "Sending diff output to %s (text size: %d)" % ( argObject.mail_recipient, textSize) )
		sendMimeText ( recipients= argObject.mail_recipient, subject= "Diff for specified repository URLs"
			, asciiText= ''.join( mailTextLines ) )
	else:
		tempFile= saveLinesToTempFile( mailTextLines )
		_infoTs( "diff output stored to %s (text size: %d)" % ( tempFile, textSize) )

def main():
	global g_primaryOraPassword

	startTime= time.strftime("%H:%M:%S") 

	argObject= parseCmdLine()
	includeSchemas, includeObjectTypes= parseCfgFileAndSetGlobals( argObject.config_file )
	
	# _dbx( " ,".join( includeSchemas ) ); _dbx( " ,".join( includeObjectTypes ) )
	_infoTs( "*" * 10 + "%s started. Program version: ?\n" % ( os.path.basename( sys.argv[0] ) ), True )

	os.makedirs( g_workAreaRoot ) # all actions will need this directory node
	if argObject.action == 'diff-db-db':
		performActionDiffDbDb( argObject= argObject, includeObjectTypes= includeObjectTypes, includeSchemas= includeSchemas )
	elif argObject.action == 'diff-db-repo':
		performActionDiffDbRepo( argObject= argObject, includeObjectTypes= includeObjectTypes, includeSchemas= includeSchemas )
	elif argObject.action == 'diff-repo-repo':
		performActionDiffRepoRepo( argObject= argObject )
	elif argObject.action == 'checkin':
		performActionCheckin( argObject= argObject, includeObjectTypes= includeObjectTypes, includeSchemas= includeSchemas )

	else:
		_errorExit( "Action %s is not yet implemented" % ( argObject.action ) )

	if argObject.keep_work_area:
		_infoTs( "Check tree beneath %s" % g_workAreaRoot )
	else:
		shutil.rmtree( g_workAreaRoot )

	_infoTs( "Reach normal end of Program %s (started at %s)" % ( os.path.basename( sys.argv[0] ), startTime ) , True )

if __name__ == "__main__":
	main()


