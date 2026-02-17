<?php

const LOG_FILE = 'data/updater.log';
const VERSION_FILE = 'VERSION';
const UPDATES_FILE = 'updates.latest.json';
const DOWNLOAD_BASE_URL = 'https://geenii.flowmotion-labs.com/releases/geenii-desktop';
const RELEASES_BASE_PATH = 'releases/geenii-desktop';

// helper function that writes a JSONL log entry to a file
function log_entry($entry)
{
    $log_file = LOG_FILE;
    $entry['timestamp'] = date('c'); // add ISO 8601 timestamp
    file_put_contents($log_file, json_encode($entry) . "\n", FILE_APPEND);
}

// helper function to read version
function get_current_version()
{
    $version_file = VERSION_FILE;
    if (file_exists($version_file)) {
        return trim(file_get_contents($version_file));
    }
    return null; // version file not found
}


// helper function to get the download URL for a given version, platform and bundle
function get_download_url($version, $platform, $bundle)
{
    $release_path = get_release_path($version, $platform, $bundle);
    if ($release_path) {
        return DOWNLOAD_BASE_URL . '/' . $release_path;
    }
    return null; // unsupported platform or bundle
}

// helper function to get the signature for a given version, platform and bundle, if the bundle is supported
function get_signature($version, $platform, $bundle)
{
    $release_path = get_release_path($version, $platform, $bundle);
    if ($release_path) {
        $sig_path = RELEASES_BASE_PATH . '/' . $release_path . '.sig';
        if (file_exists($sig_path)) {
            return file_get_contents($sig_path);
        }
    }
    return ""; // unsupported platform or bundle, or signature file not found
}

// helper function to get the relative path to the release file for a given version, platform and bundle
function get_release_path($version, $platform, $bundle)
{
    $basename = "geenii-desktop";
    if (str_contains($platform, 'darwin')) {
        if ($bundle === 'dmg') {
            if (str_contains($platform, 'aarch64')) {
                $basename .= '_aarch64';
            } else if (str_contains($platform, 'x86_64')) {
                $basename .= '_x86_64';
            }
            $ext = 'dmg';
        } else if ($bundle === 'app') {
            $ext = 'app.tar.gz';
        } else {
            return null; // unsupported bundle
        }
    } else if (str_contains($platform, 'linux')) {
        if ($bundle === 'deb') {
            $ext = 'deb';
        } else if ($bundle === 'rpm') {
            $ext = 'rpm';
        } else if ($bundle === 'appimage') {
            $ext = 'AppImage';
        } else {
            return null; // unsupported bundle
        }
    } else {
        return null; // unsupported platform
    }
    $filename = "$basename.$ext";
    return "$version/$platform/$bundle/$filename";
}

// Set JSON header
header('Content-Type: application/json');

$reqid = uniqid('req');

log_entry([
    "request_id" => $reqid,
    "type" => "request",
    "method" => $_SERVER['REQUEST_METHOD'],
    "query" => $_GET,
    "post_data" => file_get_contents('php://input')
]);

// $file = UPDATES_FILE;
// // Check if file exists
// if (!file_exists($file)) {
//     http_response_code(404);
//     echo json_encode(["error" => "File not found"]);
//     exit;
// }
// $updater_text = file_get_contents($file);
// $updater_data = json_decode($updater_text, true);

$user_target = $_GET['target'] ?? null;
$user_arch = $_GET['arch'] ?? null;
$user_version = $_GET['current_version'] ?? null;

$dump = $_GET['dump'] ?? null;

$latest_version = get_current_version();
if (!$latest_version) {
    http_response_code(500);
    echo json_encode(["error" => "Current version not found"]);
    exit;
}

$updater_data = [
    "version" => "0.1.4", $latest_version,
    "notes" => "Geenii Desktop version $latest_version is now available! This release includes bug fixes and performance improvements. Please update to the latest version for the best experience.",
    "pub_date" => date('c'),
    "platforms" => []
];

// function to map rustc target triples to our OS-arch platform keys
function platformToOSArch($platform)
{
    if ($platform === 'aarch64-apple-darwin') {
        return 'darwin-aarch64';
    } else if ($platform === 'x86_64-apple-darwin') {
        return 'darwin-x86_64';
    } else if ($platform === 'x86_64-unknown-linux-gnu') {
        return 'linux-unknown-gnu';
    } else if ($platform === 'aarch64-unknown-linux-gnu') {
        return 'linux-aarch64-gnu';
    } else if ($platform === 'x86_64-pc-windows-msvc') {
        return 'windows-x86_64';
    } else if ($platform === 'aarch64-pc-windows-msvc') {
        return 'windows-arm64';
    } else {
        return null; // unsupported platform
    }
}


function add_platform($platform, $bundle)
{
    global $updater_data, $latest_version;
    if (!platformToOSArch($platform)) {
        return; // skip unsupported platform
    }
    $platform_key = platformToOSArch($platform) . "-" . $bundle;
    $release_path = get_release_path($latest_version, $platform, $bundle);
    if (!$release_path || !file_exists(RELEASES_BASE_PATH . '/' . $release_path)) {
        return; // skip unsupported platform
    }
    $download_url = get_download_url($latest_version, $platform, $bundle);
    $sig = get_signature($latest_version, $platform, $bundle);

    $updater_data['platforms'][$platform_key] = [
        //"_path" => $release_path,
        "url" => $download_url,
        "signature" => $sig
    ];
}

// add platforms by host triple and bundle type

// MACOS PLATFORMS
// add macos x86_64 platform
add_platform("x86_64-apple-darwin", "dmg");
add_platform("x86_64-apple-darwin", "app");

// add macos ARM64 platform
add_platform("aarch64-apple-darwin", "app");
add_platform("aarch64-apple-darwin", "dmg");

// LINUX PLATFORMS
// add linux x86_64 platforms
add_platform("x86_64-unknown-linux-gnu", "deb");
add_platform("x86_64-unknown-linux-gnu", "rpm");
//todo add_platform("x86_64-unknown-linux-gnu", "appimage");

// add linux ARM64 platforms
add_platform("aarch64-unknown-linux-gnu", "deb");
add_platform("aarch64-unknown-linux-gnu", "rpm");
//todo add_platform("aarch64-unknown-linux-gnu", "appimage");

// WINDOWS PLATFORMS
// add windows x86_64 platforms
//todo add_platform("x86_64-pc-windows-msvc", "exe");
//todo add_platform("x86_64-pc-windows-msvc", "msi");

// add windows ARM64 platforms
//todo add_platform("aarch64-pc-windows-msvc", "exe");
//todo add_platform("aarch64-pc-windows-msvc", "msi");


// Dump to file if requested
if ($dump) {
    $dump_file = UPDATES_FILE;
    file_put_contents($dump_file, json_encode($updater_data, JSON_PRETTY_PRINT));
}

log_entry([
    "request_id" => $reqid,
    "type" => "response",
    "response" => $updater_data
]);

// Output file contents
echo json_encode($updater_data, JSON_PRETTY_PRINT);
