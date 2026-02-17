<?php

require_once 'func.inc.php';

const LOG_FILE = 'data/updater.log';

// helper function that writes a JSONL log entry to a file
function log_entry($entry)
{
    $log_file = LOG_FILE;
    $entry['timestamp'] = date('c'); // add ISO 8601 timestamp
    file_put_contents($log_file, json_encode($entry) . "\n", FILE_APPEND);
}

// helper function to read version
function get_latest_version()
{
    $version_file = 'VERSION';
    if (file_exists($version_file)) {
        return trim(file_get_contents($version_file));
    }
    return null; // version file not found
}


// Set JSON header
header('Content-Type: application/json');

// log request
$reqid = uniqid('req');
log_entry([
    "request_id" => $reqid,
    "type" => "request",
    "method" => $_SERVER['REQUEST_METHOD'],
    "query" => $_GET,
    "post_data" => file_get_contents('php://input')
]);

// read query parameters
$user_target = $_GET['target'] ?? null;
$user_arch = $_GET['arch'] ?? null;
$user_version = $_GET['current_version'] ?? null;
$dump = $_GET['dump'] ?? null;

// get the latest version from the VERSION file
$latest_version = get_latest_version();
if (!$latest_version) {
    http_response_code(500);
    echo json_encode(["error" => "Current version not found"]);
    exit;
}

// draft a default response with the latest version and empty platforms, which will be filled in if the updater file exists
$response = [
    "version" => $latest_version,
    "notes" => "Geenii Desktop version $latest_version",
    "pub_date" => date('c'),
    "platforms" => []
];

// read updater file for the latest version, if it exists
$updater_file = RELEASES_DIR . '/' . $latest_version . '/updater.json';
if (file_exists($updater_file)) {
    $updater_text = file_get_contents($updater_file);
    $response = json_decode($updater_text, true);
}

// Dump to file if requested
if ($dump) {
    $dump_file = UPDATES_FILE;
    file_put_contents($dump_file, json_encode($response, JSON_PRETTY_PRINT));
}

// log response
log_entry([
    "request_id" => $reqid,
    "type" => "response",
    "response" => $response
]);

// Output file contents
echo json_encode($response, JSON_PRETTY_PRINT);
