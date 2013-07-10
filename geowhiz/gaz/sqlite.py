import sqlite3
import geowhiz

GET_GAZ_DATA = """
SELECT distinct * from (
    SELECT geonameid, name, name as official_name, altnames, latitude,
           longitude, fclass, fcode, country, cc2, admin1, admin2, admin3,
           admin4, elevation, population
      FROM geoname
     WHERE name in (%s)
    UNION
    SELECT geonameid, asciiname as name, name as official_name, altnames,
           latitude, longitude, fclass, fcode, country, cc2, admin1, admin2,
           admin3, admin4, elevation, population
      FROM geoname
     WHERE asciiname in (%s)
    UNION
    SELECT geoname.geonameid, altname as name, name as official_name,
           altnames, latitude, longitude, fclass, fcode, country, cc2, admin1,
           admin2, admin3, admin4, elevation, population
      FROM altname
      JOIN geoname ON (altname.geonameid = geoname.geonameid)
     WHERE altname.altname in (%s)
 ) u
 ORDER BY name
"""

GET_CONTINENTS = """
SELECT iso2, name, continent from country;
"""

GET_TYPES = """
SELECT fclass, fcode, name, description from featurecodes;
""".strip()

GET_CONTAINER_COUNTRY_NAME = """
SELECT name FROM country WHERE iso2 in (?)
""".strip()

GET_CONTAINER_ADMIN1_NAME = """
SELECT name FROM admin1 WHERE country in (?) and admin1 in (?)
""".strip()

GET_CONTAINER_ADMIN2_NAME = """
SELECT name FROM admin2 WHERE country in (?) and admin1 in (?) and admin2 in (?)
""".strip()

class sqliteGaz(geowhiz.Gazetteer):
    def __init__(self, db_filename, recreate_conn=False):
        self.db_filename = db_filename
        self.db_conn = sqlite3.connect(db_filename)
        self.db_conn.row_factory = sqlite3.Row
        self.recreate_conn = recreate_conn
        self.continents = self._load_continents()

    def _get_conn(self):
        if self.recreate_conn:
            db_conn = sqlite3.connect(self.db_filename)
            db_conn.row_factory = sqlite3.Row
            return db_conn
        else:
            return self.db_conn

    def _load_continents(self):
        cur = self._get_conn().cursor()
        cur.execute(GET_CONTINENTS)
        return dict((r[0], r[2]) for r in cur.fetchall())

    def get_geoname_info(self, strings):
        cur = self._get_conn().cursor()
        param_sub = ', '.join('?' for i in strings)
        print strings
        get_gaz_data = GET_GAZ_DATA % (param_sub, param_sub, param_sub)
        cur.execute(get_gaz_data, strings * 3)

        res = list(dict(r) for r in cur.fetchall())
        for r in res:
            r['altnames'] = r['altnames'].count(',')
            r['continent'] = self.continents.get(r['country'])
        print len(res)
        return res

        return cur.fetchall()

    def get_types(self):
        cur = self._get_conn().cursor()
        cur.execute(GET_TYPES)
        return cur.fetchall()

    def get_container_country(self, params):
        cur = self._get_conn().cursor()
        cur.execute(GET_CONTAINER_COUNTRY_NAME, params)
        return cur.fetchone()

    def get_container_admin1(self, params):
        cur = self._get_conn().cursor()
        cur.execute(GET_CONTAINER_ADMIN1_NAME, params)
        return cur.fetchone()

    def get_container_admin2(self, params):
        cur = self._get_conn().cursor()
        cur.execute(GET_CONTAINER_ADMIN2_NAME, params)
        return cur.fetchone()

