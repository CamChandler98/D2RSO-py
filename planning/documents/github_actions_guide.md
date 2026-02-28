# GitHub Actions Guide

This document explains how to use GitHub Actions for the D2RSO Python project.

Audience:
- Repo maintainer
- Contributor opening pull requests
- Anyone responsible for shipping Windows build artifacts

Related files:
- `.github/workflows/ci.yml`
- `.github/workflows/release.yml`
- `packaging/d2rso.spec`
- `scripts/build_windows_bundle.py`
- `scripts/smoke_test_packaged_app.py`
- `scripts/archive_dist.py`

---

## 1) What workflows exist

This repo currently uses two GitHub Actions workflows:

### `CI`
Defined in `.github/workflows/ci.yml`

Purpose:
- Validate pull requests and pushes to `main`
- Run lint checks
- Run automated tests
- Build and smoke-test the Windows packaged app

### `Release`
Defined in `.github/workflows/release.yml`

Purpose:
- Build a Windows release artifact
- Smoke-test the packaged `.exe`
- Create a deterministic `.zip`
- Create a SHA-256 checksum file
- Publish release assets when a tag like `v0.1.0` is pushed

---

## 2) What the `CI` workflow does

The `CI` workflow runs automatically on:
- every pull request
- every push to `main`

It runs three jobs:

### `lint`
Runs on `ubuntu-latest`

Checks:
1. `python -m ruff check .`
2. `python -m black --check .`

### `test`
Runs on:
- `ubuntu-latest`
- `windows-latest`

Checks:
1. install project dependencies
2. run `pytest`
3. use `xvfb-run` on Linux so Qt tests can run headlessly

### `package-smoke`
Runs on `windows-latest` after `lint` and `test` pass

Checks:
1. install build dependencies including PyInstaller
2. set `SOURCE_DATE_EPOCH` from the latest git commit timestamp
3. build the Windows package with `scripts/build_windows_bundle.py`
4. launch the packaged app with `scripts/smoke_test_packaged_app.py`
5. upload the built bundle as a workflow artifact

This is the job that validates the packaged executable actually starts.

---

## 3) What the `Release` workflow does

The `Release` workflow runs:
- manually through the GitHub Actions UI
- automatically when a tag matching `v*` is pushed

It performs these steps:
1. checks out the repo
2. installs Python 3.11
3. installs project, dev, and build dependencies
4. sets `SOURCE_DATE_EPOCH` from git history
5. builds the Windows bundle with PyInstaller
6. smoke-tests the packaged `.exe`
7. creates a deterministic ZIP archive
8. creates a `.sha256` checksum file
9. uploads the ZIP and checksum as workflow artifacts
10. publishes the ZIP and checksum to a GitHub Release when the run came from a pushed tag

---

## 4) One-time repository setup

Do this once per repository.

### 4.1 Enable GitHub Actions
1. Open the repository on GitHub.
2. Go to `Settings`.
3. Open `Actions` -> `General`.
4. Make sure GitHub Actions are allowed for the repository.
5. Save changes if you had to enable anything.

### 4.2 Protect `main`
1. Go to `Settings`.
2. Open `Branches` or `Rulesets`, depending on your GitHub UI.
3. Add a rule for the `main` branch.
4. Turn on `Require a pull request before merging`.
5. Turn on `Require status checks to pass before merging`.
6. After the first successful workflow run, select the checks from the `CI` workflow as required.

Recommended required checks:
- `lint`
- `test (ubuntu-latest)`
- `test (windows-latest)`
- `package-smoke`

This is what actually gates merges.

---

## 5) Normal contributor workflow

Use this flow for day-to-day development.

### 5.1 Create a branch locally
```bash
git checkout -b your-branch-name
```

### 5.2 Make changes and commit
```bash
git add .
git commit -m "Describe the change"
```

### 5.3 Push the branch
```bash
git push -u origin your-branch-name
```

### 5.4 Open a pull request
1. Open the repo on GitHub.
2. Create a pull request from your branch into `main`.
3. Wait for the `CI` workflow to start automatically.

### 5.5 Watch the checks
1. Open the pull request page.
2. In the checks section, click `Details`.
3. Review job status for:
   - `lint`
   - `test`
   - `package-smoke`

### 5.6 Fix failures if needed
If a job fails:
1. click the failed job
2. expand the red step
3. read the command output
4. fix the issue locally
5. commit the fix
6. push again
7. wait for `CI` to rerun

Only merge after all required checks are green.

---

## 6) How to read common failures

### `lint` failed
Typical causes:
- import order
- formatting mismatch
- unused imports or variables

Fix locally with:
```bash
python -m ruff check .
python -m black --check .
```

### `test` failed
Typical causes:
- broken runtime logic
- platform-specific behavior
- failing GUI or model tests

Fix locally with:
```bash
python -m pytest
```

### `package-smoke` failed
Typical causes:
- PyInstaller missed a dependency
- packaged app cannot find assets
- packaged app crashes on startup

Key files to inspect:
- `packaging/d2rso.spec`
- `src/d2rso/main.py`
- `src/d2rso/key_icon_registry.py`
- `scripts/smoke_test_packaged_app.py`

---

## 7) How to run the `Release` workflow manually

Use this when you want a Windows package without creating a version tag yet.

1. Open the repo on GitHub.
2. Click `Actions`.
3. Select the `Release` workflow.
4. Click `Run workflow`.
5. Choose the branch you want to build from.
6. Start the workflow.
7. Wait for the `windows-release` job to finish.
8. Open the completed run.
9. Download the artifact from the run summary.

Use this for pre-release verification or ad hoc Windows builds.

---

## 8) How to create an official tagged release

Use this when you want a versioned release users can download.

### 8.1 Update the project version
1. Edit `pyproject.toml`.
2. Update `project.version`.
3. Commit the version change.

Example:
```bash
git add pyproject.toml
git commit -m "Bump version to 0.1.0"
```

### 8.2 Tag the release
Create a tag that matches the workflow trigger pattern, such as:

```bash
git tag v0.1.0
git push origin main --tags
```

### 8.3 What happens next
After the tag is pushed:
1. GitHub starts the `Release` workflow automatically.
2. The workflow builds the Windows app.
3. The workflow smoke-tests the packaged `.exe`.
4. The workflow creates:
   - `d2rso-<version>-windows-x64.zip`
   - `d2rso-<version>-windows-x64.zip.sha256`
5. GitHub publishes those files to the tag’s release page.

---

## 9) Where the Windows artifact comes from

The Windows package is built from the checked-in PyInstaller spec:
- `packaging/d2rso.spec`

The build script is:
- `scripts/build_windows_bundle.py`

The smoke test script is:
- `scripts/smoke_test_packaged_app.py`

The deterministic archive script is:
- `scripts/archive_dist.py`

The runtime auto-exit hook used by smoke tests is controlled by:
- `D2RSO_AUTO_EXIT_MS`

The packaged asset lookup logic is handled by:
- `src/d2rso/key_icon_registry.py`

---

## 10) How to download artifacts from a workflow run

If a workflow completed successfully:
1. Open `Actions`.
2. Click the workflow run.
3. Scroll to the `Artifacts` section.
4. Download the artifact you want.

Typical artifact names:
- `d2rso-windows-bundle-<commit-sha>`
- `d2rso-release-<tag>`

Note:
- workflow artifacts are not the same thing as GitHub Release assets
- artifacts are tied to a workflow run
- release assets are attached to a GitHub Release page for long-term download

---

## 11) Re-running failed workflows

If a workflow failed and you want to retry it:
1. Open the failed workflow run.
2. Click `Re-run jobs` or `Re-run failed jobs`.
3. Wait for the rerun to finish.

Only rerun if the failure was transient.
If the failure is a real code problem, fix the code and push a new commit instead.

---

## 12) Local commands that match CI behavior

These commands are useful before opening a pull request.

### Lint and format check
```bash
python -m ruff check .
python -m black --check .
```

### Tests
```bash
python -m pytest
```

### Windows packaging
Run these only on Windows:
```bash
python -m pip install -e ".[dev,build]"
python scripts/build_windows_bundle.py
python scripts/smoke_test_packaged_app.py
python scripts/archive_dist.py
```

---

## 13) Notes for this project

Important project-specific details:
- packaging is Windows-only
- CI still runs tests on Linux and Windows
- the packaged application is currently distributed as a portable ZIP
- uninstall is therefore manual, not MSI-based

For end-user installation and removal steps, see:
- `planning/documents/windows_install_uninstall_guide.md`
