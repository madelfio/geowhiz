import os
import sqlite3
import sys

DATAFILE_DIR = sys.argv[1]
TARGET_DB_FILE = './gaz.db'

conn = sqlite3.connect(TARGET_DB_FILE)

default_rowdata_func = lambda x: ([(v).decode('utf8') for v in l.strip().split('\t')]
                                  for l in x)

def table(filename, tablename, tablecols, rowdata_func=default_rowdata_func,
          indexes=[]):
    print 'creating table'
    print 'filename: ', filename
    print 'tablename: ', tablename
    print 'tablecols: ', tablecols
    if not filename: return
    wildcards = ','.join('?' for i in range(tablecols.count(',') + 1))
    drop_table_sql = 'drop table if exists %s' % (tablename,)
    create_table_sql = 'create table %s %s' % (tablename, tablecols)
    insert_sql = 'insert into %s values (%s)' % (tablename, wildcards)
    cur = conn.cursor()
    cur.execute(drop_table_sql)
    cur.execute(create_table_sql)
    print 'insert_sql: ', insert_sql
    with open(os.path.join(DATAFILE_DIR, filename)) as f:
        rowdata = rowdata_func(f)
        cur.executemany(insert_sql, rowdata)

        print 'done inserting into %s' % (tablename,)

        for n, c in indexes:
            cur.execute('create index %s on %s (%s)' % (n, tablename, c))

        print 'done creating indexes on %s' % (tablename,)

        conn.commit()

table(
    'allCountries.txt',
    'geoname',
    '(geonameid integer, name text, asciiname text, altnames text, latitude ' +
    'real, longitude real, fclass text, fcode text, country text, cc2 text, ' +
    'admin1 text, admin2 text, admin3 text, admin4 text, population integer, ' +
    'elevation integer, gtopo30 integer, timezone text, mod_date date)',
    indexes=[('geoname_pkey', 'geonameid'),
      ('geoname_name_idx', 'name'),
      ('geoname_asciiname_idx', 'asciiname'),
      ('geoname_adm_lookup', 'fcode, country, admin1, admin2, admin3, admin4')
    ]
)

table(
    'alternateNames.txt',
    'altname',
    '(altnameid integer, geonameid integer, isolanguage text, altname text, ' +
    'ispreferred text, isshort text, iscolloquial text, ishistoric text)',
    lambda x: ([(v).decode('utf8') for v in l.strip('\n').split('\t')] for l in x),
    indexes=[('altname_pkey', 'altnameid'), ('altname_name_idx', 'altname')]
)


table(
    'admin1CodesASCII.txt',
    'admin1',
    '(country text, admin1 text, name text, asciiname text, geonameid integer)',
    lambda x: ([(v).decode('utf8') for v in l.replace('.', '\t', 1).strip('\n').split('\t')] for l in x),
    indexes=[('admin1_lookup', 'country, admin1')]
)

table(
    'admin2Codes.txt',
    'admin2',
    '(country text, admin1 text, admin2 text, name text, asciiname text,' +
    'geonameid integer)',
    lambda x: ([(v).decode('utf8')
                for v in l.replace('.', '\t', 2).strip('\n').split('\t')] for l in x),
    indexes=[('admin2_lookup', 'country, admin1, admin2')]
)

def fill_rowdata(x):
    for l in x:
        vals = [(v).decode('utf8') for v in l.replace('.', '\t', 1).strip('\n').split('\t')]
        if len(vals) == 4:
            yield vals
        else:
            yield vals + [u''] * (4 - len(vals))


table(
    'featureCodes_en.txt',
    'featurecodes',
    '(fclass text, fcode text, name text, description text)',
    fill_rowdata
)

def process_country_rowdata(x):
    for l in x:
        if l.strip().startswith('#') or l.strip() == '':
            continue
        vals = [(v).decode('utf8') for v in l.strip('\n').split('\t')]
        if len(vals) != 19:
            print repr(l)
        yield vals

table(
    'countryInfo.txt',
    'country',
    '(iso2 text, iso3 text, isonum text, fips text, name text, capital text, ' +
    'areainsqkm real, population integer, continent text, tld text, currencycode ' +
    'text, currencyname text, phone text, postformat text, postregex text, ' +
    'languages text, geonameid integer, neighbors text, fipsequiv text)',
    process_country_rowdata,
    indexes=[('country_lookup', 'iso2')]
)

# TODO: no instr in sqlite 3.6 (on sametsrv01), so need workaround
add_counties = """
insert into altname
(geonameid, altname, isshort)
select
  geonameid,
  1,
  substr(name, 0, instr(name, ' County'))
from geoname
where
  instr(name, ' County') and
  fclass = 'A'
;
"""

conn.close()

