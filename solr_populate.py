from typing import *
import json
import os
from multiprocessing import Pool
import sys


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
        document["date"] = "0001-01-01"
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
    p = Pool()
    p.map(process_issue, os.listdir(issues_root))

