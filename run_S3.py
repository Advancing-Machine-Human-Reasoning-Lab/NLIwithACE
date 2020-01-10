"""This file contains the algorithm described in Marji, Nighojkar and Licato (2019). It 
uses a tiered approach.

See https://github.com/AMHRLab/NLIwithACE/edit/master/README.md for installation instructions.
"""

import stanfordnlp
from translateFOF import treeToSexp, translateFOF_formula, removeDuplicateQuantifiedVars
from FOL_resolution import printSExpNice, propStructToSExp, findContradiction, parseExpression
from ape import sentenceToTPTP, sentenceEntailment
from rewriteRules import *
import os
import sys
import re
import time

"""Point this to one of the text files that are part of the SNLI dataset. 
"""
# SNLI_LOCATION = "snli/snli/1.0_dev.txt"
SNLI_LOCATION = "snli/snli_1.0_dev.txt"
numDivisions = 10 #number of parts to divide the dataset into
experimentLabel = 'Output' #It will write output to a directory called 'attempts'.


if __name__=="__main__":
	with open(SNLI_LOCATION, 'r') as F:
		allLines = [l.strip().split('\t') for l in F.readlines()[1:]]
	processId = int(sys.argv[1])
	numPerProcess = int(len(allLines)/numDivisions)
	startAt = numPerProcess*processId
	allLines = [l for l in allLines[startAt:startAt+numPerProcess]]

	with open("garbage.txt",'w') as G: #silence the output that stanfordnlp spits out
		print("Loading stanfordnlp...")
		oldOut = sys.stdout
		sys.stdout = G
		snlp = stanfordnlp.Pipeline()
		sys.stdout = oldOut
		print("Done.")
	
#	#test case for S1
# 	p = """(ROOT (S (NP (DT A) (NN man)) (VP (VBZ hugs) (NP (DT a) (NN girl))) (. .)))"""
# 	h = """(ROOT (S (NP (DT A) (NN man)) (VP (VBZ hugs) (NP (DT a) (NN person))) (. .)))"""
# 	correct = "entailment"
	
	#test case for S2
	# p = """(ROOT (S (NP (NNP John)) (VP (VBZ runs)) (. .)))"""
	# h = """(ROOT (S (NP (NNP John)) (VP (VBZ moves)) (. .)))"""
	# h = """(ROOT
 #  (S
 #    (NP (NNP John))
 #    (VP (VBZ does) (RB not)
 #      (VP (VB move)))
 #    (. .)))"""
	# correct = "contradiction"
	
	# #test case for S3
	# p = """(ROOT (S (NP (DT A) (NN man)) (VP (VBZ hugs) (NP (DT a) (NN girl))) (. .)))"""
	# h = """(ROOT (S (NP (DT A) (NN man)) (VP (VBZ hugs) (NP (DT a) (NN cat))) (. .)))"""
	# h = """(ROOT
 #  (S
 #    (NP (DT A) (NN man))
 #    (VP (VBZ does) (RB not)
 #      (VP (VB hug)
 #        (NP (DT a) (NN girl))))
 #    (. .)))"""
	# correct = "contradiction"
	
	ruleCounts = {'S1':0, 'S2':0, 'S3':0}
	coverage=0 #number of sentences parsed successfully
	attempted = 0 #number of sentences tried to parse
	score_A2 = [0,0] #times it was correct vs wrong (out of successful parses)
	score_A3 = [0,0] #times it was correct vs wrong (out of successful parses)
	stoppedAtStage = [0,0,0,0,0]
	varsToStore = ['ruleCounts', 'coverage', 'attempted', 'experimentLabel', 'i', 'score_A2', 'score_A3', 'allTimes', 'processId', 'startAt', 'stoppedAtStage']
	
	lastTime = None
	allTimes = [0,0] #total, sum
	# for (i, [correct,p,h]) in enumerate([[correct,p,h]]):
	for (i, line) in enumerate(allLines):
		if line[0]=='-':
			continue #skip this problem
			
		currTime = time.time()
		if lastTime != None:
			allTimes[0] += (currTime - lastTime)
			allTimes[1] += 1
		lastTime = currTime
		
# 		print("ON LINE:", (i+startAt))
		
		try:
			#######FIRST, Try it without applying any rules
			correct = line[0]
			p = line[3] #constituency parse of premise
			h = line[4] #constituency parse of hypothesis
			p_raw = line[5] #raw text of premise
			h_raw = line[6] #raw text of hypothesis

			#clean them up for punctuation and shit
			for punct in ['(. ,)', '(. .)', '(. !)']:
				p = p.replace(punct, '')
				h = h.replace(punct, '')
			p = p.replace('.', '')
			h = h.replace('.', '')

			guess_values = ['neutral', 'entailment', 'contradiction']

			#status report
			if i%50==0:
				print("\n\nPROCESS", processId, "ON ITERATION", i, "of", len(allLines), ":")
				if allTimes[1]>0:
					print("\tAverage time per problem:", allTimes[0]/allTimes[1])
				for v in varsToStore:
					print('\t', v, ':', eval(v))
				with open("attempts/" + experimentLabel + '_' + str(processId) +  "_errors.txt", 'a') as F:
					F.write(str({v:eval(v) for v in varsToStore}) + '\n')

			# print("p is:", p)
			# print("p_raw is:", p_raw)
			# print("h is:", h)
			# print("h_raw is:", h_raw)
			# print("correct is:", correct)

			Tp = parseConstituency(p)
			Th = parseConstituency(h)

			def assessGuess(guess, correct, Tp, Th, p, h):
				# print("Correct:", correct, "My guess:", guess)
				# input("Press enter...")
				if correct==guess:
					with open("attempts/" + experimentLabel + '_' + str(processId) + "_correct.txt", 'a') as F:
						F.write('\t'.join([correct, treeToACEInput(Tp), treeToACEInput(Th), p, h]).strip() + '\n')
				else:
					with open("attempts/" + experimentLabel + '_' + str(processId) + "_incorrect.txt", 'a') as F:
						F.write('\t'.join([correct, guess, treeToACEInput(Tp), treeToACEInput(Th), p, h]).strip() + '\n')
			# print("ORIGINAL:")
			# print('\tP:'+' '.join(treeToACEInput(Tp)))
			# print('\tH:'+' '.join(treeToACEInput(Th)))
			attempted += 2
			#let's see if, before applying any rules whatsoever, it can parse and make a guess
			result = sentenceEntailment(treeToACEInput(Tp), treeToACEInput(Th))
			if result > 0: #if it guessed 'entailment' or 'contradiction'
				stoppedAtStage[0] += 1
				coverage += 2
				assessGuess(guess_values[result], correct, Tp, Th, p, h)
				continue

			##########NEXT, APPLY THE SYNTACTIC RULES
			
			"""Applies syntactic transformation rules to constituency tree T.
			"""
			def applySyntacticRules(T):
				sentenceHistory = []
				def updateHistory(currT, step):
					st = str(currT)
					if len(sentenceHistory)==0 or st != sentenceHistory[-1][0]:
						sentenceHistory.append([st, step])
				updateHistory(T, "start")
				#Apply rule R9, because it completes sentence fragments and must be done before R8
				try:
					[n, T] = applyRule(T, R9, False, snlp=snlp)
				except Exception as e:
					print("\n\nMessed up on rule R9, skipping...")
					print("I was trying to apply the rule to this tree:", T)
					print("Full details:", str({v:eval(v) for v in varsToStore}))
					print("Exception", e)
					traceback.print_exc(file=sys.stdout)
					# input("Press enter...")	 
				#Apply recursive rules			
				rules = [R1, R4, R5, R6, R7, R8] 
				for rule in rules:
					try:
						[n, T] = applyRule(T, rule, snlp=snlp)
						updateHistory(T, "after " + str(rule))
					except Exception as e:
						print("\n\nMessed up on rule", str(rule), ", skipping...")
						print("I was trying to apply the rule to this tree:", T)
						print("Full details:", str({v:eval(v) for v in varsToStore}))
						print("History:")
						for [s,step] in sentenceHistory:
							print("\t", step, ":", s)
						print("Exception", e)
						traceback.print_exc(file=sys.stdout)
						# input("Press enter...")
				#Apply nonrecursive rules
				rules = [R3, R2] #apply R2 last because it adds extra sentences  
				for rule in rules:
					try:
						[n, T] = applyRule(T, rule, False, snlp=snlp)
					except Exception as e:
						print("\n\nMessed up on rule", str(rule), ", skipping...")
						print("I was trying to apply the rule to this tree:", T)
						print("Full details:", str({v:eval(v) for v in varsToStore}))
						print("Exception", e)
						traceback.print_exc(file=sys.stdout)
						# input("Press enter...")
				return T
			Tp = applySyntacticRules(Tp)
			Th = applySyntacticRules(Th)

			# print("\nEntailment between:\n\t", Tp, "\n\t", Th)
			#use normal entailment. If it guesses ent. or con., then save to file and go to next pair
			result = sentenceEntailment(treeToACEInput(Tp), treeToACEInput(Th))
			# print("\tResult:", result)
			if result < 0: #there was an error parsing Tp or Th.
				# print("ERROR:\n\tTp:", Tp, "\n\tTh:", Th, "\n\tACE Tp:", treeToACEInput(Tp), "\n\tACE Th:", treeToACEInput(Th))
				# input()
				stoppedAtStage[1] += 1
				if result==-1: #at least one sentence parsed successfully
					coverage += 1
				with open("attempts/" + experimentLabel + '_' + str(processId) + "_parseFails.txt", 'a') as F:
					F.write('\t'.join([correct, treeToACEInput(Tp), treeToACEInput(Th), p, h]).strip() + '\n')
				continue #call it a loss, don't count it
			else: #both sentences parsed!
				coverage += 2
				if result > 0: #did it make a guess of non-neutral?
					stoppedAtStage[1] += 1
					assessGuess(guess_values[result], correct, Tp, Th, p, h)
					continue
			#else if result==0, keep going...

			##########FINALLY, TRY IT WITH THE SEMANTIC RULES
			# print("About to start S1")
			#####S1#########
			[hypernyms, nonHypernyms_n] = S1(Tp, Th)
			ruleUsed = False
			for k in hypernyms:
				if len(hypernyms)>0:
					ruleUsed = True
					break
			if ruleUsed:
				ruleCounts['S1'] += 1
			
			extraFormulas = []
			for w1 in hypernyms:
				for w2 in hypernyms[w1]:
					if w1==w2:
						continue
					extraFormulas.append('(FORALL x (IMPLIES (%s x) (%s x)))' % (w1, w2))
			#####S2#########
			[hypernyms, nonHypernyms_v] = S2(Tp, Th)
			ruleUsed = False
			for k in hypernyms:
				if len(hypernyms)>0:
					ruleUsed = True
					break
			if ruleUsed:
				ruleCounts['S2'] += 1
			
			for w1 in hypernyms:
				for w2 in hypernyms[w1]:
					if w1==w2:
						continue
					#TODO: A smarter version of which would know which verb arity to use based on the verbs, or the ACE parse. 
					extraFormulas.append('(FORALL a (FORALL b (IMPLIES (predicate1 a %s b) (predicate1 a %s b))))' % (w1, w2))
					extraFormulas.append('(FORALL a (FORALL b (FORALL c (IMPLIES (predicate2 a %s b c) (predicate2 a %s b c)))))' % (w1, w2))
					#extraFormulas.append('(FORALL a (FORALL b (FORALL c (FORALL d (IMPLIES (predicate3 a %s b c d) (predicate3 a %s b c d))))))' % (w1, w2))
			# print("Added formulas:", extraFormulas)
			
			# print("About to start SE")
			#use normal entailment. If it guesses ent. or con., then save to file and go to next pair
			result = sentenceEntailment(treeToACEInput(Tp), treeToACEInput(Th), additionalFormulas = extraFormulas)
			# print("RESULT (A3) WAS:", result)
			if result < 0:
				stoppedAtStage[2] += 1
				continue #call it a loss, don't count it
			elif result > 0:
				stoppedAtStage[2] += 1
				assessGuess(guess_values[result], correct, Tp, Th, p, h)
				continue


			#############NOW TRY IT BY ADDING THE NEGATIVE RULES
			for w1 in nonHypernyms_n:
				for w2 in nonHypernyms_n[w1]:
					if w1==w2:
						continue
					extraFormulas.append('(FORALL x (IFF (%s x) (NOT (%s x))))' % (w1, w2))
			for w1 in nonHypernyms_v:
				for w2 in nonHypernyms_v[w1]:
					if w1==w2:
						continue
					#TODO: A smarter version of which would know which verb arity to use based on the verbs, or the ACE parse. 
					extraFormulas.append('(FORALL a (FORALL b (IFF (predicate1 a %s b) (NOT (predicate1 a %s b)))))' % (w1, w2))
					extraFormulas.append('(FORALL a (FORALL b (FORALL c (IFF (predicate2 a %s b c) (NOT (predicate2 a %s b c))))))' % (w1, w2))
					#extraFormulas.append('(FORALL a (FORALL b (FORALL c (FORALL d (IFF (predicate3 a %s b c d) (NOT (predicate3 a %s b c d)))))))' % (w1, w2))
			result = sentenceEntailment(treeToACEInput(Tp), treeToACEInput(Th), additionalFormulas = extraFormulas)
			# print("RESULT (A3) WAS:", result)
			if result < 0:
				stoppedAtStage[3] += 1
				continue #call it a loss, don't count it
			elif result > 0:
				stoppedAtStage[3] += 1
				assessGuess(guess_values[result], correct, Tp, Th, p, h)
				continue
			
			#if we're here, it meant everybody failed to return an answer. So just guess neutral.
			assessGuess('neutral', correct, Tp, Th, p, h)
			stoppedAtStage[4] += 1
		except KeyboardInterrupt:
			exit()
		except Exception as e:
			print("MESSED UP ON:")
			print("\tPREMISE:", p)
			print("\tHYPOTHESIS:", h)
			for v in varsToStore:
				print(v, ':', eval(v))
			with open("attempts/" + experimentLabel + '_' + str(processId) + "_errors.txt", 'a') as F:
				F.write(str({v:eval(v) for v in varsToStore}) + '\n')
			print("Exception", e)
			traceback.print_exc(file=sys.stdout)
# 			input("Press enter to continue...")
			continue
	print("\nCOMPLETED SUCCESSFULLY!")
	for v in varsToStore:
		print(v, ':', eval(v))
	with open("attempts/" + experimentLabel + '_' + str(processId) + "_errors.txt", 'a') as F:
		F.write(str({v:eval(v) for v in varsToStore}) + '\n')