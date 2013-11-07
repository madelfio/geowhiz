import os
import math
import json

import taxonomy
import classifier
import cattext

###################################################################
# functions to extract dimension values from raw gazetteer result #
###################################################################

TYPE_ROOT = 'dim0'
GEO_ROOT = 'dim1'
PROM_ROOT = 'dim2'

def type_classifier(d):
    return [TYPE_ROOT,
            d['fclass'],
            (d.get('fcode') or '')[:3] or None,
            d['fcode'] if d['fcode'] and len(d['fcode']) > 3 else None]


def geo_classifier(d):
    l = [GEO_ROOT, d['continent'], d['country'],
         d['admin1'] if d['admin1'] != '00' or d['country'] else None,
         d['admin2'], d['admin3'], d['admin4']]
    # remove trailing Nones
    # unrolled list comprehension for speed & to fix "Paris" bug
    if d['admin4']:
        return l
    elif d['admin3']:
        return l[:-1]
    elif d['admin2']:
        return l[:-2]
    elif d['admin1'] and d['country']:
        return l[:-3]
    elif d['country']:
        return l[:-4]
    elif d['continent']:
        return l[:-5]
    else:
        return l[:-6]


prominence_tree = ([PROM_ROOT] +
                   ['Prominent%d' % (i + 1,) for i in range(9)])


def prominence_classifier(d):
    if 'population' not in d or d['population'] == 0:
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
    lambda x, y: 'COV',  # dummy feature to test coverage probability
    lambda x, y: x[0],
    #lambda x, y: taxonomy.get_depths(x),
    lambda x, y: depth(x[2]),
    lambda x, y: depth(x[1]),
    lambda x, y: (depth(x[1]), depth(x[2])),
    lambda x, y: (depth(x[1]), amb_log(y['ambiguity'])),
    lambda x, y: y['ambiguity'] < 1.00001,
    lambda x, y: y['ambiguity'] < 1.2,
    lambda x, y: 1.00001 <= y['ambiguity'] < 1.3,
    lambda x, y: 1.3 <= y['ambiguity'] < 1.75,
    lambda x, y: 1.75 <= y['ambiguity'],
    lambda x, y: (x[0].startswith(TYPE_ROOT+'|P'), depth(x[2])),
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

        # expose category->text helper funcs for use in web module
        self.cat_text = cattext.CatText(self.gaz)

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

    def geotag_full(self,
                    grid,
                    resolution_method=None,
                    include_text=False):
        results = self.classifier.geotag_full(grid,
                                              resolution_method=resolution_method)
        assignments = [Assignment(**r) for r in results]

        cat_node_text = None
        if include_text:
            self.include_text(assignments)
            cat_node_text = self.cat_node_text(assignments)

        return FullGeotagResults(assignments, cat_node_text)

    def include_text(self, assignments):
        # attach text description for each category (used for web interfact)
        for r in assignments:
            for col in r.categories:
                col['txt'] = self.cat_text.cat_text(col['category'],
                                                    col['stats']['total'])

    def cat_node_text(self, assignments):
        # accumulate category nodes, return text description for each (to
        # display on nodes in tree visualization)
        cat_node_text = {}
        for r in assignments:
            for col in r.cell_interpretations:
                for interp in col:
                    cat = interp['cat']
                    for i in range(len(cat)):
                        node_l = cat[i].split('|')
                        # include parent nodes
                        for j in range(len(node_l)):
                            node = '|'.join(node_l[:j+1])
                            if node not in cat_node_text:
                                cat_node_text[node] = self.cat_text.cat_node_text(node, i)
        return cat_node_text


    def web_app(self):
        import web
        return web.create_app(self)

    def cat_text(self, category, number):
        return self.cat_text_func(category, number)

    def all_cat_text(self, category):
        return self.all_cat_text_func(category)


class FullGeotagResults(object):
    def __init__(self, assignments, cat_node_text=None):
        self.assignments = assignments
        self.cat_node_text = cat_node_text

    def toJSON(self):
        return json.dumps(self, default=lambda o: o.__dict__, sort_keys=True)


class Assignment(object):
    def __init__(self, categories, likelihood, cell_interpretations,
                 *args, **kwargs):
        self.categories = categories
        self.likelihood = likelihood
        self.cell_interpretations = cell_interpretations
