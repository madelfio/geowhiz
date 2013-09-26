# GeoWhiz

A place list disambiguator.

For example, if you enter the list:

    Arlington
    Alexandria
    Springfield
    Vienna

GeoWhiz will give you results like these (your results may be different due to
classifier tweaks):

| Category                                                       | Likelihood |
| -------------------------------------------------------------- | ---------- |
| cities with population ≥ 10,000 in Virginia, USA               | 35.53%     |
| cities with population ≥ 100,000 around the world              | 27.70%     |
| populated places with population ≥ 10 in South Dakota, USA     | 22.13%     |
| ...                                                            | ...        |

Along with each category will be specific geographic interpretations of each
place name in your list.  In this case, the category possibilities help to
identify that the list is most likely to refer to cities in Virginia, rather
than the more populated places with the same names from around the world.

### Setup

To run GeoWhiz yourself, clone the repository.

Then run:

    $ make

to download the GeoNames database and transform it into a SQLite gazetteer
database (this takes ~30 minutes to run on my laptop).

To run the web interface:

    $ cd geowhiz
    $ python web.py



