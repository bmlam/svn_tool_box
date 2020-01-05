import enum, inspect, re, sys

# my modules
from plstopa import FsmState, gettokentype, StateStack, TokenStack, TokenType

foo = "got here"

g_dbxActive = True
g_dbxCnt = 0
g_maxDbxMsg = 999

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


def fsm( inpLines ):
	lnCnt = len ( inpLines )
	_dbx( lnCnt )
	lineNo = 1 

	tokStk = TokenStack()
	staStk = StateStack()

	tokBuf = ""; commentLines = [] # just for clarity. First reference is when we hit blockCommentBegin
# match for alphanumString  OR dblQuotedAlphanumString OR assignment OR singleEqual OR doubleEqual OR dotOperator
	#    match 	blockCommentBegin OR lineComment
	eng = re.compile(  '^(\s*)([a-z0-9_]+|"[a-z0-9_]+"|:=|=|==|/\*|--|\.)(\s*)', re.IGNORECASE )

	curSta = FsmState.look4Create
	for ln in inpLines [ :13 ]:
		colNo = 1; lineNo += 1 ; lnBuf = ln; eoLine= False
		_dbx( "ln %d len: %d. Ln content: %s" % ( lineNo, len( ln ), ln.rstrip("\n") ) )
		i=0 
		# do we need eoLine indeed or can we just bump colNo accordingly?
		while ( i < 999 and colNo < len( ln ) and not eoLine ) :  # process line with safety belt against infinite loop
			i += 1
			_dbx( "Ln/col %d/%d curSta:  '%s'" % ( lineNo, colNo, curSta ) )
			if curSta == FsmState.look4BlockCommentEnd:
				m = re.search( '^(.*)(\*/)', lnBuf ) # math end of block comment
				if m == None:
					_dbx( "need to cache block comment" )
					commentLines.append( lnBuf )
					colNo = len( ln )
					continue 
				else: # find end of block comment
					commentLines.append( m.group(1) )
					colNo = len( m.group(1) + m.group(2) ) ;  _dbx( colNo )
					lnBuf = ln[ colNo : ]; _dbx( "rest of line %d: %s" % ( lineNo, lnBuf.rstrip("\n")) )
					curSta = staStk.pop()
					continue # while not EOL 
				
			m = re.search( '^(\s*)$', lnBuf ) # math empty line
			if m != None:
				eoLine = True
	
			if eoLine:
				continue
	
			m = eng.match( lnBuf ) # _dbx( type( m ) )
			if m == None:
				_errorExit( "Rest of line %d could not be tokenized. Line content follows \n%s" % ( lineNo, lnBuf ) )
			else: 
				# second re group i.e. token 
				tok = m.group( 2 ) #; colNo += len( tok ) 

				# third re group i.e. optional whitespaces
				#if len( m.group(3) ) > 0: # found trailing whitespaces
				
				colNo += len( m.group( 1 ) ) + len( m.group( 2 ) ) + len( m.group( 3 ) ) ;  # _dbx( "colNo: %d" % colNo )

				_dbx( "Ln/col %d/%d tok:  '%s'" % ( lineNo, colNo, tok ) )
				lnBuf = ln[ colNo - 1: ]; _dbx( "rest of line: %s" % lnBuf )
		
				tokTyp, normed = gettokentype( tok );  _dbx( "INPUT tokTyp %s " % tokTyp )
				_dbx( "tokTyp:  %s normed: '%s'" % ( tokTyp, normed  ) )

				if tokTyp == TokenType.blockCommentBegin: 
					if curSta == FsmState.look4BlockCommentEnd: 
						_errorExit ( "Encountered tokTyp %s while in state %s!" %( tokTyp, curSta) )
					else: 
						staStk.push( curSta ); curSta = FsmState.look4BlockCommentEnd; commentLines = []; commentLines.append( tok )
						continue # we must skip the fine-grained FSM 

				if curSta == FsmState.look4Create:
					if tokTyp == TokenType.compileUnitBegin :
						curSta = FsmState.look4OrReplace1; _dbx( "push token!")
					elif tokTyp == TokenType.blockCommentBegin : 
						staStk.push( curSta ); curSta = FsmState.look4BlockCommentEnd; commentLines = []; commentLines.append( tok )
				elif curSta == FsmState.look4OrReplace1:
					if tokTyp == TokenType.blockCommentBegin :
						staStk.push( curSta ); curSta = FsmState.look4BlockCommentEnd; commentLines = []; commentLines.append( tok )
					elif tokTyp == TokenType.keywordOr : 
						curSta = FsmState.look4OrReplace2
				elif curSta == FsmState.look4OrReplace2:
					#if tokTyp == TokenType.blockCommentBegin :
					#	staStk.push( curSta ); curSta = FsmState.look4BlockCommentEnd; commentLines = []; commentLines.append( tok )
					if tokTyp == TokenType.keywordReplace : 
						curSta = FsmState.look4OrCompileUnitTypQualifierOrIdent
				elif curSta == FsmState.look4OrCompileUnitTypQualifierOrIdent:
					if tokTyp == TokenType.keywordBody : 
						curSta = FsmState.look4OrCompileUnitIdent
					elif tokTyp == TokenType.ident : 
						curSta = FsmState.look4AsOrIs
				elif curSta == FsmState.look4OrCompileUnitIdent:
					if tokTyp == TokenType.ident :
						curSta = FsmState.look4OrCompileUnitIdentDotOrAs
					elif tokTyp == TokenType.keywordAsOrIs : 
						curSta = FsmState.look4BeginOrDeclEntry
				elif curSta == FsmState.look4AsOrIs:
					if tokTyp == TokenType.keywordAsOrIs : 
						curSta = FsmState.look4BeginOrDeclEntry
				elif curSta == FsmState.look4BeginOrDeclEntry:
					if tokTyp == TokenType.ident :
						curSta = FsmState.look4ConstantOrColumnTypeOrNameType
					elif tokTyp == TokenType.keywordBegin :
						curSta = FsmState.bodyOpen
				elif curSta == FsmState.look4ConstantOrColumnTypeOrNameType:
					if tokTyp = TokenType.ident:
						curSta = FsmState.bodyFoundIdent
					else tokTyp == TokenType.keywordInsert: 
						curSta = FsmState.look4IntoOrInsertTgtIdent
				elif curSta == FsmState.bodyOpen:
				# else:						_errorExit( "No transition for state %s with input %s " % ( curSta, tokTyp) )
				_dbx( "sta at end of pass: %s"  % curSta )

	return tokStk



