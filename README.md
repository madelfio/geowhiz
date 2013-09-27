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

Running GeoWhiz requires Python 2.6/2.6.  First get the repository:

    git clone https://github.com/madelfio/geowhiz.git

Then use the included Makefile to build a SQLite gazetteer database based on
the current [GeoNames](http://www.geonames.org/) database (this takes ~20
minutes to run on my laptop):

    cd geowhiz
    make

To run the web interface, first install the required python packages (`pip
install requirements.txt`, assuming you have pip installed).  Then:

    python web.py

And head to <http://localhost:5000/> to test it out.
