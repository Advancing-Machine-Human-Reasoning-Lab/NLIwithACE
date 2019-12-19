"""
This file contains code to work with rewrite rules: rules that take a natural language sentence (and a constituency parse in some cases) and modify it so that it is more likely to be parseable by Attempto's parser, while preserving as many of the original sentence's semantics as possible.

Author: John Licato, licato@usf.edu
"""
from FOL_resolution import parseExpression, propStructToSExp
import sys
from pattern.en import conjugate, pluralize, singularize
from wordnet_utils import findHypernym, findHypernym_onedir
"""To install pattern:
git clone -b development https://github.com/clips/pattern
cd pattern
sudo python3.6 setup.py install
If it gives sql errors, remove the dependency in setup.py.
https://www.clips.uantwerpen.be/pages/pattern-en"""
import stanfordnlp
import traceback

#converts a constituency tree formatted as S-expression into a nested list structure.
def parseConstituency(s):
	s = s.replace("(. .)", "(PERIOD PERIOD)").replace("(? ?)", "(QUESTIONMARK QUESTIONMARK)").replace("(! !)", "(EXCLAMATION EXCLAMATION)")
	s = s.replace("(, ,)", "").replace("(, ;)", "")
	return parseExpression(s)

def getTagSequence(T):
	if isinstance(T, str):
		raise Exception("getTagSequence() called on a string:" + T)
	if len(T)<2:
		raise Exception("List found with no content or word:" + str(T))
	if len(T)==2:
		if isinstance(T[1], str):
			return [T[0]]
	toReturn = []
	for subtree in T[1:]:
		toReturn += getTagSequence(subtree)
	return toReturn

def getWordSequence(T):
	if isinstance(T, str):
		punctuation_names = ['PERIOD', 'QUESTIONMARK', 'EXCLAMATION']
		punctuations = ['.', '?', '!']
		if T in punctuation_names:
			return [punctuations[punctuation_names.index(T)]]
		else:
			return [T]
	if len(T)==0:
		raise Exception("Zero argument list found:" + str(T))
	toReturn = []
	for w in T[1:]:
		toReturn += getWordSequence(w)
	return toReturn

def treeToACEInput(T):
	s = ' '.join(getWordSequence(T)).strip()
# 	print("s1:", s)
	if s[1]==':':
		if s[2].islower():
			s = s[:2] + s[2].upper() + s[3:]
	else:
		s = s[0].upper() + s[1:]
	if s[-1] != '.':
		s = s + '.'
	if s[-2] == ' ':
		s = s[:-2] + s[-1]
	return s

"""
Searches through T and replaces subtrees where the rule applies. Returns [n, newT] where
n = number of times the rule was applied, newT = the new tree.
if recursive=False, then this only tries to apply the rule to the top node of the tree.
"""
def applyRule(T, rule, recursive=True, snlp=None):
	# print("T is", T, "R is", rule)
	[b, newT] = rule(T, snlp)
	if b:
		return [1, newT]
	else:
		if isinstance(T, list):
			total = 0
			TtoReturn = [T[0]]
			for child in T[1:]:
				[n, newT] = applyRule(child, rule, recursive, snlp)
				total += n
				TtoReturn.append(newT)
			return [total, TtoReturn]
		else:
			return [0, T]



"""If there is a NP consisting of a sequence of JJs followed by a NN or NNS, then attach 'a:' to each JJ and 'n:' to the noun. These are markers that APE uses to identify words that may not be in its vocabulary. If there are multiple JJs, then make them an adjective phrase using conjunctions:
(NP [(DT d)] (JJ adj1) (JJ adj2) ... (JJ adjn) (NN[S] n))
transforms into:
(NP [(DT d)] (ADJP (JJ adj1) (CC and) (JJ adj2) (CC and) ... (JJ adjn)) (NN[S] n))
"""
def R1(T, snlp=None):
	if isinstance(T, str):
		return [0,T]
	if T[0] != 'NP':
		return [0,T]
	#it's a NP
	hasDT = None
	T_original = T
	T = [x for x in T]
	if T[1][0] == 'DT':
		hasDT = T.pop(1)
	if (T[-1][0] == 'NN' or T[-1][0] == 'NNS'):
		T[-1][1] = 'n:' + T[-1][1]
	else:
		return [0,T_original]
	adjs = []
	allAdjs = True
	for i in range(1,len(T)-1):
		if T[i][0] != 'JJ':
			allAdjs = False
			break
		else:
			adjs.append(T[i])
	if len(adjs)==0:
		return [0,T_original]
	# print("For", T_original, "found adjectives:", adjs)
	if allAdjs:
		toReturn = ['NP']
		if hasDT != None:
			toReturn.append(hasDT)
		for [_,adj] in adjs[:-1]:
			toReturn += [['JJ', 'a:'+adj], ['CC', 'and']]
		toReturn.append(['JJ', 'a:' + adjs[-1][1]])
		toReturn.append(T[-1])
		return [1,toReturn]
	else:
		return [0,T_original]

"""This is the version of R2 that was used in the FLAIRS 2020 paper. It is very problematic, and has been replaced.

Replace `he/him' with `p:DMale' ('p:' identifies pronouns in APE) and `his' with `p:DMale's,' `she/her/hers' with `p:DFemale/p:DFemale's,' and `they/them/theirs' with `p:DGroup/p:DGroup's.' This is a weak form of coreference resolution; e.g., we essentially assume that whenever the premise and hypothesis use `he,' they are referring to the same person."""
def R2_OLD(T, snlp=None):
	if isinstance(T, str):
		toReplace = ['he', 'him', 'his', 'she', 'her', 'hers', 'they', 'them', 'their']
		replaceWith = ['p:dmale', 'p:dmale', "p:dmale's", 'p:dfemale', "p:dfemale's", "p:dfemale's", 'p:dgroup', 'p:dgroup', "p:dgroup's"]
		if T.lower() in toReplace:
			toReturn = replaceWith[toReplace.index(T.lower())]
			if T[0].isupper():
				toReturn = toReturn[0:2] + toReturn[2].upper() + toReturn[3:]
			return [1, toReturn]
	return [0, T]


from coref_resolution import * #comment this out if not using R2
"""New version of R2. This uses coreference resolution to find chains of coreferences, and then iteratively remove all pronominals.
You must make sure that the stanfordnlp server is running at http://localhost:9000.
DO NOT CALL THIS USING APPLYRULE()! This rule operates differently from the others: it must be called individually, and does NOT return a constituency parse tree like it is passed. 
Instead, it returns a dummy tree ['DUMMY_TREE', ['WORD', 'w1'], ['WORD', 'w2'], ...] simpy so that you can call treeToACEInput() with it.
Thus, it is best to call this rule last.

If this keeps outputting the "Starting Server with command..." line, go to (your virtualenv installation)/lib/python3.6/site-packages/stanfordnlp/server/client.py and comment out the print statement on line 118.
"""
def R2(T):
	#first, go through and attach an index to each root node tag (so the list ['DT', 'the'], not the string 'the')
	outputSentence = []
	toCheck = [T]
# 	print("INPUT:", T)
	while len(toCheck)>0:
# 		print(toCheck)
# 		input()
		curr = toCheck.pop(0)
		if isinstance(curr[1], str):
			outputSentence.append(curr[1])
		elif isinstance(curr,str):
			raise Exception("Unsure how to parse subtree:", curr)
		else:
			toCheck = curr[1:] + toCheck
	#next, contact the server to calculate coreference resolution
	flatSentence = treeToACEInput(T)
	sentenceHistory = []
	def updateHistory():
		st = ' '.join(outputSentence)
		if len(sentenceHistory)==0 or st != sentenceHistory[-1]:
			sentenceHistory.append(st)
	with CoreNLPClient(endpoint="http://localhost:9000") as client:
		crc = getCrc(flatSentence, client)
		chains = [parseCrc(str(chain)) for chain in crc]
		updateHistory()
	
	for (chainIndex, chain) in enumerate(chains):
		#find out what the name of this chain should be. Does it have any proper nouns?
		proper_links = [link for link in chain if link['mentionType']=='PROPER']
		propers = []
		for link in proper_links:
			if link['sentenceIndex']>0:
				raise Exception("There was more than one sentence here, don't know how to handle it:" + flatSentence)
			words = [outputSentence[i] for i in range(link['beginIndex'], link['endIndex'])]
			propers.append('_'.join(words))
		if len(propers)>0:
			chainName = 'p:' + propers[0]
			#replace all instances of proper nouns (even multi-word ones) with chainName
			for link in proper_links:
				outputSentence[link['beginIndex']] = chainName
				for i in range(link['beginIndex']+1, link['endIndex']):
					outputSentence[i] = None
		else:# len(propers)==0:
			chainName = 'p:DefaultName' + str(chainIndex)
		updateHistory()
		#now we know the chain's proper name, and there should be no other proper nouns.
		#TODO: next, find all pronominals, and replace them with name, name + ‘s if possessive. If pronominal has more than one word, exception. 
		pronominal_links = [link for link in chain if link['mentionType']=='PRONOMINAL']
		for link in pronominal_links:
			if link['sentenceIndex']>0:
				raise Exception("There was more than one sentence here, don't know how to handle it:" + flatSentence)
			if link['endIndex'] - link['beginIndex'] > 1:
				raise Exception("A pronominal with more than one word was found! Don't know what to do!")
			possessive = ['my', 'our', 'your', 'his', 'her', 'its', 'their', 'mine', 'ours', 'yours', 'hers', 'theirs']
			if outputSentence[link['beginIndex']].lower() in possessive:
				outputSentence[link['beginIndex']] = chainName + "'s"
			else:
				outputSentence[link['beginIndex']] = chainName
			updateHistory()
# * For each chain:
#     * Replace all multi-word NOMINALs with name, and add “[name] is [multi-word nominal]”. 
# * For each chain:
#     * Replace all LISTs with name, if the list was subject of a verb, make the verb singular. Add “[list] are in [name]”.
# For each word:
# * If a PRONOMINAL is found, assume it is alone and replace it with a unique name		
		
		if len(sentenceHistory)>1:
			print('\n\t'.join(["SENTENCE HISTORY"] + sentenceHistory))

#WHEN DONE:
#	return ['DUMMY_TREE'] + [['WORD', w] for w in outputSentence if w!=None]





nextIndex = 0
"""Replace past tense verbs (VBD/VBN) with present tense, using pattern.en. (https://www.clips.uantwerpen.be/pages/pattern)
This is NOT a recursive rule; if calling with applyRule(), use recursive=False.
"""
def R3(T, snlp=None):
	#first, convert to a sentence and get the dependency parse
	sentence = ' '.join(getWordSequence(T))
	dparse = snlp(sentence)
	#which are subjects?
	subjectOf = dict() #key: index of a verb, value: the subject of this verb
	for (v,t,o) in dparse.sentences[0].dependencies:
		if t=='nsubj':
			subjectOf[int(v.index)] = o.text
			# print("The verb", v.text, "at position", v.index, "has subject", o.text)
	#go through the tree and label all of the indices of the words
	global nextIndex
	nextIndex = 0
	def renameLeaves(T):
		if isinstance(T,str) or len(T) < 2:
			return [0,T]
		if isinstance(T[1], str):
			global nextIndex
			nextIndex += 1
			#is this one of the verbs with a subject?
			if nextIndex in subjectOf and (T[0] in ['VBD'] or T[1][-1]=='s'):
				#determine whether the subject is plural or not
				subj = subjectOf[nextIndex]
				isPlural = (subj.lower() in ['they', 'them', 'our', 'we'])
				if isPlural:
					return [1, ['VBP', conjugate(T[1], "3pl")]]
				else:
					return [1, ['VBZ', conjugate(T[1], "3sg")]]
			else:
				# print("index", nextIndex, "not in", subjectOf)
				return [0, T]
		else:
			toReturn = [T[0]]
			num = 0
			for c in T[1:]:
				[n, newC] = renameLeaves(c)
				num += n
				toReturn.append(newC)
			return [num, toReturn]
	return renameLeaves(T)

# def DtoT(D):
# 	#go through and remove all subject tags from verb words.
# 	if isinstance(D,str):
# 		return D
# 	if D[0][:2] == 'VB':
# 		if isinstance(D[1], str):
# 			return D
# 		else:
# 			return [D[0], D[1][0]]
# 	return [D[0]] + [DtoT(c) for c in D[1:]]

"""Any occurrences of numbers 1, ..., 10 are replaced with the words `one,' ..., `ten.' Ordinals `1st,' ..., `10th' are replaced with `first,' ..., `tenth.'"""
def R4(T, snlp=None):
	if isinstance(T,str) or len(T) < 2:
		return [0,T]
	if isinstance(T[1], str):
		replaceCardinal = {'0':'zero', '1':'one', '2':'two', '3':'three', '4':'four', '5':'five', '6':'six', '7':'seven', '8':'eight', '9':'nine',
			'10':'ten'}
		replaceOrdinal = {'0th':'zeroth', '1st':'first', '2nd':'second', '3rd':'third', '4th':'fourth', '5th':'fifth', '6th':'sixth', 
			'7th':'seventh', '8th':'eighth', '9th':'ninth', '10th':'tenth'}
		for k in list(replaceOrdinal.keys()):
			replaceOrdinal[k[0] + '-' + k[1:]] = replaceOrdinal[k]
		if T[1] in replaceCardinal:
			return [1, ['CD', replaceCardinal[T[1]]]]
		elif T[1] in replaceOrdinal:
			return [1, ['JJ', replaceOrdinal[T[1]]]]
		else:
			return [0, T]
	else:
		return [0, T]


"""Remove any predeterminers (PDT)."""
def R5(T, snlp=None):
	if isinstance(T,str) or len(T) < 2:
		return [0,T]
	if isinstance(T[1], str):
		return [0,T]
	toReturn = [T[0]]
	removedOne = False
	for c in T[1:]:
		if c[0]!='PDT':
			removedOne = True
			toReturn.append(c)
	if removedOne:
		return [1, toReturn]
	return [0,T]

"""If a VP has an ADVP preceding the verb, swap their order."""
def R6(T, snlp=None):
	if isinstance(T, str):
		return [0,T]
	if T[0]=='VP':
		if len(T)==3 and T[1][0] == 'ADVP' and T[2][0][:2]=='VB':
			#switch their order
			return [1, [T[0], T[2], T[1]]]
	return [0,T]

"""If an ADVP has multiple adverbs joined by 'but' or 'yet', replace it with 'and'."""
def R7(T, snlp=None):
	if isinstance(T,str):
		return [0,T]
	if T[0]=='ADVP':
		toReturn = [T[0]]
		prevWasAdv = False
		for c in T[1:]:
			if c[0] == 'RB':
				if prevWasAdv:
					prevWasAdv = False
					toReturn.append(['CC', 'and'])
				else:
					prevWasAdv = True
				toReturn.append(c)
			elif c[0] == 'CC':
				#regardless of what type of CC it is, add 'and'
				prevWasAdv = False
				toReturn.append(['CC', 'and'])
		return [1, toReturn]
	return [0,T]

"""Convert "is/are Ving [adv]" to "Vs/V [adv]". 
E.g.: "is walking gingerly" => "walks gingerly"
(VP (VBZ/VBP/VBD is/are/was/were) (VP (VBG walking) [...])) => (VP (VBZ/VBP walks/walk) [...])
"""
def R8(T, snlp=None):
# 	print("Calling on", T)
	if isinstance(T,str) or len(T)==0:
		return [0,T]
	if T[0]=='VP':
		if len(T) < 2:
			return [0,T]
		if T[1][1] in ['is','are','was','were'] and T[2][0] == 'VP' and T[2][1][0]=='VBG':
			#got a match!
			toReturn = ['VP']
			if T[1][1] in ['is','was']: #singular
				toReturn.append( [T[1][0], conjugate(T[2][1][1], '3sg')] )
			else: #plural
				toReturn.append( [T[1][0], conjugate(T[2][1][1], 'pl')] )
			for c in T[2][2:]:
				toReturn.append(c)
			return [1, toReturn]
	return [0,T]

#given a dictionary of hyperyms, returns all possible transformations
def replaceIn(T,hypernyms):
	if isinstance(T,str):
		prefix = ''
		if len(T)>1 and T[1]==':':
			tToCheck = T[2:]
			prefix = T[:2]
		else:
			tToCheck = T
		if tToCheck.lower() in hypernyms:
			toReturn = hypernyms[tToCheck.lower()]
			if tToCheck[0].isupper():
				return prefix + toReturn[0].upper() + toReturn[1:]
			else:
				return prefix + toReturn
		else:
			return T
	else:
		toReturn = [T[0]]
		for c in T[1:]:
			toReturn.append(replaceIn(c,toReturn))
		return toReturn

def getWordsByPOS(T, posTags):
	if isinstance(T,str):
		return []
	if T[0] in posTags: 
		return [T]
	else:
		toReturn = []
		for c in T:
			toReturn += getWordsByPOS(c, posTags)
		return toReturn

"""Input: the premise and hypothesis constituency trees, in the form of nested lists.
Returns: a dictionary which has singular nouns as keys, and a set of its hypernyms as values, only using nouns that appear in Tp or Th.
"""
def S1(Tp, Th):
	#find all nouns in Tp, and then in Th
	POS_tags = ['NN','NNS','NNP','NNPS']
	premiseNouns = getWordsByPOS(Tp, POS_tags) 
	hypNouns = getWordsByPOS(Th, POS_tags) 
# 	print(premiseNouns)
# 	print(hypNouns)
	#get all nouns in their singular forms
	toConvert = dict()
	allNouns = set()
	for PN in premiseNouns + hypNouns:
		if len(PN)!=2:
			print("ERROR: in S1(), an unexpected value in premiseNouns+hypNouns:", PN)
# 			print("Tp:", Tp)
# 			print("Th:", Th)
			continue
		[pos,n] = PN
		if n[:2]=='n:':
			n = n[2:]
		if pos in ['NNS', 'NNPS']:
			n = singularize(n)
		allNouns.add(n.lower())
	#find hypernym relationships between all nouns here
	hypernyms = {n:set() for n in allNouns}
	nonHypernyms = {n:set() for n in allNouns}
	for n1 in allNouns:
		for n2 in allNouns:
			if n1==n2:
				continue
			if findHypernym_onedir(n1,n2,'n'):
				hypernyms[n1].add(n2)
			else:
				if not findHypernym_onedir(n2, n1, 'n'):
					nonHypernyms[n1].add(n2)
					nonHypernyms[n2].add(n1)
	return [hypernyms, nonHypernyms]

def S2(Tp, Th):
	#find all nouns in Tp, and then in Th
	POS_tags = ['VB', 'VBZ', 'VBP'] #any other verb forms should have been filtered out already
	premiseVerbs = getWordsByPOS(Tp, POS_tags) 
	hypVerbs = getWordsByPOS(Th, POS_tags) 
	#get all verbs in their root (3rd person singular) forms
	toConvert = dict()
	allVerbs = set()
	for PN in premiseVerbs + hypVerbs:
		if len(PN)!=2:
			print("ERROR: in S2(), an unexpected value in premiseVerbs+hypVerbs:", PN)
			continue
		[pos,v] = PN
		if v[:2]=='v:':
			v = v[2:]
		v = conjugate(v, 'inf').lower()
		allVerbs.add(v)
	#find hypernym relationships between all verbs
	hypernyms = {v:set() for v in allVerbs}
	nonHypernyms = {v:set() for v in allVerbs}
	for v1 in allVerbs:
		for v2 in allVerbs:
			if v1==v2:
				continue
			if findHypernym_onedir(v1,v2,'v'):
				hypernyms[v1].add(v2)
			else:
				if not findHypernym_onedir(v2, v1, 'v'):
					nonHypernyms[v1].add(v2)
					nonHypernyms[v2].add(v1)
	return [hypernyms, nonHypernyms]

#S1_old and S2_old: no longer used
def S1_old(Tp, Th):
	#find all nouns in Tp, and then in Th
	POS_tags = ['NN','NNS','NNP','NNPS']
	premiseNouns = getWordsByPOS(Tp, POS_tags) 
	hypNouns = getWordsByPOS(Th, POS_tags) 
# 	print(premiseNouns)
# 	print(hypNouns)
	#for each pair, if one is a hypernym of the other, then replace all instances of it,
	#being careful to preserve plurality
	toConvert = dict()
	for [pos_p,pn] in premiseNouns:
		if pn[:2]=='n:':
			pn = pn[2:]
		if pos_p in ['NNS', 'NNPS']:
			pn = singularize(pn)
		for [pos_h,hn] in hypNouns:
			if hn[:2]=='n:':
				hn = hn[2:]
			if pos_h in ['NNS', 'NNPS']:
				hn = singularize(hn)
			pn = pn.lower()
			hn = hn.lower()
			if pn==hn:
				continue
			result = findHypernym_onedir(pn,hn,'n')
# 			print("Comparing:", pn, hn)
			if not result:
				continue
# 			print("Found hypernym:", pn, hn)
			#convert all instances of pn to hn, both singular and plural versions
			plural = [pluralize(pn), pluralize(hn)]
			singular = [pn, hn]
			for [w1,w2] in [plural,singular]:
				#convert all instances of w1 to w2
				if w2 in toConvert:
					toConvert[w1] = toConvert[w2]
				elif w1 in toConvert:
					w3 = toConvert[w1]
					#both w3 and w2 are hypernyms of w1. Which to use?
					#which is more abstract, w3 or w2?
					if findHypernym_onedir(w2,w3):
						toConvert[w2] = w3
						toConvert[w1] = w3
					elif findHypernym_onedir(w3,w2):
						toConvert[w3] = w2
						toConvert[w1] = w2
					else: #tiebreaker: which appears first?
						H = ' '.join(getWordSequence(Th)).lower()
						if w2 not in H and w3 not in H:
							#who cares, just use w2
							toConvert[w3] = w2
							toConvert[w1] = w2
						else:
							def getIndex(w):
								if w in H:
									return H.index(w)
								else:
									return 100000000000
							w2_i = getIndex(w2)
							w3_i = getIndex(w3)
							if w2_i > w3_i:
								toConvert[w2] = w3
								toConvert[w1] = w3
							elif w3_i < w2_i:
								toConvert[w2] = w3
								toConvert[w1] = w3
							else:
								raise Exception("w2 and w3 were equal! %s, %s, %s" % (w2,w3,H))
				else:
					toConvert[w1] = w2
# 	print("full dict:", toConvert)
	#go through Tp and Th, and convert all instances as toConvert commands
	return replaceIn(Tp,toConvert)

def S2_old(Tp, Th):
	#find all verbs in Tp, and then in Th
	POS_tags = ['VB', 'VBZ', 'VBP'] #any other verb forms should have been filtered out already
	premiseVerbs = getWordsByPOS(Tp, POS_tags) 
	hypVerbs = getWordsByPOS(Th, POS_tags)
	#for each pair, if one is a hypernym of the other, then replace all instances of it,
	#being careful to preserve verb form
	toConvert = dict()
	for [pos_p,pv] in premiseVerbs:
		if pv[:2]=='v:':
			pv = pv[2:]
		pv = conjugate(pv, 'inf').lower() #convert to infinitive form
		for [pos_h,hv] in hypVerbs:
			if hv[:2]=='v:':
				hv = hv[2:]
			hv = conjugate(hv, 'inf').lower()
			if pv==hv:
				continue
			result = findHypernym_onedir(pv,hv,'v')
			if not result:
				continue
			#convert all instances of pv to hv, preserving verb form
			vb_form = [pv, hv]
			vbz_form = [conjugate(pv,'3sg'), conjugate(hv,'3sg')]
			vbp_form = [conjugate(pv,'pl'), conjugate(hv,'pl')]
			for [w1,w2] in [vb_form, vbz_form, vbp_form]:
				#convert all instances of w1 to w2
				if w2 in toConvert:
					toConvert[w1] = toConvert[w2]
				elif w1 in toConvert:
					w3 = toConvert[w1]
					#both w3 and w2 are hypernyms of w1. Which to use?
					#which is more abstract, w3 or w2?
					if findHypernym_onedir(w2,w3):
						toConvert[w2] = w3
						toConvert[w1] = w3
					elif findHypernym_onedir(w3,w2):
						toConvert[w3] = w2
						toConvert[w1] = w2
					else: #tiebreaker: which appears first?
						H = ' '.join(getWordSequence(Th)).lower()
						if w2 not in H and w3 not in H:
							#who cares, just use w2
							toConvert[w3] = w2
							toConvert[w1] = w2
						else:
							def getIndex(w):
								if w in H:
									return H.index(w)
								else:
									return 100000000000
							w2_i = getIndex(w2)
							w3_i = getIndex(w3)
							if w2_i > w3_i:
								toConvert[w2] = w3
								toConvert[w1] = w3
							elif w3_i < w2_i:
								toConvert[w2] = w3
								toConvert[w1] = w3
							else:
								raise Exception("w2 and w3 were equal! %s, %s, %s" % (w2,w3,H))
				else:
					toConvert[w1] = w2
	#go through Tp and Th, and convert all instances as toConvert commands
	return replaceIn(Tp,toConvert)


if __name__=="__main__":
	SNLI_LOCATION = "snli/snli_1.0_dev.txt"
	with open(SNLI_LOCATION, 'r') as F:
		allLines = [l.strip().split('\t') for l in F.readlines()[1:]]
	for (i,line) in enumerate(allLines):
		if i%100==0:
			print(i, "of", len(allLines))
		for S in [line[3], line[4]]:
			#clean them up for punctuation and shit
			for punct in ['(. ,)', '(. .)', '(. !)']:
				S = S.replace(punct, '')
			S = S.replace('.', '')
			try:
				T = parseConstituency(S)
			except:
				continue
			R2(T)