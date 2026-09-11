<?php
// Local browser fixture only: minimal host shell and proxy to the test runtime.
$path=parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH);
if(str_starts_with($path,'/fpp-wled/')){
 $url='http://127.0.0.1:18787'.substr($_SERVER['REQUEST_URI'],9);
 $data=file_get_contents($url);
 foreach($http_response_header as $header)if(str_starts_with(strtolower($header),'content-type:'))header($header);
 echo $data;return;
}
if($path==='/api/plugin/FPP_WLED_10.x/icon'){header('Content-Type: image/png');readfile(dirname(__DIR__,2).'/icon.png');return;}
$page=$_GET['page']??'lights.php';if(!in_array($page,['lights.php','settings.php','plugin.php','credits.php'])){http_response_code(404);return;}
?><!doctype html><html data-bs-theme="light"><head><meta name="viewport" content="width=device-width,initial-scale=1"><style>
:root{color-scheme:light;--bs-body-bg:Canvas;--bs-body-color:CanvasText;--bs-secondary-bg:ButtonFace;--bs-tertiary-bg:ButtonFace;--bs-secondary-color:GrayText;--bs-border-color:ButtonBorder;--bs-primary-bg-subtle:Highlight;--bs-primary-text-emphasis:HighlightText}
:root[data-bs-theme=dark]{color-scheme:dark}body{font:1rem system-ui;margin:1rem;background:Canvas;color:CanvasText}iframe{width:100%}nav{display:flex;flex-wrap:wrap;gap:1rem}img{max-width:100%}
</style></head><body><header id="host-menu">FPP fixture navigation</header><?php require dirname(__DIR__,2).'/'.$page; ?></body></html>

