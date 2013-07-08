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
