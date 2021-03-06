import heapq
import itertools
import math
import operator
import sys

import category

product = lambda x: reduce(operator.mul, x, 1)
geom_mean = lambda x: math.pow(math.e, sum(math.log(v) for v in x) / len(x))
depth = lambda x: x.count('|')


def filter_column_results(results):
    seen = set()
    filtered_results = []

    for res in results:
        if tuple(res['category']) in seen:
            continue
        seen.update(itertools.product(*category.s_to_all_s(res['category'])))
        filtered_results.append(res)
    return filtered_results


class Categorizer(object):
    """Geotags a grid of strings.

    Creates a GeoNames lookup object if necessary, communicates with Hierarchy
    class for legal toponym categories, and creates candidate Path objects to
    identify the most likely categories
    """

    def __init__(self, grid, geonames, taxonomy):
        self.grid = grid
        self.geonames = geonames
        self.taxonomy = taxonomy
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

        # TODO: Identify administrative region interpretations and other cells
        # in row that are contained in those regions, as possible addition to
        # category predicate

        # counts dict keeps track of number of interpretations that fall into
        # each category.
        # Example: if cat1 is satisfied by 4 interpretations of cell1, 0
        # interpretations of cell2, and 2 interpretations of cell3, then
        # counts[cat1] = [4, 2].
        counts = self._count_categories(column)

        # Add ambiguity and coverage statistics
        # The example above would result in a coverage value of 2, total of 3,
        # and ambiguity of (4*1*2) ^ (1/3) = 2.0
        results = self._add_amb_and_cov(counts, column)

        # TODO: Add ambiguity resolution method

        # default sort order for categories:
        # - first sort by coverage ratio
        # - next by the combined depth of the category over all dimensions
        # - then by ambiguity value descending
        return self._sort_and_filter_top_categories(results)

    def _count_categories(self, column):
        counts = {}
        for cell in column:
            cell_counts = {}

            # get list of interpretations for current toponym (cell value)
            interpretations = self.geonames.get_by_name(cell)

            for interpretation in interpretations:
                cell_cats = self._category_cartesian_product(interpretation)
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
        return counts

    def _category_cartesian_product(self, interpretation):
        category_l = self.taxonomy.categorize(interpretation)
        category_ss = category.l_to_all_s(category_l)
        cell_cats = list(set(itertools.product(*category_ss)))
        return cell_cats

    def _add_amb_and_cov(self, counts, column):
        results = []
        for cat, cnts in counts.iteritems():
            amb = geom_mean(cnts)
            results.append({
                'category': cat,
                'stats': {'ambiguity': amb,
                          'coverage': len(cnts),
                          'total': len(column)}
            })
        return results

    def _sort_and_filter_top_categories(self, results):
        cats_sort_key = lambda x: (x['stats']['coverage'],
                                   sum(depth(p) for p in x['category']),
                                   -x['stats']['ambiguity'])
        results = sorted(results, key=cats_sort_key, reverse=True)
        top_results = results[:300]

        return filter_column_results(top_results)


resolution_sort = lambda x: (x['population'], x['altnames'],
                             x['fcode'] == 'MT' and x['elevation'])

def add_proximity_resolution(interpretations):
    toRadians = lambda x: x * math.pi / 180
    radius = 6371  # km

    cache_pt = {}
    cache_dist = {}
    def geo_dist(pt1, pt2):
        if (pt1, pt2) in cache_dist:
            return cache_dist[(pt1, pt2)]
        if pt1 in cache_pt:
            lat1, lng1, lat1cos = cache_pt[pt1]
        else:
            lat1 = toRadians(pt1[0])
            lng1 = toRadians(pt1[1])
            lat1cos = math.cos(lat1)
            cache_pt[pt1] = (lat1, lng1, lat1cos)
        lat2 = toRadians(pt2[0])
        lng2 = toRadians(pt2[1])
        lat2cos = math.cos(lat2)

        dlat = lat2 - lat1
        dlng = lng2 - lng1

        a = math.sin(dlat/2) ** 2 + math.sin(dlng/2) ** 2 * lat1cos * lat2cos
        res = radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        cache_dist[(pt1, pt2)] = res
        return res

    cache_coord = {}
    def geo_coord(lat, lng):
        if (lat, lng) in cache_coord:
            return cache_coord[(lat, lng)]
        phi = (90 - lat) * math.pi / 180
        theta = (lng) * math.pi / 180
        x = math.sin(phi) * math.cos(theta)
        y = math.sin(phi) * math.sin(theta)
        z = math.cos(phi)
        cache_coord[(lat, lng)] = (x, y, z)
        return x, y, z

    def geo_centroid(lat_lng_list):
        xs = []
        ys = []
        zs = []
        for lat, lng in lat_lng_list:
            x, y, z = geo_coord(lat, lng)
            xs.append(x)
            ys.append(y)
            zs.append(z)
        x_c = sum(xs)
        y_c = sum(ys)
        z_c = sum(zs)
        l = len(xs)
        r = math.sqrt(x_c**2 + y_c**2 + z_c**2) / l
        phi_c = math.acos(z_c / (l * r))
        theta_c = math.atan2(y_c, x_c)
        lat_c = 90 - 180 * (phi_c / math.pi)
        lng_c = 180 * theta_c / math.pi
        return (lat_c, lng_c)

    def geo_mean_sq_dist(interp_list):
        coord_list = [(i['latitude'], i['longitude']) for i in interp_list]

        c = geo_centroid(coord_list)
        sq_dists = [geo_dist(c, pt) ** 2 for pt in coord_list]
        return (sum(sq_dists) / len(sq_dists))

    # add two most prominent interpretations of each toponym as "seeds" for
    # proximity testing
    seeds = []
    for wi in interpretations:
        seeds.extend(wi[:2])

    # iterate through all seeds, adding closest interpretation of each other
    # toponym.  for each collection of interpretations, measure distance of
    # each to the centroid of the collection.  collection that minimizes the
    # sum of square distances "wins" and the respective interpretations are
    # selected by the "proximity" method
    best = []
    best_dist = float('inf')
    for s in seeds:
        interp_set = []
        for interp_list in interpretations:
            best_interp = None
            best_interp_dist = float('inf')
            for i in interp_list:
                i_dist = geo_dist((s['latitude'], s['longitude']),
                                  (i['latitude'], i['longitude']))
                if i_dist < best_interp_dist:
                    best_interp = i
                    best_interp_dist = i_dist
            if best_interp:
                interp_set.append(best_interp)
        mean_sq_dist = geo_mean_sq_dist(interp_set)
        if mean_sq_dist < best_dist:
            best = interp_set
            best_dist = mean_sq_dist

    # annotate likely interpretations with 'prox_likely' attribute
    for i in best:
        i['prox_likely'] = True

    return


class Resolver(object):
    def __init__(self, grid=None, geonames=None, assignment=None, method=None):
        self.grid = grid
        self.geonames = geonames
        self.assignment = assignment  # category for each column
        self.method = method

    def get_interpretations(self, **options):
        """
        Returns possible interpretations for each cell, based on column
        category
        """
        interpretations = [
            self._get_col_interpretations(column, cat, **options)
            for column, cat in zip(self.grid, self.assignment)
        ]
        return interpretations

    def get_all_interpretations(self, **options):
        o = dict(options)
        o['fetch_all'] = True
        return self.get_interpretations(**o)

    def _get_col_interpretations(self, column, cat, fetch_all=False,
                                 method=None, **options):
        """
        Identifies top candidate interpretations within a category for a column
        of values.

        fetch_all parameter determines if all interpretations are returned.
        When false, only the most likely interpretation is included in result.

        method parameter specifies resolution method.  It can be one of three
        values: ['prominence', 'proximity', 'both'].
        """
        method = method or self.method or 'proximity'

        interpretations = []

        for cell in column:
            cell_interpretations = []
            for g in self.geonames.get_by_name(cell):
                g_cat = self.geonames.get_category(g)
                if category.satisfies_s(g_cat, cat['category']):
                    return_val = dict(g)
                    return_val['cat'] = g_cat
                    if return_val['name'] != cell:
                        return_val['full_name'] = cell
                    cell_interpretations.append(return_val)

            cell_interpretations.sort(key=resolution_sort, reverse=True)
            if method in ['both', 'prominence']:
                if len(cell_interpretations) > 0:
                    cell_interpretations[0]['likely'] = True

            if fetch_all:
                interpretations.append(cell_interpretations)
            else:
                interpretations.append([cell_interpretations[0]])

        if method in ['both', 'proximity']:
            add_proximity_resolution(interpretations)

        # flatten list
        flat_interpretations = []
        for i in interpretations:
            flat_interpretations.extend(i)

        return flat_interpretations


class ColumnClassifier(object):

    def __init__(self, gaz, taxonomy, verbose=False):
        self.gaz = gaz
        self.taxonomy = taxonomy
        self.verbose = verbose

    def train(self, training_set):
        """Given a list of (grid, categories) as the training set, find
        appropriate category ratings"""

        for grid, true_category in training_set:
            if grid and isinstance(grid[0], basestring):
                grid = [grid]
                true_category = [true_category]
            # Get category candidates for each column
            all_strings = [s for col in grid for s in col]
            categorize_func = lambda x: category.l_to_s(
                self.taxonomy.categorize(x)
            )
            geonames = self.gaz.lookup(all_strings, categorize_func)
            grid_candidates = Categorizer(
                grid, geonames, self.taxonomy
            ).get_top_categories()

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
        else:
            print >> sys.stderr, 'No winner found for %r (%r)' % (cat_list, true_cat)

    def add_training_samples(self, winner, candidates):
        raise NotImplementedError

    def geotag_full(self, grid, **options):
        resolution_method = options.get('resolution_method', 'both')
        single_category = options.get('single_category', False)

        if grid and isinstance(grid[0], basestring):
            grid = [grid]
        all_strings = [s for col in grid for s in col]
        categorize_func = lambda x: category.l_to_s(
            self.taxonomy.categorize(x)
        )
        geonames = self.gaz.lookup(all_strings, categorize_func)

        # Determine possible categories for each column
        grid_candidates = Categorizer(
            grid, geonames, self.taxonomy
        ).get_top_categories()

        # Determine most likely categories for each column
        category_lists = []
        for column, candidates in zip(grid, grid_candidates):
            category_lists.append(self._classify_column(column, candidates))

        # Determine most likely category assignments for all columns in grid
        a_list = self._get_likely_category_assignments(category_lists)
        assignments = []
        for a_idxs, a_prob in a_list:
            a = ([c[i] for c, i in zip(category_lists, a_idxs) if c], a_prob)
            assignments.append(a)

        if single_category:
            assignments = assignments[:1]

        # Determine most likely interpretations for each toponym given
        # assignment
        geotag_results = []
        for assignment, a_prob in assignments:
            resolver = Resolver(grid, geonames, assignment,
                                method=resolution_method)
            interpretations = resolver.get_all_interpretations(method=resolution_method)
            c = None
            #c = [geo_centroid([(g['latitude'], g['longitude'])
            #                   for g in i if 'likely' in g])
            #     for i in interpretations]
            geotag_results.append({'categories': assignment,
                                   'likelihood': a_prob,
                                   'cell_interpretations': interpretations,
                                   'centroid': c})

        return geotag_results

    def geotag_grid(self, grid, **options):
        full_results = self.geotag_full(grid, **options)
        return full_results[0]

    def column_geotag(self, column, **options):
        grid_results = self.geotag_grid([column], **options)
        return {'assignment': grid_results['assignment'][0],
                'likelihood': grid_results['likelihood'],
                'interpretations': [i
                                    for i in grid_results['interpretations'][0]
                                    if 'likely' in i and i['likely']],
                'centroid': grid_results['centroid']}

    def geotag(self, grid, **options):
        if grid and isinstance(grid[0], basestring):
            return self.column_geotag(grid, **options)
        else:
            return self.geotag_grid(grid, **options)

    def _classify_column(self, column, category_list):
        raise NotImplementedError

    def _get_likely_category_assignments(self, category_lists, top=20):
        raise NotImplementedError


class BayesClassifier(ColumnClassifier):
    def __init__(self, *args, **kwargs):
        self.model = []
        self.feature_funcs = []
        self._cache_prob = {}
        super(BayesClassifier, self).__init__(*args, **kwargs)

    def set_feature_funcs(self, func_list):
        self.feature_funcs = func_list

    def add_training_samples(self, winner_idx, candidates):
        if self.verbose:
            print 'New Training Sample!'

        for i, res in enumerate(candidates):
            cat = res['category']
            stats = res['stats']

            # compute feature funcs for category
            func_vals = [f(cat, stats) for f in self.feature_funcs]

            instance = (i == winner_idx,
                        stats['coverage'],
                        stats['total'],
                        func_vals)
            if i == winner_idx:
                if self.verbose:
                    print 'Found true category:'
                    print cat, stats
            self.model.append(instance)

        # clear model cache
        self._cache_prob = {}

    #def geotag_full(self, *args, **kwargs):
    #    return super(BayesClassifier, self).geotag_full(*args, **kwargs)

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
                p = self._feature_prob(i, v, stats['coverage'], stats['total'])
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

        # scale probs
        prob_sum = sum(r['final_prob'] for r in results)
        for r in results:
            r['scaled_prob'] = (r['final_prob'] / prob_sum) ** 0.75

        # normalize probs
        prob_sum = sum(r['scaled_prob'] for r in results)
        for r in results:
            r['normalized_prob'] = r['scaled_prob'] / prob_sum

        return sorted(results,
                      key=lambda x: x['normalized_prob'],
                      reverse=True)

    def _feature_prob(self, f_idx, f_val, cov, tot):
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
