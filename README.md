## GeoWhiz

A place list disambiguator.  Powers <http://geowhiz.umiacs.umd.edu/>.

As an example, if you enter the list:

    Arlington
    Alexandria
    Springfield
    Vienna

GeoWhiz will give you results like these (your results may be different due to
classification model tweaks):

| Category                                                       | Likelihood |
| -------------------------------------------------------------- | ---------- |
| cities with population ≥ 10,000 in Virginia, USA               | 35.53%     |
| cities with population ≥ 100,000 around the world              | 27.70%     |
| populated places with population ≥ 10 in South Dakota, USA     | 22.13%     |
| ...                                                            | ...        |

A Bayesian classifier is used to generate the likelihood values for each
category, which in turn determines a set of specific geographic
interpretations of each place name in your list.  For this example, the
category possibilities help to identify that the list is most likely to refer
to cities in Virginia, rather than the more populated places with the same
names from around the world.

### Setup

Running GeoWhiz locally requires Python 2.6 or 2.7.  First get the repository:

    git clone https://github.com/madelfio/geowhiz.git

Then use the included Makefile to build a SQLite gazetteer database based on
the current [GeoNames](http://www.geonames.org/) database (this takes ~20
minutes to run on my laptop):

    cd geowhiz
    make

In order to run the web interface, install the required python packages (`pip
install -r requirements.txt`, assuming you have [pip](http://pip-installer)
installed).  Then:

    python web.py

This runs as a local HTTP server, defaulting to port 5000.  Head to
<http://localhost:5000/> to test it out.
