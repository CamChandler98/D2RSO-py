# Windows Dev Environment Setup Guide (Fresh Machine)

This guide is for a first-time contributor/tester setting up D2RSO on a brand-new Windows machine.

---

## 1) Install required software

Do these steps in order.

### 1.1 Install Git for Windows
1. Go to: https://git-scm.com/download/win
2. Download and run the installer.
3. During setup, default options are fine.
4. After install, open **Git Bash** from Start Menu.

Verify:
```bash
git --version
```

### 1.2 Install Python 3.11
1. Go to: https://www.python.org/downloads/windows/
2. Download **Python 3.11.x (64-bit)**.
3. Run installer and **check “Add Python to PATH”**.
4. Finish install.

Verify in a new Git Bash window:
```bash
python --version
```
Expected: `Python 3.11.x`

> If `python` is not found, try `py --version` and use `py -3.11` in commands where needed.

### 1.3 Install VS Code (recommended IDE)
1. Go to: https://code.visualstudio.com/
2. Install with default options.
3. Open VS Code and install extensions:
   - **Python** (Microsoft)
   - **Pylance** (Microsoft)
   - Optional: **GitLens**

### 1.4 Install Pipenv
In Git Bash:
```bash
python -m pip install --upgrade pip
python -m pip install pipenv
```

Verify:
```bash
pipenv --version
```

---

## 2) Get the project code

### 2.1 Choose a folder
Example (Git Bash):
```bash
mkdir -p ~/dev
cd ~/dev
```

### 2.2 Clone repository
Replace `<repo-url>` with the project URL you were given.

```bash
git clone <repo-url>
cd D2RSO-py
```

Confirm files are present:
```bash
git status
```
Expected: `On branch ...` and clean working tree.

---

## 3) Create and install the development environment

Run from the repo root (`D2RSO-py`):

```bash
pipenv --python 3.11
pipenv install --dev
```

This can take a few minutes the first time.

### 3.1 If Pipenv cannot find Python 3.11
Use one of these:
```bash
pipenv --python "$(py -3.11 -c 'import sys; print(sys.executable)')"
```
or
```bash
py -3.11 -m pip install pipenv
py -3.11 -m pipenv --python 3.11
```

---

## 4) Run the app and verify setup

From repo root:

```bash
pipenv run python -m d2rso
```

Expected behavior: a placeholder D2RSO window appears without crashing.

Close the app window after confirming it launches.

---

## 5) Run validation checks

### 5.1 Automated tests
```bash
pipenv run pytest
```

### 5.2 Core pre-CI checks
```bash
pipenv run bash scripts/pre_ci_core_logic.sh
```

### 5.3 Lint + formatting checks
```bash
pipenv run ruff check .
pipenv run black --check .
```

If all pass, environment setup is good.

---

## 6) Open the project in VS Code

1. In VS Code, click **File → Open Folder**.
2. Select your `D2RSO-py` folder.
3. Open Terminal in VS Code (**Terminal → New Terminal**).
4. Use Git Bash profile if prompted.
5. Confirm Python interpreter is from Pipenv:
   - Press `Ctrl+Shift+P`
   - Run **Python: Select Interpreter**
   - Choose the one from Pipenv/virtualenv for this repo.

---

## 7) Day-to-day commands for testing

From repo root:

```bash
pipenv run python -m d2rso
pipenv run pytest
pipenv run ruff check .
pipenv run black --check .
```

If you pull new changes, run:

```bash
git pull
pipenv install --dev
```

---

## 8) Troubleshooting

### 8.1 `pipenv` command not found
- Reopen terminal.
- Retry install:
  ```bash
  python -m pip install --user pipenv
  ```
- If needed, run Pipenv as module:
  ```bash
  python -m pipenv --version
  ```

### 8.2 `python` points to wrong version
- Check:
  ```bash
  py -0p
  ```
- Use explicit launcher:
  ```bash
  py -3.11 -m pipenv install --dev
  ```

### 8.3 `pytest` fails due to missing dependency
- Ensure you are in repo root and use `pipenv run` prefix.
- Reinstall:
  ```bash
  pipenv --rm
  pipenv --python 3.11
  pipenv install --dev
  ```

### 8.4 App doesn’t launch on first try
- Re-run install command and try again.
- Confirm Windows Defender/antivirus is not blocking Python.

---

## 9) What to send back after setup

When reporting setup results, include:
1. Output of:
   - `python --version`
   - `pipenv --version`
   - `pipenv run pytest`
2. Whether `pipenv run python -m d2rso` opened the app window.
3. Any error message screenshots.

This makes troubleshooting much faster.
