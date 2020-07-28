import platform
from typing import *
import json
import os
import sys
import csv
from collections import defaultdict
from dateutil import parser
from multiprocessing import Pool
from math import log
import re
import string

dates = defaultdict(str)
words = open("words-by-frequency.txt").read().split()
wordcost = dict((k, log((i+1)*log(len(words)))) for i,k in enumerate(words))
maxword = max(len(x) for x in words)
end_hyphen = re.compile(r" *- *$")
extended_punctuation = string.punctuation + '“”’'
punctuation = set(extended_punctuation)
whitespace = set(string.whitespace)

LAST_OCR = 1251

def infer_spaces(s):
    """Uses dynamic programming to infer the location of spaces in a string
    without spaces."""

    def normalise(x):
        return x.translate(str.maketrans('', '', extended_punctuation + string.digits + " ")).lower()
    # Find the best match for the i first characters, assuming cost has
    # been built for the i-1 first characters.
    # Returns a pair (match_cost, match_length).
    def best_match(i):
        candidates = enumerate(reversed(cost[max(0, i - maxword):i]))
        return min((c + wordcost.get(normalise(s[i - k - 1:i]), 9e999), k + 1) for k, c in candidates)

    # Build the cost array.
    cost = [0]
    for i in range(1, len(s) + 1):
        c, k = best_match(i)
        cost.append(c)

    # Backtrack to recover the minimal-cost string.
    out = []
    i = len(s)
    while i > 0:
        c, k = best_match(i)
        assert c == cost[i]
        out.append(s[i - k:i])
        i -= k

    return " ".join(reversed(out))

def rebuild_words(content:str)->str:
    def preserve(s):
        if len(s) > 1:
            if s[0].isupper():
                # Preserve proper nouns
                return True
            else:
                return s.lower()in wordcost
        else:
            return False

    parts = list(filter(None, re.split('(\W)', content)))
    ret = ""
    to_reconstruct = ""
    rebuilding = False
    for i, part in enumerate(parts):
        if preserve(part):
            if rebuilding:
                rec_result = " ".join(map(infer_spaces, to_reconstruct.split()))
                ret += rec_result + " "
                to_reconstruct = ""
                rebuilding = False
            ret += part
            continue
        elif part in whitespace:
            if rebuilding:
                #if (len(to_reconstruct) > 0 and to_reconstruct[-1] in punctuation) or (i < len(parts)-1 and parts[i+1] == '"' or parts[i+1] =="'"):
                    #to_reconstruct += part
                continue
            else:
                ret += part
        elif part in punctuation:
            if rebuilding:
                if part in set("\"“'’"):
                    # stop rebuilding when we get a quotation mark
                    if i < len(parts)-1 and preserve(parts[i+1]):
                        rec_result = " ".join(map(infer_spaces, to_reconstruct.split()))
                        ret += rec_result + " " + part
                        to_reconstruct = ""
                        rebuilding = False
                    else:
                        to_reconstruct += part
                elif part != "-":
                    to_reconstruct += part
                continue
            else:
                ret += part
        elif part.isdigit():
            if rebuilding:
                to_reconstruct += part
            else:
                ret += part
        else:
            to_reconstruct += part
            rebuilding = True

    if rebuilding:
        rec_result = infer_spaces(to_reconstruct)
        ret += rec_result + " "

    return ret

def sanitise(content:str, rebuild: bool) -> str:
    lines = content.splitlines(keepends=True)
    i = 0
    while i < len(lines):
        match = end_hyphen.search(lines[i])
        if match and i < len(lines)-1:
            rstripped = lines[i][:match.start()]
            next_line = lines[i+1].lstrip()
            words = rstripped.split()
            next_line_words = next_line.split()
            if len(words) > 0 and len(next_line) > 0 and ((words[-1] + next_line_words[0]).lower() in wordcost):
                lines[i] = rstripped
            else:
                lines[i] = lines[i].rstrip()
        i += 1

    joined = "".join(lines)

    if rebuild:
        return rebuild_words(joined)
    else:
        return joined

def read_issue(issues_root: str, issue_no: str) -> List[dict]:
    documents = []
    issue_dir = os.path.join(issues_root, issue_no)
    page_files = os.listdir(issue_dir)
    for page in page_files:
        page_path = os.path.join(issue_dir, page)
        if not os.path.isfile(page_path):
            continue
        document: dict = {}
        page_no: str = page.split(".txt")[0]
        document["id"] = issue_no + "p" + page_no
        if dates[issue_no] == "":
            print("Warning: Issue {} has no date".format(issue_no))
            document["date"] = "0001-01-01T00:00:00Z"
        else:
            document["date"] = dates[issue_no]
        document["issue"] = int(issue_no)
        document["page"] = int(page_no)
        with open(page_path, 'r', encoding='utf-8') as p:
            document["content"] = sanitise(p.read(), True if int(issue_no) <= LAST_OCR else False)
        documents.append(document)
    return documents

issues_root = sys.argv[1]
output_dir = sys.argv[2]
def process_issue(issue):
    if not os.path.isdir(os.path.join(issues_root, issue)):
        return
    issue_content = read_issue(issues_root, issue)
    with open(os.path.join(output_dir, issue + ".json"), 'w', encoding='utf-8') as f:
        json.dump(issue_content, f, indent=2)

test="""At the l a s t m e e t i n g of the S.C.C. the r e p r e s e n t -
a t i v e of the Chess Club proposed t h a t U n i o n C o u n c i l
he s t r o n g l y recommended t o p e r m i t the C a p t a i n of the
Chess Club t o award c o l o u r s t o d e s e r v i n g members of
h i s team. The motion, a f t e r c o n s i d e r a b l e d i s c u s s -
ion, was c a r r i e d nem.con."""

if __name__ == "__main__":
    if os.path.isfile("felix_dates.csv"):
        with open('felix_dates.csv', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['date'] != 'None':
                    parsed_date = parser.parse(row['date'], ignoretz=True, dayfirst=True) # Unifying date format

                    # solr's DateRangeField is more appropriate here because we are storing a
                    # date, not a point in time. But we can only use DatePointField because
                    # DateRangeField doesn't support sorting
                    # To store it as a DatePointField, we need to add in the time
                    dates[row['issue_no']] = parsed_date.date().isoformat()+"T00:00:00Z"

    """
    if platform.system() == "Linux" or platform.system() == "Darwin":
        # Unix
        # Unix's fork() behaviour allows us to share memory for objects like date, wordcost and
        # end_hyphon with little overhead and no need to for extra python code
        Pool().map(process_issue, os.listdir(issues_root))
    else:
        # Windows
        # Unfortunately Window's memory model means that we can't easily multithread this
        list(map(process_issue, os.listdir(issues_root)))
    """
    print(sanitise(test, True))