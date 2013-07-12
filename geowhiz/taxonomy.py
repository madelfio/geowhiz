ROOT = '_'


class Taxonomy(object):
    """Maintains multiple dimensions"""
    def __init__(self):
        self.dimensions = []
        self.categorizors = []

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


depth = lambda x: x.count('|')


class Dimension(object):
    """A dimension for classifying toponyms"""
    def __init__(self, classifier=None, class_extractor=None):
        self.classifier = classifier or (lambda x: ROOT)
        self.class_extractor = class_extractor or depth

    def categorize(self, instance):
        return self.classifier(instance)

    def get_depth(self, node):
        return self.class_extractor(node)
