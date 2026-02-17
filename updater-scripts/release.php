<?php

require_once 'func.inc.php';

const LOG_FILE = 'data/release.log';

// helper function that writes a JSONL log entry to a file
function log_entry($entry) {
    $log_file = LOG_FILE;
    $entry['timestamp'] = date('c'); // add ISO 8601 timestamp
    file_put_contents($log_file, json_encode($entry) . "\n", FILE_APPEND);
}


function init_updater_file($version) {
    $updater_file = RELEASES_DIR . '/' . $version . '/updater.json';
    if (file_exists($updater_file)) {
        // read existing updater file
        $updater_text = file_get_contents($updater_file);
        $updater_data = json_decode($updater_text, true);
        if ($updater_data) {
            return $updater_data;
        }
    }

    $data = [
        "version" => $version,
        "notes" => "Release notes for version $version",
        "pub_date" => date('c'),
        "platforms" => []
    ];
    file_put_contents($updater_file, json_encode($data, JSON_PRETTY_PRINT));
    return $data;
}

function update_updater_file($version, $data) {
    $updater_file = RELEASES_DIR . '/' . $version . '/updater.json';
    file_put_contents($updater_file, json_encode($data, JSON_PRETTY_PRINT));
}

function add_release($releaseData) {
    $name = $releaseData['name'] ?? null;
    $version = $releaseData['version'] ?? null;
    $platform = strtolower($releaseData['platform'] ?? '');
    $bundle = strtolower($releaseData['bundle'] ?? '');
    $filename = $releaseData['filename'] ?? null;

    // validate required fields
    if (!$name || !$version || !$platform || !$bundle || !$filename) {
        throw new Exception("Missing required fields: name, version, platform, bundle and filename");
    }

    if (!platformToOSArch($platform)) {
        throw new Exception("Unsupported platform: $platform");
    }

    // read existing updater file
    $updater_data = init_updater_file($version);

    // add platform release data
    //if (!isset($updater_data['platforms'][$platform])) {
    //    $updater_data['platforms'][$platform] = [];
    //}
    $release_path = get_release_path($version, $platform, $bundle, $filename);

    $platform_key = platformToOSArch($platform) . "-" . $bundle;
    if (!$release_path || !file_exists(RELEASES_DIR . '/' . $release_path)) {
        return; // skip unsupported platform
    }
    $download_url = get_release_download_url($release_path);
    $sig = get_release_signature($release_path) ?? "";

    $updater_data['platforms'][$platform_key] = [
        "url" => $download_url,
        "signature" => $sig
    ];

    // write updated updater file
    update_updater_file($version, $updater_data);

    log_entry([
        "type" => "release_added",
        "platform" => $platform,
        "bundle" => $bundle,
        "filename" => $filename,
        "version" => $version,
        "platform_key" => $platform_key,
        "url" => $download_url,
        "signature" => $sig
    ]);
}


//// helper functio that writes a submission entry to a json file
//function add_release($release) {
//    $file = RELEASES_FILE;
//    $releases = [];
//    if (file_exists($file)) {
//        $releases = json_decode(file_get_contents($file), true);
//    }
//    $releases[] = $release;
//    file_put_contents($file, json_encode($releases, JSON_PRETTY_PRINT));
//}

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
    // make sure platform- and bundle-directories exist
    $platform_dir=RELEASES_DIR . '/' . $data['version'] . '/' . $platform;
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

    // init updater file for this version
    init_updater_file($version);

    return [
        "success" => true,
        "message" => "Release prepared successfully",
        "version" => $version,
        "platform" => $platform
    ];
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
        try {
            add_release($data);
            $response = ["success" => true, "message" => "Release submitted successfully"];
        } catch (Exception $e) {
            http_response_code(400);
            $response = ["error" => $e->getMessage()];
        }
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