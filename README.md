# Felix Archive Builder
This repo contains scripts used to extract and clean up texts from Felix archive in pdf format, as well as the finished output

## extract_text.sh
```
Prerequisite: Have pdftotext from Xpdf command line tools installed
Usage: extract_text.sh [first issue inclusive] [last issue inclusive] [directory containing pdfs] [output directory]
```
This bash script extracts the OCRed text from Felix archive PDFs into text documents. 
Each issue has its own folder, in which there are text files representing pages in that issue. 
The text files are named with the page number in the issue PDF file, not the page number displayed in paper.

The output of this script is in `text` folder.

## extract_date.py
```
Prerequisite: Python 3.8 or above, dateutil package
Usage: python3 extract_date.py [directory containing output of extract_text.sh] [output csv file name]
```
This Python script attempts to extract the issue date from the text of each issue. **The result requires manual validation**.
A manually validated (although not error-free) mapping between issue number and issue dates is in `felix_dates.csv`

## solrify.py
```
Prerequisite: Python 3.8 or above, dateutil package, Unix-like OS preferred
Usage: python3 solrify.py [directory containing output of extract_text.sh] [output directory]
```
This Python script reads the OCRed archive content, performs a cleanup and output json files ready to be imported into solr. 
The cleanup involves mainly two things:
1. Rebuild hyphen-segmented words at the end of a line
2. Strip off extra spaces in words (a severe problem in earlier issues)

Running this script on a Unix-like OS (such as Linux or macOS) is preferred as it can utilise multiprocessing.
Running this on Windows will be extremely slow.

It outputs one json file per issue. It will try to find a file called `felix_dates.csv` to add date information into the
json files.

`output` folder contains the output of this script

## configsets/felix_archive
This is the solr schema. It has 5 fields: id, date, issue, page, content.
This should be copied to `[solr_root]/sever/solr/configsets` so that a new solr core
can be created with this schema using `bin/solr create -c [core name] -d felix_archive`
