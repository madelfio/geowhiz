(function() {
  "use strict";

  function geowhiz_json(url, callback) {
    var xhr = new XMLHttpRequest();

    xhr.onreadystatechange = ensureReadiness;

    function ensureReadiness() {
      if(xhr.readyState < 4) {
        return;
      }

      if(xhr.status !== 200) {
        return;
      }

      // all is well
      if(xhr.readyState === 4) {
        callback(xhr);
      }
    }

    xhr.open('GET', url, true);
    xhr.send('');
  }

  function geowhiz_geocode(arr, callback) {
    geowhiz_json('./geotag?vals=' + encodeURIComponent(arr.join('\n')), function(request) {
      callback(JSON.parse(request.responseText));
    });
  }

  window.geowhiz = {
    geocode: geowhiz_geocode
  };
})();
