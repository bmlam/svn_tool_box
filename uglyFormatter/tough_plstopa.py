import enum, inspect, re 

g_dbxActive = True
g_dbxCnt = 0
g_maxDbxMsg = 999

foo = "got here"
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
		print( '(Ln%d) %s' % ( inspect.stack1G()[1][2], text ) )

def _errorExit ( text ):
	print( 'ERROR raised from %s - Ln%d: %s' % ( inspect.stack()[1][3], inspect.stack()[1][2], text ) )
	sys.exit(1)


class TokenType( enum.Enum ):
	#
	# relevant keywords
	#
	AS	= inspect.stack()[0][2]
	BEGIN	= inspect.stack()[0][2]
	BODY			= inspect.stack()[0][2]
	CURSOR		= inspect.stack()[0][2]
	FUNCTION			= inspect.stack()[0][2]
	#
	# interpreted 
	#
	ident 	= inspect.stack()[0][2]
	

tokenTreeNodes = set( 
	[ TokenType.anonymBlockNoDeclare
	, TokenType.anonymBlockDeclare
	, TokenType.assignment
	, TokenType.blockComment
	, TokenType.roundBracketedList
	, TokenType.compileUnit 
	, TokenType.complexIdent # for identifier with a là schema.object.ident or schema.object@db_link 
	, TokenType.exceptionBlock 
	, TokenType.exceptionWhen 
	, TokenType.funcCall 
	, TokenType.identDecl 
	, TokenType.localFunc 
	, TokenType.localProc 
	, TokenType.procCall 
	] )

tokenLeafNodes = set( 
	[ TokenType.assignOp
	, TokenType.binaryOp 
	, TokenType.blockCommentBegin
	, TokenType.blockCommentEnd
	, TokenType.compileUnitBegin
	, TokenType.compileUnitEnd
	, TokenType.dotOp   
	, TokenType.exceptionBlockBegin 
	, TokenType.exceptionBlockEnd 
	, TokenType.exceptionWhenBegin
	, TokenType.simpleIdent 
	, TokenType.lineComment
	, TokenType.literal
	, TokenType.optionalKeyword
	, TokenType.roundBracketedLeft
	, TokenType.roundBracketedRight
	, TokenType.unaryOp 
	] )

reservedKeywords = set( 
	['AS'
	,'BEGIN'
	,'DELEE'
	,'ELSE'
	,'EXECUE'
	,'END'
	,'EXECEPION'
	,'FROM'
	,'IF'
	,'IMMEDIAE'
	,'INO'
	,'OR'
	,'OHERS'
	,'REPLACE'
	,'REURN'
	,'WHEN'
	] )

# token node type and symbols may have some overlaps


class FsmState( enum.Enum ):
	look4OrCompileUnitIdent		= inspect.stack()[0][2]
	look4OrCompileUnitType		= inspect.stack()[0][2]
	look4OrCompileUnitTypQualifierOrIdent		= inspect.stack()[0][2]
	look4Create				= inspect.stack()[0][2]
	look4Editionable		= inspect.stack()[0][2]
	look4OrReplace1			= inspect.stack()[0][2]
	look4OrReplace2			= inspect.stack()[0][2]
	look4BlockCommentEnd	= inspect.stack()[0][2]
	look4UnitName		= inspect.stack()[0][2]

class TokenNode:

	# count=0 #class attribute
	seq = 0 # static class attribute

	def __init__(self, text, type, lineNo, colNo, parentId = None ): #constructor
		if type not in tokenTreeNodes and type not in tokenTreeNodes:
			_errorExit( "Type '%s' is invld" % type )

		self.type = type 
		self.id = self.seq
		self.seq += 1
		self.text = text 
		self.lineNo = lineNo 
		self.colNo = colNo 
		self.len = len( text )

		self.treeLen = None
		# validate lineNo and colNo here

	def normedText( self ):
		return self.text.upper()
		
	def isTreeNode():
		return self.type in tokenTreeNodes

	def showInfo(self): #method
		print( 'id: %d type: %s position: %d/%d, len: %d' % ( self.id, self.type, self.lineNo, self.colNo, self.len ) )
		print( ' TEXT: "%s..."' % self.text[:80] )

######
class TokenStack:
	arr = []
	tokenCnt = 0 
	def __init__ ( self ):
		pass

	def push ( self, elem ):
		self.arr.append ( elem )
		self.tokenCnt += 1 

	def showInfo(self): #method
		if self.tokenCnt == 0:
			print( 'Stack is empty' )
		else:
			print( 'Stack contains %d elements of type %s' % ( self.tokenCnt, type( self.arr[0] ).__name__ ) )

######
class StateStack:
	arr = []
	def __init__ ( self ):
		pass

	def push ( self, elem ):
		self.arr.append ( elem )
		_dbx( "added state %s. elemCnt %d" % ( elem, len( self.arr ) ) )

	def pop ( self ):
		rv = self.arr[ -1 ]
		self.arr = self.arr[ : -1 ]
		_dbx( "returning state %s. elemCnt %d" % ( rv, len( self.arr ) ) )
		return rv
		
	def showInfo(self): #method
		if self.elemCnt == 0:
			print( 'Stack is empty' )
		else:
			print( 'Stack contains %d elements of type %s' % ( rv, type( self.arr[0] ).__name__ ) )

###
def gettokentype( str ):
	typ = None; normed = str
	if str.upper() in reservedKeywords: 
		normed = str.upper()
	if str[0] == '"' and  str[-1] == '"': 
		typ = TokenType.dblQuotedIdent
		normed = str  # send back original case 
	elif normed      == 'CREATE': typ = TokenType.compileUnitBegin
	elif normed      == 'OR': typ = TokenType.keywordOr 
	elif normed      == 'REPLACE': typ = TokenType.keywordReplace
	elif str         == '/*': typ = TokenType.blockCommentBegin
	elif str         == '*/': typ = TokenType.blockCommentEnd

	return typ, normed

####
	
