# CI & Windows Server 2016 Compatibility

This document describes how the LangID service and dashboard are validated for Windows using GitHub Actions, and what that implies for running on **Windows Server 2016**.

## 1. GitHub Actions CI on Windows

The repository includes a GitHub Actions workflow at:

- `.github/workflows/ci-windows.yml`

This workflow runs automatically on:

- Pushes to `main` or `master`
- Pull requests targeting `main` or `master`

### 1.1 Runner and OS

The job uses GitHub's **`windows-latest`** runner, which is currently based on Windows Server 2022. While this is newer than Windows Server 2016, the toolchain used here (Python, Node.js, FastAPI, React) does not rely on OS-specific features, so a successful CI run is a strong indicator that the code will also run correctly on Windows Server 2016 with the same runtime versions.

### 1.2 Toolchain Versions

The workflow pins the following versions:

- **Python:** 3.11
- **Node.js:** 20

On your Windows Server 2016 machine, you should install matching (or compatible) runtime versions:

- Python 3.11.x (64-bit)
- Node.js 20.x (LTS or later, as long as it is compatible with `react-scripts`)

### 1.3 CI Steps Overview

The `test-and-build` job performs these steps:

1. **Checkout repository**
   - Uses `actions/checkout@v4`.

2. **Set up Python**
   - Uses `actions/setup-python@v5` with `python-version: '3.11'`.

3. **Set up Node.js**
   - Uses `actions/setup-node@v4` with `node-version: '20'`.

4. **Backend (LangID service) tests**
   - `working-directory: ./langid_service`
   - Install dependencies:
     - `python -m pip install --upgrade pip`
     - `pip install -r requirements.txt`
   - Run tests:
     - `pytest`

5. **Dashboard build (React/Tailwind)**
   - `working-directory: ./dashboard`
   - Install dependencies:
     - `npm ci`
   - Run build:
     - `npm run build`

If any of these steps fail, the workflow fails, preventing merges until the issue is fixed.

## 2. Mapping CI to Windows Server 2016

To mirror the CI environment on a Windows Server 2016 machine:

1. Install the same runtime versions:
   - Python 3.11 (64-bit)
   - Node.js 20 (64-bit)

2. Clone the repository and create a virtual environment for the backend:

   ```powershell
   git clone https://github.com/<org>/LangId-mr.git C:\LangId-mr
   cd C:\LangId-mr
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r langid_service\requirements.txt
   ```

3. Run backend tests manually (optional but recommended):

   ```powershell
   .venv\Scripts\activate
   pytest
   ```

4. Install dashboard dependencies and build:

   ```powershell
   cd C:\LangId-mr\dashboard
   npm ci
   npm run build
   ```

5. Serve the dashboard (for example, using `serve`):

   ```powershell
   npm install -g serve
   serve -s build -l 3000
   ```

Your Windows Server 2016 deployment should use these same steps (or scripts that wrap them) under a service manager like NSSM.

## 3. Relationship to the Windows Deployment Guide

The main `README.md` focuses on **Windows Server deployment** of the backend service (NSSM, `.env`, logging, database, etc.). This CI document complements it by:

- Ensuring the backend and dashboard **build and test successfully on Windows** via GitHub Actions.
- Providing a clear mapping between CI steps and the manual steps you run on Windows Server 2016.

In short:

- If CI is green on `windows-latest`, and
- You install **matching Python/Node versions** and run the same commands on Windows Server 2016,

then you can be confident that the LangID service and dashboard will build and run correctly on your target Windows environment.
