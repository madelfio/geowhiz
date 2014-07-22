import os
import sqlite3
import sys

import update_gaz

DATAFILE = sys.argv[1]
TARGET_DB_FILE = './gaz.db'

conn = sqlite3.connect(TARGET_DB_FILE)

def strip_georanks(x):
    for l in x:
        v = l.strip().decode('utf8').split()
        yield (v[0], ' '.join(v[1:-3]).strip('"'), v[-3], v[-2], v[-1])

update_gaz.table(
    DATAFILE,
    'wikirank',
    '(geonameid integer, name text, wiki_article text, pagerank real, ord integer)',
    strip_georanks,
    indexes=[
        ('wikirank_pkey', 'geonameid'),
        ('wikirank_name', 'name'),
        ('wikirank_rank', 'pagerank'),
        ('wikirank_ord', 'ord')
    ]
)

conn.close()


