"use strict";

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
  div.classList.add('marker');
  div.__data__ = opt_options.__data__;
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
    google.maps.event.addListener(
      this,
      'position_changed',
      function() { me.draw(); }
    ),
    google.maps.event.addListener(
      this,
      'text_changed',
      function() { me.draw(); }
    )
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


/* GeoWhiz UI */
var data_obj;
var markers = {};
d3.select('#submit').on('click', function() {
  var txt = d3.select('#vals').property('value');
  d3.json('./geotag?vals=' + encodeURIComponent(txt), function(error, json) {
    d3.select('#results').style('display', 'table').selectAll('tr.cat').remove();
    var data_obj = json;
    var data = json.assignments.filter(function(d, i) {
      return (+d.likelihood >= 0.0000005) || (i <= 15);
    });
    data.forEach(function(d) {
      var cat = d.categories[0];
      cat.score = +cat.normalized_prob;
      cat.cats = (/[^|]*$/.exec(cat.category[0]) + ', ' +
                  cat.category[1] + ', ' +
                  /[^|]*$/.exec(cat.category[2]));
      cat.coverage = (+cat.stats.coverage) / (+cat.stats.total);
      cat.opacity = Math.sqrt(Math.sqrt(cat.score)) + 0.2;
    });
    function c(d) {return d.categories[0];}

    var cats = d3.select('#results > tbody').selectAll('tr.cat').data(data);
    var score_fmt = d3.format('.2%');
    var fmt = d3.format('.2f');

    var trs = cats.enter().append('tr')
        .attr('class', 'cat')
        .style('opacity', function(d) {return c(d).opacity;})
        .style('cursor', 'pointer');

    var categories = trs.append('td')
        .text(function(d) {return c(d).txt;})
        .attr('title', function(d) {return c(d).cats;});

    var cov = trs.append('td')
        .text(function(d) {return fmt(c(d).coverage);})
        .style('min-width', '45px')
        .style('text-align', 'right');

    var amb = trs.append('td')
        .text(function(d) {return fmt(c(d).stats.ambiguity);})
        .style('min-width', '50px')
        .style('text-align', 'right');

    var scores = trs.append('td')
        .text(function(d) {return score_fmt(c(d).score);})
        .style('width', '60px')
        .style('text-align', 'right');

    trs.on('click', function(d) {
      showTrees(d);

      var pts = d.cell_interpretations[0],
          seen = {};

      pts = pts.filter(function(p) {
        if (!(p.name in seen)) {seen[p.name] = true; return true;}
        else {return false;}
      });

      pts.forEach(function(p) {
        p.position = new google.maps.LatLng(+p.latitude, +p.longitude);
        p.xy = proj().fromLatLngToDivPixel(p.position);
      });
      showPts(pts);
    });
  });
  d3.event.preventDefault();
});

function showPts(pts) {
  var marker_divs = d3.selectAll('div.marker').data(pts, function(d) {return d.name;});

  marker_divs
      .style('opacity', 0.5)
    .transition().duration(150)
      .style('left', function(d) {return d.xy.x + 'px';})
      .style('top', function(d) {return d.xy.y + 'px';})
      .each(function(d) {markers[d.name].position = d.position;})
      .each('end', function() {
        d3.select(this).style('opacity', 1.0);
      });

  marker_divs.enter()[0].forEach(function(p) {
    var d = p.__data__;
    d.__marker__ = new Label({
      map: map,
      position: new google.maps.LatLng(+d.latitude, +d.longitude),
      text: d.name,
      __data__: d
    });
    markers[d.name] = d.__marker__;
  });

  marker_divs.exit()
    .each(function(d) {
      markers[d.name].setMap(null);
      delete markers[d.name];
    })
    .remove();
}

//
// taxonomy tree visualization
//

var width = 800,
    place_list_width = 200,
    height = 500,
    node_width = 80,
    node_height = 30;

var tree = d3.layout.tree()
    .separation(function() {return 1;})
    .nodeSize([node_height, node_width]);

var diagonal = d3.svg.diagonal()
    .projection(function(d) { return [d.y, d.x]; });

var svg = d3.selectAll('#tree-svg')
    .attr('width', width + place_list_width)
    .attr('height', height)
var tax = svg.append('g')
    .attr('transform', 'translate(30,' + node_height + ')');

function showTrees(assignment) {
  // process pts into tree fmt
  var cat = assignment.categories[0].category,
      pts = assignment.cell_interpretations[0];

  var color = d3.scale.category10();

  var root = {'name': 'Taxonomy', 'children': []};
  var hierarchy_lookup = {};

  function addElement(code) {
    var s = code.join('|'),
        ps = code.slice(code.length - 1).join('|'),
        parent = null;
    if (s == '') { throw new Error('something went wrong'); }
    if (s in hierarchy_lookup) { return hierarchy_lookup[s]; }
    if (code.length == 1) { parent = root;}
    else if (!(ps in hierarchy_lookup)) {
      parent = addElement(code.slice(0, code.length - 1));
    } else { parent = hierarchy_lookup[s]; }
    var new_element = {
      'name': code[code.length-1],
      'code': s,
      'children': []
    }
    parent.children.push(new_element);
    hierarchy_lookup[s] = new_element;
    return new_element;
  }

  pts.forEach(function(p) {
    var c = p.cat;  // this needs to be fixed

    // add each dimension to taxonomy tree
    c.forEach(function(dim, i) {
      var dim_name = ['dim' + i],
          dim_elements = dim.split('|').slice(1);
      addElement(dim_name.concat(dim_elements));
    });
  });

  var nodes = tree.nodes(root).filter(function(d) {return d.depth > 0;}),
      links = tree.links(nodes),
      node_lookup = {};

  nodes.forEach(function(d) {
    node_lookup[d.code] = d;
  });

  // adjust vertical placement of dimensions
  var dim0_min, dim1_min, dim2_min, dim0_max, dim1_max, dim2_max;
  dim0_min = dim1_min = dim2_min = 100000;
  dim0_max = dim1_max = dim2_max = -100000;
  nodes.forEach(function(n) {
    if (n.code.indexOf('dim0') != -1) {
      dim0_min = Math.min(dim0_min, n.x);
      dim0_max = Math.max(dim0_max, n.x);
    } else if (n.code.indexOf('dim1') != -1) {
      dim1_min = Math.min(dim1_min, n.x);
      dim1_max = Math.max(dim1_max, n.x);
    } else if (n.code.indexOf('dim2') != -1) {
      dim2_min = Math.min(dim2_min, n.x);
      dim2_max = Math.max(dim2_max, n.x);
    }
  });
  var dim0_offset = -dim0_min;
  var dim1_offset = dim0_max - dim1_min + 2 * node_height + dim0_offset;
  var dim2_offset = dim1_max - dim2_min + 2 * node_height + dim1_offset;
  nodes.forEach(function(n) {
    if (n.code.indexOf('dim0') != -1) {
      n.x += dim0_offset;
    } else if (n.code.indexOf('dim1') != -1) {
      n.x += dim1_offset;
    } else if (n.code.indexOf('dim2') != -1) {
      n.x += dim2_offset;
    }
  });

  //
  // Add place list and edges
  //
  var place_nodes = [],
      place_edges = [];

  pts.forEach(function(d, i) {
    var place = {};
    place.pt = d;
    place.x = i * node_height;
    place.y = width;
    place_nodes.push(place);
    var t1 = node_lookup[['dim0'].concat(d.cat[0].split('|').slice(1)).join('|')],
        t2 = node_lookup[['dim1'].concat(d.cat[1].split('|').slice(1)).join('|')],
        t3 = node_lookup[['dim2'].concat(d.cat[2].split('|').slice(1)).join('|')];
    console.log('dim0' + d.cat[0].slice(d.cat[0].indexOf('|')));
    place_edges.push({'source': place, 'target': t1});
    place_edges.push({'source': place, 'target': t2});
    place_edges.push({'source': place, 'target': t3});
  });

  svg.attr('height', Math.max(height, dim2_max + dim2_offset + node_height * 2));

  tax.selectAll('path.link').remove();
  tax.selectAll('g.node').remove();
  tax.selectAll('path.place-link').remove();
  tax.selectAll('g.place').remove();

  var link = tax.selectAll("path.link")
      .data(links)
    .enter().append("path")
      .attr("class", "link")
      .attr("d", diagonal);

  var place_link = tax.selectAll("path.place-link")
      .data(place_edges)
    .enter().append("path")
      .attr("class", "place-link")
      .attr('stroke', function(d) {return d3.rgb(color(d.source.pt.name)).brighter();})
      .attr('stroke-width', function(d) {return d.source.pt.likely ? '2px' : '1px';})
      .attr("d", diagonal);

  var nodes = tax.selectAll("g.node")
      .data(nodes, function(d) {return d.code;});

  nodes.exit().remove();

  var node = nodes.enter().append("g")
      .attr("class", "node")
      .attr("transform", function(d) { return "translate(" + d.y + "," + d.x + ")"; })

  node.append("circle")
      .attr("r", 4.5);

  node.append("text")
      .attr("dx", -8)
      .attr("dy", 10)
      .attr("text-anchor", "end")
      .text(function(d) { return d.name; });

  var places = tax.selectAll('g.place')
      .data(place_nodes);

  var place = places.enter().append('g')
      .attr('class', 'place')
      .attr('transform', function(d) {return 'translate(' + d.y + ',' + d.x + ')';});

  place.append('circle')
      .attr('r', 4.5);

  place.append('text')
      .attr('dx', 8)
      .attr('dy', 3)
      .text(function(d) {return d.pt.name;});
}

var map, proj;

function initializeMap() {
  var mapOptions = {
    center: new google.maps.LatLng(10, 0),
    zoom: 1,
    mapTypeId: google.maps.MapTypeId.ROADMAP,
    streetViewControl: false
  };
  map = new google.maps.Map(document.getElementById('map-canvas'), mapOptions);

  // hack to get easy access to projection
  // from http://stackoverflow.com/questions/1538681/
  var overlay = new google.maps.OverlayView();
  overlay.draw = function() {};
  overlay.setMap(map);
  proj = function() {
    return overlay.getProjection();
  };
}
google.maps.event.addDomListener(window, 'load', initializeMap);
