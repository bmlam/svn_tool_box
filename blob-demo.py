#! /usr/bin/python3


import cx_Oracle
import inspect
import os

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

oraPasswordEnvVar='ORA_SECRET'

if oraPasswordEnvVar in os.environ:
	secret= os.environ[ oraPasswordEnvVar ]
_dbx( secret )

myDsn = cx_Oracle.makedsn("sfwbe_2", '1521', service_name='xepdb1') # if needed, place an 'r' before any parameter in order to address special characters such as '\'.

conx= cx_Oracle.connect( user= "SERVICE", password= secret, dsn= myDsn )   


cur = conx.cursor()  # instantiate a handle
cur.execute ("""select username from user_users""")  # execute a query l_name= cur.fetchall() # fetch the complete result set
print(l_name)

