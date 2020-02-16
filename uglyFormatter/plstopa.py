import enum, inspect, re , sys 

g_dbxActive = True 
g_dbxCnt = 0
g_maxDbxMsg = 99999

g_seq = 0

foo = "got here"
def _dbx ( text ):
	global g_dbxCnt , g_dbxActive
	if g_dbxActive :
		print( 'dbx%d: %s - Ln%d: %s' % ( g_dbxCnt, inspect.stack()[1][3], inspect.stack()[1][2], text ) )
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

def bump():
	global g_seq
	g_seq += 1
	return g_seq

class TokenType( enum.Enum ): 
	aggEndIdentSemic        = bump()
	aggEndCaseSemic	        = bump()
	aggEndIfSemic	        = bump()
	aggEndLoopSemic	        = bump()
	aggEndSemic         	= bump()
	arith_operator 		= bump()
	at_operator 		= bump() # i.e commercial at
	assignment_operator 	= bump()
	comparison_operator 	= bump()
	block_comment_begin 	= bump()
	block_comment_end 	= bump()
	comma 	= bump()
	complexIdent 	= bump()
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
	,'COMMIT'
	,'CONSTANT'
	,'CONTINUE'
	,'DATE'
	,'DELETE'
	,'DEFAULT'
	,'ELSE'
	,'EQUALS'
	,'EXIT'
	,'EXECUTE'
	,'EXCEPTION'
	,'FROM'
	,'GOTO'
	,'GROUP'
	,'HAVING'
	,'IMMEDIATE'
	,'IN'
	,'INDEX'
	,'INSERT'
	,'INTEGER'
	,'INTO'
	,'IS'
	,'LIKE'
	,'LOOP'
	,'MATCHED'
	,'MERGE'
	,'NOT'
	,'NULL'
	,'NUMBER'
	,'ON'
	,'ORDER'
	,'OTHERS'
	,'OUT'
	,'PLS_INTEGER'
	,'RAISE'
	,'RETURN'
	,'RETURNING'
	,'ROLLBACK'
	,'SELECT'
	,'TABLE'
	,'THEN'
	,'UPDATE'
	,'USING'
	,'VARCHAR2'
	,'WHEN'
	,'WHERE'
	] )

# token node type and symbols may have some overlaps


class FsmState( enum.Enum ): 
	ACI_foundIdent		= bump()
	ACI_foundOperator 	= bump()
	expect_bool_expression	= bump()
	expect_expression	= bump()
	foundEnd			= bump()
	foundEndIdent		= bump()
	foundEndIdentSemic	= bump()
	foundEndIf			= bump()
	foundEndIfSemic		= bump()
	foundEndCase		= bump()
	foundEndCaseSemic	= bump()
	foundEndLoop		= bump()
	foundEndLoopSemic	= bump()
	finalising_body	= bump()
	finalising_case_stmt	= bump()
	finalising_case_stmt_expect_semicolon	= bump()
	find_block_comment_end	= bump()
	in_body			= bump()
	in_body_entry_other	= bump()
	in_bracket		= bump()
	in_case_stmt		= bump()
	in_compilation_unit_header= bump()
	in_control_block_header= bump() # this is a type of body entry
	in_declaration		= bump()
	in_new_list_element	= bump()
	in_q_notation_begin = bump()
	in_single_quoted_literal= bump()
	in_single_line_comment = bump()
	start= bump()
	started_declaration_entry		= bump()
	# special cases to hand THEN properly
	if_or_case_statement_open = bump()
	case_bool_expression_open = bump()
	
class TokenNode:

	# count=0 #class attribute
	seq = 0 # static class attribute

	def __init__(self, text, type, staAtCreation, lineNo, colNo, parentId = None ): #constructor
		#if type not in tokenTreeNodes and type not in tokenTreeNodes:
		#	_errorExit( "Type '%s' is invld" % type )

		self.type = type 
		#self.id = TokenNode.seq
		self.parentId = parentId
		TokenNode.seq += 1
		self.text = text 
		self.staAtCreation = staAtCreation 
		if lineNo < 0 or colNo < 0 :
			_errorExit( "A node with negative line or col is invalid!")
		self.lineNo = lineNo 
		self.colNo = colNo 
		self.id = "%05d:%04d" % ( lineNo, colNo )
		self.level = 0 
		self.finalized = False 

		self.recursiveTextLen = len( text ) # initially. will be adjusted later with lenght of children 
		self.recursiveNodeCnt = 1 
		# validate lineNo and colNo here

	def normedText( self ):
		return self.text.upper()
		
	#def isTreeNode():
	#	return self.type in tokenTreeNodes

	def showInfo(self): #method
		print( 'id:%s level:%d parent:%s type:%s len:%d staAtCreation:%s recursiveNodeCnt:%d recursiveTextLen:%d ' 
			% ( self.id, self.level, self.parentId, self.type, len( self.text ), self.staAtCreation, self.recursiveNodeCnt, self.recursiveTextLen ) )
		print( ' TEXT up 80 chars: "%s"' % self.text[:80] )

######
class TokenStack:
	
	levelOfElem = {}
	childrenListOfElemId = {}
	lastChildOfElemId = {}
	stackIndexOfElemId = {}
	rootAccuLen = 0 
	def __init__ ( self, name ):
		self.name = name 
		self.arr = []
		self.stackFinalized = False 

	def push ( self, elem ):
		if len(self.arr) % 10 == 0: _dbx( "Stack name %s" % (self.name))
		_dbx( "pushing node with ix %d text >>>%s" % ( len(self.arr), elem.text ) )
		# task: keep track of level of tree nodes. The first node is obviously level 0. If the node 3 has 0 as parent, if has level 1. If node 11 has 3 as parent, it obviously has level 2
		# task: keep track of which direct child nodes a tree has  
		self.childrenListOfElemId[ elem.id ] = [] # a new node does not any children yet 
		self.lastChildOfElemId[ elem.id] = None  
		# _dbx( "id %s parentId %s" % (elem.id, elem.parentId ))
		if elem.parentId == None:
			elem.level = 0 
		else:
			parentIx = self.stackIndexOfElemId[ elem.parentId ]  
			parentElem = self.arr[ parentIx ]
			elem.level = parentElem.level + 1
			self.childrenListOfElemId[ elem.parentId ].append( elem.id ) 
			self.lastChildOfElemId[ elem.parentId] = elem.id  
		# elem.showInfo()
		self.arr.append ( elem )
		self.rootAccuLen += len( elem.text )
		self.stackIndexOfElemId[ elem.id ] = len( self.arr) - 1 # remember which array index matches the id 


	def pop ( self ):
		if len( self.arr ) == 0 :

			return None
		rv = self.arr[ -1 ]
		self.arr = self.arr[ : -1 ]
	#	_dbx( "popping node with info ..." )
	#	rv.showInfo()
		return rv

	def showInfo(self): #method
		if len( self.arr ) == 0:
			print( 'Stack is empty' )
		else:
			print( 'Stack contains %d elements of type %s' % ( len( self.arr ), type( self.arr[0] ).__name__ ) )

	def finalizeStats( self, lineSize = 100 ):
		""" Do the following
			* compute the highest branch level of the tree
			* from the second highest level must contain only leaf nodes or are leaf node themselves
			  compute the accumulative tree text size length 
			* go one level down and do the same computation 
		"""
		if self.stackFinalized:

			pass
		minLev, maxLev = 9999, -1 
		for elem in self.arr:
			# _dbx( "elem id %s lev %d " % (elem.id, elem.level ) )
			if elem.level > maxLev: maxLev = elem.level
			if elem.level < minLev: minLev = elem.level
		_dbx( "minLev %d maxLev %d" %( minLev, maxLev) )
		_dbx( "arr len %d " % ( len( self.arr) ) )
		if minLev != 0 :
			_errorExit ( "minLev %d is unexpected!" % ( minLev))

		# compute the accumulative tree text size from second highest level to lowest( root )
		forQANodeCnt = 0 
		for curLevel in range( maxLev-1, -1, -1): # loop the levels. Note that the second range operand is exclusive! 
			_dbx( "*** curLevel:%d" % (curLevel ))
			for ixInStack in range(0, len( self.arr ) - 1 ): # scan all nodes of the tree 
				elemReadOnly =  self.arr[ ixInStack ]
				if elemReadOnly.level == curLevel and not elemReadOnly.finalized:
					_dbx( "ixInStack %d elem id %s, level %d" % (ixInStack, elemReadOnly.id, elemReadOnly.level) )
					childList = self.childrenListOfElemId [ elemReadOnly.id ]
					_dbx( "child cnt %d" % (len( childList )))
					for childKey in childList:
						childIx = self.stackIndexOfElemId[ childKey ]; childElem = self.arr[ childIx ]
						_dbx( "child id %s" % (childElem.id) )
						self.arr[ ixInStack ].recursiveTextLen += childElem.recursiveTextLen 
						self.arr[ ixInStack ].recursiveNodeCnt += 1
					_dbx( "recursiveNodeCnt cnt %d" % (self.arr[ ixInStack ].recursiveNodeCnt ) )
					_dbx( "recursiveTextLen cnt %d" % (self.arr[ ixInStack ].recursiveTextLen ) )
					self.arr[ ixInStack ].finalized = True 
				# for root level nodes, sum up their recursive node cnt  
				if self.arr[ ixInStack ].finalized and self.arr[ ixInStack ].level == 0: 
					forQANodeCnt += self.arr[ ixInStack].recursiveNodeCnt

		if forQANodeCnt != len( self.arr ):
			_infoTs( "forQANodeCnt %d != len of array %d " % (forQANodeCnt, len(self.arr) ) )
		self.stackFinalized = True 


	def formatTokenText( self, suppressComments= False, lineSize = 100 ): # used to be printTokenText
		"""idea: sibling tokens could be packed into lnBuf until length threshhold is nearly touched 
		as of 2020.02.15 there is a bug: recursiveNodeCnt and recursiveTextLen are NOT computed correctly.
		the values only includes self.text, children are excluded. The hash for list of child notes is outside TokenNode, in the TokenStack!
		"""

		# for NOW, dump to stdout 
		if not self.stackFinalized: 
			self.finalizeStats()

		outLines = []; lnBuf = ""
		if True: 
			ix = 0 
			while ix < len(self.arr) :
				elem = self.arr[ ix ]
				childList = self.childrenListOfElemId[elem.id] 
				#_dbx( "ix %d recursiveTextLen %d, childList len %d" % (ix, elem.recursiveTextLen, len( childList )))
				if elem.recursiveTextLen + elem.recursiveNodeCnt > lineSize: # recursive text size + separators exceed threshhold value 
					# print the current elem : 					
					outLines.append( " "*elem.level + elem.text )
					ix += 1
				else:
					# 
					# tree node line buffering node 
					#
					# assemble the current and subsequent tokens up to the last child of the current token  
					lnBuf = " "*elem.level + elem.text; ix += 1; 
					if len( childList ) > 0:
						lastChildId = self.lastChildOfElemId[ elem.id]
						#_dbx( "lastChildId: %s" %(lastChildId))
						nextElem = self.arr[ ix ] if ix < len( self.arr ) else None 
						lastChildFound = False 
						while nextElem != None and not lastChildFound:
							lnBuf += ' ' + nextElem.text 
							if nextElem.type == TokenType.single_line_comment_begin:
								outLines.append( lnBuf ); lnBuf = ""
							if nextElem.id == lastChildId: # found the last child for the line buffer 
								lastChildFound = True 
								ix += 1 
							else:
								ix += 1 
								nextElem = self.arr[ ix ] if ix < len( self.arr ) else None 

					outLines.append( lnBuf )
		else: 
			for elem in self.arr:
				outLines.append( " "*elem.level + elem.text )

		return "\n".join( outLines )
				
	def peek( self, id ):
		for elem in self.arr:
			if elem.id == id: return elem

	def assembleComplexIdents ( self ): 
		""" complex identifiers are e.g  schema_a.object_b.column_c when preceding a %TYPE
		another example: schema_a.object_b@db_link_c 
		another example: schema_a.object_b alias_b 
		This method will change the first token "schema_a" from type simple ident to complex ident
		make it the parent node of the next 4 tokens (identifiers and dot or ampersand)
		all the while allowing for comments to be interspersed. Comments are also treate as children
		of the tree 
		"""
		def resetState():
			return (FsmState.start, 0, None )

		def harvest( parentIx, stopAtIx):
			# _dbx( "harvesting with startIx %d stopAtIx %d" % (parentIx, stopAtIx))
			#_dbx( "parent type set to %s" % (self.arr[ parentIx ].tokTyp))
			childIx = parentIx + 1
			while childIx < stopAtIx: 
				self.arr[childIx].parentId = self.arr[parentIx].id
				#_dbx( "ix %d parent %s" % (childIx, self.arr[childIx].parentId))
				childIx += 1

			self.arr[ parentIx ].type = TokenType.complexIdent

		ix= 0 ; #_dbx( "cnt tok: %d" % len( self.arr) )
		sta, identCnt, startIx = resetState()
		# resetState()
		while ix < len( self.arr) :
			#_dbx( "ix %d sta %s identCnt %d" % (ix, sta, identCnt))
			tok = self.arr[ix] 
			#_dbx( "tok type %s >>>%s" % ( tok.type, tok.text ))
			if sta == FsmState.start:
				if tok.type == TokenType.ident:
					sta = FsmState.ACI_foundIdent; 	startIx = ix 
					identCnt += 1
				else:
					pass
			elif sta == FsmState.ACI_foundIdent:
				if tok.type == TokenType.ident:
					# see if we can harvest a complex ident
					if identCnt > 1: # make code reusable! 
						harvest( parentIx= startIx, stopAtIx= ix )
					sta, identCnt, startIx = resetState()
				elif tok.type in [ TokenType.dot_operator , TokenType.at_operator ]:
					sta = FsmState.ACI_foundOperator
				elif tok.type in [ TokenType.block_comment_begin , TokenType.single_line_comment_begin ]:
					pass
				else:
					if identCnt > 1: # make code reusable! 
						harvest( parentIx= startIx, stopAtIx= ix )
					sta, identCnt, startIx = resetState()
			elif sta == FsmState.ACI_foundOperator : 
				if tok.type == TokenType.ident:
					identCnt += 1
					sta = FsmState.ACI_foundIdent 
				elif tok.type in [ TokenType.block_comment_begin , TokenType.single_line_comment_begin ]:
					pass
				else:
					sta, identCnt, startIx = resetState()
			#_dbx( "new sta: %s" % (sta))
			ix += 1

	###
	def assembleComplexEndTokens( self ):
		""" complex end tokens are: END; END ident; END CASE; END IF; END LOOP;
		Subsequent signifcant raw tokens conforming to the pattern above are marked a tree
		and the first raw token becomes the parent 
		"""		
		def resetState():
			return (FsmState.start, None )

		def harvest( parentIx, upToIxInclusive, aggTokenType ):
			#_dbx( "harvesting with startIx %d upToIxInclusive %d" % (parentIx, upToIxInclusive))
			#_dbx( "parent type set to %s" % (self.arr[ parentIx ].tokTyp))
			childIx = parentIx + 1
			while childIx <= upToIxInclusive: 
				self.arr[childIx].parentId = self.arr[parentIx].id
				#_dbx( "ix %d parent %s" % (childIx, self.arr[childIx].parentId))
				childIx += 1
			self.arr[ parentIx ].type = aggTokenType

		ix= 0 ; _dbx( "cnt tok: %d" % len( self.arr) )
		sta, startIx = resetState()
		# resetState()
		while ix < len( self.arr) :
			#_dbx( "ix %d sta %s " % (ix, sta ))
			tok = self.arr[ix] 
			_dbx( "tok type %s >>>%s" % ( tok.type, tok.text ))
			if sta == FsmState.start:
				if tok.text == "END":
					sta = FsmState.foundEnd; startIx = ix 
			elif sta == FsmState.foundEnd:
				if tok.text == ";":
					harvest( parentIx= startIx, upToIxInclusive= ix, aggTokenType= TokenType.aggEndSemic )
				elif tok.text == "CASE":
					sta = FsmState.foundEndCase
				elif tok.text == "IF" :
					sta = FsmState.foundEndIf 
				elif tok.text == "LOOP":
					sta = FsmState.foundEndLoop
				elif tok.type in [ TokenType.ident, TokenType.complexIdent ]: 
					sta = FsmState.foundEndIdent 
			elif sta == FsmState.foundEndCase:
				if tok.text == ";":
					harvest( parentIx= startIx, upToIxInclusive= ix, aggTokenType= TokenType.aggEndCaseSemic )
					sta, startIx = resetState()
			elif sta == FsmState.foundEndIdent:
				if tok.text == ";":
					harvest( parentIx= startIx, upToIxInclusive= ix, aggTokenType= TokenType.aggEndIdentSemic )
					sta, startIx = resetState()
			elif sta == FsmState.foundEndIf:
				if tok.text == ";":
					harvest( parentIx= startIx, upToIxInclusive= ix, aggTokenType= TokenType.aggEndIfSemic )
					sta, startIx = resetState()
			elif sta == FsmState.foundEndLoop:
				if tok.text == ";":
					harvest( parentIx= startIx, upToIxInclusive= ix, aggTokenType= TokenType.aggEndLoopSemic )
					sta, startIx = resetState()
			else:
				sta, startIx = resetState()

			#_dbx( "new sta: %s" % (sta))
			ix += 1

	def assembleComplexTokens( self ):
		self.assembleComplexIdents() # this must be run first before assembleComplexEndTokens
		self.assembleComplexEndTokens()

	def simpleDump( self, markComplexIdents = False ):
		for ix, elem in enumerate ( self.arr ):
			# _dbx( "ix %d type %s" % (ix, elem.type ))
			if markComplexIdents and ( elem.type in [TokenType.complexIdent, TokenType.aggEndSemic, TokenType.aggEndIdentSemic, TokenType.aggEndCaseSemic, TokenType.aggEndIfSemic, TokenType.aggEndLoopSemic ] 
				or elem.parentId != None) :
				print( "%d COMPLEX self type %s parentId %s >> %s " % ( ix, elem.type, elem.parentId , elem.text ))
			else:
				print( "%d id %s type %s >> %s " % ( ix, elem.id, elem.type , elem.text ))
	
	def simpleFormatSemicolonAware( self, lineSize = 100 ):
		retVal = []; lnBuf = "" 
		for ix, elem in enumerate ( self.arr ):
			# lnBufTail = lnBuf[ : -10 ] if len(lnBuf) > 10 else lnBuf ; 	_dbx( "id %s, text len:%d lnBuf len>>%d TAIL: %s" % (elem.id, len(elem.text), len(lnBuf), lnBufTail ) )
			if elem.text in [ "PROCEDURE", "FUNCTION", "DECLARE", "BEGIN" , "CURSOR", "PRAGMA" "IF", "FOR", "WHILE"
				, "SELECT", "FROM", "WHERE", "GROUP", "ORDER" "HAVING", "INSERT", "UPDATE" ]: # these tokens force a new line before itself 
				if len( lnBuf ) > 0 :
					retVal.append( lnBuf ); # _dbx( "lnBuf>>>%s" % (lnBuf))
				lnBuf = elem.text 		
			else: 		
				#_dbx( foo )
				if len( lnBuf ) > 0 + len( elem.text ) > lineSize :	
					#_dbx( foo )
					if len( lnBuf ) > 0 :
						retVal.append( lnBuf ); _dbx( "lnBuf>>>%s" % (lnBuf))
						lnBuf = "" 
				if len( lnBuf ) > 0 : lnBuf += ' ' + elem.text
				else: 
					lnBuf = elem.text 
				#lnBufTail = lnBuf[ : -10 ] if len(lnBuf) > 10 else lnBuf; _dbx( "tail after append lnBuf>>%s" % ( lnBufTail ) )
			
			if elem.text == ";" or elem.type == TokenType.single_line_comment_begin: # these tokens force a new line AFTER itself
				retVal.append( lnBuf ); # _dbx( "lnBuf>>>%s" % (lnBuf))
				lnBuf= ""
		return retVal

	def peekAhead( self, offset= 0, skipComments= True, returnTreeAsOne= True):
		""" to enable the FSM to do a query like: if the next token is CASE and the next-next token is WHEN 
		without popping the element immediately from the stack. Since the elem returned can be complex 
		the return value is a list 
		"""
		if not skipComments or not returnTreeAsOne:
			_errorExit( "parameter values not yet supported!")
		# _dbx( "offset: %d" % ( offset))
		scanPos = 0; 
		while scanPos < len( self.arr ):
			# _dbx( "scanPos: %d" % ( scanPos))
			if scanPos < offset: 
				if self.arr[ scanPos].type in [ TokenType.single_line_comment_begin, TokenType.block_comment_begin ]:
					scanPos += 1 
				elif self.arr[ scanPos].type == TokenType.complexIdent:
					parentId = self.arr[ scanPos].id; scanPos += 1
					while self.arr[ scanPos].parentId == parentId: scanPos += 1 # fixme: we should have precalculated count of child nodes!
				else:
					break
			else:
				break
		if scanPos >= len( self.arr):
			return None # or a dummmy type 
		else:
			return  self.arr[ scanPos ] 
			
	def popComplexAware( self ):
		""" to enable the FSM to parse a complex token such as "END IF;" without using
		intermediate states. The method needs to return the head of the stack obviously,
		then each subsequent element as long as it has the head elem id as parent 
		"""
		retVal = []
		if len( self.arr ) > 0:
			retVal.append( self.arr[0])
			# _dbx( "retVal type %s >>%s" % (retVal[0].type, retVal[0].text  ))
			parentId = self.arr[0].id; childIx= 1 # will just consider if subsequent elements have this as parent, regardless of simple or complex type 
			# fixme: we should have precalculated count of child nodes!
			while childIx < len( self.arr) and self.arr[ childIx ].parentId == parentId: 
				retVal.append( self.arr[childIx]) 
				childIx += 1 
			self.arr = self.arr[ len( retVal) :]
			# _dbx( "retVal len %d" % ( len(retVal) ) )
		return retVal 
	
###
def separateCommentsFromSignficants( tree ):
	""" separate the stack into one for comments and one for significant tokens
	This is feasible when the token id is made of line no and column no so we can 
	easily merge the 2 stacks into one again without confusing the original order of tokens
	"""
	commentStack = TokenStack( name= "comments"); signifStack = TokenStack( name="significants")
	for tok in tree.arr :
		if tok.type in [ TokenType.single_line_comment_begin, TokenType.block_comment_begin ]:
			commentStack.push ( tok )
		else:
			signifStack.push( tok )

	return commentStack, signifStack

##################
class StateStack:
##################
	def __init__ ( self, name ):
		self.arr = []; self.name = name 
		
	def push ( self, state, parentId ):
		self.arr.append ( (state, parentId) )
		_dbx( "Stack %s PUSHING state  >>>>>>%s   parent:%s. elemCnt %d" % ( self.name, state, parentId, len( self.arr ) ) )

	def peek ( self ):
		if len( self.arr) == 0:

			return ( None, None)
		rv = self.arr[-1]
		state, parentId = rv 
		_dbx( "name %s PEEK returning state >>>>>>%s  elemCnt %d" % (  self.name, state, len( self.arr ) ) )
		return state, parentId
		
	def pop ( self ):
		rv = self.arr[ -1 ]
		self.arr = self.arr[ : -1 ]
		state, parentId = rv 
		_dbx( "name %s POPPING state >>>>>>%s parent %s. elemCnt %d" % ( self.name, state, parentId, len( self.arr ) ) )
		return state, parentId
		
	def isPopulated( self ):
		return len( arr ) > 0
		
	def showInfo(self): #method
		if self.elemCnt == 0:
			print( 'Stack is empty' )
		else:
			print( 'Stack contains %d elements of type %s' % ( rv, type( self.arr[0] ).__name__ ) )

def buggy_mergeTokenTrees( treeA, treeB ):
	"""Merge 2 tree assuming based on the attribute lineNo and colNo of elements, so
	that the result has the elements in ascending order of lineNo, colNo
	It is assume inserting elements of the tree with few elements into the one with more 
	elements is more efficient
	Buggy since the relation of parent-child and nesting level get lost in the process!
	"""
	mutatingTree, readOnlyTree = (treeA, treeB) if len(treeA.arr) > len( treeB.arr ) else (treeB, treeA )

	ixMu = 0 
	for elemRo in readOnlyTree.arr:
		elemMu = mutatingTree.arr[ ixMu ]
		while ixMu < len(mutatingTree.arr)-1 and elemRo.lineNo >= elemMu.lineNo or elemRo.lineNo == elemMu.lineNo and elemRo.colNo >= elemMu.colNo:
			ixMu += 1; elemMu = mutatingTree.arr[ ixMu ]
		mutatingTree.arr.insert( ixMu, elemRo ); ixMu += 1

	return mutatingTree  # buggy_mergeTokenTrees

def mergeSignifcantAndCommentTrees( signifTree, commentTree ):
	"""Merge 2 tree assuming based on the attribute lineNo and colNo of elements, so
	that the result has the elements in ascending order of lineNo, colNo. In addition
	if the token from the commentTree has a preceding signficant token p, it becomes the sibling
	of s. If not, it bocomes the sibling of the subsequent significant node 

	The looping strategy: 
	init comment and signf elem ix as first elem of respective tree
	while both elems are not None
	if comment precedes signif, push comment elem, point to next in stack
	else push signif elem, point to next in stack
	"""
	retVal = TokenStack( name= "mergeSignifcantAndCommentTrees")

	lenSignifTree, lenCommentTree = len( signifTree.arr ) , len( commentTree.arr ) 
	if lenSignifTree == 0 : 
		return commentTree
	elif lenCommentTree == 0:
		return signifTree

	ixSignif, ixComment = (0, 0)
	elemSignif =  signifTree.arr[ ixSignif ]
	elemComment = commentTree.arr[ ixComment ]

	while elemSignif != None and elemComment != None :
		_dbx( "elemSignif id: %s ix:%d >>%s" % ( elemSignif.id, ixSignif, elemSignif.text))
		_dbx( "elemComment id:%s ix:%d >>%s" % ( elemComment.id, ixComment, elemComment.text ) )
		if elemComment.lineNo < elemSignif.lineNo or ( elemComment.lineNo == elemSignif.lineNo and  elemComment.colNo < elemSignif.colNo ): 
		# comment node precedes
			_dbx( foo )
			newNode = TokenNode( text= elemComment.text, type= elemComment.type
					, staAtCreation= elemSignif.staAtCreation, lineNo=elemComment.lineNo, colNo= elemComment.colNo
					, parentId= elemSignif.parentId )
			ixComment += 1 
			elemComment = commentTree.arr[ ixComment ] if ixComment < lenCommentTree else None 
		else: # significant node precedes
			_dbx( foo )
			newNode = elemSignif
			ixSignif += 1 
			if ixSignif == lenSignifTree: 
				lastSignifElem = elemSignif
			elemSignif =  signifTree.arr[ ixSignif ] if ixSignif < lenSignifTree else None 

		retVal.push( newNode)
	# coming here, either of the arrays may having remaining unpushed elements
	while elemComment != None:
		newNode = TokenNode( text= elemComment.text, type= elemComment.type
			, staAtCreation= lastSignifElem.staAtCreation, lineNo=elemComment.lineNo, colNo= elemComment.colNo
			, parentId= lastSignifElem.parentId )
		ixComment += 1 
		retVal.push( newNode)
		elemComment = commentTree.arr[ ixComment ] if ixComment < lenCommentTree else None 
	while elemSignif != None:
		retVal.push(elemSignif)
		ixSignif += 1 
		elemSignif =  signifTree.arr[ ixSignif ] if ixSignif < lenSignifTree else None 

	if len( retVal.arr ) != lenSignifTree + lenCommentTree:
		_errorExit( "return len %d is not sum of both input trees ( %d + %d)" %( len(retVal.arr), lenSignifTree , lenCommentTree ) )
	return retVal  

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
	elif str         == '@' : typ = TokenType.at_operator
	elif str         == ',' : typ = TokenType.comma
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
	elif str.upper() in set( [ 'Q{"', 'Q["' ] ) : typ = TokenType.q_notation_begin
	elif str         == '||' : typ = TokenType.double_pipe
	# it is ok to duplicate logic for parsing normal identifier!
	else:
		# _dbx( foo )
		m = re.search( "^[a-zA-Z0-9_]+$" , str) 
		if m != None : 
			_dbx( foo )
			typ = TokenType.ident

	return typ, normed

####
	
