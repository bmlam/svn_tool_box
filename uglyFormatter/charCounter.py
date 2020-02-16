#!/Library/Frameworks/Python.framework/Versions/3.8/bin/python3
""" 
on AirBook : 
#!/usr/bin/python3
on iMac:
#!/Library/Frameworks/Python.framework/Versions/3.8/bin/python3

Count occurrence of character by classes. Example output

Bracket     char total : 66
Bracket chars          : [:3 ]:66 {:5 }:5 (:0 ):0

Digit char total       : 77
Digit chars : 0:3 1:3 3:0 ...  

ignore-case char total : 333.
ignore-case char total A thru L A:3 B:4 E:9 
ignore-case char total M thru Z M:3 N:4 O:9 

upper-case char  total : 133 
upper-case char total A thru L A:3 B:4 E:9 
upper-case char total M thru Z M:3 N:4 O:9 

analog for lower case

Other Non-ASCII-127  total: 666
Do NOT expect detail report on non-ascii character !


Research:

>>> for i in range( 0, 128 ): print( "%d %s" % ( i, chr(i) ) )
...
0
1
... 
31
32
33 !
34 "
35 #
36 $
37 %
38 &
39 '
40 (
41 )
42 *
43 +
44 ,
45 -
46 .
47 /
48 0
49 1
50 2
51 3
52 4
53 5
54 6
55 7
56 8
57 9
58 :
59 ;
60 <
61 =
62 >
63 ?
64 @
65 A
66 B
67 C
68 D
69 E
70 F
71 G
72 H
73 I
74 J
75 K
76 L
77 M
78 N
79 O
80 P
81 Q
82 R
83 S
84 T
85 U
86 V
87 W
88 X
89 Y
90 Z
91 [
92 \
93 ]
94 ^
95 _
96 `
97 a
98 b
99 c
100 d
101 e
102 f
103 g
104 h
105 i
106 j
107 k
108 l
109 m
110 n
111 o
112 p
113 q
114 r
115 s
116 t
117 u
118 v
119 w
120 x
121 y
122 z
123 {
124 |
125 }
126 ~
127 
"""


import inspect, re, sys

## my modules 
# import plstopa, fsm

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

def abbrCamelize( str, maxLen = 6, splitBy="_" ):
	retVal = str
	if len( retVal) > maxLen:
		parts = str.split( splitBy )
		pctAllowed = maxLen / len(str) 
		#_dbx( "str %s, pctAllowed %f" % (str, pctAllowed ))
		retVal = ""
		for ix, part in enumerate( parts ):
			charsAllowed = int( len(part) * pctAllowed )
			if len( retVal) + charsAllowed > maxLen: charsAllowed = maxLen - len( retVal)
			if ix == 0 and len( part ) > charsAllowed: charsAllowed += 1
			#_dbx( "charsAllowed %d" % ( (charsAllowed) ) )
			capitalized= part[ 0: charsAllowed ].title()
			retVal += capitalized
	return retVal
	
class CharStats :
	"""
	This class was created with the intention to create char count stats for MANUAL comparision.
	In practice it is not really useful. But maybe it proves one to be useful to be able to init a 
	char by it nickname. Who knows?
	"""

	def __init__ ( self, nickName, cnt= 0, ord = None ):
		if nickName != None:
			self.nickName = nickName; 
		else: nickName = "ascii%d" % ord
		
		self.cnt = 0 
		if   nickName == "ascii0": self.ord = 0; self.isCtrlChar= True
		elif nickName == "ascii1": self.ord = 1; self.isCtrlChar= True
		elif nickName == "ascii2": self.ord = 2; self.isCtrlChar= True
		elif nickName == "ascii3": self.ord = 3; self.isCtrlChar= True
		elif nickName == "ascii4": self.ord = 4; self.isCtrlChar= True
		elif nickName == "ascii5": self.ord = 5; self.isCtrlChar= True
		elif nickName == "ascii6": self.ord = 6; self.isCtrlChar= True
		elif nickName == "ascii7": self.ord = 7; self.isCtrlChar= True
		elif nickName == "ascii8": self.ord = 8; self.isCtrlChar= True
		elif nickName == "horizon_tab": self.ord = 9; self.isCtrlChar= True
		elif nickName == "new_line": self.ord = 10; self.isCtrlChar= True
		elif nickName == "ascii11": self.ord = 11; self.isCtrlChar= True
		elif nickName == "ascii12": self.ord = 12; self.isCtrlChar= True
		elif nickName == "carriage_return": self.ord = 13; self.isCtrlChar= True
		elif nickName == "ascii14": self.ord = 14; self.isCtrlChar= True
		elif nickName == "ascii15": self.ord = 15; self.isCtrlChar= True
		elif nickName == "ascii16": self.ord = 16; self.isCtrlChar= True
		elif nickName == "ascii17": self.ord = 17; self.isCtrlChar= True
		elif nickName == "ascii18": self.ord = 18; self.isCtrlChar= True
		elif nickName == "ascii19": self.ord = 19; self.isCtrlChar= True
		elif nickName == "ascii20": self.ord = 20; self.isCtrlChar= True
		elif nickName == "ascii21": self.ord = 21; self.isCtrlChar= True
		elif nickName == "ascii22": self.ord = 22; self.isCtrlChar= True
		elif nickName == "ascii23": self.ord = 23; self.isCtrlChar= True
		elif nickName == "ascii24": self.ord = 24; self.isCtrlChar= True
		elif nickName == "ascii25": self.ord = 25; self.isCtrlChar= True
		elif nickName == "ascii26": self.ord = 26; self.isCtrlChar= True
		elif nickName == "ascii27": self.ord = 27; self.isCtrlChar= True
		elif nickName == "ascii28": self.ord = 28; self.isCtrlChar= True
		elif nickName == "ascii29": self.ord = 29; self.isCtrlChar= True
		elif nickName == "ascii30": self.ord = 30; self.isCtrlChar= True
		elif nickName == "ascii31": self.ord = 31; self.isCtrlChar= True
		# 
		elif nickName == "space": self.ord = 32; self.isCtrlChar= False
		elif nickName == "exclamation": self.ord = 33; self.isCtrlChar= False
		elif nickName == "double_quote": self.ord = 34; self.isCtrlChar= False
		elif nickName == "hash": self.ord = 35; self.isCtrlChar= False
		elif nickName == "dollar": self.ord = 36; self.isCtrlChar= False
		elif nickName == "percent": self.ord = 37; self.isCtrlChar= False
		elif nickName == "ampersand": self.ord = 38; self.isCtrlChar= False
		elif nickName == "tick": self.ord = 39; self.isCtrlChar= False
		elif nickName == "left_parenthesis": self.ord = 40; self.isCtrlChar= False
		elif nickName == "right_parenthesis": self.ord = 41; self.isCtrlChar= False
		elif nickName == "star": self.ord = 42; self.isCtrlChar= False
		elif nickName == "plus": self.ord = 43; self.isCtrlChar= False
		elif nickName == "comma": self.ord = 44; self.isCtrlChar= False
		elif nickName == "minus": self.ord = 45; self.isCtrlChar= False
		elif nickName == "period": self.ord = 46; self.isCtrlChar= False
		elif nickName == "slash": self.ord = 47; self.isCtrlChar= False
		#
		elif nickName == "zero"  or ord == 48: self.ord = 48; self.isCtrlChar= False; self.nickName = "zero"  
		elif nickName == "one"   or ord == 49: self.ord = 49; self.isCtrlChar= False; self.nickName = "one" 
		elif nickName == "two"   or ord == 50: self.ord = 50; self.isCtrlChar= False; self.nickName = "two"   
		elif nickName == "three" or ord == 51: self.ord = 51; self.isCtrlChar= False; self.nickName = "three" 
		elif nickName == "four"  or ord == 52: self.ord = 52; self.isCtrlChar= False; self.nickName = "four"  
		elif nickName == "five"  or ord == 53: self.ord = 53; self.isCtrlChar= False; self.nickName = "five" 
		elif nickName == "six"   or ord == 54: self.ord = 54; self.isCtrlChar= False; self.nickName = "six"  
		elif nickName == "seven" or ord == 55: self.ord = 55; self.isCtrlChar= False; self.nickName = "seven" 
		elif nickName == "eight" or ord == 56: self.ord = 56; self.isCtrlChar= False; self.nickName = "eight" 
		elif nickName == "nine"  or ord == 57: self.ord = 57; self.isCtrlChar= False; self.nickName = "nine"  
		#
		elif nickName == "colon": self.ord = 58; self.isCtrlChar= False
		elif nickName == "semicolon": self.ord = 59; self.isCtrlChar= False
		elif nickName == "left_arrow": self.ord = 60; self.isCtrlChar= False
		elif nickName == "equal": self.ord = 61; self.isCtrlChar= False
		elif nickName == "right_arrow": self.ord = 62; self.isCtrlChar= False
		elif nickName == "question": self.ord = 63; self.isCtrlChar= False
		elif nickName == "commercial_at": self.ord = 64; self.isCtrlChar= False
		#
		elif nickName == "A": self.ord = 65; self.isCtrlChar= False
		elif nickName == "B": self.ord = 66; self.isCtrlChar= False
		elif nickName == "C": self.ord = 67; self.isCtrlChar= False
		elif nickName == "D": self.ord = 68; self.isCtrlChar= False
		elif nickName == "E": self.ord = 69; self.isCtrlChar= False
		elif nickName == "F": self.ord = 70; self.isCtrlChar= False
		elif nickName == "G": self.ord = 71; self.isCtrlChar= False
		elif nickName == "H": self.ord = 72; self.isCtrlChar= False
		elif nickName == "I": self.ord = 73; self.isCtrlChar= False
		elif nickName == "J": self.ord = 74; self.isCtrlChar= False
		elif nickName == "K": self.ord = 75; self.isCtrlChar= False
		elif nickName == "L": self.ord = 76; self.isCtrlChar= False
		elif nickName == "M": self.ord = 77; self.isCtrlChar= False
		elif nickName == "N": self.ord = 78; self.isCtrlChar= False
		elif nickName == "O": self.ord = 79; self.isCtrlChar= False
		elif nickName == "P": self.ord = 80; self.isCtrlChar= False
		elif nickName == "Q": self.ord = 81; self.isCtrlChar= False
		elif nickName == "R": self.ord = 82; self.isCtrlChar= False
		elif nickName == "S": self.ord = 83; self.isCtrlChar= False
		elif nickName == "T": self.ord = 84; self.isCtrlChar= False
		elif nickName == "U": self.ord = 85; self.isCtrlChar= False
		elif nickName == "V": self.ord = 86; self.isCtrlChar= False
		elif nickName == "W": self.ord = 87; self.isCtrlChar= False
		elif nickName == "X": self.ord = 88; self.isCtrlChar= False
		elif nickName == "Y": self.ord = 89; self.isCtrlChar= False
		elif nickName == "Z": self.ord = 90; self.isCtrlChar= False
		#
		elif nickName == "left_square": self.ord = 91; self.isCtrlChar= False
		elif nickName == "backslash": self.ord = 92; self.isCtrlChar= False
		elif nickName == "right_square": self.ord = 93; self.isCtrlChar= False
		elif nickName == "arrow_up": self.ord = 94; self.isCtrlChar= False
		elif nickName == "under_bar": self.ord = 95; self.isCtrlChar= False
		elif nickName == "back_tick": self.ord = 96; self.isCtrlChar= False
		#
		elif nickName == "a": self.ord = 97; self.isCtrlChar= False
		elif nickName == "b": self.ord = 98; self.isCtrlChar= False
		elif nickName == "c": self.ord = 99; self.isCtrlChar= False
		elif nickName == "d": self.ord = 100; self.isCtrlChar= False
		elif nickName == "e": self.ord = 101; self.isCtrlChar= False
		elif nickName == "f": self.ord = 102; self.isCtrlChar= False
		elif nickName == "g": self.ord = 103; self.isCtrlChar= False
		elif nickName == "h": self.ord = 104; self.isCtrlChar= False
		elif nickName == "i": self.ord = 105; self.isCtrlChar= False
		elif nickName == "j": self.ord = 106; self.isCtrlChar= False
		elif nickName == "k": self.ord = 107; self.isCtrlChar= False
		elif nickName == "l": self.ord = 108; self.isCtrlChar= False
		elif nickName == "m": self.ord = 109; self.isCtrlChar= False
		elif nickName == "n": self.ord = 110; self.isCtrlChar= False
		elif nickName == "o": self.ord = 111; self.isCtrlChar= False
		elif nickName == "p": self.ord = 112; self.isCtrlChar= False
		elif nickName == "q": self.ord = 113; self.isCtrlChar= False
		elif nickName == "r": self.ord = 114; self.isCtrlChar= False
		elif nickName == "s": self.ord = 115; self.isCtrlChar= False
		elif nickName == "t": self.ord = 116; self.isCtrlChar= False
		elif nickName == "u": self.ord = 117; self.isCtrlChar= False
		elif nickName == "v": self.ord = 118; self.isCtrlChar= False
		elif nickName == "w": self.ord = 119; self.isCtrlChar= False
		elif nickName == "x": self.ord = 120; self.isCtrlChar= False
		elif nickName == "y": self.ord = 121; self.isCtrlChar= False
		elif nickName == "z": self.ord = 122; self.isCtrlChar= False
		#
		elif nickName == "left_curly": self.ord = 123; self.isCtrlChar= False
		elif nickName == "pipe": self.ord = 124; self.isCtrlChar= False
		elif nickName == "right_curly": self.ord = 125; self.isCtrlChar= False
		elif nickName == "tilde": self.ord = 126; self.isCtrlChar= False
		elif nickName == "ascii127": self.ord = 127; self.isCtrlChar= True
		else:	 _errorExit( "nick name '%s' unknown!" % (nickName))

	def info(self, doPrint= True):
		retVal = 'Ordinal %d %s count %d' % ( self.ord, self.nickName, self.cnt )
		if doPrint:
			print( retVal )
		else:
			return retVal
			
	def shortInfoVCamel(self, nickPadTo=6, cntPadTo= 4, doPrint= False):
		nameAbbr = abbrCamelize( self.nickName, maxLen= nickPadTo )
		spaceLeft = nickPadTo - len( nameAbbr )
		if spaceLeft > 0: nameAbbr += " " * spaceLeft
		
		cntStr = "%d" % self.cnt
		spaceLeft = cntPadTo - len( cntStr )
		if spaceLeft > 0: cntStr = " " * spaceLeft + cntStr
		
		retVal = '%s:%s' % ( nameAbbr, cntStr )
		#_dbx( "len %d '%s'" % ( len(retVal), retVal))
		if doPrint:
			print( retVal )
		else:
			return retVal
			
	def gencode(self):
			print( """elif nickName == "%s": self.ord = %d; self.isCtrlChar= %s """ % ( self.nickName, self.ord, str(self.isCtrlChar) ) )
		
	
class CharGroupStats :
	arr = []
	totCnt = -1
	
	def __init__( self, name, arr ):
		self.name = name
		self.arr = arr
	# def add( self, CharStats  ): 		arr.append( CharStats  )
		
	def sumUp( self ):
		#_dbx( "totCnt %s" % ( self.totCnt))
		# for whichever reason, trying to compute totCnt only once does not work!	# if self.totCnt == -1:
		if True:
			#_dbx( "got here")
			self.totCnt = 0
			for elem in self.arr: 
				# _dbx( "cnt %d" % ( elem.cnt ))
				self.totCnt += elem.cnt 
			#_dbx( "totCnt %d" % ( self.totCnt ))

	def sumInfo( self, doPrint = False ):
		self.sumUp() 
		retVal = "%s total occurrence: %d" % ( self.name, self.totCnt )
		return retVal 
		
	def detailInfo( self, printZero= False ):
		#result is ugly! retVal =  "abbrCamelize( self.name, maxLen=10, splitBy=" " )
		self.sumUp()
		retVal =  self.name
		if self.totCnt == 0:
			retVal += " details irrelevant"
		else:
			for ix, elem in enumerate( self.arr ):
				if ix > 0: retVal += '; '

				camel = ' '+elem.shortInfoVCamel()
				if not printZero and elem.cnt == 0:
					retVal += " " * len( camel ) # only print blanks!
				else:
					retVal += camel 
		return retVal 
		
class TextCharStats:

	def setupGroups( self):

		self.nonAscii127Count = 0 # maybe this should be in CharGroupStats! fixme
		self.brackets = [ CharStats ( nickName= "left_curly" )
			 ,CharStats ( nickName= "right_curly" )
			 ,CharStats ( nickName= "left_parenthesis" )
			 ,CharStats ( nickName= "right_parenthesis" )
			 ,CharStats ( nickName= "left_square" )
			 ,CharStats ( nickName= "right_square" )
			]

		self.lower_a_to_l = []
		for n in range(97, 109) : self.lower_a_to_l.append( CharStats ( nickName = chr(n) ) )

		self.lower_m_to_z = []
		for n in range(109, 123) : self.lower_m_to_z.append( CharStats ( nickName = chr(n) ) )

		self.upper_a_to_l = []
		for n in range(97, 109)  : self.upper_a_to_l.append( CharStats ( nickName = chr(n).title() ) )

		self.upper_m_to_z = []
		for n in range(109, 123) : self.upper_m_to_z.append( CharStats ( nickName = chr(n).title()  ) )

		self.digits_0_to_9 = []
		for n in range(48, 58) :   self.digits_0_to_9.append( CharStats ( nickName=None, ord = n ) )
		
		self.whitespaces = [ CharStats("space"), CharStats("horizon_tab"), CharStats("new_line"), CharStats("carriage_return") ]
		
		defined_sofar = self.brackets + self.digits_0_to_9 + self.lower_a_to_l + self.lower_m_to_z + self.upper_a_to_l + self.upper_m_to_z +  self.whitespaces
		_dbx( len( defined_sofar))

		self.other_printables = []
		self.other_printables = [ CharStats( nickName= "exclamation" )
		 ,CharStats( nickName= "double_quote" )
		 ,CharStats( nickName= "hash" )
		 ,CharStats( nickName= "dollar" )
		 ,CharStats( nickName= "percent" )
		 ,CharStats( nickName= "ampersand" )
		 ,CharStats( nickName= "tick" )
		 ,CharStats( nickName= "star" )
		 ,CharStats( nickName= "plus" )
		 ,CharStats( nickName= "comma" )
		 ,CharStats( nickName= "minus" )
		 ,CharStats( nickName= "period" )
		 ,CharStats( nickName= "slash" )
		 ,CharStats( nickName= "colon" )
		 ,CharStats( nickName= "semicolon" )
		 ,CharStats( nickName= "left_arrow" )
		 ,CharStats( nickName= "equal" )
		 ,CharStats( nickName= "right_arrow" )
		 ,CharStats( nickName= "question" )
		 ,CharStats( nickName= "commercial_at" )
		 ,CharStats( nickName= "backslash" )
		 ,CharStats( nickName= "arrow_up" )
		 ,CharStats( nickName= "under_bar" )
		 ,CharStats( nickName= "back_tick" )
		 ,CharStats( nickName= "pipe" )
		 ,CharStats( nickName= "tilde" )
		]

		expected_chars= defined_sofar + self.other_printables
		self.other_ascii127= []
		for n in range( 0, 128):
			occupied = False
			for ch in expected_chars:
				if n == ch.ord:
					occupied= True
					break
			if not occupied : 
				ch = CharStats( nickName= "ascii%d" % n )
				self.other_ascii127.append( ch )

		# perform QA
		lenLst1, lenLst2 = len( expected_chars), len( self.other_ascii127 ) 
		lenSet1, lenSet2 = len( set(expected_chars) ), len( set(self.other_ascii127) )
		_dbx( "lenLst1:%d, lenSet1:%d lenLst2:%d lenSet2:%d" %(lenLst1, lenSet1, lenLst2, lenSet2 ) )
		if lenLst1 > lenSet1 or lenLst2 > lenSet2 : 
			_errorExit( "lenLst1:%d > lenSet1:%d or lenLst2:%d > lenSet2:%d" %(lenLst1, lenSet1, lenLst2, lenSet2 ) )

		self.group_lower_A_L = CharGroupStats( name="lower a to l", arr= self.lower_a_to_l)
		self.group_lower_M_Z = CharGroupStats( name="lower m to z", arr= self.lower_m_to_z)
		self.group_upper_A_L = CharGroupStats( name="UPPER A to L", arr= self.upper_a_to_l)
		self.group_upper_M_Z = CharGroupStats( name="UPPER M to Z", arr= self.upper_m_to_z)

		self.group_digits_0_to_9 = CharGroupStats( name="numeric digits",           arr= self.digits_0_to_9 )
		self.group_brackets  = CharGroupStats( name="brackets",                     arr= self.brackets  )
		self.group_whitespaces  = CharGroupStats( name="whitespaces",               arr= self.whitespaces  )
		self.group_other_printables  = CharGroupStats( name="other_printables"    , arr= self.other_printables  )
		self.group_other_ascii127    = CharGroupStats( name="other ascii127 chars", arr= self.other_ascii127 )

		self.specialGroupIgnoreCase = CharGroupStats( "UPPER + lower char merged", arr= self.lower_a_to_l + self.lower_m_to_z + self.upper_a_to_l + self.upper_m_to_z )

	####
	def __init__( self, name, shortCode=None ):
		self.name= name
		self.shortCode = shortCode 
		self.setupGroups()

	####
	def scan( self, txt ):
		_dbx( "input len %d" % ( len(txt)))
		# init local counters
		ordOccurences = []
		for n in range( 0, 128 ):  ordOccurences.append( 0 )
		nonAscii127Count = 0

		# loop over input text 
		for c in txt:
			# _dbx( "c len %d '%s' type %s" % (len(c), c, type(c)))
			n = ord(c)
			if n > 128: 
				nonAscii127Count += 1
			else:
				ordOccurences[n] += 1

		for n in range( 0, 128 ):  
			#_dbx( "n %d occ %d" % (n, ordOccurences[n])) 
			ordDone= False
			for elem in self.group_upper_A_L.arr:
				if n == elem.ord: elem.cnt = ordOccurences[n]; ordDone= True; break
			for elem in self.group_upper_M_Z.arr:
				if n == elem.ord: elem.cnt = ordOccurences[n]; ordDone= True; break

			for elem in self.group_lower_A_L.arr:
				if n == elem.ord: elem.cnt = ordOccurences[n]; ordDone= True; break
			for elem in self.group_lower_M_Z.arr:
				if n == elem.ord: elem.cnt = ordOccurences[n]; ordDone= True; break
			for elem in self.group_digits_0_to_9.arr:
				if n == elem.ord: elem.cnt = ordOccurences[n]; ordDone= True; break
			#
			for elem in self.group_whitespaces.arr:
				if n == elem.ord: elem.cnt = ordOccurences[n]; ordDone= True; break
			for elem in self.group_digits_0_to_9.arr:
				if n == elem.ord: elem.cnt = ordOccurences[n]; ordDone= True; break
			for elem in self.group_other_printables.arr:
				if n == elem.ord: elem.cnt = ordOccurences[n]; ordDone= True; break
			for elem in self.group_brackets.arr:
				if n == elem.ord: elem.cnt = ordOccurences[n]; ordDone= True; break
			for elem in self.group_other_ascii127.arr:
				if n == elem.ord: elem.cnt = ordOccurences[n]; ordDone= True; break
		# _dbx( "nick %s cnt: %d" % (charStats.nickName, charStats.cnt ))

	def report( self):
		print( "*"*30 + " STATS " + "*" *30 )
		lines = []
		
		lines.append( self.specialGroupIgnoreCase.sumInfo() )

		lines.append( self.group_lower_A_L.sumInfo() )
		lines.append( self.group_lower_A_L.detailInfo() )
		lines.append( self.group_lower_M_Z.sumInfo() )
		lines.append( self.group_lower_M_Z.detailInfo() )
		#
		lines.append( self.group_upper_A_L.sumInfo() )
		lines.append( self.group_upper_A_L.detailInfo() )
		lines.append( self.group_upper_M_Z.sumInfo() )
		lines.append( self.group_upper_M_Z.detailInfo() )
		#
		lines.append( self.group_brackets.sumInfo() )
		lines.append( self.group_brackets.detailInfo() )
		#
		lines.append( self.group_whitespaces.sumInfo() )
		lines.append( self.group_whitespaces.detailInfo() )
		#
		lines.append( self.group_digits_0_to_9.sumInfo() )
		lines.append( self.group_digits_0_to_9.detailInfo() )
		#
		lines.append( self.group_other_printables.sumInfo() )
		lines.append( self.group_other_printables.detailInfo() )
		#
		lines.append( self.group_other_ascii127.sumInfo() )
		lines.append( self.group_other_ascii127.detailInfo() )

		if self.shortCode != None:
			for ix, line in enumerate( lines ):
				lines[ix] = "%s <-%s" % ( line, self.shortCode )
		print( "\n".join( lines))

class WordCounter:
	####
	def __init__( self, name, lines, shortCode=None ):
		self.ignoreCase = True 
		self.name= name
		self.shortCode = shortCode 
		self.lines = lines 

	####
	def scan( self ):
		_dbx( "input line cnt %d" % ( len(self.lines)))
		# init local counters
		self.wordOccurAt = {}
		matchEng = re.compile ( "([^a-zA-Z0-9_]*)([a-zA-Z0-9_]+)" ) 
		# loop over input text 
		for lineNo, lineText in enumerate( self.lines ) :
			_dbx( "ln %d text>>>%s" % (lineNo, lineText))
			scanFrom = 0
			while scanFrom < len( lineText ):
				m = matchEng.match( lineText[ scanFrom : ])
				if m != None: # found an ident
					_dbx( "g1: %s" % ( m.group(1)))
					word = m.group( 2); foundAt = scanFrom + len( m.group(1))
					if self.ignoreCase: word = word.upper()
					_dbx( "scanFrom %d word '%s' found at %d/%d" % (scanFrom, word, lineNo, foundAt ))
					if not word in self.wordOccurAt.keys():
						self.wordOccurAt[ word ] = []
					self.wordOccurAt[ word].append ( "%d/%d" % ( lineNo+1, foundAt+1) ) 

					scanFrom += len( m.group(1) ) + len ( m.group(2) )
				else: scanFrom = len ( lineText )

	def report( self, printToStdout= True , maxOccToPrint = 0):
		
		print( "*"*30 + " WORD STATS " + "*" *30 )
		outLines = []
		for word in sorted(self.wordOccurAt): # returns keys only in sorted order
			posList =  self.wordOccurAt[ word ]
			occurToPrint = len( posList ); firstOcc= 0
			if occurToPrint > maxOccToPrint: 		occurToPrint = maxOccToPrint
			# we have not completely implemented paging control yet! 
			positionDisplayStr = " ".join( posList[ firstOcc: occurToPrint] )
			outLine=  "%s \t%d-%d/(%d): %s" % ( word, firstOcc, firstOcc+occurToPrint, len( posList), positionDisplayStr) 
			if self.shortCode != None:
				outLine += "<--%s" % (self.shortCode)
			outLines.append( outLine )
		if printToStdout:
			print( "\n".join( outLines ))
		else:
			return outLines

		
class TextCharStatsIgnoreCase:
	""" treat a as A, b as B etc 
	loop thru the ordinal of found characters when reporting, no grouping to letters, punctuation marks etc
	"""

	####
	def __init__( self, textName, txt  ):
		self.textName= textName
		self.countOfCharWithOrder = {}
		_dbx( "input len %d" % ( len(txt)))
		# init local counters
		ordOccurences = []

		# loop over input text 
		for ln in txt:
			for ix in range( 0, len( ln ) ) :
				c = ln[ix]
				n = ord(c)
				if n in range( 97, 122+1): # treat a as A, b as B ...
					n -= 32 
				if n in self.countOfCharWithOrder.keys():
					self.countOfCharWithOrder [ n ] += 1
				else:
					self.countOfCharWithOrder [ n ] = 1 

	def report( self, printToStdout= True):
		print( "*"*30 + " STATS for " + self.textName + "*" *30 )
		lines = []
		for n in sorted( self.countOfCharWithOrder.keys() ):
			lines.append( "Chr-%d (%s): %d" % ( n, chr(n) if (n >= 32 and n <= 126) else "", self.countOfCharWithOrder[n]) )
		if printToStdout:
			print( "\n".join( lines))
		else:
			return lines

def parseCmdLine() :
	import argparse

	global g_inpFilePath, g_outFilePath, g_inpLines, g_inpLines2, g_shortCode1, g_shortCode2

	parser = argparse.ArgumentParser()
	# lowercase shortkeys
	parser.add_argument( '-i', '--inputFile' , help='input file, could also be sent as STDIN', required= False )
	parser.add_argument( '-j', '--inputFile2' , help='2nd input file', required= False )
	parser.add_argument( '-1', '--shortCode1' , help='short code to distinguish source file 1', required= False )
	parser.add_argument( '-2', '--shortCode2' , help='short code to distinguish source file 2', required= False )

	result= parser.parse_args()
	if True: 
		if result.inputFile != None:
			g_inpFilePath = result.inputFile
			g_inpLines =  open( g_inpFilePath, "r" ).readlines()
		else: 
			print( "reading text from stdin...")
			g_inpLines =  sys.stdin.readlines() 
		
		_dbx( len( g_inpLines) )
	# _dbx( "\n".join( g_inpLines[:3] ) )
		if result.inputFile2 != None:
			if result.shortCode1 == None or result.shortCode2 == None :
				_errorExit( "When 2nd input file is supplied, short codes must be supplied for 1st and 2nd input file!")
			g_inpFilePath2 = result.inputFile2
			g_inpLines2 =  open( g_inpFilePath2, "r" ).readlines()

		if result.shortCode1 != None:
			g_shortCode1 = result.shortCode1
		if result.shortCode2 != None:
			g_shortCode2 = result.shortCode2

	return result
	
def main_using_chargroups():
	global brackets, lower_a_to_l, upper_m_to_z, digits_0_to_9, other_printables
	argParserResult = parseCmdLine()
	global g_inpLines, g_inpLines2, g_shortCode1 

	# for i in range ( 0, 128): 		foo = CharStats (i)		foo.gencode()
	# for ch in brackets: print( ch.shortInfoVCamel() )
	#for n, ch in enumerate( upper_m_to_z ): 
	#	ch.cnt = n
	#	info = ch.shortInfoVCamel() 
	#	#_dbx( "Len %d txt'%s'" % (len(info), info))
	#	print( ch.shortInfoVCamel() )

	textCharStat1 = TextCharStats( name="text1" , shortCode= g_shortCode1 )
	# print( textCharStat1.group_lower_A_L.sumInfo() )

	inpStream = "".join( g_inpLines )
	_dbx( "input len %d" % ( len(inpStream)))
	textCharStat1.scan( inpStream )
	textCharStat1.report()

	if False:
		inpStream2 = "".join( g_inpLines2 )
		_dbx( "input len %d" % ( len(inpStream2)))

		textCharStat2 = TextCharStats( name="text1", shortCode= "B" )
		textCharStat2.scan( inpStream2)
		textCharStat2.report()

	if "to" == "print info":
		print( group_lower_A_L.sumInfo() )
		print( group_lower_A_L.detailInfo() )
		print( group_upper_M_Z.sumInfo() )
		print( group_upper_M_Z.detailInfo() )
		print( group_digits_0_to_9.sumInfo() )
		print( group_digits_0_to_9.detailInfo() )
	
		print( group_whitespaces .sumInfo() )
		print( group_whitespaces .detailInfo() )
	
		print( group_other_printables .sumInfo() )
		print( group_other_printables .detailInfo() )
	
def main ():
	argParserResult = parseCmdLine()
	global g_inpLines, g_shortCode1, g_inpLines2, g_shortCode2

	if False:
		textCharCounter1 = TextCharStatsIgnoreCase( textName= g_shortCode1, txt = g_inpLines )
		textCharCounter1.report()

	if True:
		textWordCounter1 = WordCounter( name="text1" , lines= g_inpLines, shortCode= g_shortCode1 )
		textWordCounter1.scan()
		textWordCounter1.report()

		g_inpLines2 = None 
		if g_inpLines2 != None:
			textWordCounter2 = WordCounter( name="text2" , lines= g_inpLines2, shortCode= g_shortCode2 )
			textWordCounter2.scan()
			textWordCounter2.report()

# main()


