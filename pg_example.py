import geowhiz
from geowhiz.gaz.pg import pgGaz

gaz = pgGaz('datname', 'user', 'hostname')

g = geowhiz.GeoWhiz(gaz=gaz)

grid = ['Washington', 'New York']

results = g.geotag(grid)
print results.categories
print results.cell_interpretations

results = g.geotag_full(grid)
print results.assignments[1].categories
print results.assignments[1].cell_interpretations
