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
var fit_to_pts = true,
    show_all_pts = false,
    prox_resolution = false;
d3.select('#zoom-to-points').on('change', function() {
  fit_to_pts = this.checked;
  if (fit_to_pts) {updatePts();}
});
d3.select('#show-all-points').on('change', function() {
  show_all_pts = this.checked;
  updatePts();
});
d3.select('#prox-resolution').on('change', function() {
  prox_resolution = this.checked;
  showTrees(cat_data);
  updatePts();
});

function reveal(sel) {
  d3.select(sel)
      .style('display', null)
      .style('visibility', null)
    .transition().duration(600)
      .style('opacity', 1.0);
}

function isHighlighted(pt) {
  if (prox_resolution) {return !!pt.prox_likely;}
  else {return !!pt.likely;}
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
    data_obj = json;
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
      cat.opacity = Math.sqrt(Math.sqrt(cat.score))*0.7 + 0.3;
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
      trs
        .style('background-color', 'white')
        .style('color', null)
        .style('opacity', function(d) {return c(d).opacity;});
      d3.select(this)
        .style('background-color', 'red')
        .style('color', 'white')
        .style('opacity', function(d) {return c(d).opacity * 2;});

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
    pts = pts.filter(function(p) {return isHighlighted(p);});
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
    .transition()
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
  // Don't zoom in too far on only one marker
  if (bounds.getNorthEast().equals(bounds.getSouthWest())) {
     var extendPoint1 = new google.maps.LatLng(bounds.getNorthEast().lat() + 0.01, bounds.getNorthEast().lng() + 0.01);
     var extendPoint2 = new google.maps.LatLng(bounds.getNorthEast().lat() - 0.01, bounds.getNorthEast().lng() - 0.01);
     bounds.extend(extendPoint1);
     bounds.extend(extendPoint2);
  }
  map.fitBounds(bounds);
}

//
// taxonomy tree visualization
//

var width = 640,
    place_list_width = 110,
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
      m1 = 0.8 * p0.y + 0.2 * p3.y,
      m2 = 0.6 * p0.y + 0.4 * p3.y,
      p = [p0, {x: p0.x, y: m1}, {x: p3.x, y: m2}, p3];
  p = p.map(diagonal.projection());
  return 'M' + p[0] + 'C' + p[1] + ' ' + p[2] + ' ' + p[3];
}

// from http://bl.ocks.org/mbostock/6738109
var superscript = "⁰¹²³⁴⁵⁶⁷⁸⁹",
    formatPower = function(d) { return (d + "").split("").map(function(c) { return superscript[c]; }).join(""); };


var svg = d3.select('.tree-buffer')
  .append('svg')
    .attr('width', width + place_list_width)
    .attr('height', height);
var tax = svg.append('g')
    .attr('transform', 'translate(-25,10)');

function showTrees(assignment) {
  // process pts into tree fmt
  var cat = assignment.categories[0].category,
      pts = assignment.cell_interpretations[0];

  //var color = d3.scale.category10();
  var color = d3.scale.ordinal()
      .range(["#8cf64b", "#17becf", "#d62728", "#7f7f7f", "#e377c2",
             "#c49c94", "#98df8a", "#c7c7c7", "#2ca02c", "#dbdb8d",
             "#1f77b4", "#ff7f0e", "#ff9896", "#c5b0d5", "#bcbd22",
             "#9467bd", "#9edae5", "#aec7e8"]);

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
    else if (name.indexOf('Prominent') === 0) {
      name = 'Pop ≥ 10' + formatPower(+name.slice(name.length-1) - 1);
    }
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

  var buffer_height = parseInt(d3.select('.tree-buffer').style('height'), 10) - 5 || 0,
      height_diff = buffer_height - (dim2_max + dim2_offset + node_height);

  var dim1_offset2 = 0,
      dim2_offset2 = 0;

  if (height_diff > 0) {
    dim1_offset2 = height_diff / 2;
    dim2_offset2 = height_diff;

    window.dim1_offset2 = dim1_offset2;
    window.dim2_offset2 = dim2_offset2;
    nodes.forEach(function(n) {
      if (n.code.indexOf('dim1') != -1) {
        n.x += dim1_offset2;
      } else if (n.code.indexOf('dim2') != -1) {
        n.x += dim2_offset2;
      }
    });
  }

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
    place_edges.push({'source': place, 'target': t1});
    place_edges.push({'source': place, 'target': t2});
    place_edges.push({'source': place, 'target': t3});
  });

  var place_range = d3.extent(place_nodes, function(d) {return d.x;}),
      place_height_diff = buffer_height - 2 * node_height - place_range[1],
      place_offset = 0;

  if (place_height_diff > 0) {
    // center vertically if there's space
    place_offset = (place_height_diff - place_range[0]) / 2;
    place_nodes.forEach(function(d) {
      d.x += place_offset;
    });
  }

  var max_height = Math.max(dim2_max + dim2_offset + dim2_offset2, place_range[1] + place_offset);

  reveal('#tree-container');
  reveal('#map-container');
  svg.transition().attr('height', max_height + node_height);

  tax.selectAll('path.link').remove();
  tax.selectAll('g.node').remove();
  tax.selectAll('path.place-link').remove();
  tax.selectAll('g.place').remove();

  tax.selectAll("path.link")
      .data(links)
    .enter().append("path")
      .attr("class", "link")
      .attr("d", diagonal);

  var place_link = tax.selectAll("path.place-link")
      .data(place_edges)
    .enter().append("path")
      .attr("class", "place-link")
      .attr('stroke', function(d) {
        return d3.rgb(color(d.source.pt.name)).brighter(0.1);
      })
      .attr('d', connector);

  place_link
      .filter(function(d) {return isHighlighted(d.source.pt);})
      .attr('stroke-width', '2px');

  place_link
      .filter(function(d) {return !isHighlighted(d.source.pt);})
      .attr('stroke-width', '1.5px')
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

  node.append('title')
      .text(function(d) {return data_obj.cat_node_text[d.code];});

  var places = tax.selectAll('g.place')
      .data(place_nodes);

  var place = places.enter().append('g')
      .attr('class', 'place')
      .attr('transform', function(d) {
        return 'translate(' + d.y + ',' + d.x + ')';
      });

  place.filter(function(d) {return !isHighlighted(d.pt);})
      .attr('opacity', 0.7);

  place.append('circle')
      .attr('r', 4.5);

  place.append('text')
      .attr('x', 8)
      .attr('y', 3)
      .text(function(d) {return d.pt.name;});

  place.append('title')
      .text(function(d) {
        return d.pt.official_name + '\nPop: ' + d.pt.population
      });


  place.on('mouseover', function(p) {
    var place_sel = d3.select(this);
    place_link
      .filter(function(d) {return d.source.pt.geonameid === p.pt.geonameid;})
      .transition()
        .attr('stroke-width', '4px');
    place_sel
      .transition()
        .attr('opacity', 1);
    place_sel.selectAll('circle')
      .transition()
        .attr('fill', 'steelblue');
  }).on('mouseout', function(p) {
    var place_sel = d3.select(this);
    place_link
      .filter(function(d) {return d.source.pt.geonameid === p.pt.geonameid;})
      .transition()
      .attr('stroke-width', function(d) {return isHighlighted(d.source.pt) ? '2px' : '1.5px';});
    place_sel
      .transition()
        .attr('opacity', function(d) {return isHighlighted(p.pt) ? 1 : 0.5;});
    place_sel.selectAll('circle')
      .transition()
        .attr('fill', '#aaa');
  });
}

var sample_lists = [
  ['Dublin', 'Athens', 'Rome'],
  ['Springfield', 'Alexandria', 'Arlington', 'Vienna'],
  ['White House', 'Washington Monument', 'Lincoln Memorial', 'The Mall'],
  ['Corpus Christi', 'Jacksonville', 'New York City', 'Phoenix',
    'Sonoma County', 'Williamsburg'],
  ['Allen Park', 'Southgate', 'Birmingham', 'Flint', 'Detroit', 'Taylor',
    'McMillan', 'Bellville', 'Grass Lake'],
  ['San Juan', 'Newark', 'Hackensack', 'Paterson', 'Kearny', 'Bronx',
    'Westchester', 'Queens', 'Staten Island', 'Hicksville'],
  ['Encino', 'Pacific Palisades', 'Rancho Park'],
  ['B.C.', 'Alberta', 'Saskatchewan', 'Manitoba', 'Ontario', 'Quebec',
    'New Brunswick', 'Nova Scotia', 'Prince Edward Island', 'Newfoundland'],
  ['Reinbek', 'Heidelberg', 'Frankfurt', 'Stuttgart', 'München', 'Hamburg',
    'Paderborn', 'Augsburg'],
  ['Doha', 'Osaka', 'Dakar', 'Hengelo', 'Belem', 'Filothei', 'Beograd', 'Gotzis'],
  ['Fort Rucker', 'Redsone Arsenal', 'Fort Richardson', 'Fort Huachuca',
    'Pine Bluff Army Depot'],
  ['Leicester', 'Macclesfield', 'Aberdeen', 'Broxburn', 'Tayside', 'Yeovil',
    'Inverurie', 'Crawford', 'Bournemouth', 'Newport', 'Ipswich'],
  ['Aliso Viejo', 'Anaheim', 'Anaheim Hills', 'Brea', 'Buena Park',
    'Corona del Mar', 'Costa Mesa', 'Coto De Caza', 'Cypress', 'Dana Point',
    'Laguna Woods'],
  ['Brazil', 'China', 'Kazakhstan', 'Madagascar', 'Mozambique', 'Portugal',
    'Russia', 'United States', 'Zambia'],
  ['Sat', 'Sun', 'Thu', 'Fri', 'Mon', 'Wed'],
  ['Norway', 'Sweden', 'Australia', 'Canada', 'Netherlands', 'Belgium',
    'Iceland', 'United States', 'Japan', 'Ireland'],
  ['Achille', 'Afton', 'Agra', 'Albion', 'Alex', 'Aline', 'Allen', 'Tulsa',
    'Amber', 'Sand Springs'],
  ['Bucuresti', 'Ploiesti', 'Campina', 'Mizil', 'Valenii de Munte', 'Pitesti',
    'Campulung Muscel', 'Curtea de Arges', 'Calarasi', 'Oltenita',
    'Alexandria'],
  ['Paris', 'London', 'Rome'],
  ['Babylon', 'Center Moriches', 'Long Beach', 'Groton', 'Onset', 'Baltimore',
    'San Francisco', 'Topsail Beach', 'St Petersburg', 'North Haven'],
  ['Afghanistan', 'Albania', 'Algerie', 'Amerikansk Samoa',
    'Amerikanske Jomfruyene, de', 'Andorra', 'Angola', 'Anguilla',
    'Antigua og Barbuda', 'Argentina'],
  ['Lazio', 'Trentino Alto Adige', 'Lazio', 'Lombardy', 'Tuscany',
    'Umbria', 'Lombardy', 'Campania', 'Trentino Alto Adige', 'Emilia Romagna'],
  ['Harris', 'El Paso', 'Bexar', 'Dallas', 'Collin'],
  ['Johor Bahru', 'Puchong', 'Petaling Jaya', 'Kuala Lumpur', 'Kota Baharu',
    'Bukit Jalil', 'Melaka', 'Shah Alam', 'Kuala Lumpur', 'Jalan Sultan Ismail'],
  ['Sydney', 'Abaco', 'Hong Kong', 'Malau', 'Bordeaux', 'Tuticorin',
    'New Mangalore', 'Bushehr', 'Bahonar', 'Sirri Island']
];

function Modal(selector) {
  var modal = {},
      sel = d3.select(selector),
      overlay = null,
      container = null,
      div = null;
  modal.open = function() {
    overlay = d3.select('body')
      .append('div')
        .style('background-color', 'black')
        .style('opacity', 0.5)
        .style('height', '100%')
        .style('width', '100%')
        .style('position', 'absolute')
        .style('top', '0')
        .style('left', '0')
        .style('padding', '10px')
        .style('z-index', '1001');
    container = d3.select('body')
      .append('div')
        .attr('class', 'modal-container')
        .style('position', 'absolute')
        .style('top', '50%')
        .style('left', '50%')
        .style('z-index', '1002')
      .append('div')
        .attr('class', 'modal-wrap');

    sel.style('display', 'block');
    container.node().appendChild(sel.node());
  };
  modal.close = function() {
    overlay.style('display', 'none');
    container.style('display', 'none');
  };
  return modal;
}

var samples = d3.select('#sample-lists').selectAll('div.sample')
  .data(sample_lists).enter()
  .append('div')
    .attr('class', 'sample')
    .on('click', function(d) {
      d3.select('#vals')
        .property('value', d.join('\n'));
      modal.close();
    });

samples.selectAll('span')
  .data(function(d) {return d.filter(function(_, i) {return (i <= 5);});}).enter()
  .append('span')
    .attr('class', 'sample-place')
    .text(function(d, i) {return i < 5 ? d : '...';});

// set up modal dialog
var modal = Modal('#sample-popup');
d3.select('#modal-open').on('click', function() {
  modal.open();
  return false;
});
d3.select('body').on('keydown', function() {
  if (d3.event.keyCode == 27) {modal.close();}
});


var map, proj;

function initializeMap() {
  var mapOptions = {
    center: new google.maps.LatLng(10, 0),
    zoom: 1,
    mapTypeId: google.maps.MapTypeId.ROADMAP,
    streetViewControl: false,
    panControl: false,
    zoomControl: false
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
