<?php
/**
 * Simple release management script for Geenii Desktop updater bundles.
 *
 * This script provides an API endpoint to submit new releases, which will be added to the corresponding updater.json
 * file for the version.
 * The script also logs all requests and responses to a log file in JSONL format for auditing and debugging purposes.
 *
 * @version 0.1
 * @author fm-labs
 */
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
    //file_put_contents($updater_file, json_encode($data, JSON_PRETTY_PRINT));
    return $data;
}

function update_updater_file($version, $data) {
    $updater_file = RELEASES_DIR . '/' . $version . '/updater.json';
    if (!$data || !is_array($data) || empty($data) || !isset($data['version'])) {
        throw new Exception("Invalid data for updater file: " . json_encode($data));
    }
    file_put_contents($updater_file, json_encode($data, JSON_PRETTY_PRINT));
}

/**
 * @throws Exception
 */
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

    // make sure release directories exist
    ensure_release_dirs($version, $platform);

    // read existing updater file
    $updater_data = init_updater_file($version);
    if (!$updater_data) {
        throw new Exception("Failed to initialize updater file for version: $version");
    }

    $release_path = get_release_path($version, $platform, $bundle, $filename);
    if (!$release_path || !file_exists(RELEASES_DIR . '/' . $release_path)) {
        //return; // skip unsupported platform
        throw new Exception("Release file not found for platform: $platform, bundle: $bundle, filename: $filename");
    }
    $download_url = get_release_download_url($release_path);
    $sig = get_release_signature($release_path);

    $platform_key = platformToOSArch($platform) . "-" . $bundle;
    if ($platform_key === "linux-x86_64-appimage") {
        $platform_key = "linux-x86_64"; // special case for linux appimage bundle, which has a different platform key in the updater file
    }

    $updater_data['platforms'] = $updater_data['platforms'] ?? [];
    $updater_data['platforms'][$platform_key] = [
        "url" => $download_url,
        "signature" => $sig
    ];

    log_entry([
        "type" => "release_added",
        "release" => $releaseData,
        "platform" => $platform,
        "bundle" => $bundle,
        "filename" => $filename,
        "version" => $version,
        "platform_key" => $platform_key,
        "url" => $download_url,
        "signature" => $sig,
    ]);

    update_updater_file($version, $updater_data);
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
function ensure_release_dirs($version, $platform) {
    // make sure platform- and bundle-directories exist
    $platform_dir=RELEASES_DIR . '/' . $version . '/' . $platform;
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
}

// Set JSON header
header('Content-Type: application/json');

//$auth_header = "Basic " . base64_encode(get_release_credentials());
//if (!isset($_SERVER['HTTP_AUTHORIZATION']) || $_SERVER['HTTP_AUTHORIZATION'] !== $auth_header) {
//    http_response_code(401);
//    echo json_encode(["error" => "Unauthorized"]);
//    exit;
//}


$reqid = uniqid('req');
$method = $_SERVER['REQUEST_METHOD'];
$action = $_GET['action'] ?? 'default';
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
    default:
        //http_response_code(400);
        //$response = ["error" => "Unknown action"]
        $response = [
            "success" => false,
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

// emit response as JSON
echo json_encode($response);
