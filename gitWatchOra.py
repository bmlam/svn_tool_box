#!/usr/bin/python3
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

./gitWatchOra.py -a extract -f my_input.txt -O IOS_APP_DATA -D 217.160.60.203:1521:xepdb1 -u dummySvnUser --keep_work_area --use_default_svn_auth y -r $HOME/testGitRepo --use_dba_views n

"""

import argparse
import cx_Oracle
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
	for line in lines: rc += len( line )
	return rc	

def conxOutputTypeHandler(cursor, name, defaultType, size, precision, scale):
	if defaultType == cx_Oracle.CLOB:
		return cursor.var(cx_Oracle.LONG_STRING, arraysize=cursor.arraysize)
	if defaultType == cx_Oracle.BLOB:
		return cursor.var(cx_Oracle.LONG_BINARY, arraysize=cursor.arraysize)



def parseCmdLine() :

	global g_primaryConnectString
	global g_primaryOraUser

	global g_secondaryConnectString
	global g_secondaryOraUser

	global g_useDbaViews

	parser = argparse.ArgumentParser()
	# lowercase shortkeys
	parser.add_argument( '-a', '--action', help='which action applies', choices=[ 'diff-db-db', 'diff-db-repo', 'diff-repo-repo', 'extract' ], required= True)
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
	""" config file example:
INCLUDE_SCHEMA::SCOTT
	"""
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


####
def getOracSqlRunner( oraUser, password, host, port, service ):
	""" set up an Oracle session and return a cursor with which queries can be executed. Result of query
		can be fetched using fetchone or fetchall. Why exactly we need a cursor instead of using the 
		connection handle directly, remains to be clarified.
	"""
	myDsn = cx_Oracle.makedsn(host, port, service_name= service) # if needed, place an 'r' before any parameter in order to address special characters such as '\'.
	
	conx= cx_Oracle.connect( user= oraUser, password= password, dsn= myDsn )   
	conx.outputtypehandler = conxOutputTypeHandler
	
	cur = conx.cursor()  # instantiate a handle
	cur.execute ("""select username, sys_context( 'userenv', 'db_name' ) from user_users""")  
	connectedAs, dbName = cur.fetchone()
	_infoTs( "connected as %s to %s" % ( connectedAs, dbName ) )

	return cur

####
def getSqlRunnerForPrimaryDB():
	""" connect to primary Oracle DB and return a cursor to run SQL
	"""
	global g_primaryConnectString
	global g_primaryOraUser
	global g_envVarNamePrimarySecret
	
	password = getOraPassword ( oraUser= g_primaryOraUser, oraPasswordEnvVar= g_envVarNamePrimarySecret, batchMode= False )
	host, port, service = g_primaryConnectString.split( ":" )
	# _dbx( host ); _dbx( service )
	sqlRunner =  getOracSqlRunner( oraUser= g_primaryOraUser, password= password, host=host, port= port, service= service )

	return sqlRunner

####
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
	elif argObject.action == 'extract' :
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
			

####
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

####
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

####
def extractScriptsFromDatabase( includeSchemas, includeObjectTypes, sqlRunner ) :
	"""Extract DDL scripts for the given schemas and object types from the given database
	"""
	_dbx( type( sqlRunner ) )
	query = ' '.join( open( "./parameterized_extractor.sql", "r").readlines() )
	_dbx(  query[ : 100] ) 

	statsMsgs= []
	if len( includeSchemas ) == 0:
		_errorExit( "No schemas have been specified from which objects are to be extracted!"  )
	if len( includeObjectTypes ) == 0:
		_errorExit( "No object types have been specified for which scripts are to be extracted" ) 

	statsMsgs.append("Scripts are to be extracted for the following %d schemas:" % ( len( includeSchemas ) ) )
	
	for schema in includeSchemas: 
		statsMsgs.append( "\t" + schema )
	statsMsgs.append("And for the following %d object types:" % len( includeObjectTypes ) ) 
	for objectType in includeObjectTypes: 
		statsMsgs.append( "\t" + objectType )

	# _dbx( len( includeObjectTypes ) )

	_infoTs( statsMsgs )

	sqlRunner.execute( """SELECT content, 1 dummy FROM test_blob WHERE ROWNUM = 1 """ )
	zipContent = sqlRunner.fetchone()[0]
	_dbx( len( zipContent ) )
	
	tempFile = tempfile.mktemp()
	_dbx( tempFile )
	zipBasename = os.path.basename( tempFile ) + '.zip'
	zipFile = os.path.join( os.path.dirname(tempFile), os.path.basename( tempFile ) + '.zip' )
	_dbx( zipFile )
	fh = open( zipFile, "wb" ); 
	fh.write( zipContent ); 
	fh.close()

	return zipFile	

####
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

####
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
							excerpt= msgLines [ 1 : g_maxDiffLines - 1] 
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

####
def diffTwoTexts( text1, text2 ):
	file1= saveLinesToTempFile( text1 )
	file2= saveLinesToTempFile( text2 )
	result = genUnixDiff( file1, file2 )
	# _dbx( file1 ); _dbx( file2 )
	# diffFile= saveLinesToTempFile( result ); _errorExit( diffFile )
	return result 
	
####
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


####
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

####
def forceCopyTree ( src, dst ):
	"""since shutil plays safe and does not provide any API to force copy a tree
	we will use the OS "cp -r" for this purpose
	"""
	subprocess.check_call( [ 'cp', '-r', src, dst ] )


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

###
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

###
def performActionExtract ( argObject, includeSchemas= None, includeObjectTypes= None ) :
	""" extract DDL scripts
	"""
	sqlRunner = getSqlRunnerForPrimaryDB()
	_dbx( type( sqlRunner ) )
	zipFile = extractScriptsFromDatabase( includeSchemas, includeObjectTypes, sqlRunner ) 
	_dbx( zipFile )
	newPath = os.path.join( os.environ['HOME'], 'Downloads' , os.path.basename( zipFile ) )
	_dbx( newPath )
	shutil.move( zipFile, newPath)

###
def performActionDiff2Trees ( argObject, includeSchemas= None, includeObjectTypes= None ) :
	""" 
	"""
	validateSettings( argObject )

	if argObject.repo_url1 == argObject.repo_url2:
		_errorExit( "repo_urlr1 and repo_url2 must not be identical!" )

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
	
	_dbx( " ,".join( includeSchemas ) ); _dbx( " ,".join( includeObjectTypes ) )
	_infoTs( "*" * 10 + "%s started. Program version: ?\n" % ( os.path.basename( sys.argv[0] ) ), True )

	os.makedirs( g_workAreaRoot ) # all actions will need this directory node
	if argObject.action == 'extract':
		performActionExtract( argObject= argObject, includeObjectTypes= includeObjectTypes, includeSchemas= includeSchemas )
	elif argObject.action == 'diff-db-repo':
		performActionDiffDbRepo( argObject= argObject, includeObjectTypes= includeObjectTypes, includeSchemas= includeSchemas )
	elif argObject.action == 'diff-repo-repo':
		performActionDiffRepoRepo( argObject= argObject )

	else:
		_errorExit( "Action %s is not yet implemented" % ( argObject.action ) )

	if argObject.keep_work_area:
		_infoTs( "Check tree beneath %s" % g_workAreaRoot )
	else:
		shutil.rmtree( g_workAreaRoot )

	_infoTs( "Reach normal end of Program %s (started at %s)" % ( os.path.basename( sys.argv[0] ), startTime ) , True )

if __name__ == "__main__":
	main()


