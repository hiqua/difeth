# difeth

## Setup
`pyvenv env`
`. env/bin/activate`
`pip install -r requirements.txt`

## Crawling
`python3 crawl.py`

This will crawl ethscan to find verified contracts and, for each of them, the
associated similar contracts.

The diffs are then computed and stored in the folder diffs.

The subdirectory indicates the reference contract which also has its code within
this folder.

The name of the diff is the contract which resulted in the diff when compared to
the reference contract.



## Diff analysis
`python3 analyze_diffs.py`

This interactive program outputs the diffs and allows to quickly interactively
select the interesting ones, by writing their path in the file
"interesting_diffs.txt".
