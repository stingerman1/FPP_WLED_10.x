<?php
// Served through FPP's plugin wrapper, inheriting its web access controls.
// The custom header forces cross-origin browsers to preflight; no CORS access
// is granted here. Never expose the credential through a GET or page markup.
header('Content-Type: application/json');
header('Cache-Control: no-store');
header('X-Content-Type-Options: nosniff');
header('Referrer-Policy: no-referrer');
if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    http_response_code(405);
    header('Allow: POST');
    echo json_encode(['error' => 'Use the Get runtime token button on the FPP plugin page.']);
    exit;
}
if (!isset($_GET['nopage']) || ($_SERVER['HTTP_X_FPP_WLED_ACTION'] ?? '') !== 'retrieve-token'
    || ($_SERVER['HTTP_SEC_FETCH_SITE'] ?? '') === 'cross-site') {
    http_response_code(403);
    echo json_encode(['error' => 'Request the token from this FPP plugin page.']);
    exit;
}
$path = '/home/fpp/media/config/plugin.FPP_WLED_10.x/auth.json';
$auth = is_readable($path) ? json_decode(file_get_contents($path), true) : null;
if (!is_array($auth) || !is_string($auth['token'] ?? null) || strlen($auth['token']) < 32) {
    http_response_code(503);
    echo json_encode(['error' => 'The runtime token is unavailable. Complete installation and start the fpp-wled service, then try again.']);
    exit;
}
echo json_encode(['token' => $auth['token']]);
exit;
