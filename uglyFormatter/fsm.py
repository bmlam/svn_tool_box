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


def fsm( inpLines ):
	lnCnt = len ( inpLines )
	_dbx( lnCnt )
	lineNo = 0

	nodeStack = TokenStack(); curTreeId = None
	stateStack = StateStack()

	tokBuf = ""; interceptBufferLines = []; (interceptStartLineNo,interceptStartColNo) = (-1, -1 ); # just for clarity. First reference is when we hit block_comment_begin
# match for alphanumString  OR dblQuotedAlphanumString OR assignment OR singleEqual OR doubleEqual OR dotOperator
	#    match 	macros 
	#    match 	block_comment_begin OR lineComment
	#    match 	 single quote, assignment operator
	#    match comparison operators, named param operator
	#    match arithmetric operators, left or right parenthesis, comma, semicolon
	eng = re.compile(  '^(\s*)(\$\$plsql_unit|\$\$plsql_line|[\$#a-z0-9_]+|"[\$#a-z0-9_]+"|:=|>=|<=|>|<|!=|=>|=|/\*|--|\|\||\.|%|\(|\)|\+|-|\*|/|,|;)(\s*)', re.IGNORECASE )

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
					interceptBufferLines.append( m.group(1) )
					colNo += len( m.group(1) + m.group(2) ) ;  _dbx( "found block comment end at col %d" %colNo )
					lnBuf = line[ colNo : ]; _dbx( "stuff at comment is >> %s" % ( lnBuf.rstrip("\n")) )
					curSta, curTreeId = stateStack.pop()
					node =  TokenNode( text= "".join( interceptBufferLines ), type= TokenType.block_comment_begin, staAtCreation= curSta, lineNo=-1, colNo=-1, parentId= curTreeId ) 
					nodeStack.push( node ); 

					continue # while not EOL 

			elif curSta == FsmState.in_single_quoted_literal:
				_dbx( "scanning for end single quote in >>> %s " % lnBuf )
				m = re.search( "^(.*)([']+)", lnBuf ) # match as many consecutive single quotes as available 
				if m == None: # line break is part of string literal
					interceptBufferLines.append( lnBuf ); eoLine = True # line is done
				else: # found one or several single quote 
					_dbx( "before quote chain: %s " % m.group(1) )
					_dbx( "quote chain: %s " % m.group(2) )
					singleQuoteChainLen = len( m.group(2) )
					tempBufLine = interceptBufferLines[-1]
					tempBufLine = tempBufLine + m.group(1) + m.group(2)
					interceptBufferLines[-1] = tempBufLine # may be we can do without a temp variable?
					if singleQuoteChainLen % 2 == 0: # we only found escaped single quote
						pass # do not transition 
					else: # found end of single quoted literal, possibly with trailing escaped single quotes
						curSta, curTreeId = stateStack.pop()
						node =  TokenNode( text= "".join( interceptBufferLines ), type= TokenType.single_quoted_literal_begin, staAtCreation= curSta, lineNo=-1, colNo=-1, parentId= curTreeId ) 
						nodeStack.push( node ); 

					colNo += len( m.group(1) + m.group(2) ) ;  _dbx( colNo )
					continue
				
			m = re.search( '^(\s*)$', lnBuf ) # match empty line
			if m != None:
				eoLine = True
	
			if eoLine:
				continue
	
			m = eng.match( lnBuf ) # _dbx( type( m ) )
			_dbx( 'lnBuf>> %s' % lnBuf.rstrip("\n") )
			if m == None:
				# special scan for single quoted literal in a single quoted python pattern, there is problem to look for a single quote
				# we had to single quote the pattern since we want to match double quoted indentifier
				m = re.search( "^(\s*)(')", lnBuf ) # match single quote
				if m != None: # found single quote
					stateStack.push( curSta, curTreeId  )
					curSta = FsmState.in_single_quoted_literal
					interceptBufferLines = []; (interceptStartLineNo, interceptStartColNo) = (lineNo, colNo ); interceptBufferLines.append( m.group(2) )
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
				lnBuf = line[ colNo - 1: ]; _dbx( "rest of line: %s" % lnBuf.rstrip("\n") )
		
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
					if curSta == FsmState.in_single_line_comment: 
						_errorExit ( "Encountered tokTyp %s while in state %s!" %( tokTyp, curSta) )
					else: # not in wrong status, just push line comment node, no change of state 
						stateStack.push( curSta, curTreeId )
						node =  TokenNode( text= lnBuf, type= TokenType.single_line_comment_begin, staAtCreation= curSta, lineNo=interceptStartLineNo, colNo=interceptStartColNo, parentId= curTreeId ) 
						eoLine = True
						continue
				#
				# the main finite state machine 
				#
				if curSta == FsmState.start: 
					if tokTyp == TokenType.relevant_keyword and normed == "CREATE":
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
					elif tokTyp == TokenType.relevant_keyword and  normed in set( 'IF', 'FOR' )  :
						_dbx( foo )
						stateStack.push( curSta, curTreeId)
						curSta = FsmState.in_control_block_header
						node =  TokenNode( text= normed, type= tokTyp, staAtCreation= curSta, lineNo=lineNo, colNo=colNo, parentId= curTreeId ) 
						curTreeId = node.id
					else:
						_dbx( foo )
						stateStack.push( curSta, curTreeId)
						curSta = FsmState.in_body_entry_other
						node =  TokenNode( text= normed, type= tokTyp, staAtCreation= curSta, lineNo=lineNo, colNo=colNo, parentId= curTreeId ) 
						curTreeId = node.id
				elif curSta == FsmState.in_control_block_header: 
					if tokTyp == TokenType.relevant_keyword and normed in set ( ['LOOP', 'THEN' ]) :
						_dbx( foo )
						curSta = FsmState.in_body 
						node =  TokenNode( text= normed, type= tokTyp, staAtCreation= curSta, lineNo=lineNo, colNo=colNo, parentId= curTreeId ) 
					else: 
						_dbx( foo )
						node =  TokenNode( text= normed, type= tokTyp, staAtCreation= curSta, lineNo=lineNo, colNo=colNo, parentId= curTreeId ) 
						# curSta and curTreeId  not changed
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
	_dbx( "node at finnal: %d" % curTreeId )
	if curTreeId != None:
		nodeAtFinal = nodeStack.peek( curTreeId )
		nodeAtFinal.showInfo()
	if curSta in set( [ FsmState.in_declaration ] ):
		_infoTs( "final state is ok")
	else:
		_infoTs( "WARNING: final state is unexpected!")
	return nodeStack



