# coding=utf-8
"""
The geotag module accepts grids of string values and returns a lat/long
coordinate for each row if the grid contains geographic references.

References can be in the form of:
- Latitude/Longitude values
- Place Names (Countries, Cities, States/Provinces, Mountains, Rivers, etc)
- Street Addresses

The implementation is divided into several components.

*BayesClassifier class* - the primary interface for geotagging grids.

*GridClassifier class* - abstract base class for performing geotagging
training, testing, and classification.  The BayesClassifier class inherits
from this.

*Categorizer class* - an object that returns possible categories for each
column.

*Resolver class* - an object that returns possible interpretations for each
cell, given a category.

*GeoNames class* - a lookup object for caching values returned from the
geonames database.

*Dimension class* - holds functions for classifying an instance along a
certain dimension and measuring the "depth" of a classification.

*Taxonomy class* - holds multiple dimensions.
"""

import sys
import psycopg2, psycopg2.extras
import math
import util
import itertools
import operator
import heapq
import csv

base_config = util.load_base_config()
config = util.load_config('geotag')
_v = util._v

GET_COLUMN_INFO = """
SELECT table_id, db_column_name, column_header
  FROM columns
 WHERE document_id = %s
 ORDER BY table_id, raw_column_number
"""

GET_ROW_DATA = """
SELECT table_id, raw_row_number, row_number, %s
  FROM bit_bucket
 WHERE table_id = %%s
   AND row_number <= %%s
 ORDER BY row_number
"""

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
"""

GET_CONTAINER_COUNTRY_NAME = """
SELECT name FROM gaz.country WHERE iso2 = %s
"""

GET_CONTAINER_ADMIN1_NAME = """
SELECT name FROM gaz.admin1 WHERE country = %s and admin1 = %s
"""

GET_CONTAINER_ADMIN2_NAME = """
SELECT name FROM gaz.admin2 WHERE country = %s and admin1 = %s and admin2 = %s
"""

ROOT = '_'
product = lambda x: reduce(operator.mul, x, 1)
db = util.db_conn()


def gaz_db_conn():
    connect_str = ('dbname=%s user=%s host=%s' % (
        config['gaz_database']['name'],
        config['gaz_database']['user'],
        config['gaz_database']['host']
    ))
    return psycopg2.connect(connect_str)


gaz_db = gaz_db_conn()


def process_doc(doc_id):
    cur = db.cursor()

    # Get column info for document
    cur.execute(GET_COLUMN_INFO, (doc_id,))

    col_names = {}
    col_headers = {}
    for table_id, db_column_name, column_header in cur.fetchall():
        if table_id not in col_names:
            col_names[table_id] = []
            col_headers[table_id] = []
        col_names[table_id].append(db_column_name)
        col_headers[table_id].append(column_header)

    # Sample strings from first rows of each table in document
    table_strings = {}
    for table_id in col_names:
        table_strings[table_id] = get_table_strings(table_id,
                                                    col_names[table_id], 10)

    # Get set of unique strings
    all_strings = [s
                   for table in table_strings
                   for col in table_strings[table]
                   for s in col]

    # Remove unlikely toponyms
    unique_strings = remove_unlikely_strings(set(all_strings))

    # Get geoname info for each unique string from table
    # Geoname info includes a feature class, feature code, country code, and
    # administrative codes (levels 1, 2, and 3)
    geoname_results = get_geoname_info(unique_strings)

    geotags = {}
    for table_id in table_strings:
        geotags[table_id] = Categorizer(table_strings[table_id],
                                        geoname_results)
        geotags[table_id].geotag()

    # For each column, find any

    _v('Retrieved text for document %d' % (doc_id,))


def get_table_strings(table_id, col_names, row_limit):
    cur = db.cursor()
    col_list = ', '.join(col_names)
    limited_string_query = GET_ROW_DATA % (col_list,)
    cur.execute(limited_string_query, (table_id, row_limit))

    cols = [list(v) for v in zip(*cur.fetchall())[3:]]
    return cols


def get_geoname_info(strings):
    cur = gaz_db.cursor(cursor_factory=psycopg2.extras.DictCursor)
    param_sub = ', '.join('%s' for i in strings)
    get_gaz_data = GET_GAZ_DATA % (param_sub, param_sub, param_sub)
    cur.execute(get_gaz_data, strings*3)
    return cur.fetchall()


def remove_unlikely_strings(strings):
    return [
        s for s in strings
        if len(unicode(s)) >= 2
        and s not in ['No', 'Pharmacy']
    ]


def add_comma_strings(strings):
    results = []
    for s in strings:
        if ',' in s:
            results.extend([pt.strip() for pt in s.split(',')])
        results.append(s)
    return results


def filter_column_results(results):
    seen = set()
    filtered_results = []

    for res in results:
        if tuple(res['category']) in seen:
            continue
        seen.update(itertools.product(*category_helpers.s_to_all_s(res['category'])))
        filtered_results.append(res)
    return filtered_results


class Categorizer(object):
    """Geotags a grid of strings.

    Creates a GeoNames lookup object if necessary, communicates with Hierarchy
    class for legal toponym categories, and creates candidate Path objects to
    identify the most likely categories
    """

    def __init__(self, grid=None, geonames=None):
        self.grid = grid
        self.geonames = geonames
        self._cache_prob = {}

    def get_top_categories(self):
        """Given grid of strings, finds possible categories for each column"""
        top_categories = [self._get_top_col_categories(column)
                          for column in self.grid]

        return top_categories

    def _get_top_col_categories(self, column):
        """Computes top candidate categories for a column of values.

        Return value is a list of tuples (category, covered_values_cnt, total)
        """
        # compute list of categories that are satisfied by some number of
        # cell values, along with the number of cells they cover

        # counts dict keeps track of number of interpretations that fall into
        # each category.
        # Example: if cat1 is satisfied by 4 interpretations of cell1, 0
        # interpretations of cell2, and 2 interpretations of cell3, then
        # counts[cat1] = [4, 2].
        # This would result in a coverage value of 2, total of 3, and
        # ambiguity of (4*1*2) ^ (1/3) = 2.0
        counts = {}
        for cell in column:

            cell_counts = {}

            # get list of interpretations for current toponym (cell value)
            interpretations = self.geonames.get_by_name(cell)

            for interpretation in interpretations:
                category_l = taxonomy.categorize(interpretation)
                category_ss = category_helpers.l_to_all_s(category_l)
                cell_cats = list(set(itertools.product(*category_ss)))

                for category_s in cell_cats:
                    if category_s not in cell_counts:
                        cell_counts[category_s] = 0
                    cell_counts[category_s] += 1

            # aggregate cell_counts values, for use in computing ambiguity and
            # coverage
            for cat, cnt in cell_counts.iteritems():
                if cat not in counts:
                    counts[cat] = []
                counts[cat].append(cnt)

        # Add ambiguity and coverage statistics
        results = []
        for cat, cnts in counts.iteritems():
            amb = 1.0 * product(cnts) ** (1.0 / len(cnts))
            results.append({
                'category': cat,
                'stats': {'ambiguity': amb,
                          'coverage': len(cnts),
                          'total': len(column)}
            })

        # Add ambiguity resolution method

        # default sort order for categories:
        # - first sort by coverage ratio
        # - next by the combined depth of the category over all dimensions
        # - then by ambiguity value descending
        cats_sort_key = lambda x: (x['stats']['coverage'],
                                   sum(depth(p) for p in x['category']),
                                   -x['stats']['ambiguity'])
        results = sorted(results, key=cats_sort_key, reverse=True)
        top_results = results[:300]

        return filter_column_results(top_results)


resolution_sort = lambda x: (x['population'], len(x['altnames'] or ''),
                             x['fcode'] == 'MT' and x['elevation'])


def geo_dist(pt1, pt2):
    radius = 6371  # km
    toRadians = lambda x: x * math.pi / 180
    lat1 = toRadians(pt1[0])
    lng1 = toRadians(pt1[1])
    lat2 = toRadians(pt2[0])
    lng2 = toRadians(pt2[1])
    dlat = lat2 - lat1
    dlng = lng2 - lng1

    a = (math.sin(dlat/2) ** 2 +
         math.sin(dlng/2) ** 2 * math.cos(lat1) * math.cos(lat2))
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return radius * c


def geo_centroid(lat_lng_list):
    xs = []
    ys = []
    zs = []
    for lat, lng in lat_lng_list:
        phi = (90 - lat) * math.pi / 180
        theta = (lng) * math.pi / 180
        x = math.sin(phi) * math.cos(theta)
        y = math.sin(phi) * math.sin(theta)
        z = math.cos(phi)
        #print '%2f, %2f, %2f' % (x, y, z)
        xs.append(x)
        ys.append(y)
        zs.append(z)
    x_c = sum(xs) / len(xs)
    y_c = sum(ys) / len(ys)
    z_c = sum(zs) / len(zs)
    #print 'geo_centroid: %2f, %2f, %2f' % (x_c, y_c, z_c)
    r = math.sqrt(x_c**2 + y_c**2 + z_c**2)
    #print 'r: ', r
    phi_c = math.acos(z_c / r)
    #print 'phi_c: ', phi_c
    theta_c = math.atan2(y_c, x_c)
    lat_c = 90 - 180 * (phi_c / math.pi)
    lng_c = 180 * theta_c / math.pi
    return (lat_c, lng_c)


def closest_interpretations(list_of_lat_lng_lists):
    """Given a list of lat/lng lists, return list of indexes into each of
    those lists that point to the set of points with the smallest sum of
    square distances to their centroid.  Also return the location of that
    centroid and the sum of square distances."""

    num_combs = product([len(l) for l in list_of_lat_lng_lists])
    print num_combs

    combs = itertools.product(*[range(len(l)) for l in list_of_lat_lng_lists])

    best_comb = None
    best_c = None
    best_dist = None
    for l in combs:
        pts = [list_of_lat_lng_lists[i][j] for i, j in enumerate(l)]
        #print l
        #print pts
        c = geo_centroid(pts)
        #print c
        dists = [geo_dist(c, p) ** 2 for p in pts]
        #print dists
        dist = math.sqrt(sum(dists) / len(dists))
        #print dist
        if best_dist is None or dist < best_dist:
            best_comb = l
            best_c = c
            best_dist = dist

    return (best_comb, best_c, best_dist)


#print closest_interpretations([[(20,30),(31,31), (40,40), (35,13), (38, 30)],
#                               [(21,31), (35, 35), (37, 34), (22, 25)],
#                               [(33, 33), (26, 32), (30, 34), (35, 39)],
#                               [(36, 32), (36, 50), (39, 39)],
#                               [(36, 36), (27, 29), (34, 34)],
#                               [(34, 37), (39, 90), (33, 33)]])
#exit()


class Resolver(object):
    def __init__(self, grid=None, geonames=None, assignment=None):
        self.grid = grid
        self.geonames = geonames
        self.assignment = assignment  # category for each column

    def get_interpretations(self, fetch_all=False):
        """
        Returns possible interpretations for each cell, based on column
        category
        """
        interpretations = [
            self._get_col_interpretations(column, cat, fetch_all=fetch_all)
            for column, cat in zip(self.grid, self.assignment)
        ]
        return interpretations

    def get_all_interpretations(self):
        return self.get_interpretations(fetch_all=True)

    def _get_col_interpretations(self, column, category, fetch_all=False):
        """
        Computes top candidate categories for a column of values.
        """

        interpretations = []

        for cell in column:
            cell_interpretations = []
            for g in self.geonames.get_by_name(cell):
                g_cat = self.geonames.get_category(g)
                #g_cat = category_helpers.l_to_s(taxonomy.categorize(g))
                if category_helpers.satisfies_s(g_cat, category['category']):
                    cell_interpretations.append(dict(g))

            cell_interpretations.sort(key=resolution_sort, reverse=True)
            if len(cell_interpretations) > 0:
                cell_interpretations[0]['likely'] = True

            if fetch_all:
                interpretations.extend(cell_interpretations)
            else:
                interpretations.append(cell_interpretations[0])

        return interpretations


class GeoNames(object):
    """A lookup class that is populated by querying the geonames database for
    specified strings"""
    def __init__(self, strings):
        self.strings = []
        self.geoname_lookup = {}
        self.geoname_id_lookup = {}
        self.add_strings(strings)
        self.type_lookup = {}
        self._category_cache = {}

    def add_strings(self, strings):
        unique_strings = remove_unlikely_strings(set(strings))
        unique_strings = set(add_comma_strings(unique_strings))
        geoname_results = get_geoname_info(list(unique_strings))

        for geoname in geoname_results:
            g_dict = dict(geoname)
            if g_dict['name'] not in self.geoname_lookup:
                self.geoname_lookup[g_dict['name']] = []
            self.geoname_lookup[g_dict['name']].append(g_dict)

            self.geoname_id_lookup[g_dict['geonameid']] = g_dict

        for s in unique_strings:
            if (',' not in s) or (s in self.geoname_lookup):
                continue

            qualified_lookup = self._qualified_name(s)

            self.geoname_lookup.update(qualified_lookup)

    def _qualified_name(self, s):
        containers = None
        parts = [pt.strip() for pt in s.split(',')]
        qualified_lookup = {}

        for i, pt in enumerate(reversed(parts)):
            last = (i == len(parts) - 1)
            admins = []
            for g in self.geoname_lookup.get(pt, []):
                if g['fclass'] == 'A' or last:
                    a = [g['country']]
                    a += [g['admin1'], g['admin2'], g['admin3'], g['admin4']]
                    if None in a: a = a[:a.index(None)]
                    if g['fcode'] and g['fcode'].startswith('PCL'): a = a[:1]

                    valid = False
                    if containers is None: valid = True
                    elif (a[:1] in containers or a[:2] in containers or
                          a[:3] in containers or a[:4] in containers):
                        valid = True
                    if valid and not last:
                        admins.append(a)
                    elif valid:
                        if s not in qualified_lookup:
                            qualified_lookup[s] = []
                        qualified_lookup[s].append(g)
            containers = admins
        return qualified_lookup

    def get_by_name(self, name):
        return self.geoname_lookup.get(name, [])

    def get_by_id(self, id_val):
        return self.geoname_id_lookup.get(id_val, None)

    def get_category(self, geoname):
        if 'geonameid' not in geoname:
            return None
        geonameid = geoname['geonameid']
        if geonameid in self._category_cache:
            return self._category_cache[geonameid]
        else:
            cat = category_helpers.l_to_s(taxonomy.categorize(geoname))
            self._category_cache[geonameid] = cat
            return cat


class Taxonomy(object):
    """Maintains multiple dimensions"""
    def __init__(self):
        self.dimensions = []

    def add_dimension(self, dimension):
        self.dimensions.append(dimension)
        self.categorizors = [d.classifier for d in self.dimensions]

    def get_dimension(self, idx):
        return self.dimensions[idx]

    def num_dimensions(self):
        return len(self.dimensions)

    def categorize(self, instance):
        # call functions directly for speed instead of calling d.categorize
        #return tuple(d.categorize(instance) for d in self.dimensions)
        return tuple(f(instance) for f in self.categorizors)

    def get_depths(self, category):
        return tuple(d.get_depth(c)
                     for d, c in zip(self.dimensions, category))


class Dimension(object):
    """A dimension for classifying toponyms"""
    def __init__(self, classifier=None, class_extractor=None):
        self.classifier = classifier or (lambda x: ROOT)
        self.class_extractor = class_extractor or (lambda x: depth(x))

    def categorize(self, instance):
        return self.classifier(instance)

    def get_depth(self, node):
        return self.class_extractor(node)


GEONAME_TYPES = {}
def lookup_type_code(type_code):
    """
    Return information about the fclass/fcode specified.
    """
    if type_code == ROOT:
        return {'type': 'place', 'plural': 'places'}

    if type_code == ROOT + '|A|ADM':
        return {'type': 'administrative region', 'plural': 'administrative regions'}

    if len(GEONAME_TYPES) == 0:
        with open(config['type_code_file']) as f:
            type_lookup_reader = csv.reader(f)
            for row in type_lookup_reader:
                code_str = '|'.join(n for n in [ROOT] + row[:3] if n)
                attrs = {'type': row[3], 'plural': row[4], 'desc': row[5]}
                GEONAME_TYPES[code_str] = attrs

    return GEONAME_TYPES.get(type_code)


import locale
locale.setlocale(locale.LC_ALL, 'en_US')


def prominence_text(prominence_s):
    if prominence_s == ROOT:
        return ''
    elif prominence_s[-1] == '1':
        return 'with population > 0'
    val = locale.format('%d', 10 ** (int(prominence_s[-1]) - 1), grouping=True)
    return 'with population ≥ %s' % (val,)


GEONAME_CONTAINERS = {'_|US': 'USA'}
STATIC = {'_|US': 'the United States'}
fmt = lambda x: 'in %s' % (STATIC.get(x, GEONAME_CONTAINERS.get(x, 'UNKNOWN')),)
def geo_text(geo_s):
    if geo_s == ROOT:
        return 'around the world'

    geo_l = geo_s.split('|')

    k = '|'.join(geo_l[:4])

    if k in GEONAME_CONTAINERS:
        return fmt(k)

    cur = gaz_db.cursor()

    last_vals = None
    for i, q in enumerate([GET_CONTAINER_COUNTRY_NAME,
                           GET_CONTAINER_ADMIN1_NAME,
                           GET_CONTAINER_ADMIN2_NAME]):
        if len(geo_l) < i + 2:
            break
        k = '|'.join(geo_l[:i+2])
        if k not in GEONAME_CONTAINERS:
            cur.execute(q, geo_l[1:i+2])
            res = cur.fetchone()
            if res and res[0] and last_vals:
                GEONAME_CONTAINERS[k] = res[0] + ', ' + last_vals
            elif last_vals:
                GEONAME_CONTAINERS[k] = last_vals
            elif res and res[0]:
                GEONAME_CONTAINERS[k] = res[0]
            else:
                GEONAME_CONTAINERS[k] = ''
        last_vals = GEONAME_CONTAINERS[k]

    return fmt(k)


class CategoryHelpers(object):
    """Helper functions for dealing with categories that may have different
    representations.
    """

    def s_to_l(self, strings):
        return [d.split('|') for d in strings]

    def l_to_s(self, lists):
        """
        (['A', 'B', 'C'], ['1', '2', '3']) => ['A|B|C', '1|2|3']
        """
        return ['|'.join((n for n in d if n is not None)) for d in lists]

    def l_to_all_s(self, lists):
        dimensions = []
        for d in lists:
            dimensions.append(['|'.join(str(n) for n in d[:i+1])
                               for i in range(len(d))
                               if d[i] is not None])
        return dimensions

    def s_to_all_s(self, strings):
        return self.l_to_all_s(self.s_to_l(strings))

    def satisfies_s(self, strings1, strings2):
        """
        Returns true iff s1 satisfies s2
        """
        # Add '|' to ensure that we don't erroneously think prefix categories
        # match (i.e., _|P|PPL|PPLA2 does not satisfy _|P|PPL|PPLA2)
        return all((s1 + '|').startswith(s2 + '|')
                   for (s1, s2) in zip(strings1, strings2))

    def cat_text(self, cat_s, cnt=2):
        # Handle type
        type_s = lookup_type_code(cat_s[0])

        if cnt == 1:
            type_txt = type_s['type']
        else:
            type_txt = type_s['plural']

        # Handle prominence
        prom_txt = prominence_text(cat_s[2])

        # Handle geo container
        geo_txt = geo_text(cat_s[1])

        return ' '.join(t for t in (type_txt, prom_txt, geo_txt) if t)


category_helpers = CategoryHelpers()


def get_type_dimension():
    fclass = lambda d: d['fclass']
    fcode1 = lambda d: (d.get('fcode') or '')[:3] or None
    fcode2 = lambda d: d['fcode'] if fcode1(d) != d['fcode'] else None

    def classifier(d):
        return [ROOT, fclass(d), fcode1(d), fcode2(d)]

    return Dimension(classifier)


def get_geo_dimension():
    country = lambda d: d['country']
    admin1 = lambda d: d['admin1'] if d['admin1'] != '00' or d['country'] else None
    admin2 = lambda d: d['admin2']
    admin3 = lambda d: d['admin3']
    admin4 = lambda d: d['admin4']

    def classifier(d):
        return [ROOT, country(d), admin1(d), admin2(d), admin3(d), admin4(d)]

    return Dimension(classifier)


def get_prominence_dimension():
    prominence_tree = [ROOT] + ['Prominent%d' % (i + 1,) for i in range(9)]

    def classifier(d):
        if (d.get('population', 0) or 0) == 0:
            prom = 0
        else:
            prom = int(math.log10(d['population'])) + 1
        return prominence_tree[:prom + 1]

    return Dimension(classifier)


def initialize_taxonomy():
    t = Taxonomy()
    t.add_dimension(get_type_dimension())
    t.add_dimension(get_geo_dimension())
    t.add_dimension(get_prominence_dimension())
    return t
taxonomy = initialize_taxonomy()


class GridClassifier(object):

    def __init__(self, verbose=False):
        self.verbose = verbose

    def train(self, training_set):
        """Given a list of (grid, categories) as the training set, find
        appropriate category ratings"""

        for grid, true_category in training_set:
            if self.verbose:
                print 'Classifying %r' % (grid,)
                print 'True category: %r' % (true_category,)

            # Get category candidates for each column
            all_strings = [s for col in grid for s in col]
            geonames = GeoNames(all_strings)
            grid_candidates = Categorizer(grid, geonames).get_top_categories()

            for cat_list, true_cat in zip(grid_candidates, true_category):
                self.train_column(cat_list, true_cat)

    def train_column(self, cat_list, true_cat):
        winner_idx = None

        # cats_match function expects x to have full category strings,
        # y has suffixes (i.e., the child node for each dimension)
        cats_match = lambda x, y: all(c.endswith(t) for c, t in zip(x, y))

        for i, res in enumerate(cat_list):
            if cats_match(res['category'], true_cat):
                winner_idx = i

        if winner_idx is not None:
            self.add_training_samples(winner_idx, cat_list)

    def add_training_samples(self, winner, candidates):
        raise NotImplementedError

    def full_geotag(self, grid):
        all_strings = [s for col in grid for s in col]
        geonames = GeoNames(all_strings)

        # Determine possible categories for each column
        grid_candidates = Categorizer(grid, geonames).get_top_categories()

        # Determine most likely categories for each column
        category_lists = []
        for column, candidates in zip(grid, grid_candidates):
            category_lists.append(self._classify_column(column, candidates))

        # Determine most likely category assignments for all columns in grid
        assignments = []
        for a_idxs, a_prob in self._get_likely_category_assignments(category_lists):
            a = ([c[i] for c, i in zip(category_lists, a_idxs)], a_prob)
            assignments.append(a)

        # Determine most likely interpretations for each toponym given assignment
        geotag_results = []
        for assignment, a_prob in assignments:
            resolver = Resolver(grid, geonames, assignment)
            interpretations = resolver.get_all_interpretations()
            c = [geo_centroid([(g['latitude'], g['longitude'])
                               for g in i if 'likely' in g])
                 for i in interpretations]
            geotag_results.append({'assignment': assignment,
                                   'likelihood': a_prob,
                                   'interpretations': interpretations,
                                   'centroid': c})

        return geotag_results

    def grid_geotag(self, grid):
        full_results = self.full_geotag(grid)
        return full_results[0]

    def column_geotag(self, column):
        grid_results = self.grid_geotag([column])
        return {'assignment': grid_results['assignment'][0],
                'likelihood': grid_results['likelihood'],
                'interpretations': [i
                                    for i in grid_results['interpretations'][0]
                                    if 'likely' in i and i['likely']],
                'centroid': grid_results['centroid']}

    def _classify_column(self, column, category_list):
        raise NotImplementedError

    def _get_likely_category_assignments(self, category_lists, top=20):
        raise NotImplementedError


class BayesClassifier(GridClassifier):
    def __init__(self, *args, **kwargs):
        self.model = []
        self.feature_funcs = []
        super(BayesClassifier, self).__init__(*args, **kwargs)

    def set_feature_funcs(self, *func_list):
        self.feature_funcs = func_list

    def add_training_samples(self, winner_idx, candidates):
        if self.verbose:
            print 'New Training Sample!'

        for i, res in enumerate(candidates):
            cat = res['category']
            stats = res['stats']

            # compute feature funcs for category
            func_vals = [f(cat, stats) for f in self.feature_funcs]

            instance = (i == winner_idx, stats['coverage'], stats['total'], func_vals)
            if i == winner_idx:
                if self.verbose:
                    print 'Found true category:'
                    print cat, stats
            self.model.append(instance)

        # clear model cache
        self._cache_prob = {}

    #def full_geotag(self, *args, **kwargs):
    #    return super(BayesClassifier, self).full_geotag(*args, **kwargs)

    def _classify_column(self, column, candidates):
        # input:
        #  - list of column values
        #  - list of candidate categories (with stats)
        # output:
        #  - list of category/stats/probabilities, sorted by probability desc

        results = []
        for res in candidates:
            cat = res['category']
            stats = res['stats']

            # compute feature funcs for category
            func_vals = [f(cat, stats) for f in self.feature_funcs]

            if self.verbose:
                print cat
                print stats
                print func_vals

            # compute independent feature probs
            feature_probs = []
            for i, v in enumerate(func_vals):
                p = self.feature_prob(i, v, stats['coverage'], stats['total'])
                if self.verbose:
                    print i, v
                    print p
                feature_probs.append(p)

            # combine feature probs to final prob
            final_prob = product(feature_probs)
            assert(0 <= final_prob <= 1)
            results.append({'category': cat,
                            'stats': stats,
                            'final_prob': final_prob})

        # normalize probs
        prob_sum = sum(r['final_prob'] for r in results)
        for r in results:
            r['normalized_prob'] = math.sqrt(r['final_prob'] / prob_sum)

        prob_sum = sum(r['normalized_prob'] for r in results)
        for r in results:
            r['normalized_prob'] = r['normalized_prob'] / prob_sum

        return sorted(results, key=lambda x: x['normalized_prob'], reverse=True)

    def feature_prob(self, f_idx, f_val, cov, tot):
        if (f_idx, f_val, cov, tot) in self._cache_prob:
            return self._cache_prob.get((f_idx, f_val, cov, tot))

        # seed with pseudocounts to correct for small sample size
        t1 = [1.0, 0.5]
        t2 = [True, True, False, False]
        t3 = [1.0, 0.5, 0.6, 0.1]

        for is_winner, sample_cov, sample_tot, func_vals in self.model:
            if is_winner and func_vals[f_idx] == f_val:
                t1.append(1.0 * sample_cov / sample_tot)

            if func_vals[f_idx] == f_val:
                t2.append(is_winner)

            if func_vals[f_idx] == f_val:
                t3.append(1.0 * sample_cov / sample_tot)

        # compute mean, variance of t1, t3
        t1_mean, t1_var = self._get_mean_var(t1)
        t3_mean, t3_var = self._get_mean_var(t3)

        # compute individual probabilities
        t1_term = self._get_prob_density(t1_mean, t1_var, float(cov) / tot)
        t2_term = float(t2.count(True)) / len(t2)
        t3_term = self._get_prob_density(t3_mean, t3_var, float(cov) / tot)

        res = t1_term * t2_term / t3_term
        self._cache_prob[(f_idx, f_val, cov, tot)] = res
        return res

    def _get_mean_var(self, vals):
        n = len(vals)
        sum1 = sum(vals)
        mean = float(sum1) / n

        sum2 = sum((x - mean) ** 2 for x in vals)
        variance = float(sum2) / (n - 1)

        return (mean, variance)

    def _get_prob_density(self, mean, variance, val):
        density = float(1) / (math.sqrt(math.pi * 2 * variance))
        exp = ((val - mean) ** 2) / (2 * variance)
        return density * math.exp(-exp)

    def _get_likely_category_assignments(self, category_lists, top=20):
        """
        Returns list of top assignments, by probability.

        For example, given [[0.9, 0.05, 0.04, 0.01], [0.6, 0.4]],
        The result should be:
            [([0, 0], 0.54(=0.9*0.6)), ([0, 1], 0.54)], ([1, 0], .03), ...]
        """
        # create priority queue seeded with most likely assignment (top
        # category for each column)
        pq = []

        def probs(indexes):
            return [p[idx]['normalized_prob']
                    for idx, p in zip(indexes, category_lists)
                    if len(p) > idx + 1]

        def assignment_prob(indexes):
            return product(probs(indexes))

        start_indexes = [0] * len(category_lists)

        heapq.heappush(pq, (-assignment_prob(start_indexes), start_indexes))

        results = []
        while len(results) < top and len(pq) > 0:
            cur_prob, cur_indexes = heapq.heappop(pq)

            results.append((cur_indexes, -cur_prob))
            for i in range(len(cur_indexes)):
                next_indexes = cur_indexes[:]
                # add next category at current column index if it exists
                next_indexes[i] += 1
                if next_indexes[i] < len(category_lists[i]):
                    heapq.heappush(pq, (-assignment_prob(next_indexes),
                                        next_indexes))

        return results

#
# Command-line options and dispatch
#


def usage():
    print ('Usage: %s {<doc_id1> [<doc_id2> ...] | <min_doc_id>-<max_doc_id>}' %
           (sys.argv[0].split('/')[-1],))
    exit()


depth = lambda x: x.count('|')
amb_log = lambda x: math.floor(math.log(x) / math.log(1.1))


def train_classifier(verbose=False):
    classifier = BayesClassifier(verbose=verbose)
    classifier.set_feature_funcs(
        lambda x, y: '_',  # dummy feature to test coverage probability
        lambda x, y: x[0],
        #lambda x, y: taxonomy.get_depths(x),
        lambda x, y: depth(x[2]),
        lambda x, y: depth(x[1]),
        lambda x, y: (depth(x[1]), depth(x[2])),
        lambda x, y: (depth(x[1]), amb_log(y['ambiguity'])),
        lambda x, y: y['ambiguity'] < 1.00001,
        lambda x, y: 1.00001 <= y['ambiguity'] < 1.3,
        lambda x, y: 1.3 <= y['ambiguity'] < 1.75,
        #lambda x, y: 1.75 <= y['ambiguity'] < 2.5,
        #lambda x, y: 2.5 <= y['ambiguity'],
        lambda x, y: (x[0].startswith(ROOT+'|P'), depth(x[2])),
    )
    classifier.train([
        ([['Australia', 'Brunei', 'Cambodia', 'China']],
         [('PCLI', ROOT, 'Prominent6')]),
        ([['Paris', 'Rome', 'Brussels', 'London', 'Venice']],
         [('PPL', ROOT, 'Prominent6')]),
        ([['Washington', 'Oregon', 'Idaho', 'Missouri']],
         [('ADM1', 'US', 'Prominent7')]),
        ([['Delaware', 'Powell', 'Sunbury']],
         [('PPL', 'OH|041', 'Prominent4')]),
        ([['Washington', 'New York', 'Boston']],
         [('PPL', 'US', 'Prominent6')]),
        ([['Orlando', 'Sanford', 'Leesburg']],
         [('PPL', 'US|FL', 'Prominent5')]),
        ([['Richmond', 'Roanoke']],
         [('PPL', 'US|VA', 'Prominent5')]),
        ([['Arlington', 'Vienna', 'Springfield', 'Alexandria', 'Richmond',
           'Stafford', 'Ashland']],
         [('PPL', 'US|VA', 'Prominent4')]),
        ([['Mount Everest', 'Grand Teton']],
         [('MT', '_', '_', 'Elevation3')]),
        ([['Washington, USA']],
         [('PPLC', 'DC|001', 'Prominent6')]),
        ([['New York, USA']],
         [('PPL', 'NY', 'Prominent7')]),
        ([['Los Angeles']],
         [('PPLA2', 'CA|037', 'Prominent7')]),
        ([['Arlington', 'Springfield', 'Vienna', 'Alexandria']],
         [('PPL', 'VA', 'Prominent5')]),
        ([['Athens', 'Rome', 'Dublin']],
         [('PPLA2', 'GA', 'Prominent5')]),
        ([['Athens', 'Rome', 'Dublin']],
         [('PPL', 'OH', 'Prominent5')]),
    ])
    return classifier


def test_classify():
    classifier = train_classifier(verbose=False)

    def test_column(column, cat):
        print 'Testing column: ', column
        res = classifier.column_geotag(column)
        cats_match = lambda x, y: all(c.endswith(t) for c, t in zip(x, y))
        if cats_match(res['assignment']['category'], cat):
            print 'classified correctly'
        else:
            print res['assignment']['category']
            print 'does not match'
            print cat
            assert cats_match(res['assignment']['category'], cat)

    test_column(
        ['Washington', 'Boston', 'San Francisco', 'Austin'],
        ['PPL', 'US', 'Prominent6']
    )
    test_column(
        ['Annapolis', 'Albany', 'Richmond'],
        ['PPLA', 'US', 'Prominent5']
    )
    test_column(
        ['Verizon Center', 'Madison Square Garden', 'Astrodome'],
        ['S', 'US', ROOT]
    )
    test_column(
        ['Rappahannock River', 'Occoquan River', 'James River', 'York River'],
        ['STM', 'US|VA', ROOT]
    )
    test_column(
        ['Rome', 'Paris', 'London', 'Berlin', 'Athens'],
        ['PPLC', ROOT, 'Prominent6']
    )
    test_column("""Aberdeen,Albert Lea,Appleton,Beaver Dam,Bellevue,Bend,Billings,Boise,Bountiful,Brigham City,Burlington,Coeur d'Alene,Council Bluffs,Dallas,DePere,Eau Claire,Escanaba,Eugene,Fairmont,Fort Madison,Grand Island,Great Falls,Green Bay,Helena,Hutchinson,Idaho Falls,Jacksonville,Kalispell,Kennewick,Kingsford,LaCrosse,Lacey,Layton,Lewiston,Lincoln,Logan,Manitowoc,Mankato,Marquette,Marshall,Marshfield,Mason City,Meridian,Missoula,Mitchell,Monmouth,Murray,Nampa,Norfolk,North Platte,Ogden,Omaha,Orem,Pocatello,Provo,Pullman,Quincy,Rapid City,Redding,Riverdale,Rothschild,Salem,Salt Lake City,Sandy,Sioux City,Sioux Falls,Spanish Fork,Spokane,Spokane Valley,Springfield,St Cloud,Taylorsville,Twin Falls,Union Gap,Walla Walla,Watertown,Wenatchee,West Bend,West Jordan,West Valley,Wisconsin Rapids,Worthington,Yakima""".split(','),
        ('PPL', 'US', 'Prominent4')
    )


def test_table_classify():
    classifier = train_classifier(verbose=False)

    res = classifier.full_geotag([
        ['Marco', 'Kate', 'Marco E.', 'Peter'],
        ['Boston', 'Washington', 'Montreal', 'Washington']
    ])

    assignment = res[0]
    print assignment.keys()
    for col in assignment['assignment']:
        print col['category'], col['stats'], col['final_prob']

    res = classifier.full_geotag([
        ['Arlington', 'Laurel', 'Columbia'],
        ['VA', 'MD', 'MD']
    ])

    assignment = res[0]
    print assignment.keys()
    for col in assignment['assignment']:
        print col['category'], col['stats'], col['final_prob']


def test_probabilities():
    classifier = train_classifier(verbose=False)
    classifier.verbose = True
    classifier.full_geotag([['Washington', 'New York']])


def test_lookup():
    assert lookup_type_code(ROOT)['plural'] == 'places'
    assert lookup_type_code(ROOT + '|P')['plural'] == 'cities or villages'
    assert lookup_type_code(ROOT + '|P|PPL')['plural'] == 'populated places'
    assert lookup_type_code(ROOT + '|S|SCH|SCH')['plural'] == 'schools'


def test_cat_text():
    cat = ('_|P', '_|US|NH', '_|Prominent1')
    txt = 'cities or villages with population > 0 in New Hampshire, USA'
    cat_txt = category_helpers.cat_text(cat)
    assert cat_txt == txt

    cat = ('_|S|SCH', '_|US|DC|001', '_')
    txt = 'schools in Washington, D.C., USA'
    cat_txt = category_helpers.cat_text(cat)
    assert cat_txt == txt

    cat = ('_', '_|US|MD|033', '_')
    txt = 'places in Prince George\'s County, Maryland, USA'
    cat_txt = category_helpers.cat_text(cat)
    assert cat_txt == txt

    cat = ('_', '_|US|MD|033', '_')
    txt = 'places in Prince George\'s County, Maryland, USA'
    cat_txt = category_helpers.cat_text(cat)
    assert cat_txt == txt


def web():
    from flask import Flask, jsonify, request
    app = Flask(__name__)
    app.debug = True

    classifier = train_classifier(verbose=True)

    page = """
    <!doctype html>
    <style>
      html {height: 100%; font-family: sans;}
      body {background-color: #eee; height: 90%;}
      #title {
        font-size: 36px;
        text-align: center;
        font-family: time;
        font-variant: small-caps;
      }
      #content {background-color: #fff; width: 1100px; margin: 0 auto; min-height: 100%;}
      table {margin-left:auto; margin-right:auto;}
      td {vertical-align: top;}
      #results td {padding-right: 10px;}
      #results th {padding: 0px 5px;}
      #map-canvas {height: 600px; width: 750px;}
      tr.cat:hover {background-color: #edd; opacity: 1.0;}
    </style>
    <div id="title">GeoWhiz - Place List Disambiguator</div>
    <div id="content">
    <table><tr>
    <td style="width: 450px; height: 300px">
      <div>Enter List of Places</div>
      <form action="geotag" method="get">
      <div>
      <textarea id="vals" style="width: 400px; height: 200px">
Washington
New York</textarea>
      </div>
      <input type="submit" id="submit" value="Submit" />
      </form>
    </td>
    <td><div id="map-canvas"></div></td>
    </tr>
    <tr>
    <td colspan="2" style="width: auto">
      <table id="results" style="display: none; max-height: 400px; overflow: auto;">
      <tr><th>Category</th><th>Coverage</th><th>Ambiguity</th><th>Likelihood</th></tr>
      </table>
    </td>
    </tr></table>
    </div>
    <script type="text/javascript" src="https://maps.googleapis.com/maps/api/js?key=AIzaSyC35erx3rMr4iTIE_AghLsYYKvuAs150PA&sensor=false"></script>
    <script src="//d3js.org/d3.v3.js"></script>
    <script>
      // Define the overlay, derived from google.maps.OverlayView
      function Label(opt_options) {
        // Initialization
        this.setValues(opt_options);

        // Label specific
        var span = this.span_ = document.createElement('span');
        //span.style.cssText = 'position: relative; left: -50%; top: -8px; ' +
        span.style.cssText = 'position: relative; left: -50%; top: 8px; ' +
                             'white-space: nowrap; border: 1px solid blue; ' +
                             'padding: 2px; border-radius: 3px; background-color: rgba(255, 255, 255, 0.9);';

        var span2 = this.span2_ = document.createElement('span');
        span2.style.cssText = 'position: absolute; height: 6px; width: 6px; ' +
        'top: -3px; left: -3px; background: brown; border-radius: 3px;';

        var div = this.div_ = document.createElement('div');
        div.appendChild(span);
        div.appendChild(span2);
        div.style.cssText = 'position: absolute; display: none';
      };
      Label.prototype = new google.maps.OverlayView;

      // Implement onAdd
      Label.prototype.onAdd = function() {
        var pane = this.getPanes().overlayLayer;
        pane.appendChild(this.div_);

        // Ensures the label is redrawn if the text or position is changed.
        var me = this;
        this.listeners_ = [
          google.maps.event.addListener(this, 'position_changed',
              function() { me.draw(); }),
          google.maps.event.addListener(this, 'text_changed',
              function() { me.draw(); })
        ];
      };

      // Implement onRemove
      Label.prototype.onRemove = function() {
        this.div_.parentNode.removeChild(this.div_);

        // Label is removed from the map, stop updating its position/text.
        for (var i = 0, I = this.listeners_.length; i < I; ++i) {
          google.maps.event.removeListener(this.listeners_[i]);
        }
      };

      // Implement draw
      Label.prototype.draw = function() {
        var projection = this.getProjection();
        var position = projection.fromLatLngToDivPixel(this.get('position'));

        var div = this.div_;
        div.style.left = position.x + 'px';
        div.style.top = position.y + 'px';
        div.style.display = 'block';

        this.span_.innerHTML = this.get('text').toString();
      };

    var data_obj;
    var markers = [];
    d3.select('#submit').on('click', function() {
      var txt = d3.select('#vals').property('value');
      d3.json('/geotag?vals=' + encodeURIComponent(txt), function(error, json) {
          d3.select('#results').style('display', 'table').selectAll('tr.cat').remove();
          var data_obj = json;
          var data = json.response.filter(function(d, i) {
            return (+d['likelihood'] >= 0.0000005) || (i <= 15);
          });
          data.forEach(function(d) {
            var cat = d.assignment[0];
            cat.score = +cat['normalized_prob'];
            cat.cats = (/[^|]*$/.exec(cat['category'][0]) + ', ' +
                        cat['category'][1] + ', ' +
                        /[^|]*$/.exec(cat['category'][2]));
            cat.coverage = +cat['stats']['coverage']/+cat['stats']['total'];
            cat.opacity = Math.sqrt(Math.sqrt(cat.score)) + 0.2;
          });
          function c(d) {return d.assignment[0];}

          var cats = d3.select('#results').selectAll('tr.cat')
                       .data(data);
          var score_fmt = d3.format('.2%');
          var fmt = d3.format('.2f');

          var trs = cats.enter()
              .append('tr')
              .attr('class', 'cat')
              .style('opacity', function(d) {return c(d).opacity;})
              .style('cursor', 'pointer');

          var categories = trs.append('td')
              .text(function(d) {return c(d).txt;})
              .attr('title', function(d) {return c(d).cats;});

          var cov = trs.append('td')
              .text(function(d) {return fmt(c(d).coverage);})
              //.style('display', 'inline-block')
              .style('min-width', '45px')
              .style('text-align', 'right');

          var amb = trs.append('td')
              .text(function(d) {return fmt(c(d).stats.ambiguity);})
              //.style('display', 'inline-block')
              .style('min-width', '50px')
              .style('text-align', 'right');

          var scores = trs.append('td')
              .text(function(d) {return score_fmt(c(d).score);})
              //.style('display', 'inline-block')
              .style('width', '60px')
              .style('text-align', 'right');

          trs.on('click', function() {
            // clear markers
            markers.forEach(function(m) {
              m.setMap(null);
            });
            markers = [];
            var pts = d3.select(this).datum().interpretations[0];
            var seen = {};
            pts.forEach(function(d) {
              if (typeof seen[d['name']] === 'undefined') {
                markers.push(new Label({
                  map: map,
                  position: new google.maps.LatLng(+d['latitude'],
                  +d['longitude']),
                  text: d['name']
                }));
                seen[d['name']] = true;
              }
            });
          });
        });
      d3.event.preventDefault();
    });
    var map;
    function initializeMap() {
      var mapOptions = {
        center: new google.maps.LatLng(10, 0),
        zoom: 1,
        mapTypeId: google.maps.MapTypeId.ROADMAP,
        streetViewControl: false
      };
      map = new google.maps.Map(document.getElementById('map-canvas'),
        mapOptions);
    }
    google.maps.event.addDomListener(window, 'load', initializeMap);
    </script>
    """

    @app.route('/')
    def index():
        return page

    @app.route('/geotag')
    def geotag():
        vals = request.args.get('vals', '')
        rows = []
        for row in vals.split('\n'):
            if len(row.strip()) > 0:
                rows.append([row.strip()])
                #rows.append([c.strip() for c in row.split(',')])
        grid = list(itertools.izip_longest(*rows))
        geotag_results = classifier.full_geotag(grid)

        for r in geotag_results:
            for g in r['assignment']:
                g['txt'] = category_helpers.cat_text(g['category'],
                                                     g['stats']['total'])

        return jsonify({'response': geotag_results})

    app.run(host='0.0.0.0')


def handle_args(args):
    doc_list = []
    for arg in args:
        if '-' in arg:
            doc_limits = arg.split('-')
            if len(doc_limits) != 2:
                usage()
            doc_range = range(int(doc_limits[0]), int(doc_limits[1]) + 1)
            doc_list.extend(doc_range)
        if arg.isdigit():
            doc_list.append(int(arg))
    for i, doc in enumerate(doc_list):
        sys.stdout.write('\rGeotagging doc %d/%d (%d%%)' %
                         (i, len(doc_list), 100 * (0.0 + i)/len(doc_list))),
        sys.stdout.flush()
        process_doc(doc)
    print


if __name__ == '__main__':
    if len(sys.argv) < 2:
        usage()

    if len(sys.argv) == 2:
        test_arg = sys.argv[1]
        found = True
        if test_arg == 'test-classify':
            test_classify()
        elif test_arg == 'test-tables':
            test_table_classify()
        elif test_arg == 'web':
            web()
        elif test_arg == 'test-lookup':
            test_lookup()
        elif test_arg == 'test-categories':
            test_cat_text()
        elif test_arg == 'test-probabilities':
            test_probabilities()
        elif test_arg == 'test-all':
            test_classify()
            print 'completed classification test'
            test_table_classify()
            print 'completed table classification test'
            test_lookup()
            print 'completed lookup test'
            test_cat_text()
            print 'completed category test'
        else:
            found = False
        if found:
            exit()

    handle_args(sys.argv[1:])
