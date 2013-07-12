"""
Helper functions for dealing with categories that may have different
representations.
"""


def s_to_l(strings):
    return [d.split('|') for d in strings]


def l_to_s(lists):
    """
    (['A', 'B', 'C'], ['1', '2', '3']) => ['A|B|C', '1|2|3']
    """
    return ['|'.join((n for n in d if n is not None)) for d in lists]


def l_to_all_s(lists):
    dimensions = []
    for d in lists:
        dimensions.append(['|'.join(str(n) for n in d[:i+1])
                           for i in range(len(d))
                           if d[i] is not None])
    return dimensions


def s_to_all_s(strings):
    return l_to_all_s(s_to_l(strings))


def satisfies_s(strings1, strings2):
    """
    Returns true iff s1 satisfies s2
    """
    # Add '|' to ensure that we don't erroneously think prefix categories
    # match (i.e., _|P|PPL|PPLA2 does not satisfy _|P|PPL|PPLA)
    return all((s1 + '|').startswith(s2 + '|')
               for (s1, s2) in zip(strings1, strings2))
