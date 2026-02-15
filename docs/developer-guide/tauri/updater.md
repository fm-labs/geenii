# auto-updater

## Generate signing keys

```bash
pnpm tauri signer generate -w ~/.tauri/signing.key
pnpm run v1.22.22
$ tauri signer generate -w /Users/phil/.tauri/signing.key
Please enter a password to protect the secret key.
Password: 
<empty>
Password (one more time): 
<empty>
Deriving a key from the password in order to encrypt the secret key... done

Your keypair was generated successfully
Private: /Users/phil/.tauri/signing.key (Keep it secret!)
Public: /Users/phil/.tauri/signing.key.pub
---------------------------

Environment variables used to sign:
`TAURI_SIGNING_PRIVATE_KEY`  Path or String of your private key
`TAURI_SIGNING_PRIVATE_KEY_PASSWORD`  Your private key password (optional)

ATTENTION: If you lose your private key OR password, you'll not be able to sign your update package and updates will not work.
---------------------------
```

## Sign an update package

```bash
tauri signer sign \
  --private-key ./private.pem \
  --input ./path/to/your-installer.exe
```

## Configure updater

Edit `tauri.conf.json`:

The endpoint base URLs must be HTTPS or return a JSON with updater info. 

```json
{
  "bundle": {
    "createUpdaterArtifacts": true
  },
  "plugins": {
    "updater": {
      "active": true,
      "endpoints": [
        "https://your-domain.com/api/updates",
        "https://your-domain.com/api/updates/latest.json"
      ],
      "dialog": true,
      "pubkey": "YOUR_PUBLIC_KEY",
      "windowsStore": false,
      "macOSStore": false
    }
  }
}
```

## Updater JSON file format

```json
{
  "version": "1.2.3",
  "pub_date": "2025-07-30T12:00:00Z",
  "platforms": {
    "darwin-x86_64": {
      "signature": "BASE64_SIGNATURE",
      "url": "https://example.com/downloads/your-app-1.2.3.dmg"
    },
    "windows-x86_64": {
      "signature": "BASE64_SIGNATURE",
      "url": "https://example.com/downloads/your-app-1.2.3.exe"
    },
    "linux-x86_64": {
      "signature": "BASE64_SIGNATURE",
      "url": "https://example.com/downloads/your-app-1.2.3.AppImage"
    }
  }
}
```



For more details, see the official Tauri Updater plugin documentation:

https://tauri.app/plugin/updater/