<?php

const UPDATES_FILE = 'updates.latest.json';
const DOWNLOAD_BASE_URL = 'https://geenii.flowmotion-labs.com/releases/geenii-desktop';
const RELEASES_DIR = 'releases/geenii-desktop';


// function to map rustc target triples to our OS-arch platform keys
function platformToOSArch($platform)
{
    if ($platform === 'aarch64-apple-darwin') {
        return 'darwin-aarch64';
    } else if ($platform === 'x86_64-apple-darwin') {
        return 'darwin-x86_64';
    } else if ($platform === 'x86_64-unknown-linux-gnu') {
        return 'linux-x86_64';
    } else if ($platform === 'aarch64-unknown-linux-gnu') {
        return 'linux-aarch64';
    } else if ($platform === 'x86_64-pc-windows-msvc') {
        return 'windows-x86_64';
    } else if ($platform === 'aarch64-pc-windows-msvc') {
        return 'windows-aarch64';
    } else {
        return null; // unsupported platform
    }
}

// helper function to get the download URL for a given version, platform and bundle
function get_release_download_url($release_path)
{
    if ($release_path) {
        return DOWNLOAD_BASE_URL . '/' . $release_path;
    }
    return null; // unsupported platform or bundle
}

// helper function to get the signature for a given version, platform and bundle, if the bundle is supported
function get_release_signature($release_path)
{
    if ($release_path) {
        $sig_path = RELEASES_DIR . '/' . $release_path . '.sig';
        if (file_exists($sig_path)) {
            return file_get_contents($sig_path);
        }
    }
    return ""; // unsupported platform or bundle, or signature file not found
}

// helper function to get the relative path to the release file for a given version, platform and bundle
function get_release_path($version, $platform, $bundle, $filename = null)
{
    if ($filename === null) {
        // TODO usage without filename is deprecated, remove in future and make filename required
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
                if (str_contains($platform, 'aarch64')) {
                    $basename = $basename . '_aarch64';
                } else if (str_contains($platform, 'x86_64')) {
                    $basename = $basename . '_amd64';
                }
                $ext = 'deb';
            } else if ($bundle === 'rpm') {
                if (str_contains($platform, 'aarch64')) {
                    $basename = $basename . '-' . $version . '-1.aarch64';
                } else if (str_contains($platform, 'x86_64')) {
                    $basename = $basename . '-' . $version . '-1.x86_64';
                }
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
    }
    return "$version/$platform/$bundle/$filename";
}