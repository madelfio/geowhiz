# coding=utf-8
import locale
locale.setlocale(locale.LC_ALL, 'en_US.utf8')

ROOT = '_'
GEONAME_CONTAINERS = {'_|NA|US': 'USA'}
STATIC = {'_|NA|US': 'the United States'}
fmt = lambda x: 'in %s' % (
    STATIC.get(x, GEONAME_CONTAINERS.get(x, 'UNKNOWN')),
)

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
        return u'with population ≥ %s' % (val,)

    def geo_text(self, geo_s, max_depth=4):
        if geo_s == ROOT:
            return 'around the world'

        geo_l = geo_s.split('|')

        k = '|'.join(geo_l[:max_depth])

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
        type_txt = prom_txt = geo_txt = None

        cat_t, cat_g, cat_p = cat_s

        if cat_t.endswith('|ADM1') and '|NA|US' in cat_g:
            type_txt = 'states' if cnt > 1 else 'state'
        elif cat_t.endswith('|ADM2') and '|NA|US' in cat_g:
            type_txt = 'counties' if cnt > 1 else 'county'
        elif cat_t.endswith('|PPL') and cat_p.count('|') > 4:
            type_txt = 'cities' if cnt > 1 else 'city'

        # Handle type
        type_txt = type_txt or self.lookup_type_code(cat_s[0], plural=(cnt > 1))

        # Handle prominence
        prom_txt = prom_txt or self.prominence_text(cat_s[2])

        # Handle geo container
        geo_txt = geo_txt or self.geo_text(cat_s[1])

        return ' '.join(t for t in (type_txt, prom_txt, geo_txt) if t)

    def all_cat_text(self, cat_s):
        type_txt = geo_txt = prom_txt = ''
        cat_t, cat_g, cat_p = cat_s

        l = cat_t.split('|')
        type_txt = '|'.join([self.lookup_type_code('|'.join(l[:i + 1]))
                             for i in range(len(l))])

        l = cat_g.split('|')
        geo_txt = '|'.join([self.geo_text('|'.join(l[:i + 1]))
                            for i in range(len(l))])

        l = cat_p.split('|')
        prom_txt = '|'.join([self.prominence_text('|'.join(l[:i + 1]))
                             for i in range(len(l))])

        return [type_txt, prom_txt, geo_txt]



def load_geoname_types(gaz):
    types = [
        {'t1': 'A', 't2': None, 't3': None, 'desc': '',
         'type': 'Administrative region',
         'plural': 'Administrative regions'},
        {'t1': 'H', 't2': None, 't3': None, 'desc': '',
         'type': 'stream, lake, or hydrological feature',
         'plural': 'streams, lakes, or hydrological features'},
        {'t1': 'L', 't2': None, 't3': None, 'desc': '',
         'type': 'park or area', 'plural': 'parks or areas'},
        {'t1': 'P', 't2': None, 't3': None, 'desc': '',
         'type': 'city or village',
         'plural': 'cities or villages'},
        {'t1': 'R', 't2': None, 't3': None, 'desc': '',
         'type': 'road or railroad',
         'plural': 'roads or railroads'},
        {'t1': 'S', 't2': None, 't3': None, 'desc': '',
         'type': 'spot, building, or farm',
         'plural': 'spots, buildings, or farms'},
        {'t1': 'T', 't2': None, 't3': None, 'desc': '',
         'type': 'mountain, hill, or rocky area',
         'plural': 'mountains, hills, or rocky areas'},
        {'t1': 'U', 't2': None, 't3': None, 'desc': '',
         'type': 'undersea area',
         'plural': 'undersea areas'},
        {'t1': 'V', 't2': None, 't3': None, 'desc': '',
         'type': 'forest or area of vegetation',
         'plural': 'forests or areas of vegetation'},
    ]
    geoname_types_raw = list(gaz.get_types())
    for fclass, fcode, name, description in geoname_types_raw:
        if not fclass or not name:
            continue
        types.append({'t1': fclass,
                      't2': fcode[:3],
                      't3': fcode,
                      'type': name,
                      'desc': description})

    # add plurals column
    for t in types:
        if 'plural' in t or 'type' not in t:
            continue
        s = t['type']
        last = s.split()[-1]
        p = None

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
