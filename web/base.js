// Keep plugin requests on FPP's origin, while retaining direct runtime access.
function wledURL(path) {
  return (window.location.pathname.startsWith('/fpp-wled/') || document.getElementById('fpp-wled-settings') ? '/fpp-wled' : '') + path;
}
function wledSettingsURL(hash = '') {
  return location.pathname.startsWith('/fpp-wled/') ? '/plugin.php?plugin=FPP_WLED_10.x&page=settings.php' + hash : '/settings' + hash;
}
function wledFetch(path, options) {
  return window.fetch(wledURL(path), options);
}
