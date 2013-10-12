- Better support for multi-column geo-references.
  - Fetch all interpretations for each topo cell, as usual.
  - Next, for every Admin or Political entity encountered, test if other cells
    in row have any interpretations within.  If so, tag with containment.
  - Then, when computing cartesian product of categories that satisfy, also
    take categories w/ presence or absence of each containment predicate
    (new quasi-dimension).
