""" the big bad FSM spun out / decommissioned from fsm.py on 2020.01.25
"""
def fsm_1_pass_only( inpLines ):
	lnCnt = len ( inpLines )
	_dbx( lnCnt )
	lineNo = 0

	nodeStack = TokenStack(); curTreeId = None
	stateStack = StateStack()
	caseStatementStack = StateStack()
  
	tokBuf = ""; interceptBufferLines = []; (interceptStartLineNo,interceptStartColNo) = (-1, -1 ); # just for clarity. First reference is when we hit block_comment_begin
# match for alphanumString  OR dblQuotedAlphanumString OR assignment OR singleEqual OR doubleEqual OR dotOperator
	#    match 	macros 
	#    match 	block_comment_begin OR lineComment
	#    match 	 single quote, assignment operator
	#    match comparison operators, named param operator
	#    match arithmetric operators, left or right parenthesis, comma, semicolon
	#    match Q notation begin in various flavours
	eng = re.compile(  """^(\s*)(\$\$plsql_unit|\$\$plsql_line|q\{"|[\$#a-z0-9_]+|"[\$#a-z0-9_]+"|:=|>=|<=|>|<|!=|=>|=|/\*|--|\|\||\.|%|\(|\)|\+|-|\*|/|,|;)(\s*)""", re.IGNORECASE )

	# qNotationBeginPattern = """^(\s*)(q[\[\]]")"""

	curSta = FsmState.start
	for line in inpLines [ :9999 ]:
		colNo = 1; lineNo += 1 ; lnBuf = line; eoLine= False
		if 	None != re.search( '^(\s*)$', line ): # match empty line
			_dbx( 'Line %d is empty' % lineNo )
		else:
			_dbx( "line %d len: %d. Line content >>>>>>>>>%s" % ( lineNo, len( line ), line.rstrip("\n") ) )
		i=0 
		# do we need eoLine indeed or can we just bump colNo accordingly?
		while ( i < 999 and colNo < len( line ) and not eoLine ) :  # process line with safety belt against infinite loop
			i += 1
			_dbx( "Ln/col %d/%d curSta:  '%s'" % ( lineNo, colNo, curSta ) )
			if curSta == FsmState.find_block_comment_end:
				m = re.search( '^(.*)(\*/)', lnBuf ) # math end of block comment
				if m == None:
					_dbx( "need to cache block comment" )
					interceptBufferLines.append( lnBuf )
					eoLine = True
					continue 
				else: # found end of block comment
					interceptBufferLines.append( m.group(1) + m.group(2) )
					colNo += len( m.group(1) + m.group(2) ) ;  _dbx( "found block comment end at col %d" %colNo )
					lnBuf = line[ colNo : ]; _dbx( "stuff at comment is >> %s" % ( lnBuf.rstrip("\n")) )
					curSta, curTreeId = stateStack.pop()
					node =  TokenNode( text= "".join( interceptBufferLines ), type= TokenType.block_comment_begin, staAtCreation= curSta, lineNo=-1, colNo=-1, parentId= curTreeId ) 
					nodeStack.push( node ); 

					continue # while not EOL 

			elif curSta == FsmState.in_single_quoted_literal:
				_dbx( "scanning for end single quote in >>> %s " % lnBuf )
				endOfLitFound, partOfLit = scanEndOfSQLiteral( lnBuf )
				if not endOfLitFound: # line break is part of string literal
					interceptBufferLines.append( lnBuf )
					eoLine = True # line is done
				else: # found end of literal in line, possibly with rest not belonging to literal
						curSta, curTreeId = stateStack.pop()
						interceptBufferLines.append( partOfLit )
						literalText = "".join( interceptBufferLines )
						node =  TokenNode( text= literalText, type= TokenType.single_quoted_literal_begin, staAtCreation= curSta, lineNo=-1, colNo=-1, parentId= curTreeId ) 
						nodeStack.push( node ); 
						colNo += len( partOfLit ) ;  lnBuf= line[ colNo-1:];  _dbx( "lnBuf>>>%s" % lnBuf )
				continue
			elif curSta == FsmState.in_q_notation_begin :
				_dbx( "scanning for end q notation literal in >>> %s " % lnBuf )
				endOfLitFound, partOfLit = scanEndOfQNotationLiteral( q2and3, lnBuf )
				if not endOfLitFound: # line break is part of string literal
					interceptBufferLines.append( lnBuf )
					eoLine = True # line is done
				else: # found end of literal in line, possibly with rest not belonging to literal
						curSta, curTreeId = stateStack.pop()
						interceptBufferLines.append( partOfLit )
						literalText = "".join( interceptBufferLines )
						node =  TokenNode( text= literalText, type= TokenType.single_quoted_literal_begin, staAtCreation= curSta, lineNo=-1, colNo=-1, parentId= curTreeId ) 
						nodeStack.push( node ); 
						colNo += len( partOfLit ) ;  lnBuf= line[ colNo-1:];  _dbx( "lnBuf>>>%s" % lnBuf )
				continue
			m = re.search( '^(\s*)$', lnBuf ) # match empty line
			if m != None:
				eoLine = True
				
			if eoLine:
				continue
	
			m = eng.match( lnBuf ) # _dbx( type( m ) )
			_dbx( 'lnBuf being parsed        >>>>>> %s' % lnBuf.rstrip("\n") )
			if m == None:

				# the special scan for single quoted literal is no longer needed since we can use the triple single quotes!
				m = re.search( "^(\s*)(')", lnBuf ) # match single quote
				if m != None: # found single quote
					stateStack.push( curSta, curTreeId  )
					curSta = FsmState.in_single_quoted_literal
					interceptBufferLines = []
					(interceptStartLineNo, interceptStartColNo) = (lineNo, colNo ) # just used for troubleshooting
					interceptBufferLines.append( m.group(2) )
					colNo += len( m.group(1) + m.group(2) ) ; lnBuf = line[ colNo-1: ]; _dbx( colNo )

					continue # we must skip the fine-grained FSM 
				else:
					_errorExit( "Rest of line %d could not be tokenized. Line content follows \n%s" % ( lineNo, lnBuf ) )
			else: 
				# second re group i.e. token 
				tok = m.group( 2 ) #; colNo += len( tok ) 

				# third re group i.e. optional whitespaces
				#if len( m.group(3) ) > 0: # found trailing whitespaces
				
				colNo += len( m.group( 1 ) ) + len( m.group( 2 ) ) + len( m.group( 3 ) ) ;  # _dbx( "colNo: %d" % colNo )

				_dbx( "Ln/col %d/%d raw tok:  '%s'" % ( lineNo, colNo, tok ) )
				lnBuf = line[ colNo - 1: ]; # _dbx( "rest of line: %s" % lnBuf.rstrip("\n") )
		
				tokTyp, normed = gettokentype( tok ); 
				_dbx( "tokTyp:  %s normed: '%s'" % ( tokTyp, normed  ) )

				if tokTyp == TokenType.block_comment_begin: 
					if curSta == FsmState.find_block_comment_end: 
						_errorExit ( "Encountered tokTyp %s while in state %s!" %( tokTyp, curSta) )
					else: # found block_comment if the middle of somewhere, switch the parser to specifically search for end of comment
						stateStack.push( curSta, curTreeId )
						curSta = FsmState.find_block_comment_end
						interceptBufferLines = []; (interceptStartLineNo, interceptStartColNo) = (lineNo, colNo ); interceptBufferLines.append( tok )
						_dbx( "we must skip the fine-grained FSM ")
						continue # we must skip the fine-grained FSM 

				elif tokTyp == TokenType.single_line_comment_begin: # found double minus 
					_dbx( foo )
					if curSta == FsmState.find_block_comment_end: 
						_errorExit ( "Encountered tokTyp %s while in state %s!" %( tokTyp, curSta) )
					else: # not in wrong status, just push line comment node, no change of state 
						node =  TokenNode( text= normed + lnBuf.rstrip("\n"), type= TokenType.single_line_comment_begin, staAtCreation= curSta, lineNo=interceptStartLineNo, colNo=interceptStartColNo, parentId= curTreeId ) 
						nodeStack.push( node )
						eoLine = True
						continue
				elif tokTyp == TokenType.q_notation_begin:
					_dbx( foo )
					if curSta == FsmState.in_q_notation_begin: 
						_errorExit ( "Encountered tokTyp %s while in state %s!" %( tokTyp, curSta) )
					else: # not in wrong status, just push line comment node, no change of state 
						stateStack.push( curSta, curTreeId  )
						q2and3 = normed[ 1:3 ] # should be the open bracket and single or double quote, in any order
						#_dbx( "normed: %s q2and3: %s" % ( normed, q2and3 ))
						_dbx( "normed>>>%s lnBuf>>> %s" % ( normed, lnBuf ))
						curSta = FsmState.in_q_notation_begin
						interceptBufferLines = []; (interceptStartLineNo, interceptStartColNo) = (lineNo, colNo ); interceptBufferLines.append( m.group(1) + m.group(2) )
					# colNo += len( m.group(1) + m.group(2) ) ; lnBuf = line[ colNo-1: ]; _dbx( colNo )

					continue # we must skip the fine-grained FSM 
				#
				# the main finite state machine 
				#
				if curSta == FsmState.start: 
					if tokTyp == TokenType.relevant_keyword and normed == "CREATE":
						stateStack.push( curSta, curTreeId ) # at the end, we want to pop back this without the stack hitting index out of range 
						curSta = FsmState.in_compilation_unit_header
						node =  TokenNode( text= normed, type= tokTyp, staAtCreation= curSta, lineNo=lineNo, colNo=colNo, parentId= curTreeId ) 
						curTreeId = node.id

				elif curSta == FsmState.in_compilation_unit_header: 
					if tokTyp == TokenType.relevant_keyword and normed == "AS":
						_dbx( foo )
						curSta = FsmState.in_declaration
						node =  TokenNode( text= normed, type= tokTyp, staAtCreation= curSta, lineNo=lineNo, colNo=colNo, parentId= curTreeId ) 
						curTreeId = node.id
					elif tokTyp == TokenType.semicolon: # forward declaration of function/procedure
						_dbx( foo )
						node =  TokenNode( text= normed, type= tokTyp, staAtCreation= curSta, lineNo=lineNo, colNo=colNo, parentId= curTreeId ) 
						curSta, curTreeId = stateStack.pop()
					else:
						_dbx( foo )
						node =  TokenNode( text= normed, type= tokTyp, staAtCreation= curSta, lineNo=lineNo, colNo=colNo, parentId= curTreeId ) 
				elif curSta == FsmState.in_declaration: 
					if tokTyp == TokenType.relevant_keyword and normed == "END": # a package/type body does NOT need to have a BEGIN section
						_dbx( foo )
						curSta = FsmState.finalising_body 
						node =  TokenNode( text= normed, type= tokTyp, staAtCreation= curSta, lineNo=lineNo, colNo=colNo, parentId= curTreeId ) 
					elif ( tokTyp == TokenType.relevant_keyword and( normed == "CURSOR" or normed == "TYPE" ) ) or tokTyp == TokenType.ident :
						_dbx( foo )
						stateStack.push( curSta, curTreeId )
						curSta = FsmState.started_declaration_entry 
						node =  TokenNode( text= normed, type= tokTyp, staAtCreation= curSta, lineNo=lineNo, colNo=colNo, parentId= curTreeId ) 
						curTreeId = node.id
					elif ( tokTyp == TokenType.relevant_keyword and( normed == "PROCEDURE" or normed == "FUNCTION" ) ):
						_dbx( foo )
						stateStack.push( curSta, curTreeId  )
						curSta = FsmState.in_compilation_unit_header
						node =  TokenNode( text= normed, type= tokTyp, staAtCreation= curSta, lineNo=lineNo, colNo=colNo, parentId= curTreeId ) 
						curTreeId = node.id
					elif ( tokTyp == TokenType.relevant_keyword and( normed == "BEGIN" ) ):
						_dbx( foo )
						curSta = FsmState.in_body
						node =  TokenNode( text= normed, type= tokTyp, staAtCreation= curSta, lineNo=lineNo, colNo=colNo, parentId= curTreeId ) 
						curTreeId = node.id

					else : _errorExit( "got unexpected input")
				elif curSta == FsmState.started_declaration_entry: 
					if tokTyp == TokenType.semicolon:
						_dbx( foo )
						node =  TokenNode( text= normed, type= tokTyp, staAtCreation= curSta, lineNo=lineNo, colNo=colNo, parentId= curTreeId ) 
						curSta, curTreeId = stateStack.pop() 
					#elif ( tokTyp == TokenType.single_quoted_literal_begin ):
					else: 
						_dbx( foo )
						node =  TokenNode( text= normed, type= tokTyp, staAtCreation= curSta, lineNo=lineNo, colNo=colNo, parentId= curTreeId ) 
						# curSta and curTreeId  not changed
				elif curSta == FsmState.in_body: 
					if tokTyp == TokenType.relevant_keyword and ( normed == "END" ):
						_dbx( foo )
						curSta = FsmState.finalising_body
						node =  TokenNode( text= normed, type= tokTyp, staAtCreation= curSta, lineNo=lineNo, colNo=colNo, parentId= curTreeId ) 
						# curTreeId not changed
					elif tokTyp == TokenType.relevant_keyword and ( normed == "BEGIN" ):
						_dbx( foo )
						stateStack.push( curSta, curTreeId)
						node =  TokenNode( text= normed, type= tokTyp, staAtCreation= curSta, lineNo=lineNo, colNo=colNo, parentId= curTreeId ) 
						curTreeId = node.id
					elif tokTyp == TokenType.relevant_keyword and  normed in set( ['IF', 'FOR', 'CASE' ])  :
						_dbx( foo )
						stateStack.push( curSta, curTreeId)
						curSta = FsmState.in_control_block_header
						node =  TokenNode( text= normed, type= tokTyp, staAtCreation= curSta, lineNo=lineNo, colNo=colNo, parentId= curTreeId ) 
						curTreeId = node.id
						if normed == "CASE": 
							caseStatementStack.push( FsmState.in_case_stmt, curTreeId) 
					else:
						_dbx( foo )
						stateStack.push( curSta, curTreeId)
						curSta = FsmState.in_body_entry_other
						node =  TokenNode( text= normed, type= tokTyp, staAtCreation= curSta, lineNo=lineNo, colNo=colNo, parentId= curTreeId ) 
						curTreeId = node.id
				elif curSta == FsmState.in_control_block_header: 
					if tokTyp == TokenType.relevant_keyword and normed in set ( ['LOOP', 'THEN' , 'CASE' ]) :
						if normed == "CASE" and caseStatementStack.isPopulated :
							_dbx( foo )
							curSta = FsmState.finalising_case_stmt 
						else: 
							_dbx( foo )
							curSta = FsmState.in_body 
						node =  TokenNode( text= normed, type= tokTyp, staAtCreation= curSta, lineNo=lineNo, colNo=colNo, parentId= curTreeId ) 
					else: 
						_dbx( foo )
						node =  TokenNode( text= normed, type= tokTyp, staAtCreation= curSta, lineNo=lineNo, colNo=colNo, parentId= curTreeId ) 
						# curSta and curTreeId  not changed
				elif curSta == FsmState.finalising_case_stmt: 
						_dbx( foo )
						if tokTyp == TokenType.semicolon:
							caseStatementStack.pop()
							curSta = FsmState.in_body
						else: 
							_errorExit( "in state %s and found normed token %s " % ( curSta, normed ) )
						node =  TokenNode( text= normed, type= tokTyp, staAtCreation= curSta, lineNo=lineNo, colNo=colNo, parentId= curTreeId )
				elif curSta == FsmState.in_body_entry_other: 
					if tokTyp == TokenType.semicolon :
						_dbx( foo )
						node =  TokenNode( text= normed, type= tokTyp, staAtCreation= curSta, lineNo=lineNo, colNo=colNo, parentId= curTreeId ) 
						curSta, curTreeId = stateStack.pop()
					if tokTyp == TokenType.left_bracket :
						stateStack.push( curSta, curTreeId)
						curSta = FsmState.in_bracket 
						node =  TokenNode( text= normed, type= tokTyp, staAtCreation= curSta, lineNo=lineNo, colNo=colNo, parentId= curTreeId ) 
						curTreeId = node.id 
					else:
						_dbx( foo )
						node =  TokenNode( text= normed, type= tokTyp, staAtCreation= curSta, lineNo=lineNo, colNo=colNo, parentId= curTreeId ) 
						# curSta and curTreeId  not changed
				elif curSta == FsmState.in_bracket: 
					if tokTyp == TokenType.right_bracket :
						_dbx( foo )
						node =  TokenNode( text= normed, type= tokTyp, staAtCreation= curSta, lineNo=lineNo, colNo=colNo, parentId= curTreeId ) 
						curSta, curTreeId = stateStack.pop()
					# what should we do here? elif tokTyp == TokenType.comma :
					elif tokTyp == TokenType.left_bracket :
						_dbx( foo )
						# no change of state but we have a new tree and we are blink to what is comming!
						stateStack.push( curSta, curTreeId)
						node =  TokenNode( text= normed, type= tokTyp, staAtCreation= curSta, lineNo=lineNo, colNo=colNo, parentId= curTreeId ) 
						curTreeId = node.id 
					else:
						_dbx( foo )
						node =  TokenNode( text= normed, type= tokTyp, staAtCreation= curSta, lineNo=lineNo, colNo=colNo, parentId= curTreeId ) 
				elif curSta == FsmState.finalising_body: 
					if tokTyp == TokenType.ident :
						_dbx( foo )
						node =  TokenNode( text= normed, type= tokTyp, staAtCreation= curSta, lineNo=lineNo, colNo=colNo, parentId= curTreeId ) 
						# curSta not changed, curTreeId not changed
					elif tokTyp == TokenType.semicolon :
						_dbx( foo )
						node =  TokenNode( text= normed, type= tokTyp, staAtCreation= curSta, lineNo=lineNo, colNo=colNo, parentId= curTreeId ) 
						curSta, curTreeId = stateStack.pop()
				else:						
					_errorExit( "No transition for state %s with input %s " % ( curSta, tokTyp) )
				
				_dbx( "sta at end of pass: %s"  % curSta )
				nodeStack.push( node )
	_dbx( "node at finnal: %s" % curTreeId )
	if curTreeId != None:
		nodeAtFinal = nodeStack.peek( curTreeId )
		nodeAtFinal.showInfo()
	if curSta in set( [ FsmState.in_declaration, FsmState.start ] ):
		_infoTs( "final state is ok")
	else:
		_infoTs( "WARNING: final state is unexpected!")
	return nodeStack

#def fsmBodyEntry( startNode ):
#	"""     EXPERIMENTAL!!!
#		a spin-out from fsmMain(), this method handles a body entry such as a SQL, an assignment or a flow control statement. All of them should end on a semicolon and we do not need to expect a another body entry getting nested. Good prerequisites for a spin-out of a lengthy piece of code 
#	"""
#	global g_preTokStack, g_retTokStack 
#	normed, tokTyp = (startNodetext, startNodetype )
#	lineNo, colNo = (startNodelineNo, startNodecolNo )
#
#	curSta = FsmState.in_body_entry_other; stateStack = StateStack()
#	node =  TokenNode( text= normed, type= tokTyp, staAtCreation= curSta, lineNo=lineNo, colNo=colNo, parentId= curTreeId ) 
#	#while g_preTokStack.peekAhead() != None:
#	tokensAhead = []
#	# fetch ahead once for repeatedly query later 
#	for offset in range( 0 .. 3 ):
#		tokensAhead.append( g_preTokStack.peekAhead() )
#		toksCur = tokensAhead[ offset ]
#		_dbx( "toksCur 1st type: %s >>>%s " % (tokesCur{0}.type, tokesCur{0}.text ) )
#	if startNode.text == "CASE" and tokensAhead[0] == "WHEN":
#		_dbx( foo )
#		stateStack.push( curSta, curTreeId )
#		curSta = FsmState.expect_expression
#	elif startNode.text == "CASE" and tokensAhead[0] != "WHEN":
#		_dbx( foo )
#		curSta = FsmState.expect_bool_expression
#	elif startNode.text in [ "FOR", "IF", "WHILE"]:
#		_dbx( foo )
#		curSta = FsmState.expect_expression

def fsmMain( preTokStack, startStatus = FsmState.start ):
	""" make ASSUMPTION that comments tokens are in a different stack and in the main stack 
	we only have non-comment tokens. when later on significant tokens have been linked properpy
	we will have another pass to insert the comment tokens based on lineNo/ColNo
	"""
	stateStack = StateStack()
	retTokStack = TokenStack(); curTreeId = None; curSta = startStatus
	
	while preTokStack.peekAhead() != None:
		curTokens = preTokStack.popComplexAware()
		normed, tokTyp = (curTokens[0].text, curTokens[0].type )
		lineNo, colNo = (curTokens[0].lineNo, curTokens[0].colNo )
		_dbx( "began with sta %s curTokens len %d, 1st>>%s" % ( curSta, len(curTokens), normed) )
		
		# handle comments regardless of curSta 
		if tokTyp in [ TokenType.single_line_comment_begin, TokenType.block_comment_begin ]:
				# since staAtCreation and parentId may have change, we need instantiate a new node 
				node =  TokenNode( text= normed, type= tokTyp, staAtCreation= curSta, lineNo=lineNo, colNo=colNo, parentId= curTreeId ) 
				retTokStack.push ( node )

				continue

		node =  TokenNode( text= normed, type= tokTyp, staAtCreation= curSta, lineNo=lineNo, colNo=colNo, parentId= curTreeId ) 
		if curSta == FsmState.start:
			if tokTyp == TokenType.relevant_keyword and normed == "CREATE":
				stateStack.push( curSta, curTreeId ) # at the end, we want to pop back this without the stack hitting index out of range, curTreeId being None is ok
				curSta = FsmState.in_compilation_unit_header
				node.staAtCreation = curSta 
				curTreeId = node.id

		elif curSta == FsmState.in_compilation_unit_header:
			if tokTyp == TokenType.relevant_keyword and normed == "AS":
				_dbx( foo )
				curSta = FsmState.in_declaration
				node.staAtCreation = curSta 
				curTreeId = node.id
			elif tokTyp == TokenType.semicolon: # forward declaration of function/procedure
				_dbx( foo )
				curSta, curTreeId = stateStack.pop()
			else:
				_dbx( foo )
		elif curSta == FsmState.in_declaration: 
			pass 
		elif curSta == FsmState.started_declaration_entry:
			pass
		elif curSta == FsmState.in_body:

			if normed == "END":
				_dbx( foo )
				curSta = FsmState.finalising_body
				# node status and curTreeId not changed
			elif normed == "BEGIN":
				_dbx( foo )
				stateStack.push( curSta, curTreeId)
				curTreeId = node.id
			elif normed in ['CASE' ] :
				curTreeId = node.id
				if preTokStack.peekAhead().normed == "WHEN":
					curSta = FsmState.expect_bool_expression
				else:
					curSta = FsmState.expect_xpression
			elif normed in ['IF', 'FOR', 'WHILE' ]  :
				_dbx( foo )
				stateStack.push( curSta, curTreeId)
				curSta = FsmState.expect_bool_expression
				node =  TokenNode( text= normed, type= tokTyp, staAtCreation= curSta, lineNo=lineNo, colNo=colNo, parentId= curTreeId ) 
				curTreeId = node.id
			else:
				_dbx( foo )
				stateStack.push( curSta, curTreeId)
				curSta = FsmState.in_body_entry_other
				node =  TokenNode( text= normed, type= tokTyp, staAtCreation= curSta, lineNo=lineNo, colNo=colNo, parentId= curTreeId ) 
				curTreeId = node.id
		elif curSta in [ FsmState.in_body_entry_other,FsmState.finalising_body,FsmState.expect_expression,FsmState.expect_bool_expression] :
			if tokTyp == TokenType.semicolon:
				_dbx( foo )
				curSta, curTreeId = stateStack.pop()
				node =  TokenNode( text= normed, type= tokTyp, staAtCreation= curSta, lineNo=lineNo, colNo=colNo, parentId= curTreeId ) 
			elif tokTyp == TokenType.left_bracket:
				_dbx( foo )
				stateStack.push( curSta, curTreeId)
				node =  TokenNode( text= normed, type= tokTyp, staAtCreation= curSta, lineNo=lineNo, colNo=colNo, parentId= curTreeId ) 
				curTreeId = node.id
			elif tokTyp == TokenType.right_bracket:
				_dbx( foo )
				curSta, curTreeId = stateStack.pop()
				node =  TokenNode( text= normed, type= tokTyp, staAtCreation= curSta, lineNo=lineNo, colNo=colNo, parentId= curTreeId ) 
				# no transition 
			else:
				_dbx( foo )
				node =  TokenNode( text= normed, type= tokTyp, staAtCreation= curSta, lineNo=lineNo, colNo=colNo, parentId= curTreeId ) 
				# no transition 
		#elif curSta == FsmState.finalising_body:			pass
		#elif curSta == FsmState.expect_expression:			pass
		#elif curSta == FsmState.expect_bool_expression:			pass
		else:
			_errorExit( "No handler for state %s with input %s " % ( curSta, tokTyp) )
				
		_dbx( "sta at end of pass: %s"  % curSta )
		
		retTokStack.push( node )
		
		#for tok in curTokens: 			retTokStack.push( tok )
	return retTokStack

	def finalizeStats( self, lineSize = 100 ):
		""" Do the following
			* compute the highest branch level of the tree
			* from the second highest level must contain only leaf nodes or are leaf node themselves
			  compute the accumulative tree text size length 
			* go one level down and do the same computation 
		"""
		minLev, maxLev = 9999, -1 
		for lev in self.levelOfElem.values():
			if lev > maxLev: maxLev = lev
			if lev < minLev: minLev = lev
		_dbx( "minLev %d maxLev %d" %( minLev, maxLev) )
		_dbx( "arr len %d " % ( len( self.arr) ) )
		#
		# use a recursive algorithm to assemble the tokens of one tree into one single line
		# as long as this single line does NOT exceed a configured length 
		#
		for lev in range( maxLev-1, minLev-1, -1): # loop from bottom to top level. Note that the second range operand is exclusive! 
			_dbx( "lev:%d" % (lev ))
			for curElemIx in range(0, len( self.arr ) - 1 ): # loop over all node on this level 
				if self.arr[ curElemIx ].level == lev:
					#_dbx( "curElemIx %d" % (curElemIx) )
					for childIx in self.childIndexesOfElemId [ self.arr[ curElemIx ].id ]:
						#_dbx( "childIx %d" % (childIx) )
						self.arr[ curElemIx ].treeLen += self.arr[ childIx ].treeLen + 1 # cater for space as separator
		for ( k,v ) in self.childIndexesOfElemId.items(): # dump hierarchy
			# _dbx( k )
			pass # _dbx( "childIx %d. children:%s " % ( k, ','.join( map( str, v )) ) )
			#_dbx( "Above was childIx. val type:%s " % ( type( v) ) )

		for ix, elem in enumerate( self.arr ):
			#_dbx( "ix %d tokTyp: %s, lev %d textLen %d treeLen:%d " % ( ix, elem.type, elem.level, len(elem.text), elem.treeLen) )
			if elem.treeLen < lineSize: # assemble texts of child nodes 
				self.tempTextList = [ ]; self.safetyNestLevel = 0  # reset assembly area
				self.assembleText( elem )
				if len( self.tempTextList ) > 1:
					self.arr[ ix ].textList = self.tempTextList
					# _dbx( "text assembled>>> %s " %( " ".join( self.arr[ ix ].textList ) ) )

	def _deprecated_assembleText ( self, elem ):
		#_dbx( "safetyNestLevel %d, elem.textList>> %s" % (self.safetyNestLevel, elem.text ))
		self.safetyNestLevel += 1
		if self.safetyNestLevel > 99:
			_errorExit( "safetyNestLevel reached %d!!!" % (self.safetyNestLevel))

		if elem.type == TokenType.single_line_comment_begin:
			self.tempTextList.append( elem.text + "\n" )
		else:
			self.tempTextList.append( elem.text )
		childCnt = len( self.childrenListOfElemId[ elem.id ] )
		#_dbx( "childCnt %d " % ( childCnt))
		if childCnt > 0: # this node has at least one child, fixme: 	this check is probably redundant!
			for childIndex in self.childrenListOfElemId[ elem.id ] :
 				self.assembleText( self.arr[ childIndex] )

