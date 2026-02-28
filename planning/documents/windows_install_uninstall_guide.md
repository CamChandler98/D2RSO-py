# Windows Install and Uninstall Guide

This guide explains how to install, use, update, and uninstall the packaged D2RSO Windows app.

Audience:
- friend or tester using the app
- non-developer end user

Important:
- this app is currently distributed as a portable ZIP
- there is no MSI installer yet
- install means "download, extract, and run"
- uninstall means "close it and delete its files"

---

## 1) Before you start

You will need:
- a Windows 10 or Windows 11 PC
- permission to download and extract a ZIP file
- a D2RSO Windows ZIP from either:
  - the GitHub Releases page, or
  - a GitHub Actions artifact shared by the maintainer

The file name will look like:
- `d2rso-0.1.0-windows-x64.zip`

You may also receive a checksum file:
- `d2rso-0.1.0-windows-x64.zip.sha256`

---

## 2) Download the app

### Option A: Download from GitHub Releases
1. Open the GitHub repository in your browser.
2. Click `Releases`.
3. Open the latest release.
4. Download the Windows ZIP file.
5. Save it somewhere easy to find, such as `Downloads`.

### Option B: Download from a GitHub Actions artifact
Use this only if someone shared a workflow artifact with you.

1. Open the link to the completed workflow run.
2. Find the `Artifacts` section.
3. Download the Windows artifact ZIP.
4. Save it to `Downloads`.

Note:
- Actions artifacts may require GitHub access to the repository
- GitHub Release downloads are easier for non-technical users

---

## 3) Optional integrity check

If you were also given a `.sha256` file, you can verify the ZIP before extracting it.

### Using Command Prompt
1. Open `Command Prompt`.
2. Change to the folder containing the ZIP.
3. Run:

```cmd
certutil -hashfile d2rso-0.1.0-windows-x64.zip SHA256
```

4. Compare the displayed hash with the value in the `.sha256` file.

If the values match, the download is intact.

If they do not match:
1. delete the ZIP
2. download it again
3. do not continue until the hash matches

---

## 4) Install the app

Because this is a portable app, installation is just extraction.

### Recommended install locations
Choose one:
- `C:\Users\<YourName>\Apps\D2RSO\`
- `C:\Users\<YourName>\Desktop\D2RSO\`

Avoid extracting directly inside:
- `C:\Windows\`
- `C:\Program Files\` unless you know you have permission

### Step-by-step install
1. Open File Explorer.
2. Go to your `Downloads` folder.
3. Right-click the D2RSO ZIP file.
4. Click `Extract All...`.
5. Choose your install location.
6. Finish extraction.
7. Open the extracted folder.
8. Open the `d2rso` folder inside it if the ZIP created one.
9. Find `d2rso.exe`.
10. Double-click `d2rso.exe`.

If the app opens, installation is complete.

---

## 5) First launch

On first launch:
1. Windows may show a security warning.
2. The app should open its main window.
3. It may create settings the first time it runs.

### If Windows SmartScreen appears
If you trust the file source:
1. Click `More info`.
2. Click `Run anyway`.

This warning is common for unsigned desktop apps.

---

## 6) Create a shortcut

If you want easier access:

### Desktop shortcut
1. Right-click `d2rso.exe`.
2. Click `Show more options` if needed.
3. Click `Send to`.
4. Click `Desktop (create shortcut)`.

### Pin to taskbar
1. Right-click `d2rso.exe`.
2. Click `Pin to taskbar` if available.

### Pin to Start
1. Right-click `d2rso.exe`.
2. Click `Pin to Start` if available.

---

## 7) Where settings are stored

The app stores user settings separately from the app folder.

Default settings location:

```text
%LOCALAPPDATA%\D2RSO\settings.json
```

This means:
- deleting the app folder does not automatically delete your settings
- reinstalling or updating the app can keep your saved settings

---

## 8) How to update to a newer version

There is no in-app updater yet.

To update:
1. Download the new ZIP.
2. Close the running app.
3. Extract the new ZIP to a new folder or over the existing app folder.
4. Launch the new `d2rso.exe`.

### Recommended safe update method
1. Keep your current version folder as-is.
2. Extract the new version to a separate folder.
3. Launch the new version.
4. Confirm it works.
5. Delete the old folder after you are satisfied.

Because settings live under `%LOCALAPPDATA%`, updates should not remove them.

---

## 9) How to uninstall the app

Since this is a portable ZIP app, uninstall is manual.

### 9.1 Close the app
1. Close the D2RSO window.
2. If it minimizes to the tray, fully exit it from the tray or from Task Manager.

### 9.2 Confirm it is not still running
1. Press `Ctrl + Shift + Esc` to open Task Manager.
2. Look for `d2rso.exe`.
3. If it is still running, select it.
4. Click `End task`.

### 9.3 Delete the app files
1. Open File Explorer.
2. Go to the folder where you extracted D2RSO.
3. Delete the D2RSO folder.

### 9.4 Remove shortcuts
If you created shortcuts:
1. delete the desktop shortcut
2. unpin from taskbar
3. unpin from Start

At this point, the app files are removed.

---

## 10) How to fully uninstall including settings

If you want a complete cleanup, remove the settings too.

### Step-by-step
1. Press `Win + R`.
2. Enter:

```text
%LOCALAPPDATA%\D2RSO
```

3. Press Enter.
4. Delete `settings.json`, or delete the whole `D2RSO` folder.

This removes saved local app settings.

---

## 11) How to verify uninstall is complete

Check these items:
1. the app folder is deleted
2. `d2rso.exe` is no longer present
3. there is no `d2rso.exe` process in Task Manager
4. any desktop/start/taskbar shortcuts are removed
5. `%LOCALAPPDATA%\D2RSO` is removed if you wanted a full cleanup

---

## 12) Troubleshooting

### The app will not open
Try this:
1. make sure you extracted the ZIP fully
2. do not run the app from inside the ZIP preview window
3. move the app to a normal user folder like `Downloads` or `Desktop`
4. try launching `d2rso.exe` again

### Windows says the app is blocked
Try this:
1. right-click the ZIP or `.exe`
2. click `Properties`
3. if you see `Unblock`, check it
4. click `Apply`
5. try again

### The app closes immediately
Possible causes:
- incomplete extraction
- antivirus intervention
- a bad download

What to do:
1. delete the extracted folder
2. download the ZIP again
3. extract it again
4. retry launch

### I deleted the app but my settings came back after reinstall
That is expected if `%LOCALAPPDATA%\D2RSO\settings.json` was left in place.

Delete that folder too if you want a full reset.

---

## 13) Short version to share with a friend

If you want a minimal version to send someone:

1. Download the latest `d2rso-...-windows-x64.zip`.
2. Right-click it and choose `Extract All`.
3. Open the extracted folder.
4. Double-click `d2rso.exe`.
5. If Windows warns, click `More info` -> `Run anyway` only if you trust the source.
6. To uninstall later, close the app and delete the extracted folder.
7. To remove settings too, delete `%LOCALAPPDATA%\D2RSO`.

---

## 14) For developers instead of end users

If you need a Windows developer machine setup guide instead of end-user install steps, use:
- `planning/documents/windows_dev_environment_guide.md`
