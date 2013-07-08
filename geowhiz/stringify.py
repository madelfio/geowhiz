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
