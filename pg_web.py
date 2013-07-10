import geowhiz
from geowhiz.gaz.pg import pgGaz

gaz = pgGaz('hybrid2', 'marco', 'sametdb00')

g = geowhiz.GeoWhiz(gaz=gaz)

g.run_web()
