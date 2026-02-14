# Tauri Icons


## Icon Formats

| Icon Name                | Format | Size    |
|--------------------------|--------|---------|
| 32x32.png                | PNG    | 32x32   |
| 128x128.png              | PNG    | 128x128 |
| 128x128@2x.png           | PNG    | 256x256 |
| icon.icns                | ICNS   |         |
| icon.ico                 | ICO    | 16x16   |
| icon.png                 | PNG    | 512x512 |
| Square30x30Logo.png      | PNG    | 30x30   |
| Square44x44Logo.png      | PNG    | 44x44   |
| Square71x71Logo.png      | PNG    | 71x71   |
| Square89x89Logo.png      | PNG    | 89x89   |
| Square107x107Logo.png    | PNG    | 107x107 |
| Square142x142Logo.png    | PNG    | 142x142 |
| Square150x150Logo.png    | PNG    | 150x150 |
| Square284x284Logo.png    | PNG    | 284x284 |
| Square310x310Logo.png    | PNG    | 310x310 |
| StoreLogo.png            | PNG    | 50x50   |
|                          |        |         |


## Icon Usage

In `tauri.conf.json`, specify the icon paths:

```json
{
  "tauri": {
    "bundle": {
      "icon": [
          "icons/32x32.png",
          "icons/128x128.png",
          "icons/128x128@2x.png",
          "icons/icon.icns",
          "icons/icon.ico"
        ]
    }
  }
}
```