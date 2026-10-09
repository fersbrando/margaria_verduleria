<?php
// Puente para abrir el panel desde Apache/XAMPP (http://localhost/margaria_verduleria/servicioweb/).
// Reenvía cada pedido al servicio Python (servidor.py), que es el único que lee y escribe los datos.

$cfg = json_decode(@file_get_contents(__DIR__ . '/../config.json'), true) ?: [];
$puerto = intval($cfg['web']['puerto'] ?? 8085);
$clave = (string)($cfg['web']['clave'] ?? '');

function responder_json($codigo, $data) {
    http_response_code($codigo);
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode($data, JSON_UNESCAPED_UNICODE);
    exit;
}

// Si hay clave configurada, Apache también la pide.
if ($clave !== '' && !hash_equals($clave, (string)($_SERVER['PHP_AUTH_PW'] ?? ''))) {
    header('WWW-Authenticate: Basic realm="La Verduleria de Margarita", charset="UTF-8"');
    responder_json(401, ['error' => 'Clave requerida']);
}

$headers = ['Content-Type: ' . ($_SERVER['CONTENT_TYPE'] ?? 'application/json')];
if ($clave !== '') {
    $headers[] = 'Authorization: Basic ' . base64_encode('web:' . $clave);
}
$ctx = stream_context_create(['http' => [
    'method' => $_SERVER['REQUEST_METHOD'] === 'POST' ? 'POST' : 'GET',
    'header' => implode("\r\n", $headers),
    'content' => file_get_contents('php://input'),
    'ignore_errors' => true,
    'timeout' => 30,
]]);
$url = "http://127.0.0.1:$puerto/servicioweb/api.php?" . ($_SERVER['QUERY_STRING'] ?? '');
$resp = @file_get_contents($url, false, $ctx);
if ($resp === false) {
    responder_json(503, ['error' => 'El servicio Python no está iniciado. Ejecutá iniciar_servicio.bat']);
}

$cabeceras = function_exists('http_get_last_response_headers') ? http_get_last_response_headers() : $http_response_header;
foreach ($cabeceras ?: [] as $h) {
    if (preg_match('#^HTTP/\S+\s+(\d{3})#', $h, $m)) {
        http_response_code((int)$m[1]);
    } elseif (stripos($h, 'Content-Type:') === 0) {
        header($h);
    }
}
header('Cache-Control: no-store');
echo $resp;
