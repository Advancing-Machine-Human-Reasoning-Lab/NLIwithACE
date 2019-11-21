import requests
from translateFOF import treeToSexp, translateFOF_formula, removeDuplicateQuantifiedVars
from FOL_resolution import printSExpNice, propStructToSExp, findContradiction, parseExpression
# from rewriteRules import *
import os
import sys
import re

#requires installation of APE: https://github.com/Attempto/APE
#and swi-prolog: https://www.swi-prolog.org/

APE_dir = "../APE" #directory containing ape.exe and clex_lexicon.pl.

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


"""Determines if the natural language sentence s2 follows from s1.
Returns: 0 (neutral), 1 (entailment), 2 (contradiction), or
-2 - error or failure to parse on both hypothesis and at least one premise sentence
-1 - error or failure to parse on either hypothesis or at least one premise sentence
additionalFormulas = additional formulas to add into the resolution prover step. Must be s-expression strings.
"""
def sentenceEntailment(s1, s2, maxNumClauses=1500, additionalFormulas=[]):
	# print("Converting sentences...\n\t", s1, '\n\t', s2)
	tptps = [sentenceToTPTP(s) for s in [s1,s2]]
	# print("TPTPS:\n\t", tptps[0], '\n\t', tptps[1])
	if None in tptps: #at least one of the parsed sentences was unable to parse
		if tptps[0]==None and tptps[1]==None:
			return -2
		else:
			return -1
	[parsedPremise, parsedHypothesis] = [propStructToSExp(removeDuplicateQuantifiedVars(translateFOF_formula(t))) for t in tptps]
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

if __name__=="__main__":
	pass