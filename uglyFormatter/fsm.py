import enum, inspect, re, sys

# my modules
from plstopa import FsmState, gettokentype, StateStack, TokenNode, TokenStack, TokenType, flowControlStartKeywords, declarationKeywords

foo = "got here"

g_dbxActive = True
g_dbxCnt = 0
g_maxDbxMsg = 99600

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

###
def scanEndOfSQLiteral( str ):
	""" this function is called when FSM found a single quote which starts a single quoted literal.
	We are to return True, <port of literal> if the closing single quote is found within the input. Note that intermediate pairs of of single quotes may occur inside and even at the end of the second return value
	We are to return False, None if the closing single quote is NOT found within the input
	"""
	_dbx ( "input len:%d >>>%s" % ( len(str), str ) )
	ix = 0; part = ""; endFound = False
	while ix < len ( str ) and not endFound :
		# print("dbx  ix:%d ch:%s" % ( ix, str[ ix ] ) )
		if str[ ix ] == "'":
			if str[ ix : ].find( "''" ) == 0 : # found two, at least
				# print( "found 2" )
				part += "''"; ix += 2
			else: # ok only found one
				# print( "found 1" )
				part += "'"; ix +=1; endFound = True
		else:
				part += str[ ix ]; ix +=1
		
	if endFound: 
		rv1, rv2 = True, part
	else:
		rv1, rv2 = False, None
	_dbx( "rv1:%s, rv2>>%s" % ( rv1, rv2) )
	return rv1, rv2
		
###
def scanEndOfQNotationLiteral ( q2and3, str ):
	""" this function is called when FSM found a q notation start token, the literal can span many lines.
	We are to return True, <port of literal> if the closing single quote is found within the input. Note that intermediate pairs of of single quotes may occur inside and even at the end of the second return value
	We are to return False, None if the closing single quote is NOT found within the input
	"""
	qNotationCharPairs = { 
		 "[": "]"
		,"{": "}"
		,"'": "'"
		,'"': '"'
		,"#": "#"
	}
	_dbx ( "q2and3: %s >>>%s" % ( q2and3, str ) )
	q2Closer = qNotationCharPairs[ q2and3[0]]
	q3Closer = qNotationCharPairs[ q2and3[1]]
	q2and3Closer= q3Closer + q2Closer # indeed order must be reversed
	
	part = ""; endFound = False
	foundAt = str.find(q2and3Closer)
	#_dbx ( "q2and3Closer: %s foundAt %d" % ( q2and3Closer, foundAt ) )
	if  foundAt >= 0 : 
		substrUpTo = foundAt + len(q2and3Closer) + 1
		part += str[ 0: substrUpTo ]
		_dbx ( "part: %s" % ( part ) )
		endFound = True
		
	if endFound: 
		rv1, rv2 = True, part
	else:
		rv1, rv2 = False, None
	_dbx( "rv1:%s, rv2>>%s" % ( rv1, rv2) )
	return rv1, rv2
	

def plsqlTokenize ( inpLines ):
	lnCnt = len ( inpLines )
	_dbx( lnCnt )
	lineNo = 0

	nodeStack = TokenStack( name='plsqlTokenize'); curTreeId = None
  
	tokBuf = ""; interceptBufferLines = []; (interceptStartLineNo,interceptStartColNo) = (-1, -1 ); # just for clarity. First reference is when we hit block_comment_begin
# match for alphanumString  OR dblQuotedAlphanumString OR assignment OR singleEqual OR doubleEqual OR dotOperator
	#    match 	macros 
	#    match 	block_comment_begin OR lineComment
	#    match 	 single quote, assignment operator
	#    match comparison operators, named param operator
	#    match arithmetric operators, left or right parenthesis, comma, semicolon
	#    match Q notation begin in various flavours
	eng = re.compile(  """^(\s*)(\$\$plsql_unit|\$\$plsql_line|q\{"|[\$#a-z0-9_]+|"[\$#a-z0-9_]+"|:=|>=|<=|>|<|!=|=>|=|/\*|--|\|\||\.\.|\.|%|\(|\)|\+|-|\*|/|,|;|@)(\s*)""", re.IGNORECASE )

	curSta = FsmState.start
	for line in inpLines [ :29999 ]:
		colNo = 1; lineNo += 1 ; lnBuf = line; 
		eoLine= False; 	
		if 	None != re.search( '^(\s*)$', line ): # match empty line
			pass # _dbx( 'Line %d is empty' % lineNo )
		else:
			pass # _dbx( "line %d len: %d. Line content >>>>>>>>>%s" % ( lineNo, len( line ), line.rstrip("\n") ) )
		i=0 
		# do we need eoLine indeed or can we just bump colNo accordingly?
		while ( i < 999 and colNo < len( line ) and not eoLine ) :  # process line with safety belt against infinite loop
			i += 1
			#_dbx( "Ln/col %d/%d curSta:  '%s'" % ( lineNo, colNo, curSta ) )
			if curSta == FsmState.find_block_comment_end:
				m = re.search( '^(.*)(\*/)', lnBuf ) # math end of block comment
				if m == None:
					#_dbx( "need to cache block comment" )
					interceptBufferLines.append( lnBuf )
					eoLine = True
					continue 
				else: # found end of block comment
					interceptBufferLines.append( m.group(1) + m.group(2) )
					_dbx( "group1>>%s, group2>>%s, lnBuf>>>>%s" % ( m.group(1), m.group(2), lnBuf ) )
					lenUptoStarSlash = len( m.group(1) ) + len( m.group(2) ); _dbx( "lenUptoStarSlash:%d" % (lenUptoStarSlash))
					colNo += lenUptoStarSlash ;  _dbx( "found block comment end at col %d" %colNo )
					lnBuf = lnBuf[ lenUptoStarSlash : ]; _dbx( "stuff at comment is >>>%s" % ( lnBuf.rstrip("\n")) )
					curSta = FsmState.start 
					node =  TokenNode( text= "".join( interceptBufferLines )
						, type= TokenType.block_comment_begin, staAtCreation= curSta, lineNo=interceptStartLineNo, colNo= interceptStartColNo, parentId= curTreeId ) 
					nodeStack.push( node ); 

					continue # while not EOL 

			elif curSta == FsmState.in_single_quoted_literal:
				#_dbx( "scanning for end single quote in >>> %s " % lnBuf )
				endOfLitFound, partOfLit = scanEndOfSQLiteral( lnBuf )
				if not endOfLitFound: # line break is part of string literal
					interceptBufferLines.append( lnBuf )
					eoLine = True # line is done
				else: # found end of literal in line, possibly with rest not belonging to literal
						curSta = FsmState.start 
						interceptBufferLines.append( partOfLit )
						literalText = "".join( interceptBufferLines )
						node =  TokenNode( text= literalText, type= TokenType.single_quoted_literal_begin
							, staAtCreation= curSta, lineNo= interceptStartLineNo, colNo= interceptStartColNo
							, parentId= curTreeId ) 
						nodeStack.push( node ); 
						colNo += len( partOfLit ) ;  lnBuf= line[ colNo-1:];  #_dbx( "lnBuf>>>%s" % lnBuf )
				continue
			elif curSta == FsmState.in_q_notation_begin :
				#_dbx( "scanning for end q notation literal in >>> %s " % lnBuf )
				endOfLitFound, partOfLit = scanEndOfQNotationLiteral( q2and3, lnBuf )
				if not endOfLitFound: # line break is part of string literal
					interceptBufferLines.append( lnBuf )
					eoLine = True # line is done
				else: # found end of literal in line, possibly with rest not belonging to literal
						curSta = FsmState.start 
						interceptBufferLines.append( partOfLit )
						literalText = "".join( interceptBufferLines )
						node =  TokenNode( text= literalText, type= TokenType.single_quoted_literal_begin
							, staAtCreation= curSta, lineNo=interceptStartLineNo, colNo= interceptStartColNo
							, parentId= curTreeId ) 
						nodeStack.push( node ); 
						colNo += len( partOfLit ) ;  lnBuf= line[ colNo-1:]; # _dbx( "lnBuf>>>%s" % lnBuf )
				continue

			m = re.search( '^(\s*)$', lnBuf ) # match empty line
			if m != None:
				eoLine = True
				
			if eoLine:
				continue
	
			# process other types of token 
			m = eng.match( lnBuf ) # _dbx( type( m ) )
			#_dbx( 'lnBuf being parsed        >>>>>> %s' % lnBuf.rstrip("\n") )
			if m == None:

				# the special scan for single quoted literal is no longer needed since we can use the triple single quotes!
				m = re.search( "^(\s*)(')", lnBuf ) # match single quote
				if m != None: # found single quote
					# stateStack.push( curSta, curTreeId  )
					curSta = FsmState.in_single_quoted_literal
					interceptBufferLines = []; 	(interceptStartLineNo, interceptStartColNo) = (lineNo, colNo ) 
					interceptBufferLines.append( m.group(2) )
					colNo += len( m.group(1) + m.group(2) ) ; lnBuf = line[ colNo-1: ]; #_dbx( colNo )

					continue # we must skip the fine-grained FSM 
				else:
					_errorExit( "Rest of line %d could not be tokenized. Line content follows \n%s" % ( lineNo, lnBuf ) )
			else: 
				# second re group i.e. token 
				tok = m.group( 2 ) 

				# third re group i.e. optional whitespaces
				#if len( m.group(3) ) > 0: # found trailing whitespaces
				
				colNo += len( m.group( 1 ) ) + len( m.group( 2 ) ) + len( m.group( 3 ) ) ;  # _dbx( "colNo: %d" % colNo )

				#_dbx( "Ln/col %d/%d raw tok:  '%s'" % ( lineNo, colNo, tok ) )
				lnBuf = line[ colNo - 1: ]; # _dbx( "rest of line: %s" % lnBuf.rstrip("\n") )
		
				tokTyp, normed = gettokentype( tok ); 
				#_dbx( "tokTyp:  %s normed: '%s'" % ( tokTyp, normed  ) )

				if tokTyp == TokenType.block_comment_begin: 
					if curSta == FsmState.find_block_comment_end: 
						_errorExit ( "Encountered tokTyp %s while in state %s!" %( tokTyp, curSta) )
					else: # found block_comment if the middle of somewhere, switch the parser to specifically search for end of comment
						curSta = FsmState.find_block_comment_end
						interceptBufferLines = []; (interceptStartLineNo, interceptStartColNo) = (lineNo, colNo ); interceptBufferLines.append( tok )
						#_dbx( "we must skip the fine-grained FSM ")
						continue # we must skip the fine-grained FSM 

				elif tokTyp == TokenType.single_line_comment_begin: # found double minus 
					#_dbx( foo )
					if curSta == FsmState.find_block_comment_end: 
						_errorExit ( "Encountered tokTyp %s while in state %s!" %( tokTyp, curSta) )
					else: # not in wrong status, just push line comment node, no change of state 
						node =  TokenNode( text= normed + lnBuf.rstrip("\n"), type= TokenType.single_line_comment_begin, staAtCreation= curSta
							, lineNo=lineNo, colNo=colNo - len(normed), parentId= curTreeId ) 
						nodeStack.push( node )
						eoLine = True
						continue
				elif tokTyp == TokenType.q_notation_begin:
					#_dbx( foo )
					if curSta == FsmState.in_q_notation_begin: 
						_errorExit ( "Encountered tokTyp %s while in state %s!" %( tokTyp, curSta) )
					else: # not in wrong status, just push line comment node, no change of state 
						# stateStack.push( curSta, curTreeId  )
						q2and3 = normed[ 1:3 ] # should be the open bracket and single or double quote, in any order
						_dbx( "normed>>>%s lnBuf>>> %s" % ( normed, lnBuf ))
						curSta = FsmState.in_q_notation_begin
						interceptBufferLines = []; (interceptStartLineNo, interceptStartColNo) = (lineNo, colNo ); interceptBufferLines.append( m.group(1) + m.group(2) )

					continue # we must skip the fine-grained FSM 
				else : 
					pass #_dbx( "lineNo/colNo: %d/%d lnBuf >>>%s" % ( lineNo, colNo, lnBuf ))
				#
				#
				node =  TokenNode( text= normed, type= tokTyp, staAtCreation= None
					, lineNo=lineNo, colNo=colNo - len(normed), parentId= curTreeId ) 
				nodeStack.push( node )

	return nodeStack # plsqlTokenize
	

def fsmMain( preTokStack, startStatus = FsmState.start ):
	""" make ASSUMPTION that comments tokens are in a different stack and in the main stack 
	we only have non-comment tokens. when later on significant tokens have been linked properpy
	we will have another pass to insert the comment tokens based on lineNo/ColNo
	"""
	retTokStack = TokenStack( name="fsmMain" )
	stateStack = StateStack( name = "main_state")
	preTokStackLen = len( preTokStack.arr)
	curTreeId = None; curSta = startStatus
	thenComesFromStack = StateStack( name= "thenComesFrom")
	
	while preTokStack.peekAhead() != None:
		curTokens = preTokStack.popComplexAware()
		tokId, normed, tokTyp = (curTokens[0].id, curTokens[0].text, curTokens[0].type )
		# lineNo, colNo = (curTokens[0].lineNo, curTokens[0].colNo )
		_dbx( "curSta %s curTokens len %d, 1st id:%s type:%s >>>%s" % ( curSta, len(curTokens), tokId, tokTyp, normed) )
		
		if curSta == FsmState.start:
			if tokTyp == TokenType.relevant_keyword and normed == "CREATE":
				stateStack.push( curSta, curTreeId)
				newSta = FsmState.in_compilation_unit_header
				curTokens[0].state = staAtCreation = newSta 
				newTreeId = curTokens[0].id
			else: _errorExit( "Unknown token id %s type %s in state %s " % (tokId, tokTyp, curSta ))
		elif curSta == FsmState.in_compilation_unit_header:
			if tokTyp == TokenType.relevant_keyword and normed == "AS":
				_dbx( foo )
				newSta = FsmState.in_declaration
				curTokens[0].state = staAtCreation = newSta 
				newTreeId = curTokens[0].id
			elif tokTyp == TokenType.semicolon: # forward declaration of function/procedure
				_dbx( foo )
				newSta, newTreeId = stateStack.pop()
			else: 
				_dbx( "other token type %s in state %s " % (tokTyp, curSta ))
		elif curSta == FsmState.in_declaration: 
			if tokTyp == TokenType.relevant_keyword and normed in ["BEGIN"]:
				_dbx( foo )
				newSta = FsmState.in_body
				newTreeId = curTokens[0].id
			else: 
				_dbx( "other token type %s in state %s " % (tokTyp, curSta ))
				newSta = FsmState.started_declaration_entry				
				newTreeId = curTokens[0].id
		elif curSta == FsmState.started_declaration_entry:
			if tokTyp == TokenType.semicolon:
				_dbx( foo )
				newSta = FsmState.in_declaration
			else: 
				_dbx( "other token type %s in state %s " % (tokTyp, curSta ))
		elif curSta == FsmState.in_body:
			if tokTyp in [ TokenType.aggEndIdentSemic, TokenType.aggEndSemic ]:
				_dbx( foo )
				newSta, newTreeId = stateStack.pop()
			elif normed == "BEGIN":
				_dbx( foo )
				newSta = FsmState.in_body
				newTreeId = curTokens[0].id; 	stateStack.push( curSta, curTreeId)
			elif normed in ['IF', 'WHILE'] :
				newSta = FsmState.expect_bool_expression
				newTreeId = curTokens[0].id; 	stateStack.push( curSta, curTreeId)
				if normed == "IF":
					thenComesFromStack.push( FsmState.if_or_case_statement_open, None)
			elif normed == "CASE" and preTokStack.peekAhead().text == "WHEN":
				_dbx( foo )
				for nextTok in preTokStack.popComplexAware() :
					curTokens.append( nextTok )
				newSta = FsmState.expect_bool_expression
				newTreeId = curTokens[0].id
				stateStack.push( curSta, curTreeId)
				thenComesFromStack.push( FsmState.if_or_case_statement_open, None)
			elif normed == "CASE" and preTokStack.peekAhead().text != "WHEN":
				# here we must not pop the peeked token, it must go thru normal FSM 
				newSta = FsmState.expect_expression
				newTreeId = curTokens[0].id
				#no pop expected!  stateStack.push( curSta, curTreeId)
				thenComesFromStack.push( FsmState.if_or_case_statement_open)
			elif normed in ['DECLARE'] :
				newSta = FsmState.in_declaration
				newTreeId = curTokens[0].id
				stateStack.push( curSta, curTreeId)
			else:
				_dbx( "other token type %s in state %s " % (tokTyp, curSta ))
				stateStack.push( curSta, curTreeId)
				newSta = FsmState.expect_expression
				newTreeId = curTokens[0].id
		elif curSta in [ FsmState.expect_expression ] :
			if tokTyp in [ TokenType.semicolon, TokenType.aggEndSemic, TokenType.aggEndIfSemic, TokenType.aggEndCaseSemic, TokenType.aggEndLoopSemic]:
				_dbx( foo )
				newSta, newTreeId = stateStack.pop()

			elif normed in [ 'THEN' ]:   # this is for "CASE WHEN .. THEN .."
				_dbx( foo )
				peekThenComesFrom = thenComesFromStack.peek()[0] # we dont care about the parentId
				if peekThenComesFrom == FsmState.case_bool_expression_open:
					newSta = FsmState.in_body; 				newTreeId = curTokens[0].id
				else: 
					_errorExit( "Found THEN at %s without opening CASE token in thenComesFromStack" % tokId )
				thenComesFromStack.pop() # ignore return values
			elif normed == "ELSE" :
				_dbx( foo )
				newSta = FsmState.in_body 
				newTreeId = curTokens[0].id
			elif normed == "CASE" and preTokStack.peekAhead().text == "WHEN":
				_dbx( foo )
				for nextTok in  preTokStack.popComplexAware() :
					curTokens.append( nextTok )
				newSta = FsmState.expect_bool_expression
				newTreeId = curTokens[0].id
				#do not expect pop!  stateStack.push( curSta, curTreeId)
				thenComesFromStack.push( FsmState.case_bool_expression_open, None)
			elif normed == "CASE" and preTokStack.peekAhead().text != "WHEN":
				_dbx( foo )
				# here we must not pop the peeked token, it must go thru normal FSM 
				newSta = FsmState.expect_expression
				newTreeId = curTokens[0].id
				# stateStack.push( curSta, curTreeId)
				thenComesFromStack.push( FsmState.case_bool_expression_open, None)
			elif normed in [ 'LOOP' ]: 
				# this is for "FOR rec IN ( select * from xyz ) LOOP or similar constructs"
				newSta = FsmState.in_body
			elif tokTyp == TokenType.left_bracket:
				_dbx( foo )
				stateStack.push( curSta, curTreeId)
				newTreeId = curTokens[0].id
			elif tokTyp == TokenType.right_bracket:
				newSta, newTreeId = stateStack.pop()
			else:
				_dbx( "other token type %s in state %s " % (tokTyp, curSta ))
		elif curSta in [ FsmState.expect_bool_expression ] :
			_dbx( foo )
			if tokTyp in [ TokenType.aggEndSemic ]:   # this is for "CASE ... END;" 
				_dbx( foo )
				newSta, newTreeId = stateStack.pop()
			elif normed in [ 'THEN' ]:   # this is for "IF x THEN .. ELSE " or "WHILE y LOOP" or "CASE WHEN .. THEN .."
				_dbx( foo )
				peekThenComesFrom = thenComesFromStack.peek()[0] # we dont care about the parentId
				if peekThenComesFrom == FsmState.if_or_case_statement_open:
					newSta = FsmState.in_body; 				newTreeId = curTokens[0].id
				elif peekThenComesFrom == FsmState.case_bool_expression_open:
					newSta = FsmState.expect_expression; 				newTreeId = curTokens[0].id
				else: 
					_errorExit( "No matching OPENER for THEN at %s" % tokId )
				thenComesFromStack.pop() # ignore return values

			elif normed in [ 'ELSE', 'ELSIF', 'LOOP' ]:   # this is for "IF x THEN .. ELSE " or "WHILE y LOOP" or "CASE WHEN .. THEN .."
				_dbx( foo )
				newSta = FsmState.in_body; 				newTreeId = curTokens[0].id

			elif tokTyp == TokenType.left_bracket:
				_dbx( foo )
				stateStack.push( curSta, curTreeId)
				newTreeId = curTokens[0].id
			elif tokTyp == TokenType.right_bracket:
				newSta, newTreeId = stateStack.pop()
			elif normed == "CASE" and preTokStack.peekAhead().text == "WHEN":
				for nextTok in  preTokStack.popComplexAware():
					curTokens.append( nextTok )
				newSta = FsmState.expect_bool_expression
				newTreeId = curTokens[0].id
				stateStack.push( curSta, curTreeId)
			elif normed == "CASE" and preTokStack.peekAhead().text != "WHEN":
				# here we must not pop the peeked token, it must go thru normal FSM 
				newSta = FsmState.expect_expression
				newTreeId = curTokens[0].id
				stateStack.push( curSta, curTreeId)
		else:
			_errorExit( "No handler for state %s with input %s " % ( curSta, tokTyp) )

		for ix, curTok in enumerate(curTokens):
			# _dbx( "ix: %d type %s" % (ix, type( curTok)) )
			newNode = TokenNode( text= curTok.text, type= curTok.type
				, staAtCreation= curSta, lineNo=curTok.lineNo, colNo= curTok.colNo
				, parentId= curTreeId )
			retTokStack.push( newNode )
			#_dbx( "ret stack len %d" % (len( retTokStack.arr ) ) )
			
		_dbx( "cur sta %s new sta %s" %(curSta, newSta))
		curSta, curTreeId = newSta, newTreeId
	_infoTs( "final sta was %s" % ( newSta ))
	if preTokStackLen != len( retTokStack.arr ):
		_errorExit( "OOPPS preTokStackLen is  %d and len( retTokStack.arr ) is %d" % ( preTokStackLen, len( retTokStack.arr ) ) )
	return retTokStack

#
# editing mark
#

	return retTokStack


kickStartStatusByCode = { 
	"start" : FsmState.start
 		,"in_body" : FsmState.in_body
	}


