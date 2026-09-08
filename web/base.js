// Keep plugin requests on FPP's origin, while retaining direct runtime access.
function wledURL(path) {
  return (window.location.pathname.startsWith('/wled/') ? '/wled' : '') + path;
}
function wledFetch(path, options) {
  return window.fetch(wledURL(path), options);
}
