# NLIwithACE
A project for converting Natural Language Inference problems into Attempto Controlled English, and then solving them. Based on paper currently being considered by FLAIRS 2020.

## Installation

0. [Highly recommended] Install and set up a virtual environment (https://docs.python.org/3/library/venv.html). All instructions listed here should be run while that virtualenv is activated.
1. First, download our resolution-based prover and TPTP-to-S-expression convertor (https://github.com/AMHRLab/ResolutionProver). Probably easiest to just put them in the same directory as the python files in this repo.
2. Install pattern.io (https://www.clips.uantwerpen.be/pages/pattern-en). Note that it appears they still haven't updated it to work with Python 3+, so we have to do a bit of a hack:

```
git clone -b development https://github.com/clips/pattern
cd pattern
python3 setup.py install
```
If this last line gives sql errors, open setup.py and look for the sql dependency, and remove it. Then run it again.
Finally, rename the 'pattern' folder to something else like 'pattern_library', or it seems to confuse the python module importer. Test if it works by opening python and typing: `from pattern.en import conjugate`

3. Download and install SWI-Prolog: https://www.swi-prolog.org/
4. Download the Attempto parsing engine (https://github.com/Attempto/APE) and install it using the instructions on that page (clone repo, then use `make install`). Test by going into the directory where ape.exe is installed, and running the command `./ape.exe -text "John waits." -solo tptp`. Make note of this directory, and edit "ape.py" to point to it.
5. Download the Clex lexicon, clex_lexicon.pl from (https://github.com/Attempto/Clex). Put this file in the same directory as ape.exe.
6. Download the StanfordNLP library (https://stanfordnlp.github.io/stanfordnlp/). Don't forget to do the one-time download using `stanfordnlp.download('en')`, as per the directions on that page.
7. (Optional) If you are using the latest version of the syntactic rewrite rule R2 in rewriteRules.py, you also need to install the stanford corenlp server. Make sure you download it here (https://stanfordnlp.github.io/CoreNLP/index.html#download). The current zip file to download and uncompress is http://nlp.stanford.edu/software/stanford-corenlp-full-2018-10-05.zip but check the website for the most up-to-date version. In a separate window, point the environmental variable to where you unzipped those jar files:
`export CORENLP_HOME=~/stanfordnlp_resources/stanford-corenlp-full-2018-10-05` (your directory may differ)
Now cd to that folder where you have the jar files unzipped, and type this:
`java -mx4g -cp "*" edu.stanford.nlp.pipeline.StanfordCoreNLPServer -port 9000 -timeout 15000 -preload coref`
It will start up a CoreNLPServer that will listen on port 9000. R2() in rewriteRules.py will be communicating with this.

## Example Usage

If you want to replicate what we did for the paper, then download the SNLI dataset (https://nlp.stanford.edu/projects/snli/). Update the line in run_S3.py to point to it; we used the dev set because this approach doesn't use a training step. So log in to the server, activate your virtualenv environment, and then start up the CoreNLP server using the java command listed above. Then, on the window you're running the python script on, point Python to the stanford corenlp folder, using something like this:

`export CORENLP_HOME=~/stanfordnlp_resources/stanford-corenlp-full-2018-10-05`

Then, run using:

`python -W ignore run_S3.py 0`

The "-W ignore" flag gets rid of all of the annoying warning messages that CoreNLP prints out. The number at the end is because the code splits the data set into 500 parts, so that we could divide the workload amongst different servers. '0' tells it to run process 0, which processes over the first 20 sentence pairs (the dev set has 10,000 pairs). You can automate this, e.g. to start the first ten processes, I created a shell script containing:

```
for i in {0..9}; do
    python -W ignore run_S3.py $i &
done
```

This might give an error because 'attempts' folder does not exist. If that happens, create an empty folder 'attempts' in the directory same as 'run_S3.py'.

If this keeps outputting the "Starting Server with command..." line, go to (your virtualenv installation)/lib/python3.6/site-packages/stanfordnlp/server/client.py and comment out the print statement, usually around line 118, that says: 
`print(f"Starting server with command: {' '.join(self.start_cmd)}")`
