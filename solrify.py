from typing import *
import json
import os
import sys
import csv
from collections import defaultdict
from dateutil import parser

dates = defaultdict(str)

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
            document["content"] = p.read()
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

if __name__ == "__main__":
    if os.path.isfile("felix_dates.csv"):
        with open('felix_dates.csv', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['date'] != 'None':
                    parsed_date = parser.parse(row['date'],ignoretz=True) # Unifying date format

                    # solr's DateRangeField is more appropriate here because we are storing a
                    # date, not a point in time. But we can only use DatePointField because
                    # DateRangeField doesn't support sorting
                    # To store it as a DatePointField, we need to add in the time
                    dates[row['issue_no']] = parsed_date.date().isoformat()+"T00:00:00Z"

    list(map(process_issue, os.listdir(issues_root)))

