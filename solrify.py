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
wordcost = dict((k, log((i + 1) * log(len(words)))) for i, k in enumerate(words))
maxword = max(len(x) for x in words)

# Matches hyphens at the ned of a line
end_hyphen = re.compile(r" *- *$")

# Possible OPENING quotation mark characters, includes unicode characters
opening_quotes = set("\"“'’")
extended_punctuation = string.punctuation + '“”’'
punctuation = set(extended_punctuation)
whitespace = set(string.whitespace)

# This may NOT be the last issue before digitisation, as issue 1252-1298 are missing from the archive
LAST_OCR = 1251


def infer_spaces(s):
    """Uses dynamic programming to infer the location of spaces in a string
    without spaces.

    Modified from https://stackoverflow.com/a/11642687
    """

    # Strip all punctuation, digits and whitespaces
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


def preserve(s, min_length=2):
    # test if a string should be preserved as-is
    # all strings that contains non-ascii characters are preserved as-is
    # all strings whose length is fewer than min_length is NOT preserved
    if s.isascii():
        if len(s) >= min_length:
            if s[0].isupper():
                # Preserve proper nouns
                return True
            else:
                # Preserve a word if it's in the dictionary
                return s.lower() in wordcost
        else:
            return False
    else:
        # preserve all special characters
        return True

# This function handles the situation where extra spaces are inserted in the middle of a word
# during the OCR process. This is especially problematic in earlier issues
# e.g. a sentence may be scanned as "The q u i c k b r o w n fox j u m p s o v e r t h e l a z y do g"
# sometimes punctuations are involved, too, like "I ' v e e a t e n" which is nasty
#
# The strategy here is to split the entire page's text into a list by whitespace characters (space, tab, linebreak etc),
# And then we go through each substring. As soon as we meet a substring that shouldn't be preserved using the previous
# function, is not a whitespace, punctuation or a digit, we enter the rebuilding process (if not already) and put that
# substring into to_reconstruct.
# we keep concatenating following parts into to_reconstruct, until we meed a preservable word or an opening quotation.
# at which point we use infer_spaces algorithm to segment to_reconstruct, put the word-segmented substring into
# return buffer, then start over again
def rebuild_words(content: str) -> str:
    # Splits on white space characters
    parts = list(filter(None, re.split('(\W)', content)))
    ret = []
    to_reconstruct = ""
    rebuilding = False
    for i, part in enumerate(parts):
        if preserve(part):
            if rebuilding:
                rec_result = " ".join(map(infer_spaces, to_reconstruct.split()))
                ret.append(rec_result + " ")
                to_reconstruct = ""
                rebuilding = False
            ret.append(part)
            continue
        elif part in whitespace:
            if rebuilding:
                continue
            else:
                ret.append(part)
        elif part in punctuation:
            if rebuilding:
                if part in opening_quotes:
                    # stop rebuilding when we get a quotation mark
                    if i < len(parts) - 1 and preserve(parts[i + 1]):
                        rec_result = " ".join(map(infer_spaces, to_reconstruct.split()))
                        ret.append(rec_result + " " + part)
                        to_reconstruct = ""
                        rebuilding = False
                    else:
                        to_reconstruct += part
                elif part != "-":
                    to_reconstruct += part
                continue
            else:
                ret.append(part)
        elif part.isdigit():
            if rebuilding:
                to_reconstruct += part
            else:
                ret.append(part)
        else:
            to_reconstruct += part
            rebuilding = True

    if rebuilding:
        rec_result = infer_spaces(to_reconstruct)
        ret.append(rec_result + " ")

    return ''.join(ret)


def strip_hyphens(content: str) -> str:
    lines = content.splitlines(keepends=True)
    i = 0
    while i < len(lines):
        match = end_hyphen.search(lines[i])
        if match and i < len(lines) - 1:
            rstripped = lines[i][:match.start()]
            next_line = lines[i + 1].lstrip()
            words = rstripped.split()
            next_line_words = next_line.split()
            if len(words) > 0 and len(next_line) > 0 and (preserve(words[-1] + next_line_words[0], 3)):
                lines[i] = rstripped
            else:
                lines[i] = lines[i].rstrip()
        i += 1

    return "".join(lines)


def sanitise(content: str, rebuild: bool) -> str:
    dehyphened = strip_hyphens(content)
    if rebuild:
        return rebuild_words(dehyphened)
    else:
        return dehyphened


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
            document["date"] = "0001-01-01T00:00:00Z"
        else:
            document["date"] = dates[issue_no]
        document["issue"] = int(issue_no)
        document["page"] = int(page_no)
        with open(page_path, 'r', encoding='utf-8') as p:
            document["content"] = sanitise(p.read(), True if int(issue_no) <= LAST_OCR else False)
        documents.append(document)
    return documents


min_issue = int(sys.argv[1]) if len(sys.argv) > 1 else 1
max_issue = int(sys.argv[2]) if len(sys.argv) > 2 else 9999  # good for a few centuries
issues_root = sys.argv[3] if len(sys.argv) > 3 else "text"
output_dir = sys.argv[4] if len(sys.argv) > 4 else "output"


def process_issue(issue):
    if not os.path.isdir(os.path.join(issues_root, issue)):
        return
    print(f"processing Issue {issue}")
    if dates[issue] == "":
        print("Warning: Issue {} has no date".format(issue))
    issue_content = read_issue(issues_root, issue)
    with open(os.path.join(output_dir, issue + ".json"), 'w', encoding='utf-8') as f:
        json.dump(issue_content, f, indent=2)


if __name__ == "__main__":
    if os.path.isfile("felix_dates.csv"):
        with open('felix_dates.csv', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['date'] != 'None':
                    parsed_date = parser.parse(row['date'], ignoretz=True, dayfirst=True)  # Unifying date format

                    # solr's DateRangeField is more appropriate here because we are storing a
                    # date, not a point in time. But we can only use DatePointField because
                    # DateRangeField doesn't support sorting
                    # To store it as a DatePointField, we need to add in the time
                    dates[row['issue_no']] = parsed_date.date().isoformat() + "T00:00:00Z"

    issues = os.listdir(issues_root)
    issues = filter(lambda i: min_issue <= int(i) <= max_issue, issues)
    if platform.system() == "Linux" or platform.system() == "Darwin":
        # Unix
        # Unix's fork() behaviour allows us to share memory for objects like date, wordcost and
        # end_hyphon with little overhead and no need to for extra python code
        Pool().map(process_issue, issues)
    else:
        # Windows
        # Unfortunately Window's memory model means that we can't easily multithread this
        print("Warning: this script does not have parallelism support on Windows. This will run very slowly."
              "Consider running this script on a Unix-like system, "
              "like Windows Subsystem for Linux, or on a Linux or Mac machine."
              "If that's not available, considering running this script on a Just-in-Time Python compiler,"
              "such as PyPy, for better performance")
        list(map(process_issue, issues))
