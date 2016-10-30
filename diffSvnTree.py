#! /usr/bin/python 
"""This program compares two SVN folders and and generate diff report.
Directory or file nodes only present in one tree will be reported.
A svn diff is performed on a file node which exists in both tree. 

In details, we will checkout tree A to a temp directory and export
tree B to another temp dir. 
We will walk tree B and performs the following tasks:
* if the node is a directory, we check if the same directory exists in A and set a flag.
* if the node is a file, we check if the same file exists in A and set a flag. In 
*   addition, the A file node is overwritten with B. A svn diff is run on the node
*   in tree A. The result is cached.
We continue by walking tree B and perform the following tasks
* regardless if it is a directory or file node, we check if the same node exists in A and set a flag
*   if B does not have the node.
In both cases, node type mismatch is flagged in a separate array!
"""

import argparse
# import difflib
import getpass
import glob
import inspect
import os
import shutil
# import subprocess
import svnHelper
import sys
import tempfile
import time
# import zipfile


g_maxDbxMsg = 999  # best to adjust to screen height
g_dbxCnt = 0

g_svnUser= "USER_XYZ"

g_treeAUrlFromEnv=None
g_treeBUrlFromEnv=None

def _line_():
	return inspect.stack()[1][2]

def _func_():
	return inspect.stack()[1][3]

def _dbx ( text ):
	global g_dbxCnt
	print( 'dbx: %s - Ln %d: %s' % ( inspect.stack()[1][3], inspect.stack()[1][2], text ) )
	g_dbxCnt += 1
	if g_dbxCnt > g_maxDbxMsg:
		_errorExit( "g_maxDbxMsg of %d exceeded" % g_maxDbxMsg )

def _verbose ( text ):
	print( '%s - Ln %d: %s' % ( inspect.stack()[1][3], inspect.stack()[1][2], text ) )

def infoWithTS ( text ):
	print( '%s (Ln %d) %s' % ( time.strftime("%H:%M:%S"), inspect.stack()[1][2], text ) )

def _errorExit ( text ):
	print( 'ERROR raised from %s - Ln %d: %s' % ( inspect.stack()[1][3], inspect.stack()[1][2], text ) )
	sys.exit(1)

def nullableEnvVar ( varName ):
	_dbx( varName )
	if varName in os.environ.keys() :
		_dbx( 'got here' )
		return os.environ[ varName ] 
	else:
		return None

def parseCmdLine() :

	parser = argparse.ArgumentParser()
	# lowercase shortkeys
	parser.add_argument( '-a', '--tree_a', help='URL of tree A', default=g_treeAUrlFromEnv)
	parser.add_argument( '-b', '--tree_b', help='URL of tree B', default=g_treeBUrlFromEnv)

	result= parser.parse_args()

	for (k, v) in vars( result ).iteritems () :
		print( "%s : %s" % (k, v) )

	return result


def main() :
	global g_treeAUrlFromEnv
	global g_treeBUrlFromEnv

	envVarName = 'SVN_PASSWORD'
	svnAuth = nullableEnvVar( envVarName )
	if None == svnAuth:
		_errorExit( "Set password for user %s as environment variable %s !" % (g_svnUser, envVarName ) )
	svnHelper.g_svnAuth = svnAuth

	g_treeAUrlFromEnv = nullableEnvVar( 'URL_TREE_A_DEFAULT' )
	g_treeBUrlFromEnv = nullableEnvVar( 'URL_TREE_B_DEFAULT' )

	argObject = parseCmdLine()

	treeALocalPath = svnHelper.exportToTempDir ( argObject.tree_a, 'TREE_A' )
	_dbx( treeALocalPath )
	treeBLocalPath = svnHelper.exportToTempDir ( argObject.tree_b, 'TREE_B' )
	_dbx( treeBLocalPath )

if __name__ == "__main__":
	main()
	infoWithTS( "Reach normal end of Program %s." % sys.argv[0] )

