import itertools
from flask import Flask, request, send_file


def create_app(geowhiz):
    app = Flask(__name__)

    @app.route('/')
    def index():
        return send_file('index.html')

    @app.route('/geowhiz.js')
    def js():
        return send_file('geowhiz.js')

    @app.route('/geowhiz-api.js')
    def api():
        return send_file('geowhiz-api.js')

    @app.route('/geotag')
    def geotag():

        vals = request.args.get('vals', '')
        rows = []

        for row in vals.split('\n'):
            if len(row.strip()) > 0:
                rows.append([row.strip()])
                #rows.append([c.strip() for c in row.split(',')])

        grid = list(itertools.izip_longest(*rows))

        geotag_results = geowhiz.geotag_full(
            grid,
            resolution_method='both',
            include_text=True
        )

        return geotag_results.toJSON()

    return app
