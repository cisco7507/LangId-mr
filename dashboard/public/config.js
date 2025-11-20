// Public configuration for the LangID dashboard
// This file is loaded before the React bundle and can be swapped per environment
// without rebuilding the app.

// Base URL for the LangID API
// For local development:
//   http://localhost:8080
// For Windows Server deployment, update this to your service URL, e.g.:
//   http://your-server-hostname:8080

//window.API_URL = "http://localhost:8080";

window.API_URL = `${location.protocol}//${location.hostname}:8080`;