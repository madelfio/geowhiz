import geowhiz
from geowhiz.gaz.sqlite import sqliteGaz

gaz = sqliteGaz('./gaz.db', recreate_conn=True)

g = geowhiz.GeoWhiz(gaz=gaz)

g.run_web()
