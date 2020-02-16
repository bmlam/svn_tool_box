#!/Library/Frameworks/Python.framework/Versions/3.8/bin/python3

""" 
on AirBook : 
#!/usr/bin/python3
on iMac:

the UglyFormatter is supposed to format PLSQL solely for the purpose of providing consistent output given tbe same input
"""


import inspect, subprocess, sys, tempfile

## my modules 
import charCounter, plstopa, fsm

g_dbxActive = True
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

	global g_inpFilePath, g_outFilePath, g_inpLines, g_fsmInitStatusCode

	parser = argparse.ArgumentParser()
	# lowercase shortkeys
	parser.add_argument( '-i', '--inFile' , help='input file, could also be sent as STDIN', required= False )
	parser.add_argument( '-o', '--outFile' , help='output file', required= False )
	parser.add_argument( '-f', '--fsmStartStatus' , help='finite machine start status', required= False )

	result= parser.parse_args()

	if result.inFile != None:
		g_inpFilePath = result.inFile
		g_inpLines =  open( g_inpFilePath, "r" ).readlines()
	else: 
		g_inpLines =  sys.stdin.readlines() 
		
	_dbx( len( g_inpLines) )
	# _dbx( "\n".join( g_inpLines[:3] ) )

	if result.outFile != None:
		pass

	if result.fsmStartStatus != None:
		g_fsmInitStatusCode = result.fsmStartStatus
	else:
		g_fsmInitStatusCode = None

	return result

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

    _dbx(  len( unixOutMsgs ) )
    return unixOutMsgs

def main():
	global g_fsmInitStatusCode
	argParserResult = parseCmdLine()

	# nodeA = TokenNode( 'create', 'CompileUnit', 1, 1 )
	# nodeA.showInfo()

	# stack1 = TokenStack( ); stack1.showInfo()
	# stack1.push (nodeA); stack1.showInfo()

	#tree = fsm.fsm( g_inpLines )
	# tree.printTokenText( suppressComments= True )

	if True:
		tree = fsm.plsqlTokenize( g_inpLines )
		outLines = tree.simpleFormatSemicolonAware()
		# print( "\n".join( outLines ) )

	if True or "want to" == "compare output manually":
		#print( "*"*20 + "input sql" + "*"*20 )
		#print( "".join( g_inpLines))
		
		print( "*"*20 + "formatted" + "*"*20 )
		print( "\n".join( outLines))
		
	if "want to compare" == "char count":
		forCharCountCheck_A = tempfile.mktemp()
		_dbx ( "forCharCountCheck_A: %s" % (forCharCountCheck_A ))
		charCounter_A = charCounter.TextCharStatsIgnoreCase( textName = "sql input", txt = g_inpLines)
		charCountResultLines_A = charCounter_A.report( printToStdout= False )
		open( forCharCountCheck_A, "w").write( "\n".join( charCountResultLines_A ) )

		forCharCountCheck_B = tempfile.mktemp()
		_dbx ( "forCharCountCheck_B: %s" % (forCharCountCheck_B ))
		charCounter_B = charCounter.TextCharStatsIgnoreCase( textName = "formatted output", txt = outLines)
		charCountResultLines_B = charCounter_B.report( printToStdout= False )
		open( forCharCountCheck_B, "w").write( "\n".join( charCountResultLines_B ) )

		_infoTs( " ************ DIFFing CharCounts ... ")
		diffCharCountResult = genUnixDiff( forCharCountCheck_A, forCharCountCheck_B)

		_infoTs( " ************ result of DIFFing CharCounts")
		print( diffCharCountResult ) 

	if True:
		textWordCounter_a = charCounter.WordCounter( name="sql input" , lines= g_inpLines, shortCode= "sqlInput" )
		textWordCounter_a.scan()
		wordCountResultLines_a = textWordCounter_a.report( printToStdout= False )
		forWordCountCheck_a = tempfile.mktemp()
		_dbx ( "forWordCountCheck_a: %s" % (forWordCountCheck_a ))
		open( forWordCountCheck_a, "w").write( "\n".join( wordCountResultLines_a ) )

		textWordCounter_b = charCounter.WordCounter( name="sql input" , lines= outLines, shortCode= "sqlInput" )
		textWordCounter_b.scan()
		wordCountResultLines_b = textWordCounter_b.report( printToStdout= False )
		forWordCountCheck_b = tempfile.mktemp()
		_dbx ( "forWordCountCheck_b: %s" % (forWordCountCheck_b ))
		open( forWordCountCheck_b, "w").write( "\n".join( wordCountResultLines_b ) )

		_infoTs( " ************ DIFFing WordCounts ... ")
		diffWordCountResult = genUnixDiff( forWordCountCheck_a, forWordCountCheck_b)

		_infoTs( " ************ result of DIFFing WORD Counts")
		print( diffWordCountResult ) 


	if "want to " == "use fsmMain":
		commentStack, signifStack = plstopa.separateCommentsFromSignficants( tree )

		#print( "*"*80 ); 		commentStack.simpleDump()
		#print( "*"*80 ); 		signifStack.simpleDump()

		signifStack.assembleComplexTokens( )
		#signifStack.simpleDump( markComplexIdents= True )

		useStatus = fsm.kickStartStatusByCode[g_fsmInitStatusCode] if g_fsmInitStatusCode != None else plstopa.FsmState.start
		parsedTree = fsm.fsmMain( signifStack, startStatus = useStatus )
		# parsedTree.simpleDump()

		# eunitedTree = plstopa.mergeTokenTrees( commentStack, parsedTree )
		reunitedTree = plstopa.mergeSignifcantAndCommentTrees( signifTree= parsedTree, commentTree= commentStack )
		_dbx( "reunitedTree len %d" % (len( reunitedTree.arr) ) )
		print( "*"*30 + "reunited " + "*"*20); 	
		#eunitedTree.simpleDump( markComplexIdents = True )
			
		# reunitedTree.finalizeStats()
		# for node in reunitedTree.arr: node.showInfo()
		print( reunitedTree.formatTokenText() )

	if False: 
		tree.assembleComplexTokens()
		# tree.simpleDump( markComplexIdents= False )
		tree.simpleDump( markComplexIdents= False )
	
main()


