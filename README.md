# NLIwithACE
A project for converting Natural Language Inference problems into Attempto Controlled English, and then solving them. Based on paper currently being considered by FLAIRS 2019.

## Installation

1. First, download our resolution-based prover and TPTP-to-S-expression convertor (https://github.com/AMHRLab/ResolutionProver). Probably easiest to just put them in the same directory as the python files in this repo.
2. Install pattern.io (https://www.clips.uantwerpen.be/pages/pattern-en). Note that it appears they still haven't updated it to work with Python 3+, so we have to do a bit of a hack:

```
git clone -b development https://github.com/clips/pattern
cd pattern
sudo python3.6 setup.py install
```
Might be a good idea to rename the 'pattern' folder to something else like 'pattern_library', or it seems to confuse the python module importer.

If this last line gives sql errors, open setup.py and look for the sql dependency, and remove it. Then run the above line again.

3. Install SWI-Prolog: https://www.swi-prolog.org/
4. Download the Attempto parsing engine (https://github.com/Attempto/APE) and install it using the instructions on that page. Make note of the directory into which you download this engine, and edit "ape.py" to point to it.
5. Download the Clex lexicon, clex_lexicon.pl (https://github.com/Attempto/Clex). Put this file in the same directory as ape.exe.
6. Download the StanfordNLP library (https://stanfordnlp.github.io/stanfordnlp/). Don't forget to do the one-time download using `stanfordnlp.download('en')`, as per the directions on that page.

## Example Usage

If you want to replicate what we did for the paper, then download the SNLI dataset (https://nlp.stanford.edu/projects/snli/). Update the line in run_S3.py to point to it; we used the dev set because this approach doesn't use a training step. Then, run using:

`python -W ignore run_S3.py 0`

The "-W ignore" flag gets rid of all of the annoying warning messages that CoreNLP prints out. The number at the end is because the code splits the data set into 500 parts, so that we could divide the workload amongst different servers. '0' tells it to run process 0, which processes over the first 20 sentence pairs (the dev set has 10,000 pairs). You can automate this, e.g. to start the first ten processes, I created a shell script containing:

```
for i in {0..9}; do
    python -W ignore run_S3.py $i &
done
```
