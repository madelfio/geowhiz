import itertools
from flask import Flask, jsonify, request

page = """
<!doctype html>
<style>
  html {height: 100%; font-family: sans;}
  body {background-color: #eee; height: 90%;}
  #title {
    font-size: 36px;
    text-align: center;
    font-family: time;
    font-variant: small-caps;
  }
  #content {background-color: #fff; width: 1100px; margin: 0 auto; min-height: 100%;}
  table {margin-left:auto; margin-right:auto;}
  td {vertical-align: top;}
  #results td {padding-right: 10px;}
  #results th {padding: 0px 5px;}
  #map-canvas {height: 600px; width: 750px;}
  tr.cat:hover {background-color: #edd; opacity: 1.0;}
</style>
<div id="title">GeoWhiz - Place List Disambiguator</div>
<div id="content">
<table><tr>
<td style="width: 450px; height: 300px">
  <div>Enter List of Places</div>
  <form action="geotag" method="get">
  <div>
  <textarea id="vals" style="width: 400px; height: 200px">
Washington
New York</textarea>
  </div>
  <input type="submit" id="submit" value="Submit" />
  </form>
</td>
<td><div id="map-canvas"></div></td>
</tr>
<tr>
<td colspan="2" style="width: auto">
  <table id="results" style="display: none; max-height: 400px; overflow: auto;">
  <tr><th>Category</th><th>Coverage</th><th>Ambiguity</th><th>Likelihood</th></tr>
  </table>
</td>
</tr></table>
</div>
<script type="text/javascript" src="https://maps.googleapis.com/maps/api/js?key=AIzaSyC35erx3rMr4iTIE_AghLsYYKvuAs150PA&sensor=false"></script>
<script src="//d3js.org/d3.v3.js"></script>
<script>
  // Define the overlay, derived from google.maps.OverlayView
  function Label(opt_options) {
    // Initialization
    this.setValues(opt_options);

    // Label specific
    var span = this.span_ = document.createElement('span');
    //span.style.cssText = 'position: relative; left: -50%; top: -8px; ' +
    span.style.cssText = 'position: relative; left: -50%; top: 8px; ' +
                         'white-space: nowrap; border: 1px solid blue; ' +
                         'padding: 2px; border-radius: 3px; background-color: rgba(255, 255, 255, 0.9);';

    var span2 = this.span2_ = document.createElement('span');
    span2.style.cssText = 'position: absolute; height: 6px; width: 6px; ' +
    'top: -3px; left: -3px; background: brown; border-radius: 3px;';

    var div = this.div_ = document.createElement('div');
    div.appendChild(span);
    div.appendChild(span2);
    div.style.cssText = 'position: absolute; display: none';
  };
  Label.prototype = new google.maps.OverlayView;

  // Implement onAdd
  Label.prototype.onAdd = function() {
    var pane = this.getPanes().overlayLayer;
    pane.appendChild(this.div_);

    // Ensures the label is redrawn if the text or position is changed.
    var me = this;
    this.listeners_ = [
      google.maps.event.addListener(this, 'position_changed',
          function() { me.draw(); }),
      google.maps.event.addListener(this, 'text_changed',
          function() { me.draw(); })
    ];
  };

  // Implement onRemove
  Label.prototype.onRemove = function() {
    this.div_.parentNode.removeChild(this.div_);

    // Label is removed from the map, stop updating its position/text.
    for (var i = 0, I = this.listeners_.length; i < I; ++i) {
      google.maps.event.removeListener(this.listeners_[i]);
    }
  };

  // Implement draw
  Label.prototype.draw = function() {
    var projection = this.getProjection();
    var position = projection.fromLatLngToDivPixel(this.get('position'));

    var div = this.div_;
    div.style.left = position.x + 'px';
    div.style.top = position.y + 'px';
    div.style.display = 'block';

    this.span_.innerHTML = this.get('text').toString();
  };

var data_obj;
var markers = [];
d3.select('#submit').on('click', function() {
  var txt = d3.select('#vals').property('value');
  d3.json('/geotag?vals=' + encodeURIComponent(txt), function(error, json) {
      d3.select('#results').style('display', 'table').selectAll('tr.cat').remove();
      var data_obj = json;
      var data = json.response.filter(function(d, i) {
        return (+d['likelihood'] >= 0.0000005) || (i <= 15);
      });
      data.forEach(function(d) {
        var cat = d.assignment[0];
        cat.score = +cat['normalized_prob'];
        cat.cats = (/[^|]*$/.exec(cat['category'][0]) + ', ' +
                    cat['category'][1] + ', ' +
                    /[^|]*$/.exec(cat['category'][2]));
        cat.coverage = +cat['stats']['coverage']/+cat['stats']['total'];
        cat.opacity = Math.sqrt(Math.sqrt(cat.score)) + 0.2;
      });
      function c(d) {return d.assignment[0];}

      var cats = d3.select('#results').selectAll('tr.cat')
                   .data(data);
      var score_fmt = d3.format('.2%');
      var fmt = d3.format('.2f');

      var trs = cats.enter()
          .append('tr')
          .attr('class', 'cat')
          .style('opacity', function(d) {return c(d).opacity;})
          .style('cursor', 'pointer');

      var categories = trs.append('td')
          .text(function(d) {return c(d).txt;})
          .attr('title', function(d) {return c(d).cats;});

      var cov = trs.append('td')
          .text(function(d) {return fmt(c(d).coverage);})
          //.style('display', 'inline-block')
          .style('min-width', '45px')
          .style('text-align', 'right');

      var amb = trs.append('td')
          .text(function(d) {return fmt(c(d).stats.ambiguity);})
          //.style('display', 'inline-block')
          .style('min-width', '50px')
          .style('text-align', 'right');

      var scores = trs.append('td')
          .text(function(d) {return score_fmt(c(d).score);})
          //.style('display', 'inline-block')
          .style('width', '60px')
          .style('text-align', 'right');

      trs.on('click', function() {
        // clear markers
        markers.forEach(function(m) {
          m.setMap(null);
        });
        markers = [];
        var pts = d3.select(this).datum().interpretations[0];
        var seen = {};
        pts.forEach(function(d) {
          if (typeof seen[d['name']] === 'undefined') {
            markers.push(new Label({
              map: map,
              position: new google.maps.LatLng(+d['latitude'],
              +d['longitude']),
              text: d['name']
            }));
            seen[d['name']] = true;
          }
        });
      });
    });
  d3.event.preventDefault();
});
var map;
function initializeMap() {
  var mapOptions = {
    center: new google.maps.LatLng(10, 0),
    zoom: 1,
    mapTypeId: google.maps.MapTypeId.ROADMAP,
    streetViewControl: false
  };
  map = new google.maps.Map(document.getElementById('map-canvas'),
    mapOptions);
}
google.maps.event.addDomListener(window, 'load', initializeMap);
</script>
"""

def run_web(geowhiz):
    app = Flask(__name__)
    app.debug = True

    @app.route('/')
    def index():
        return page

    @app.route('/geotag')
    def geotag():
        vals = request.args.get('vals', '')
        rows = []
        for row in vals.split('\n'):
            if len(row.strip()) > 0:
                rows.append([row.strip()])
                #rows.append([c.strip() for c in row.split(',')])
        grid = list(itertools.izip_longest(*rows))
        geotag_results = geowhiz.full_geotag(grid)

        for r in geotag_results:
            for g in r['assignment']:
                g['txt'] = category_helpers.cat_text(g['category'],
                                                     g['stats']['total'])

        return jsonify({'response': geotag_results})

    app.run(host='0.0.0.0')
