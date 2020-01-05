import enum, inspect, re 

g_dbxActive = False
g_dbxCnt = 0
g_maxDbxMsg = 9999

g_seq = 0

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

def bump():
	global g_seq
	g_seq += 1
	return g_seq

class TokenType( enum.Enum ): 
	arith_operator 		= bump()
	assignment_operator 	= bump()
	comparison_operator 	= bump()
	block_comment_begin 	= bump()
	block_comment_end 	= bump()
	comma 	= bump()
	# control_statement_begin 	= bump()
	# control_statement_end_qualifier 	= bump()
	db_link_operator 	= bump()
	dot_operator 	= bump()
	double_pipe 	= bump()
	ident 	= bump()
	left_bracket 	= bump()
	literal_string 	= bump()
	named_parameter_operator 	= bump()
	other_keyword 	= bump()
	q_notation_begin 	= bump() # the closing part needs to be constructed dynamically
	relevant_keyword	= bump()
	right_bracket 	= bump()
	semicolon 	= bump()
	single_line_comment_begin	= bump()
	single_quoted_literal_begin 	= bump()

declarationKeywords = set(
	['AS'
	,'BEGIN'
	,'CASE'
	,'CREATE'
	,'CURSOR'
	,'DECLARE'
	,'END'
	,'FUNCTION'
	,'OR'
	,'PROCEDURE'
	,'REPLACE'
	,'TYPE'
	,'WHILE'
	] )

flowControlStartKeywords = set(
	['IF'
	,'FOR'
	,'WHILE'
	] )

otherKeywords = set(
	['BFILE'
	,'BINARY_INTEGER'
	,'BLOB'
	,'BULK'
	,'BY'
	,'CHAR'
	,'CLOB'
	,'COLLECT'
	,'CONSTANT'
	,'DATE'
	,'DELETE'
	,'DEFAULT'
	,'ELSE'
	,'EXECUTE'
	,'EXCEPTION'
	,'FROM'
	,'IMMEDIATE'
	,'IN'
	,'INDEX'
	,'INTO'
	,'INTEGER'
	,'IS'
	,'NULL'
	,'NUMBER'
	,'OTHERS'
	,'OUT'
	,'PLS_INTEGER'
	,'RETURN'
	,'RETURNING'
	,'TABLE'
	,'VARCHAR2'
	,'WHEN'
	] )

# token node type and symbols may have some overlaps


class FsmState( enum.Enum ): 
	finalising_body	= bump()
	find_block_comment_end	= bump()
	in_body			= bump()
	in_body_entry_other	= bump()
	in_bracket		= bump()
	in_compilation_unit_header= bump()
	in_control_block_header= bump() # this is a type of body entry
	in_declaration		= bump()
	started_declaration_entry		= bump()
	in_new_list_element	= bump()
	in_single_quoted_literal= bump()
	in_single_line_comment = bump()
	start= bump()
	
class TokenNode:

	# count=0 #class attribute
	seq = 0 # static class attribute

	def __init__(self, text, type, staAtCreation, lineNo, colNo, parentId = None ): #constructor
		#if type not in tokenTreeNodes and type not in tokenTreeNodes:
		#	_errorExit( "Type '%s' is invld" % type )

		self.type = type 
		self.id = TokenNode.seq
		self.parentId = parentId
		TokenNode.seq += 1
		self.text = text 
		self.staAtCreation = staAtCreation 
		self.lineNo = lineNo 
		self.colNo = colNo 

		self.treeLen = 0
		# validate lineNo and colNo here

	def normedText( self ):
		return self.text.upper()
		
	#def isTreeNode():
	#	return self.type in tokenTreeNodes

	def showInfo(self): #method
		print( 'id: %d parent: %s type: %s position: %d/%d, len: %d' % ( self.id, self.parentId, self.type, self.lineNo, self.colNo, len( self.text ) ) )
		print( ' TEXT up 80 chars: "%s"' % self.text[:80] )

######
class TokenStack:
	arr = []
	tokenCnt = 0 
	def __init__ ( self ):
		pass

	def push ( self, elem ):
		_dbx( "pushing node with info ..." )
		# elem.showInfo()
		self.arr.append ( elem )
		self.tokenCnt += 1 

	def pop ( self ):
		rv = self.arr[ -1 ]
		self.arr = self.arr[ : -1 ]
		_dbx( "popping node with info ..." )
		rv.showInfo()
		return rv

	def showInfo(self): #method
		if self.tokenCnt == 0:
			print( 'Stack is empty' )
		else:
			print( 'Stack contains %d elements of type %s' % ( self.tokenCnt, type( self.arr[0] ).__name__ ) )

	def printTokenText( self, suppressComments= False ):
		# for NOW, dump to stdout 
		prevParent = None; textGroup= []
		for tok in self.arr:
			if suppressComments and tok.type in set( [TokenType.block_comment_begin, TokenType.single_line_comment_begin] ) :
				pass
			else:
				textGroup.append( tok.text )
				if prevParent == None: 
					prevParent = tok.parentId
				else: 
					if tok.parentId == prevParent :
						pass
					else:
						print( ' '.join( textGroup ) )
						prevParent = None;	textGroup = []

######
class StateStack:
	arr = []
	def __init__ ( self ):
		pass

	def push ( self, state, parentId ):
		self.arr.append ( (state, parentId) )
		_dbx( "added state %s parent %s. elemCnt %d" % ( state, parentId, len( self.arr ) ) )

	def pop ( self ):
		rv = self.arr[ -1 ]
		self.arr = self.arr[ : -1 ]
		state, parentId = rv 
		_dbx( "returning state %s parent %s. elemCnt %d" % ( state, parentId, len( self.arr ) ) )
		return state, parentId
		
	def showInfo(self): #method
		if self.elemCnt == 0:
			print( 'Stack is empty' )
		else:
			print( 'Stack contains %d elements of type %s' % ( rv, type( self.arr[0] ).__name__ ) )

###
def gettokentype( str ):
	typ = None; normed = str
	if str.upper() in declarationKeywords or str.upper() in  flowControlStartKeywords : 
		typ = TokenType.relevant_keyword; normed = str.upper()
	elif str.upper() in flowControlStartKeywords: 
		typ = TokenType.relevant_keyword; normed = str.upper()
	elif str.upper() in otherKeywords: 
		typ = TokenType.other_keyword; normed = str.upper()
	elif str[0] == '"' and  str[-1] == '"': 
		typ = TokenType.ident
		normed = str  # send back original case 
	elif str         == '/*': typ = TokenType.block_comment_begin
	elif str         == '.' : typ = TokenType.dot_operator
	elif str         == '=' : typ = TokenType.comparison_operator
	elif str         == ';' : typ = TokenType.semicolon
	elif str         == '+' : typ = TokenType.arith_operator
	elif str         == '-' : typ = TokenType.arith_operator
	elif str         == '*' : typ = TokenType.arith_operator
	elif str         == '/' : typ = TokenType.arith_operator
	elif str         == '(' : typ = TokenType.left_bracket
	elif str         == ')' : typ = TokenType.right_bracket
	elif str         == ':=' : typ = TokenType.assignment_operator
	elif str         == '--' : typ = TokenType.single_line_comment_begin
	elif str         == '||' : typ = TokenType.double_pipe
	# it is ok to duplicate logic for parsing normal identifier!
	else:
		#_dbx( foo )
		m = re.search( "^[a-z0-9_]+$" , str) 
		if m != None : 
			_dbx( foo )
			typ = TokenType.ident

	return typ, normed

####
	
