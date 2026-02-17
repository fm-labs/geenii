<?php

// enable error reporting for debugging
error_reporting(E_ALL);
ini_set('display_errors', 1);

const LOG_FILE = 'data/release.log';
const RELEASES_FILE = 'data/releases.json';

// helper function that writes a JSONL log entry to a file
function log_entry($entry) {
    $log_file = LOG_FILE;
    $entry['timestamp'] = date('c'); // add ISO 8601 timestamp
    file_put_contents($log_file, json_encode($entry) . "\n", FILE_APPEND);
}

// helper functio that writes a submission entry to a json file
function add_release($release) {
    $file = RELEASES_FILE;
    $releases = [];
    if (file_exists($file)) {
        $releases = json_decode(file_get_contents($file), true);
    }
    $releases[] = $release;
    file_put_contents($file, json_encode($releases, JSON_PRETTY_PRINT));
}

// helper function to ensure a directory exists, and create it recursively if it doesn't
function ensure_directory_exists($dir) {
    if (!is_dir($dir)) {
        mkdir($dir, 0755, true);
    }
}


// helper function to prepare a release (setup dirs, validate data, etc)
function prepare_release($data) {
    // validate data
    if (!isset($data['version']) || !isset($data['platform'])) {
        return ["error" => "Missing required fields: version, bundle and platform"];
    }

    $version = $data['version'];
    $platform = strtolower($data['platform']);

    // make sure directories exist
    $platform_dir='releases/geenii-desktop/' . $data['version'] . '/' . $platform;
    ensure_directory_exists($platform_dir);

    // for darwin platforms we create subdirs for each bundle
    if (str_contains($platform, 'darwin')) {
        $bundles = ['dmg', 'app'];
        foreach ($bundles as $bundle) {
            ensure_directory_exists($platform_dir . '/' . $bundle);
        }
    }

    // for linux we create a subdir for the deb, rpm and appimage bundles
    if (str_contains($platform, 'linux')) {
        $bundles = ['deb', 'rpm', 'appimage'];
        foreach ($bundles as $bundle) {
            ensure_directory_exists($platform_dir . '/' . $bundle);
        }
    }

    // for windows we create a subdir for the exe and msi bundles
    if (str_contains($platform, 'windows')) {
        $bundles = ['exe', 'msi'];
        foreach ($bundles as $bundle) {
            ensure_directory_exists($platform_dir . '/' . $bundle);
        }
    }

    return ["success" => true];
}

// Set JSON header
header('Content-Type: application/json');

// $file = 'versions.json';
//
// // Check if file exists
// if (!file_exists($file)) {
//     http_response_code(404);
//     echo json_encode(["error" => "File not found"]);
//     exit;
// }

$reqid = uniqid('req');

$method = $_SERVER['REQUEST_METHOD'];
// read action from query parameters
$action = $_GET['action'] ?? 'default';
// read JSON POST data
$data = [];
if ($method === 'POST') {
  $data = json_decode(file_get_contents('php://input'), true);
}

log_entry([
    "request_id" => $reqid,
    "type" => "request",
    "method" => $method,
    "action" => $action,
    "data" => $data
]);

$response = [
    "success" => false,
    "message" => "Unknown error",
    "data" => $data
];
switch ($action) {
    case 'submit':
          // For now, submit and release are the same, but we can differentiate them later if needed
          add_release($data);
          $response = ["success" => true, "message" => "Release submitted successfully"];
          break;
    case 'prepare':
        $result = prepare_release($data);
        if (isset($result['error'])) {
            http_response_code(400);
            $response = ["error" => $result['error']];
            break;
        }
        $response = ["success" => true, "message" => "Release prepared successfully"];
        break;
    default:
        //http_response_code(400);
        //$response = ["error" => "Unknown action"]
        $response = [
            "success" => true,
            "_action" => $action,
            "_data" => $data
        ];
        break;
}

log_entry([
    "request_id" => $reqid,
    "type" => "response",
    "response" => $response
]);

echo json_encode($response);