import os
import math
import json

import taxonomy
import classifier
import cattext

###################################################################
# functions to extract dimension values from raw gazetteer result #
###################################################################

def type_classifier(d):
    return [taxonomy.ROOT,
            d['fclass'],
            (d.get('fcode') or '')[:3] or None,
            d['fcode'] if d['fcode'] and len(d['fcode']) > 3 else None]

def geo_classifier(d):
    l = [taxonomy.ROOT, d['continent'], d['country'],
         d['admin1'] if d['admin1'] != '00' or d['country'] else None,
         d['admin2'], d['admin3'], d['admin4']]
    return l[:-[(not i) for i in reversed(l)].index(False)]


prominence_tree = [taxonomy.ROOT] + ['Prominent%d' % (i + 1,) for i in range(9)]

def prominence_classifier(d):
    if (d.get('population', 0) or 0) == 0:
        prom = 0
    else:
        prom = int(math.log10(d['population'])) + 1
    return prominence_tree[:prom + 1]

#############################################
# feature functions for Bayesian classifier #
#############################################

depth = lambda x: x.count('|')
amb_log = lambda x: math.floor(math.log(x) / math.log(1.1))

feature_funcs = [
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
    lambda x, y: (x[0].startswith(taxonomy.ROOT+'|P'), depth(x[2])),
]

###############################################
# prepare classifier using training data file #
###############################################

def load_training_set():
    cur_dir = os.path.dirname(os.path.realpath(__file__))
    train_file = os.path.join(cur_dir, 'train.txt')
    training_set = []
    with open(train_file) as f:
        lines = list(f)
        pairs = zip(lines[::3], lines[1::3])
        for toponyms_line, cat_line in pairs:
            toponyms = [t.strip() for t in toponyms_line.strip().split(';')]
            cat = [c.strip() or None for c in cat_line.strip().split(';')]
            training_set.append((toponyms, cat))
    return training_set

##################################
# primary object for geowhiz API #
##################################

class GeoWhiz(object):
    def __init__(self, gaz):
        self.gaz = gaz
        self.taxonomy = self._initialize_taxonomy()
        self.classifier = self._initialize_classifier()
        self.cat_text = cattext.CatText(self.gaz).cat_text

    def _initialize_taxonomy(self):
        t = taxonomy.Taxonomy()
        t.add_dimension(taxonomy.Dimension(type_classifier))
        t.add_dimension(taxonomy.Dimension(geo_classifier))
        t.add_dimension(taxonomy.Dimension(prominence_classifier))
        return t

    def _initialize_classifier(self):
        c = classifier.BayesClassifier(self.gaz, self.taxonomy)
        c.set_feature_funcs(feature_funcs)
        c.train(load_training_set())
        return c

    def geotag(self, grid):
        results = self.classifier.geotag(grid)
        return Assignment(**results)

    def geotag_full(self, grid):
        results = self.classifier.geotag_full(grid)
        assignments = [Assignment(**r) for r in results]
        return FullGeotagResults(assignments)

    def web_app(self):
        import web
        return web.create_app(self)

    def cat_text(self, category, number):
        print repr(category), number
        return self.cat_text(category, number)


class FullGeotagResults(object):
    def __init__(self, assignments):
        self.assignments = assignments

    def toJSON(self):
        return json.dumps(self, default=lambda o: o.__dict__, sort_keys=True)


class Assignment(object):
    def __init__(self, categories, likelihood, cell_interpretations,
                 *args, **kwargs):
        self.categories = categories
        self.likelihood = likelihood
        self.cell_interpretations = cell_interpretations
