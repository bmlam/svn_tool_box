#!/usr/bin/python
"""This module contains helper functions interfacing with the svn line command
"""

g_svnUser= 'SVC_SVN_DBA' 
g_svnPasswordEnvVar= 'NVS__XYZ' 
g_svnAuth= None
g_needCredentials= True

def _line_():
	return inspect.stack()[1][2]

def _func_():
	return inspect.stack()[1][3]

def _dbx ( text ):
	print( '%s - Ln %d: %s' % ( inspect.stack()[1][3], inspect.stack()[1][2], text ) )

def _errorExit ( text ):
	print( 'ERROR raised from %s - Ln %d: %s' % ( inspect.stack()[1][3], inspect.stack()[1][2], text ) )
	sys.exit(1)

def svnQuery ( queryArgs = [], useShellFeatures = False ):
	""" queryArgs only contains "action" such as path, recursive option, revision etc. 
	The credentials are derived from global variables. Credentials are however not used
	if the Url protocol is file://
	""" 
	global g_svnAuth

	msgLines = []
	errLines = []

	cmdArgs = ['svn', '--non-interactive', '--no-auth-cache']
	if g_needCredentials:
		cmdArgs.extend( [ '--username', g_svnUser, '--password', g_svnAuth ] )
	for ix, arg in enumerate( queryArgs ):
	 	# _dbx( "arg %d: %s" % (ix, arg) )
		cmdArgs.append ( arg )

	svnProc = subprocess.Popen( cmdArgs
		, shell= useShellFeatures
	    ,stdin=subprocess.PIPE 
	    ,stdout=subprocess.PIPE 
	    ,stderr=subprocess.PIPE)
	
	for errLine in svnProc.stderr.readlines():
		errLines.append( errLine )
		# print("Ln %d: %s" % ( inspect.stack()[0][2] , errLine ) )

	for msgLine in svnProc.stdout.readlines():
		msgLines.append( msgLine )
	# wait for the svnProcs to terminate
	out, err = svnProc.communicate()
	rc = svnProc.returncode

	return rc, msgLines, errLines

def doesUrlExist ( url ):
	"""Check if the node already exist in the repository. 
	The function returns a boolean and an error message array which may be empty
	If the node exists, the boolean return is True. 
	If the node does not exists, False is returned and at least one element will
	be in the error message array
	"""
	errLines = []
	msgLines = []
	outputMsgLines = []

	_dbx( 'Cheking Url %s' %( url) )
	svnRc, msgLines, errLinesFromSvn = svnQuery ( ['info', url] )

	if svnRc != 0 :
		myRc = False
		outputMsgLines.append ( "Got error code %d from svn." % ( svnRc ) )
		if len( errLinesFromSvn ) > 0:
			# for errLine in errLinesFromSvn: errLines.append (  errLine ) 
			outputMsgLines.append ( errLinesFromSvn )
	else:
		if len ( msgLines ) > 0:
			myRc = True
		else :
			myRc = False

	# print("test exit") ; sys.exit(1)

	return myRc, outputMsgLines
	

def getNodesFromSvnFolder (originSvnFolderUrl):

	svnRc, nodes, errLinesFromSvn = svnQuery ( [ '--recursive',  'list', originSvnFolderUrl ] )
	if svnRc != 0 :
		print( "Function %s got error code %d from svn." % ( _func_(), svnRc ) )
		if len( errLinesFromSvn ) > 0:
			print( "Error output:" )
			for line in errLinesFromSvn: print(line)
		sys.exit(1)

	for ix, val in enumerate( nodes ):
		nodes[ ix ] = val.rstrip()
		
	return nodes


def checkoutToTempDir ( originUrl ):
	""" Check out the origin folder so get the svn metadata. Do take care to cleanup
	at the end of your program
	"""
	osPath= tempfile.mkdtemp()
	svnRc, msgLines, errLinesFromSvn = svnQuery ( [ 'checkout', originUrl, osPath ] )
	if svnRc != 0 :
		print( "Function %s got error code %d from svn." % ( _func_(), svnRc ) )
		if len( errLinesFromSvn ) > 0:
			print( "Error output:" )
			for errLine in errLinesFromSvn: print(  errLine ) 

		sys.exit(1)
	return osPath

def exportToTempDir ( originUrl , targetBaseName ):
	""" Export the origin folder. Do take care to cleanup at the end of your program
	"""
	osPath= tempfile.mkdtemp()
	osPath= os.path.join( osPath, targetBaseName )
	svnRc, msgLines, errLinesFromSvn = svnQuery ( [ 'export', originUrl, osPath ] )
	if svnRc != 0 :
		print( "Function %s got error code %d from svn." % ( _func_(), svnRc ) )
		if len( errLinesFromSvn ) > 0:
			print( "Error output:" )
			for errLine in errLinesFromSvn: print(  errLine ) 

		sys.exit(1)
	return osPath

def checkoutDepthEmpty ( originUrl , osPath ):
	""" Check out the origin folder with --depth empty
	"""
	svnRc, msgLines, errLinesFromSvn = svnQuery ( [ 'checkout', '--depth', 'empty', originUrl, osPath ] )
	if svnRc != 0 :
		print( "Function %s got error code %d from svn." % ( _func_(), svnRc ) )
		if len( errLinesFromSvn ) > 0:
			print( "Error output:" )
			for errLine in errLinesFromSvn: print(  errLine ) 

		sys.exit(1)

def extractRepoRootUrl ( anySvnNodeUrl ):
	global svnRepoRootUrl
	foundLine=None

	svnRc, msgLines, errLinesFromSvn = svnQuery ( [ 'info', anySvnNodeUrl ] )
	if svnRc != 0 :
		print( "Function %s got error code %d from svn." % ( _func_(), svnRc ) )
		if len( errLinesFromSvn ) > 0:
			print( "Error output:" )
			for errLine in errLinesFromSvn: print(  errLine ) 
		_errorExit( 'Failed to extract repo root URL' )

	for line in msgLines:
		if line.find( 'Repository Root:' ) == 0:
			foundLine = line
			break;

	if foundLine == None :
		_errorExit( 'Svn response does not seem to contain repo root URL' )

	urlStart = foundLine.find ( r'http://')
	if 0 > urlStart :
		urlStart = foundLine.find ( r'https://')
	if 0 > urlStart :
		_errorExit( 'Failed to extract repo root URL' )
	rootUrl= foundLine[ urlStart: ]	
	#_dbx( rootUrl )

	return rootUrl.rstrip()
	

def getSvnPassword ( svnUser ):
	"""Prompt for SVN password if it is not found from environment variable. 
	Password entered will be hidden.
	"""
	if g_svnPasswordEnvVar in os.environ:
		passwordEnv= os.environ[ g_svnPasswordEnvVar ]
		if passwordEnv:
			print('INFO: Found a value from the environment varable %s. Will use it if you just hit Enter on the password prompt' % g_svnPasswordEnvVar )
	hiddenPassword = getpass.getpass('Enter password for SVN user %s. (The input will be hidden if supported by the OS platform)' % svnUser)
	if hiddenPassword == "" :
		if passwordEnv:
			hiddenPassword= passwordEnv
	return hiddenPassword

def getUrlNodeKind ( url ):
	"""Check if the node already exists in the repository, if no return None as the first return value
	If the node exists, check if the node is directory or file and return 'directory', 'file' accordingly. 
	"""

	errLines = []
	msgLines = []
	outputMsgLines = []

	# _dbx( 'Cheking Url %s' %( url) )
	args =  ['info', url] 
	svnRc, msgLines, errLinesFromSvn = svnQuery ( args , False )

	if svnRc != 0 :
		nodeKind = None
	else:
		if len ( msgLines ) > 0:
			for line in msgLines: 
				if line.find( 'Node Kind:' ) == 0 :	
					nodeKindLine = line
					break
			if nodeKindLine == None:
				_errorExit( "Unexpected error: Could not determine node kind" )

			nodeKind = nodeKindLine.split(':')[1]
			nodeKind = nodeKind.strip()
			if nodeKind == 'directory' or  nodeKind == 'file' :
				return nodeKind
			else:
				_errorExit( "Unexpected error: node kind '%s' is not recognized" % nodeKind )
	
#############
def main ():
#############

	global g_svnAuth

	if len( sys.argv ) == 1:
		print( "Enter a SVN URL for test")
		sys.exit()

	svnUrlForTest = sys.argv[1]

	print("Testing getSvnPassword()...")
	g_svnAuth = getSvnPassword( g_svnUser )

	print("Testing doesUrlExist()..")
	nodeExists, errMsgLines = doesUrlExist ( svnUrlForTest )
	if nodeExists:
		print("\tYes!")
	else:
		_errorExit( 'Node %s does not exists' % svnUrlForTest)

	print("Testing extractRepoRootUrl()...")
	rootUrl= extractRepoRootUrl ( svnUrlForTest )
	print("\tRoot is %s" % rootUrl)

	print("Testing getNodesFromSvnFolder()...")
	nodes= getNodesFromSvnFolder( svnUrlForTest ) 
	for ix, node in enumerate( nodes ): 
		print("\tNode %d: %s" % (ix, node) )
	if len( nodes ) == 0:
		print ( '\tURL does not have any child node!' )

	print("Testing checkoutToTempDir()...")
	tempDir = checkoutToTempDir( svnUrlForTest )
	print( "\tSandbox checked out to %s. Remember to 'rm -r %s' " % (tempDir, tempDir) )

	print("All tests done")

import getpass
import inspect
import os
import shutil
import subprocess
import sys
import tempfile

if __name__ == "__main__":
	main()

