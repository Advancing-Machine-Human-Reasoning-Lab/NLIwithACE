from nltk.corpus import wordnet as wn

def findHypernym_onedir(word1,word2,pos='n'):
	toCheck = [s for s in wn.synsets(word1) if s.pos()==pos]
	alreadyChecked = set()
	while len(toCheck)>0:
		s = toCheck.pop(0)
# 		print("Checking node:", s)
		if s in alreadyChecked:
			continue
		else:
			alreadyChecked.add(s)
# 		print("\tLemmas:", [l.name() for l in s.lemmas()])
		if word2 in [l.name() for l in s.lemmas()]:
			return True
		toCheck = toCheck + [h for h in s.hypernyms() if h.pos()==pos]
	return False
		
"""If one word is a parent class of another, then this returns a 
pair [wc,wp] where wp is the parent class of wc. Note that quantity
is essentially ignored.
"""
def findHypernym(w1,w2,pos='n'):

	if w1==w2:
		return [w2,w1]
	if findHypernym_onedir(w1,w2,pos):
		return [w1,w2]
	if findHypernym_onedir(w2,w1,pos):
		return [w2,w1]
	return None

# print(findHypernym('person', 'women'))
# print(findHypernym('jog', 'running'))