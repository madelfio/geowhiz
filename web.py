import geowhiz
from geowhiz.gaz.sqlite import sqliteGaz

gaz = sqliteGaz('./gaz.db', recreate_conn=True)

g = geowhiz.GeoWhiz(gaz=gaz)
application = g.web_app()

if __name__ == '__main__':
    application.debug = True
    application.run(host='0.0.0.0')
