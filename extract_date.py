"""
Andy Wang (cbeuw.andy@gmail.com)
2020

This script is used to extract issue dates from OCRed historical
Felix issue archives.

The dates for issues between 1 to 1737 (with gaps) can be found here:
https://gist.github.com/cbeuw/d421a4d1e4c4f421029ad5192ec71fc5
they were extracted using this script and manually validated.
But in case that's lost (hopefully not), you can reconstruct it using this script
"""
import csv
import re
import os
import sys
from dateutil import parser
from typing import *
from datetime import date, datetime

LAST_C20_ISSUE = 1161
MAX_SEARCH_PAGE = 3
STARTING_ISSUE = 1

# we assume all years are written with 4 digits, as is the case for vast majority of issues
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


    # returns true if no further attempts need to be made
    def parse_attempt(self, string, substr_max_left_index) -> bool:
        # Here, the last character of string should be the last digit in the year number
        # and we try to use dateutil.parser to parse substrings of string until we get a successful parse.
        # substrings are picked as string[0:], string[1:], string[2:] etc. until string[substr_max_left_index-1:]
        # where string[substr_max_left_index-1] is the first digit in the year number
        default_date = datetime(1,1,1,0,0,0,0)
        for i in range(0, substr_max_left_index):
            substring = string[i:]
            try:
                extracted_date = parser.parse(substring, default=default_date, dayfirst=True, yearfirst=False,
                                    ignoretz=True)
            except:
                continue
            else:
                if self.year != extracted_date.year:
                    continue
                # due to limitations of dateutil.parser, a partial date (e.g. "March 2019) is parsed as
                # 2019-03-(default_date.day). We can't tell if the date string was meant to be the 1st or it
                # has missing information. So we have to assume all dates whose day of month is 1st to be anomalous
                # and need to be double checked
                elif extracted_date.day == default_date.day:
                    # if the substring has the number 1 in, it's highly likely that the date string was well formed
                    # and the date is correctly parsed, so we accept that and return. We return false because
                    # we want to still make further attempts using string that has been sanitised differently
                    if re.match(r"1|01", substring.replace(str(self.year), "")):
                        self.date = extracted_date.date()
                        self.anomalous = True
                        return False
                    else:
                        continue
                else:
                    self.date = extracted_date.date()
                    return True
        return False

    def parse_date(self, preceding=""):
        # preceding represents the line before the line the year number is in
        # we need this information because in some of the issues, there is a linebreak between
        # the day of month and the rest of issue date (e.g. "3\nMarch2018")
        if self.match is None:
            self.anomalous = True
            return

        # we ignore anything on the line after the last digit of the year
        string = self.match.string[:self.match.end()]
        string = ''.join(preceding.split()) + string

        #TODO: instead of +1, give stricter limits?

        # first, we try the matched line as-is
        if self.parse_attempt(string, len(preceding)+self.match.start()+1):
            return

        # if failed, we strip all whitespace characters because it may be something like "1 M A R 1 9 6 9"
        string_stripped = ''.join(string.split())
        if self.parse_attempt(string_stripped, len(string_stripped)-3):
            return

        # parser doesn't like it when it's like 6thNOVEMBER1965
        string_stripped_defed = re.sub(r"st|nd|rd|th|ST|ND|RD|TH|[^0-9a-zA-Z]+", " ", string_stripped)
        if self.parse_attempt(string_stripped_defed, len(string_stripped_defed)-3):
            return

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

    def extract(self):
        issue_dirs = os.listdir(self.issues_root)
        issue_numbers = sorted(list(map(int, issue_dirs)))
        for issue_no in issue_numbers:
            if issue_no == 1:
                continue
            if issue_no < STARTING_ISSUE:
                continue
            if not os.path.isdir(os.path.join(self.issues_root, str(issue_no))):
                continue

            if issue_no <= LAST_C20_ISSUE:
                extracted_issue = self.read_issue(str(issue_no), c20_year)
            else:
                extracted_issue = self.read_issue(str(issue_no), c21_year)
            # if you are using this in the 22nd century, please don't

            self.extracted.append(extracted_issue)

            if extracted_issue.match is None:
                extracted_issue.anomalous = True
                continue

            if extracted_issue.anomalous:
                continue

            # Since match isn't None, extracted_issue.year isn't none, but date may be none
            # Validation
            last_normal = None
            # Find the last issue that isn't anomalous to do sanity checks on date
            for j in range(len(self.extracted)-2, -1, -1):
                if not self.extracted[j].anomalous:
                    last_normal = self.extracted[j]
                    break

            # since we are matching on years, all issues with a match should have a year
            # number extracted
            if extracted_issue.year < last_normal.year:
                extracted_issue.anomalous = True
                continue

            if (extracted_issue.date - last_normal.date).days < 0:
                extracted_issue.anomalous = True
            elif extracted_issue.date > datetime.now().date():
                extracted_issue.anomalous = True
            # Gaps in publication is mostly due to holidays. Here we allow 150 days between
            # two (semi-)consecutive issues
            elif extracted_issue.issue_no - last_normal.issue_no <= 2 and (extracted_issue.date - last_normal.date).days >= 5 * 30:
                extracted_issue.anomalous = True


    def read_issue(self, issue_no: str, matcher) -> Issue:
        issue_dir = os.path.join(self.issues_root, issue_no)
        page_files = os.listdir(issue_dir)

        page_numbers = sorted([int(num.replace(".txt", "")) for num in page_files])

        # i is the index in page_numbers, such that page_numbers[i].txt is the page we are currently dealing
        # i is NOT the actual page number, since some issues don't have text on the first page and hence
        # the text files start from 2.txt
        i = 0
        ret: Issue = Issue(int(issue_no), None, None, True)
        # We look for date from the first MAX_SEARCH_PAGE pages of any issue
        while i < MAX_SEARCH_PAGE and i < len(page_numbers):
            page_path = os.path.join(issue_dir, str(page_numbers[i]) + ".txt")
            if not os.path.isfile(page_path):
                continue
            with open(page_path, 'r', encoding='utf-8') as p:
                content = p.read()

            lines = content.splitlines()
            for line_no, line in enumerate(lines):
                # Read through each line and attempt to match on a 4-digit year number
                matched = matcher.search(line)
                if matched is not None:
                    year_num = line[matched.start():matched.end()]
                    year_num = ''.join(year_num.split())
                    ret = Issue(int(issue_no), matched, int(year_num), False)
                    # if the year number didn't appear on the first line, we give the previous line
                    # to parse_date in case the day of year is included on that line
                    if line_no != 0:
                        ret.parse_date(lines[line_no-1])
                    else:
                        ret.parse_date()
                    if ret.date is None:
                        # if the current line, despite having a year number, doesn't
                        # give us a proper date, we keep going down
                        continue
                    else:
                        # otherwise we return the extracted issue with all the information
                        return ret
            i += 1

        # year not found
        return ret

    def write_to_csv(self, filename):
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['issue', 'date', 'recheck', 'matched_line']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            writer.writeheader()
            for issue in self.extracted:
                writer.writerow({'issue': issue.issue_no, 'date': str(issue.date),
                                 'recheck': issue.anomalous,
                                 'matched_line': issue.match.string if issue.match is not None else ''})


if __name__ == "__main__":
    issues_root = sys.argv[1]
    extractor = DateExtractor(issues_root)
    extractor.extract()
    extractor.write_to_csv(sys.argv[2])
