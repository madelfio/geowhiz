# coding=utf-8
import locale
locale.setlocale(locale.LC_ALL, 'en_US.utf8')

ROOT = '_'
GEONAME_CONTAINERS = {'_|NA|US': 'USA'}
STATIC = {'_|NA|US': 'the United States'}
fmt = lambda x: 'in %s' % (STATIC.get(x, GEONAME_CONTAINERS.get(x, 'UNKNOWN')),)

CONTINENTS = {
    'NA': 'North America',
    'AS': 'Asia',
    'EU': 'Europe',
    'SA': 'South America',
    'AF': 'Africa',
    'OC': 'Oceania',
    'AN': 'Antarctica'
}

class CatText(object):

    def __init__(self, gaz):
        self.geoname_types = {}
        self.gaz = gaz

    def lookup_type_code(self, type_code, plural=True):
        """
        Return information about the fclass/fcode specified.
        """
        default = {'type': 'place', 'plural': 'places'}
        if type_code == ROOT:
            t = default

        elif type_code == ROOT + '|A|ADM':
            t = {'type': 'administrative region',
                    'plural': 'administrative regions'}

        else:

            if len(self.geoname_types) == 0:
                print 'LOADING GEONAME TYPE STRINGS'
                self.geoname_types = load_geoname_types(self.gaz)

            t = self.geoname_types.get(type_code, default)

        if plural:
            return t['plural']
        else:
            return t['type']


    def prominence_text(self, prominence_s):
        if prominence_s == ROOT:
            return ''
        elif prominence_s[-1] == '1':
            return 'with population > 0'
        val = locale.format(
            '%d',
            10 ** (int(prominence_s[-1]) - 1),
            grouping=True
        )
        return ('with population ≥ %s' % (val,)).decode('utf8')


    def geo_text(self, geo_s):
        if geo_s == ROOT:
            return 'around the world'

        geo_l = geo_s.split('|')

        k = '|'.join(geo_l[:4])

        if k in GEONAME_CONTAINERS:
            return fmt(k)

        # return continent name
        if geo_s.count('|') == 1:
            continent_code = geo_s[geo_s.index('|') + 1:]
            GEONAME_CONTAINERS[k] = CONTINENTS[continent_code]
            return fmt(k)

        last_vals = None
        for i, f in enumerate([self.gaz.get_container_country,
                               self.gaz.get_container_admin1,
                               self.gaz.get_container_admin2]):
            if len(geo_l) < i + 2:
                break
            k = '|'.join(geo_l[:i+3])
            if k not in GEONAME_CONTAINERS:
                res = f(geo_l[2:i+3])
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


    def cat_text(self, cat_s, cnt=2):
        # Handle type
        type_txt = self.lookup_type_code(cat_s[0], plural=(cnt>1))

        # Handle prominence
        prom_txt = self.prominence_text(cat_s[2])

        # Handle geo container
        geo_txt = self.geo_text(cat_s[1])

        return ' '.join(t for t in (type_txt, prom_txt, geo_txt) if t)


plural_map = {
    'country, state, region,...': 'countries, states, or administrative regions',
    'stream, lake, ...': 'streams, lakes, or hydrological features',
    'parks,area, ...': 'parks or areas',
    'city, village,...': 'cities or villages',
    'road, railroad': 'roads or railroads',
    'spot, building, farm': 'spots, buildings, or farms',
    'mountain,hill,rock,...': 'mountains, hills, or rocky areas',
    'undersea': 'undersea areas',
    'forest,heath,...': 'forests or areas of vegetation',
}

def load_geoname_types(gaz):
    types = []
    geoname_types_raw = list(gaz.get_types())
    for fclass, fcode, name, description in geoname_types_raw:
        if not fclass or not name: continue
        fcode1 = fcode[:3]
        types.append({'t1': fclass,
                      't2': fcode[:3],
                      't3': fcode,
                      'type': name,
                      'desc': description})

    # add plurals column
    for t in types:
        s = t['type']
        if not s:
            continue
        last = s.split()[-1]
        p = None

        if s in plural_map:
            t['plural'] = plural_map[s]
            continue

        # Handle:
        # - 'seat of government of a political entity'
        if s.startswith('section of'):
            s = 'sections of' + s[len('section of'):]
        elif s.startswith('seat of a'):
            s = 'seats of' + s[len('seat of a'):]
        elif 'capital of a' in s:
            s = s.replace('capital of a', 'capitals of')


        if last[-2:] in ['sh', 'ch', 'ss']:
            p = s + 'es'
        elif last[-1] == 'y' and last[-2:] not in ['ay', 'ey']:
            p = s[:-1] + 'ies'
        elif last[-1] == 's':
            p = s
        elif '(s)' in s:
            p = s.replace('(s)', 's')
        elif '(es)' in s:
            p = s.replace('(es)', 'es')
        elif 'y(-ies)' in s:
            p = s.replace('y(-ies)', 'ies')
        elif 'is(-es)' in s:
            p = s.replace('is(-es)', 'es')
        elif 'f(-ves)' in s:
            p = s.replace('f(-ves)', 'ves')
        else:
            p = s + 's'
        t['plural'] = p

    # add intermediate types (pseudotypes)
    lookup = lambda x, y, z: '|'.join([x, y or '', z or ''])
    t_set = set([lookup(t['t1'], t.get('t2'), t.get('t3')) for t in types])
    pseudotypes = []
    for t in types:
        if lookup(t['t1'], None, None) not in t_set:
            pt = t.copy()
            pt['t2'] = None
            pt['t3'] = None
            pseudotypes.append(pt)
            t_set.add(lookup(pt['t1'], None, None))
        if lookup(t['t1'], t.get('t2'), None) not in t_set:
            pt = t.copy()
            pt['t3'] = None
            pseudotypes.append(pt)
            t_set.add(lookup(pt['t1'], t['t2'], None))

    types.extend(pseudotypes)

    geoname_types = {}
    for t in types:
        code_str = '|'.join(n for n in [ROOT, t['t1'], t['t2'], t['t3']] if n)
        attrs = {'type': t['type'], 'plural': t['plural'], 'desc': t['desc']}
        geoname_types[code_str] = attrs

    return geoname_types
