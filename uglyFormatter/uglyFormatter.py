#!/Library/Frameworks/Python.framework/Versions/3.8/bin/python3
""" 
on AirBook : 
#!/usr/bin/python3
on iMac:
#!/Library/Frameworks/Python.framework/Versions/3.8/bin/python3

the UglyFormatter is supposed to format PLSQL solely for the purpose of providing consistent output given tbe same input
"""


import inspect, sys

## my modules 
import plstopa, fsm

g_dbxActive = False
g_dbxCnt = 0
g_maxDbxMsg = 999

g_inpFilePath= None
g_inpLines = ""
g_outFilePath= None

def _dbx ( text ):
	global g_dbxCnt , g_dbxActive
	if g_dbxActive :
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

def parseCmdLine() :
	import argparse

	global g_inpFilePath, g_outFilePath, g_inpLines

	parser = argparse.ArgumentParser()
	# lowercase shortkeys
	parser.add_argument( '-i', '--inputFile' , help='input file, could also be sent as STDIN', required= False )
	parser.add_argument( '-o', '--outFile' , help='output file', required= False )

	result= parser.parse_args()

	if result.inputFile != None:
		g_inpFilePath = result.inputFile
		g_inpLines =  open( g_inpFilePath, "r" ).readlines()
	else: 
		g_inpLines =  sys.stdin.readlines() 
		
	_dbx( len( g_inpLines) )
	# _dbx( "\n".join( g_inpLines[:3] ) )

	return result



def main():
	argParserResult = parseCmdLine()
	tree = fsm.fsm( g_inpLines )
	# tree.printTokenText( suppressComments= True )

	# nodeA = TokenNode( 'create', 'CompileUnit', 1, 1 )
	# nodeA.showInfo()

	# stack1 = TokenStack( ); stack1.showInfo()
	# stack1.push (nodeA); stack1.showInfo()

main()


