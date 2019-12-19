import json
import traceback
import sys
from stanfordnlp.server import CoreNLPClient

#Parses a coreference chain (must be a string of a SINGLE coref chain.) If C was returned
#by stanfordnlp, you should pass str(C[i]) for i in range(len(C)).
def parseCrc(crc):
	toReturn = []
	thisMention = "{"
	for l in crc.split('\n'):
		if l.strip()=="mention {" or l.strip()=='':
			pass
		elif l.strip()=='}':
			thisMention += '}'
# 			print("processing:\n", thisMention) 
			toReturn.append(eval(thisMention))
			thisMention = "{"
		elif ':' in l:
			l = l.strip()
			thisMention += "'" + l[:l.index(':')] + "'" + l[l.index(':'):] + ', '
		else:
			print("Unrecognized (skipping):", l.strip())
	return toReturn

def getCrc(s, coreNlpClient):
	ann = coreNlpClient.annotate(s)
	return ann.corefChain

"""EXAMPLE:

with CoreNLPClient(endpoint="http://localhost:9000") as client:
	crc = getCrc("John loves his wife. She has flowers for him.", client)
	chains = [parseCrc(str(chain)) for chain in crc]
"""

if __name__=="__main__":
	SNLI_LOCATION = "snli/snli_1.0_dev.txt"
	with open(SNLI_LOCATION, 'r') as F:
		allLines = [l.strip().split('\t') for l in F.readlines()[1:]]
	
	with CoreNLPClient(endpoint="http://localhost:9000") as client:
		for (i,line) in enumerate(allLines):
			if i%100==0:
				print("On line", i, "of", len(allLines))		
			for S in [line[5],line[6]]:
				try:
					crc = getCrc(S, client)
					chains = [parseCrc(str(chain)) for chain in crc]
					if len(chains)==0:
						continue
					thisEntry = {'original_line':S, 'chains':chains}
					with open("all_crc_chains.txt", 'a') as F:
						F.write(json.dumps(thisEntry) + '\n')
				except:
					print("ERROR on line", i)
					traceback.print_exc(file=sys.stdout)
					exit()