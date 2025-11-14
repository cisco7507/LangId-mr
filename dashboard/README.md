# LangID Dashboard

This directory contains the React-based dashboard for monitoring LangID jobs and inspecting detailed results.

It is designed to:
- Show live job statistics (total, succeeded, failed, processing)
- List jobs with status, progress, timestamps, and errors
- Let you delete selected jobs
- Display detailed results (language, probability, processing time, transcript snippet, raw JSON) in a modal

The dashboard is built with **Create React App**, **Tailwind CSS**, and talks to the LangID backend via a configurable API base URL.

---

## 1. Prerequisites

- Node.js (v18+ recommended)
- npm
- LangID backend running (by default on `http://localhost:8080`)

From the repo root:

```bash
cd LangId-mr
source .venv/bin/activate  # if you have a virtualenv
python -m uvicorn langid_service.app.main:app --reload --host 0.0.0.0 --port 8080
```

---

## 2. Local development

From the `dashboard` folder:

```bash
cd dashboard
npm install
npm start
```

This will:
- Start the CRA dev server on `http://localhost:3000`
- Use the API base URL from `public/config.js` (see below)

Make sure the backend is running at the URL configured in `config.js`.

---

## 3. API base URL configuration (`public/config.js`)

The dashboard uses a small runtime config file to know where the API lives, so you can use a **single build** in multiple environments.

File: `dashboard/public/config.js`

```js
// Default for local dev
window.API_URL = "http://localhost:8080";
```

Behavior:
- The React app reads `window.API_URL` at runtime (via `src/config.js`).
- To point the dashboard at a different backend, edit this file and rebuild.

Examples:

```js
// On a Windows server where the API is on a different host
window.API_URL = "http://langid-api.internal:8080";
```

After changing `config.js`, rebuild the dashboard:

```bash
cd dashboard
npm run build
```

---

## 4. Tailwind CSS setup

The dashboard styling uses Tailwind. The relevant files are:

- `src/index.css` — imports Tailwind layers and sets global styles:
  - `@tailwind base;`
  - `@tailwind components;`
  - `@tailwind utilities;`
  - Dark background and typography using `@apply`.
- `tailwind.config.js` — tells Tailwind where to scan for class names.
- `postcss.config.js` — wires Tailwind and Autoprefixer into CRA's PostCSS pipeline.

You normally don't need to touch these, but if you do:

```bash
cd dashboard
npm run build
```

will regenerate the CSS bundle with your changes.

---

## 5. Production build and serving

To create a production build:

```bash
cd dashboard
npm run build
```

This generates a `build/` directory ready to be served as static files.

### Local test with `serve`

```bash
cd dashboard
npx serve -s build -l 3000
```

Then open `http://localhost:3000`.

> Note: In production on Windows Server, the provided installation script uses **NSSM** and the `serve` CLI to host this `build/` directory as a Windows service. The commands above mirror what the service does.

---

## 6. Windows Server deployment notes

On Windows Server, the typical flow is:

1. Install Node.js and npm.
2. Clone the repo and build the dashboard:
   ```powershell
   cd C:\langid_service\dashboard
   npm install
   # Edit public\config.js to point to your API URL
   npm run build
   ```
3. Use the existing PowerShell/NSSM install script (in `dashboard/launch-script`) to:
   - Register a Windows service that runs `serve -s build -l <port>`
   - Configure log output and restart behavior.

No changes to the install script are required for the new UI; just ensure `public\config.js` has the correct API URL **before** running `npm run build`.

---

## 7. Troubleshooting

**Dashboard loads but looks unstyled / plain HTML**
- Make sure `tailwind.config.js` and `postcss.config.js` exist in the `dashboard` directory.
- Ensure `src/index.css` contains the `@tailwind` directives and is imported from `src/index.js`.
- Run `npm run build` again and re-serve the `build/` folder.

**Dashboard cannot reach the API**
- Open the browser devtools console for CORS/network errors.
- Verify `window.API_URL` in `public/config.js` points to a reachable backend (e.g., `http://localhost:8080`).
- Confirm you can open `http://<API_HOST>:8080/jobs` directly in the browser.

---

## 8. Summary

- Use `npm start` for local development.
- Use `npm run build` + `serve -s build` (or the NSSM service) for production.
- Configure the API base URL via `public/config.js`.
- Tailwind + PostCSS are already wired; rebuilding will regenerate the styles.
