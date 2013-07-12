import psycopg2
import psycopg2.extras
import geowhiz

GET_GAZ_DATA = """
SELECT distinct * from (
    SELECT geonameid, name, name as official_name, altnames, latitude,
           longitude, fclass, fcode, country, cc2, admin1, admin2, admin3,
           admin4, elevation, population
      FROM gaz.geoname
     WHERE name in (%s)
    UNION
    SELECT geonameid, asciiname as name, name as official_name, altnames,
           latitude, longitude, fclass, fcode, country, cc2, admin1, admin2,
           admin3, admin4, elevation, population
      FROM gaz.geoname
     WHERE asciiname in (%s)
    UNION
    SELECT geoname.geonameid, altname as name, name as official_name,
           altnames, latitude, longitude, fclass, fcode, country, cc2, admin1,
           admin2, admin3, admin4, elevation, population
      FROM gaz.altname
      JOIN gaz.geoname ON (altname.geonameid = geoname.geonameid)
     WHERE altname.altname in (%s)
 ) u
 ORDER BY name
""".strip()

GET_CONTINENTS = """
SELECT iso2, name, continent from gaz.country;
""".strip()


class pgGaz(geowhiz.Gazetteer):
    def __init__(self, db_name, db_user, db_host):
        conn_str = 'dbname=%s user=%s host=%s' % (
            db_name, db_user, db_host
        )
        self.db_conn = psycopg2.connect(conn_str)
        self.continents = self._load_continents()

    def _load_continents(self):
        cur = self.db_conn.cursor()
        cur.execute(GET_CONTINENTS)
        return dict((r[0], r[2]) for r in cur.fetchall())

    def get_geoname_info(self, strings):
        cur = self.db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        param_sub = ', '.join('%s' for i in strings)
        #print strings
        get_gaz_data = GET_GAZ_DATA % (param_sub, param_sub, param_sub)
        cur.execute(get_gaz_data, strings * 3)

        res = list(dict(r) for r in cur.fetchall())
        for r in res:
            r['altnames'] = (r.get('altnames') or '').count(',')
            r['continent'] = self.continents.get(r['country'])

        return res
