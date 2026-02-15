# Tauri Icons


## Icon Formats

| Icon Name                | Format | Size    |
|--------------------------|--------|---------|
| 32x32.png                | PNG    | 32x32   |
| 128x128.png              | PNG    | 128x128 |
| 128x128@2x.png           | PNG    | 256x256 |
| icon.icns                | ICNS   | 512x512 |
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

### ICNS

The ICNS format is used for macOS applications. 
It can contain multiple icon sizes within a single file, allowing the operating system to choose the appropriate size based on the context (e.g., Finder, Dock, etc.). 
The recommended sizes for ICNS files are 16x16, 32x32, 64x64, 128x128, 256x256, and 512x512 pixels.

**However**, Tauri requires the ICNS file to contain **only a 512x512 icon** for proper display on macOS.
(This is the only size that worked during testing, and the Tauri documentation does not specify otherwise.)

#### Create an ICNS file using iconutil

The `iconutil` command-line tool can be used to create an ICNS file from a folder of PNG icons.

```bash
# 1. Create a folder for the icon set
mkdir MyApp.iconset

# 2. Add PNG icons to the folder with the correct naming convention
cp 16x16.png MyApp.iconset/icon_512x512.png

# 3. Use iconutil to create the ICNS file
iconutil -c icns MyApp.iconset -o icon.icns
```



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