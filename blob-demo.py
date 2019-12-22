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

def conxOutputTypeHandler(cursor, name, defaultType, size, precision, scale):
	if defaultType == cx_Oracle.CLOB:
		return cursor.var(cx_Oracle.LONG_STRING, arraysize=cursor.arraysize)
	if defaultType == cx_Oracle.BLOB:
		return cursor.var(cx_Oracle.LONG_BINARY, arraysize=cursor.arraysize)


oraPasswordEnvVar='ORA_SECRET'

if oraPasswordEnvVar in os.environ:
	secret= os.environ[ oraPasswordEnvVar ]
_dbx( secret )

myDsn = cx_Oracle.makedsn("sfwbe_2", '1521', service_name='xepdb1') # if needed, place an 'r' before any parameter in order to address special characters such as '\'.

conx= cx_Oracle.connect( user= "SERVICE", password= secret, dsn= myDsn )   
conx.outputtypehandler = conxOutputTypeHandler

cur = conx.cursor()  # instantiate a handle
cur.execute ("""select username from user_users""")  
# execute a query 
userName= cur.fetchall() # fetch the complete result set
print( userName )

# test array as bind variable
#this gives ORA-01036 illegal variable name/numbe: cur.execute(r"select content, 1 bar from table ( ora_mining_number_nt( :1) )", [1,2,3] );
cur.execute(r"select count(1), 0 dummy from table ( split_to_array(:1) )", [ "ab,bd" ] );
cnt, dummy = cur.fetchone()
_dbx( cnt )

import tempfile
if "test" == "blob":
	# the query has to return at least 2 columns so that a BLOB is indeed treated as a BLOB. 
	# A single BLOB column would be treated as tuple!
	# cur.execute(r"select to_blob( hextoraw( 'f0f1f2fe' ) ) foo, 1 bar from dual where 1 = :1", [ 1 ]) # this query demos use of bind variables
	cur.execute(r"select content, 1 bar from test_blob where 1 = :1", [ 1 ]) # this query demos use of bind variables
	
	blobData, aNum = cur.fetchone()
	_dbx( type(aNum) )
	_dbx( type(blobData) )
	_dbx( "BLOB length:%d" % len(blobData) )

	tempFile = tempfile.mktemp()
	_dbx( tempFile )
	fh = open( tempFile, "wb" ); 
	fh.write( blobData ); 
	fh.close()
	
