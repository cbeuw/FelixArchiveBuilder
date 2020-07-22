import csv
import re
import os
import sys
from dateutil import parser
from operator import attrgetter
from typing import *
from datetime import date, datetime

LAST_C20_ISSUE = 1161
MAX_SEARCH_PAGE = 3

c20_year = re.compile(r"1\s*9\s*[4-9]\s*[0-9]")
c21_year = re.compile(r"2\s*0\s*[0-9]\s*[0-9]")


class Issue:
    __slots__ = ['issue_no', 'match', 'year', 'anomalous', 'date']

    def __init__(self, issue_no:int, match, year:int, anomalous:bool):
        self.issue_no = issue_no
        self.match = match
        self.year = year
        self.anomalous = anomalous
        self.date: date = None

    def parse_attempt(self,string,index_range) -> bool:
        default_date = datetime(1,1,1,0,0,0,0)
        for i in index_range:
            try:
                date = parser.parse(string[i:], default=default_date, dayfirst=True, yearfirst=False,
                                    ignoretz=True)
            except:
                continue
            else:
                if self.year != date.year:
                    continue
                elif date.day == default_date.day:
                    continue
                else:
                    self.date = date.date()
                    return True
        return False

    def parse_date(self, preceding=""):
        if self.match is None:
            self.anomalous = True
            return

        string = self.match.string[:self.match.end()] # ends with the last year digit as we assume year always comes last
        string = ''.join(preceding.split()) + string
        #TODO: instead of +1, give stricter limits?
        self.parse_attempt(string, range(0, self.match.start()+1))

        string_stripped = ''.join(string.split())
        self.parse_attempt(string_stripped, range(0, len(string_stripped)-3))

        # parser doesn't like it when it's like 6thNOVEMBER1965
        string_stripped_defed = re.sub(r"st|nd|rd|th|ST|ND|RD|TH|[^0-9a-zA-Z]+", " ", string_stripped)

        self.parse_attempt(string_stripped_defed, range(0, len(string_stripped_defed)-3))

        if self.date is None:
            print("Issue " + str(self.issue_no) + ": " + self.match.string)
            self.anomalous = True

class DateExtractor:
    issues_root = ""
    extracted: List[Issue] = []
    def __init__(self, issues_root:str):
        self.issues_root = issues_root
        # we give a baseline here so that subsequent year incremental sanity check can be made
        first = Issue(1, c20_year.search('1949'), 1949, False)
        first.date = date(1949,12,9)

        self.extracted=[first]

    def last_normal_issue(self) -> Issue:
        for i in range(len(self.extracted) - 1, -1, -1):
            if not self.extracted[i].anomalous:
                return self.extracted[i]

    def extract(self):
        issue_dirs = os.listdir(self.issues_root)
        issue_numbers = sorted(list(map(int, issue_dirs)))
        for issue in issue_numbers:
            if issue == 1:
                continue
            #if issue < 1611:
                #continue
            if not os.path.isdir(os.path.join(self.issues_root, str(issue))):
                continue

            if issue <= LAST_C20_ISSUE:
                extracted_issue = self.read_issue(str(issue), c20_year)
            else:
                extracted_issue = self.read_issue(str(issue), c21_year)
            # if you are using this in the 22nd century, please don't

            if extracted_issue.match is None:
                self.extracted.append(extracted_issue)
                continue

            # If the issue with greater number is issued before the year the previous
            # issue is published, mark it as anomalous
            baseline = self.last_normal_issue()
            assert extracted_issue.issue_no > baseline.issue_no
            if extracted_issue.year < baseline.year:
                extracted_issue.anomalous = True

            self.extracted.append(extracted_issue)

    def read_issue(self, issue_no: str, matcher) -> Issue:
        issue_dir = os.path.join(self.issues_root, issue_no)
        page_files = os.listdir(issue_dir)

        page_numbers = sorted([int(num.replace(".txt", "")) for num in page_files])
        i = 0

        ret: Issue = Issue(int(issue_no), None, None, True)
        while i < MAX_SEARCH_PAGE and i < len(page_numbers):
            page_path = os.path.join(issue_dir, str(page_numbers[i]) + ".txt")
            if not os.path.isfile(page_path):
                continue
            with open(page_path, 'r', encoding='utf-8') as p:
                content = p.read()

            # We assume dates are on the same line
            lines = content.splitlines()
            for line_no, line in enumerate(lines):
                matched = matcher.search(line)
                if matched is not None:
                    year_num = line[matched.start():matched.end()]
                    year_num = ''.join(year_num.split())
                    ret = Issue(int(issue_no), matched, int(year_num), False)
                    if line_no != 0:
                        ret.parse_date(lines[line_no-1])
                    else:
                        ret.parse_date()
                    if ret.date is None:
                        continue
                    return ret
            i += 1

        # year not found
        return ret

    def validate(self):
        self.extracted.sort(key=attrgetter('issue_no'))

    def write_to_csv(self, filename):
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['issue', 'date', 'matched_line']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            writer.writeheader()
            for issue in self.extracted:
                writer.writerow({'issue': issue.issue_no, 'date': str(issue.date),
                                 'matched_line': issue.match.string if issue.match is not None else ''})


if __name__ == "__main__":
    issues_root = sys.argv[1]
    extractor = DateExtractor(issues_root)
    extractor.extract()
    extractor.write_to_csv("extracted3.csv")
