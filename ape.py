import requests
from translateFOF import treeToSexp, translateFOF_formula, removeDuplicateQuantifiedVars
from FOL_resolution import printSExpNice, propStructToSExp, findContradiction, parseExpression, applySubstitution
# from rewriteRules import *
import os
import sys
import re

#requires installation of APE: https://github.com/Attempto/APE
#and swi-prolog: https://www.swi-prolog.org/

APE_dir = "APE" #directory containing ape.exe and clex_lexicon.pl.

"""Call APE webservice to translate a sentence into TPTP format."""
def sentenceToTPTP_web(sentence):
	# THE URL FOR THE APE WEBSERVICE
	main_url = 'http://attempto.ifi.uzh.ch/ws/ape/apews.perl?text='
	# FOR MORE INFORMATION ON THE WEBSERVICE REFER TO http://attempto.ifi.uzh.ch/site/docs/ape_webservice.html
	addition_url = '&solo=tptp'
	result = []
	sentence = sentence.replace(' ', '+') + addition_url
	# print("full request:", main_url + sentence)
	r = requests.get(main_url+sentence)
	if r.text.find('error') == -1:
		return r.text#.replace('\n', '')
	else:
		return None

#Uses local version of APE to parse sentence into TPTP.
def sentenceToTPTP(sentence):
	# pwd = os.popen("pwd").read()
	# r = os.popen("cd ~ && ls").read()
	# print("R:", r)
	r = os.popen("cd " + APE_dir + " && ./ape.exe -text \"" + sentence + "\" -solo tptp -ulexfile \"clex_lexicon.pl\"").read().strip() #server
	# r = os.popen("cd APE && ./ape.exe -text \"" + sentence + "\" -solo tptp -ulexfile \"clex_lexicon.pl\"").read().strip() #home laptop
	# r = os.popen("cd /Users/licato/Downloads/APE-master && ./ape.exe -text \"" + sentence + "\" -solo tptp -ulexfile \"clex_lexicon.pl\"").read().strip() 
	# print("going back to ", pwd)
	# os.popen("cd \"" + pwd + "\"")
	if 'importance="error"' in r or r=="":
		return None
	else:
		#the APE code has a bug where whenever "Table" appears, it converts it to (table X) instead of table(X).
		return re.sub(r'\(table ([a-zA-Z0-9]+)\)', r'\(table\(\1\)\)', r)#.replace('\n', '')

"""Takes a sequence of tptp formulae (in string form), removes any formulae with single unnecessary equalities (see below), and returns a single S-expression string (all ANDed together).
Unnecessary equalities are formulae that are existentially quantified, where there is a single clause in the scope of the quantifier that has an equality with the
quantified variable which can be replaced. We only check for one form which is common in APE-to-TPTP:
	(EXISTS x (EXISTS y (AND (x='cat') (Hates x 'dog' y))))
		can be replaced with
	(EXISTS y (AND (Hates 'cat' 'dog' y)))
		and since this leaves an unnecessary AND, it becomes:
	(EXISTS y (Hates 'cat' 'dog' 'y'))
Can either return it in string or nested list form.
"""
def tptpsToSexp(tptp, returnList=False):
	tptps = [t.strip() for t in tptp.split('.\n') if t.strip()!='']
	for (i,t) in enumerate(tptps):
		t = t.strip()
		if t[-1]!='.':
			tptps[i] = t + '.'
		else:
			tptps[i] = t
	# print("tptps:", tptps) 
	Ts = [removeDuplicateQuantifiedVars(translateFOF_formula(t)) for t in tptps]
	newTs = []
	#remove unnecessary equalities
	#first, check if it starts with a string of 'EXISTS' followed by 'AND':
	for (i,T) in enumerate(Ts):
		vars = set()
		conjuncts = []
		currNode = T
		isForm = True #is T in the form we're looking for?
		while True:
			if isinstance(currNode, list):
				if currNode[0]=='EXISTS':
					vars.add(currNode[1])
					currNode = currNode[2]
					continue
				elif currNode[0]=='AND':
					#look for a child that has 'EQUALS' as its top-level predicate.
					foundEquals = False
					for j in range(1,len(currNode)):
						if isinstance(currNode[j], list) and currNode[j][0]=='EQUALS':
							foundEquals = True
							break
						# else:
						# 	print("Child was", currNode[0], j)
					if foundEquals:
						if (currNode[j][1] in vars and currNode[j][2][0]=="'" and currNode[j][2][-1]=="'") or \
							(currNode[j][2] in vars and currNode[j][1][0]=="'" and currNode[j][1][-1]=="'"):
							#this is the one!
							if currNode[j][1] in vars:
								varToRemove = currNode[j][1]
								objToReplaceWith = currNode[j][2]
							else:
								varToRemove = currNode[j][2]
								objToReplaceWith = currNode[j][1]
							sub = {varToRemove:objToReplaceWith}
							vars.remove(varToRemove)
							#replace all instances of varToRemove in the conjuncts with objToReplaceWith
							for k in range(1, len(currNode)):
								if k==j:
									continue
								conjuncts.append( applySubstitution(currNode[k], sub) )
							isForm = True
							break
						else:
							isForm = False
							#print("1")
							break
					else:
						isForm = False
						#print("2")
						break
				else:
					isForm = False
					#print("3")
					break
			else:
				isForm = False
				#print("4")
				break
		if isForm:
			if len(conjuncts) == 1:
				newT = conjuncts[0]
			else:
				newT = ['AND'] + conjuncts
			for v in vars:
				newT = ['EXISTS', v, newT]
			newTs.append(newT)
		else:
			newTs.append(T)
	if len(newTs)==0:
		raise Exception("There were no formulae detected in the tptp string! " + tptp)
	elif len(newTs)==1:
		if returnList:
			return newTs[0]
		else:
			return propStructToSExp(newTs[0])
	else:
		if returnList:
			return ['AND'] + newTs
		else:
			return "(AND " + ' '.join([propStructToSExp(t) for t in newTs]) + ")"


"""Determines if the natural language sentence s2 follows from s1.
Returns: 0 (neutral), 1 (entailment), 2 (contradiction), or
-2 - error or failure to parse on both hypothesis and at least one premise sentence
-1 - error or failure to parse on either hypothesis or at least one premise sentence
additionalFormulas = additional formulas to add into the resolution prover step. Must be s-expression strings.
if passingFormulas==True, then s1 and s2 are expected to be s-expression strings rather than NL sentences.
"""
def sentenceEntailment(s1, s2, passingFormulas=False, maxNumClauses=1500, additionalFormulas=[]):
	if not passingFormulas:
		# print("Converting sentences...\n\t", s1, '\n\t', s2)
		tptps = [sentenceToTPTP(s) for s in [s1,s2]]
		# print("TPTPS:\n\t", tptps[0], '\n\t', tptps[1])
		if None in tptps: #at least one of the parsed sentences was unable to parse
			if tptps[0]==None and tptps[1]==None:
				return -2
			else:
				return -1
		[parsedPremise, parsedHypothesis] = [tptpsToSexp(t) for t in tptps]
	else:
		parsedPremise = propStructToSExp(s1)
		parsedHypothesis = propStructToSExp(s2)
	# print("S-exps:\n\t", parsedPremise, '\n\t', parsedHypothesis)
	#test for entailment
	[result,trace,clauses] = findContradiction(additionalFormulas + [parsedPremise, "(NOT " + parsedHypothesis + ")"], maxNumClauses, verbose=False, returnTrace=True)
	entailment = result
	#test for contradiction
	[result,trace,clauses] = findContradiction(additionalFormulas + [parsedPremise, parsedHypothesis], maxNumClauses, verbose=False, returnTrace=True)
	contradiction = result
	if entailment:
		return 1
	elif contradiction:
		return 2
	else:
		return 0
"""
Compresses a formula to remove multiple nested existential quantifiers and binary ANDs. E.g.,
it replaces (EXISTS x (EXISTS y (AND a (AND b c)))) with (EXISTS (x y) (AND a b c)).
"""
def compressFormulaTree(T):
	#collapse all exists nodes starting at T
	def compressExistsTree(T):
		if isinstance(T,str) or T==None or T[0]!='EXISTS':
			return T
		if isinstance(T[1], str):
			varList = [T[1]]
		else:
			varList = T[1]
		if isinstance(T[2], str) or (isinstance(T[2],list) and T[2][0]!='EXISTS'): #cannot collapse more
			return T#, varList]
		#collapse
		Tchild = compressExistsTree(T[2])
		if isinstance(Tchild[1], str):
			moreVars = [Tchild[1]]
		else:
			moreVars = Tchild[1]
		# print("it returned", moreVars, ", combining with", varList)
		# print("\t", varList + moreVars)
		vars = varList + moreVars
		if len(vars)==1:
			return ['EXISTS', vars[0], Tchild[2]]
		else:
			return ['EXISTS', varList + moreVars, Tchild[2]]

	#collapse all AND nodes starting at T
	def compressAndTree(T):
		if isinstance(T, str) or T==None or T[0]!='AND':
			return T
		children = []
		for c in T[1:]:
			if isinstance(c,list) and c[0]=='AND':
				C = compressAndTree(c)
				children = children + C[1:]
			else:
				children.append(c)
		return ['AND'] + children

	Tnew = compressExistsTree(compressAndTree(T))
	if isinstance(Tnew,str) or Tnew==None:
		return Tnew
	if Tnew[0]=='EXISTS' or Tnew[0]=='FORALL':
		return [Tnew[0], Tnew[1], compressFormulaTree(Tnew[2])]
	else:
		return [Tnew[0]] + [compressFormulaTree(t) for t in Tnew[1:]]


if __name__=="__main__":
	T = parseExpression("(EXISTS w (EXISTS (y,z) (EXISTS x (AND a (AND b (EXISTS b (EXISTS c (AND a b (AND c d)))))))))")
	# T = parseExpression("(AND a g)")
	print("Original:", T)
	Tnew = compressFormulaTree(T)
	print(propStructToSExp(Tnew))
	exit()

	tptps = sentenceToTPTP("p:DefaultName0 and a girl play in p:DefaultName0's yard and she laughs . p:DefaultName0 is a boy .")
# 	print("tptps:", tptps)
	print(tptpsToSexp(tptps))