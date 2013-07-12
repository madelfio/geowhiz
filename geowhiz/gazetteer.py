class Gazetteer(object):
    """Abstract base class for fetching GeoNames data"""
    def get_geoname_info(self, strings):
        pass

    def get_country_name(self, country_code):
        pass

    def get_admin1_name(self, country_code, admin1):
        pass

    def get_admin2_name(self, country_code, admin1, admin2):
        pass

    def lookup(self, strings, categorize_func):
        return Lookup(strings, self, categorize_func)


def remove_unlikely_strings(strings):
    return [
        s for s in strings
        if len(unicode(s)) >= 2
        and s not in ['No']
    ]


def add_comma_strings(strings):
    results = []
    for s in strings:
        if ',' in s:
            results.extend([pt.strip() for pt in s.split(',')])
        results.append(s)
    return results


class Lookup(object):
    """A lookup class that is populated by querying the geonames database for
    specified strings"""
    def __init__(self, strings, gaz, categorize_func):
        self.strings = []
        self.geoname_lookup = {}
        self.geoname_id_lookup = {}
        self.gaz = gaz
        self.categorize_func = categorize_func
        self.add_strings(strings)
        self.type_lookup = {}
        self._category_cache = {}

    def add_strings(self, strings):
        unique_strings = remove_unlikely_strings(set(strings))
        unique_strings = set(add_comma_strings(unique_strings))
        geoname_results = self.gaz.get_geoname_info(list(unique_strings))

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
                    if None in a:
                        a = a[:a.index(None)]
                    if g['fcode'] and g['fcode'].startswith('PCL'):
                        a = a[:1]

                    valid = False
                    if containers is None:
                        valid = True
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
            cat = self.categorize_func(geoname)
            self._category_cache[geonameid] = cat
            return cat
