/* global document */
/* global window */
/* global google */
/* global d3 */
/* global console */
/* jshint globalstrict: true */
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
}
Label.prototype = new google.maps.OverlayView();

// Implement onAdd
Label.prototype.onAdd = function() {
  var pane = this.getPanes().overlayLayer;
  pane.appendChild(this.div_);

  // Ensures the label is redrawn if the text or position is changed.
  var me = this;
  this.listeners_ = [
    google.maps.event.addListener(this, 'position_changed', function() {
      me.draw();
    }),
    google.maps.event.addListener(this, 'text_changed', function() {
      me.draw();
    })
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

/* Map Options UI */
var fit_to_pts = false,
    show_all_pts = false;
d3.select('#zoom-to-points').on('change', function() {
  fit_to_pts = this.checked;
  if (fit_to_pts) {updatePts();}
});
d3.select('#show-all-points').on('change', function() {
  show_all_pts = this.checked;
  updatePts();
});

function reveal(sel) {
  d3.select(sel)
      .style('display', null)
      .style('visibility', null)
    .transition()
      .style('opacity', 1.0);
}

/* GeoWhiz UI */
var data_obj;
var markers = {};
var cat_data = {};
d3.select('#submit').on('click', function() {
  var txt = d3.select('#vals').property('value');
  d3.json('./geotag?vals=' + encodeURIComponent(txt), function(error, json) {
    reveal('#results-container');
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
      cat_data = d;
      showTrees(cat_data);
      updatePts(cat_data);
    });
  });
  d3.event.preventDefault();
});

function updatePts() {
  var pts = cat_data.cell_interpretations[0],
      seen = {};

  pts.forEach(function(p) {
    p.position = new google.maps.LatLng(+p.latitude, +p.longitude);
    p.xy = proj().fromLatLngToDivPixel(p.position);
  });

  if (!show_all_pts) {
    pts = pts.filter(function(p) {return !!p.likely;});
  }

  showPts(pts);
  if (fit_to_pts) {fitBounds(pts);}
}

function showPts(pts) {
  pts.forEach(function(d) {
    d.old_id = d.id;
    if (show_all_pts) {d.id = 'gid' + d.geonameid;}
    else {d.id = d.name;}
  });

  var marker_divs = d3.selectAll('div.marker')
      .data(pts, function(d) {return d.id;});

  marker_divs
      .style('opacity', 0.5)
    .transition().duration(150)
      .style('left', function(d) {return d.xy.x + 'px';})
      .style('top', function(d) {return d.xy.y + 'px';})
      .each(function(d) {
        if (!(d.id in markers)) {
          markers[d.id] = markers[d.old_id];
          delete markers[d.old_id];
        }
        markers[d.id].position = d.position;
      })
      .each('end', function() {
        d3.select(this)
            .each(function (d) {
              d.xy = proj().fromLatLngToDivPixel(d.position);
            })
            .style('opacity', 1.0)
            .style('left', function(d) {return d.xy.x + 'px';})
            .style('top', function(d) {return d.xy.y + 'px';});
      });

  marker_divs.enter()[0].forEach(function(p) {
    var d = p.__data__;
    d.__marker__ = new Label({
      map: map,
      position: new google.maps.LatLng(+d.latitude, +d.longitude),
      text: d.name,
      __data__: d
    });
    markers[d.id] = d.__marker__;
  });

  marker_divs.exit()
    .each(function(d) {
      if (d.id in markers) {
        markers[d.id].setMap(null);
        delete markers[d.id];
      } else {
        if (d.old_id in markers) {
          markers[d.old_id].setMap(null);
          delete markers[d.old_id];
        } else {
          console.log('d.id: ' + d.id + ', d.old_id: ' + d.old_id + ', markers: ' + JSON.stringify(Object.keys(markers)));
        }
      }
    })
    .remove();
}

function fitBounds(pts) {
  if (!pts.length) {return;}
  var bounds = new google.maps.LatLngBounds();
  pts.forEach(function(p) {
    bounds.extend(new google.maps.LatLng(+p.latitude, +p.longitude));
  });
  map.fitBounds(bounds);
}

//
// taxonomy tree visualization
//

var width = 650,
    place_list_width = 80,
    height = 500,
    node_width = 70,
    node_height = 30;

var tree = d3.layout.tree()
    .separation(function() {return 1;})
    .nodeSize([node_height, node_width]);

var diagonal = d3.svg.diagonal()
    .projection(function(d) { return [d.y, d.x]; });

function connector(d, i) {
  var p0 = d.source,
      p3 = d.target,
      m1 = (2*p0.y/3 + p3.y/3),
      m2 = (p0.y/3 + 2*p3.y/3),
      p = [p0, {x: p0.x, y: m1}, {x: p3.x, y: m2}, p3];
  p = p.map(diagonal.projection());
  return 'M' + p[0] + 'C' + p[1] + ' ' + p[2] + ' ' + p[3];
}


var svg = d3.selectAll('#tree-svg')
    .attr('width', width + place_list_width)
    .attr('height', height);
var tax = svg.append('g')
    .attr('transform', 'translate(-25,' + node_height + ')');

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
    if (s === '') { throw new Error('something went wrong'); }
    if (s in hierarchy_lookup) { return hierarchy_lookup[s]; }
    if (code.length == 1) { parent = root;}
    else if (!(ps in hierarchy_lookup)) {
      parent = addElement(code.slice(0, code.length - 1));
    } else { parent = hierarchy_lookup[s]; }
    var name = code[code.length-1];
    if (name == 'dim0') {name = 'Place';}
    else if (name == 'dim1') {name = 'Earth';}
    else if (name == 'dim2') {name = 'Pop ≥ 0';}
    var new_element = {
      'name': name,
      'code': s,
      'children': []
    };
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
  var dim1_offset = dim0_max - dim1_min + 2.5 * node_height + dim0_offset;
  var dim2_offset = dim1_max - dim2_min + 2.5 * node_height + dim1_offset;
  nodes.forEach(function(n) {
    if (n.code.indexOf('dim0') != -1) {
      n.x += dim0_offset;
    } else if (n.code.indexOf('dim1') != -1) {
      n.x += dim1_offset;
    } else if (n.code.indexOf('dim2') != -1) {
      n.x += dim2_offset;
    }
  });
  //nodes.forEach(function(n) {
  //  n.x += n.depth * 3;
  //});

  //
  // Add place list and edges
  //
  var place_nodes = [],
      place_edges = [],
      offset = 0;

  pts.forEach(function(d, i) {
    var place = {};
    place.pt = d;
    if (d.likely) {offset += node_height;}
    place.x = i * node_height + offset;
    place.y = width + node_width / 2.0;
    place_nodes.push(place);
    var t1 = node_lookup[['dim0'].concat(d.cat[0].split('|').slice(1)).join('|')],
        t2 = node_lookup[['dim1'].concat(d.cat[1].split('|').slice(1)).join('|')],
        t3 = node_lookup[['dim2'].concat(d.cat[2].split('|').slice(1)).join('|')];
    console.log('dim0' + d.cat[0].slice(d.cat[0].indexOf('|')));
    place_edges.push({'source': place, 'target': t1});
    place_edges.push({'source': place, 'target': t2});
    place_edges.push({'source': place, 'target': t3});
  });

  var place_max = d3.max(place_nodes, function(d) {return d.x;});
  var max_height = Math.max(dim2_max + dim2_offset, place_max);
  console.log(place_max);
  console.log(max_height);

  //svg.attr('height', Math.max(height, dim2_max + dim2_offset + node_height * 2));
  reveal('#tree-container');
  reveal('#map-container');
  svg.attr('height', max_height + node_height * 2);

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
      .attr('stroke', function(d) {
        return d3.rgb(color(d.source.pt.name)).brighter();
      })
      .attr('d', connector);

  place_link
      .filter(function(d) {return d.source.pt.likely;})
      .attr('stroke-width', '3px');

  place_link
      .filter(function(d) {return !d.source.pt.likely;})
      .attr('stroke-width', '1px')
      .attr('opacity', '0.5')
      .attr('stroke-dasharray', '2,2');

  var node_group = tax.selectAll("g.node")
      .data(nodes, function(d) {return d.code;});

  node_group.exit().remove();

  var node = node_group.enter().append("g")
      .attr("class", "node")
      .attr("transform", function(d) {
        return "translate(" + d.y + "," + d.x + ")";
      });

  node.append("circle")
      .attr("r", 4.5);

  node.append("text")
      .attr("x", -5)
      .attr("y", 12)
      .attr("text-anchor", "end")
      .text(function(d) { return d.name; });

  var places = tax.selectAll('g.place')
      .data(place_nodes);

  var place = places.enter().append('g')
      .attr('class', 'place')
      .attr('transform', function(d) {
        return 'translate(' + d.y + ',' + d.x + ')';
      });

  place.filter(function(d) {return !d.pt.likely;})
      .attr('opacity', 0.7);

  place.append('circle')
      .attr('r', 4.5);

  place.append('text')
      .attr('x', 8)
      .attr('y', 3)
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
