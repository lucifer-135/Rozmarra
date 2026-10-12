# Rozmarra doctor dashboard

This folder contains the doctor dashboard for Rozmarra. The dashboard is built with React, TypeScript and Vite. It uses Tailwind CSS and shadcn/ui for the layout and components, and i18next for English and Hindi text.

The dashboard only displays results. All data processing, modelling and prediction logic lives in the Rozmarra Python package in the `backend` folder.

## Commands

Please run these commands in this folder.

| Command | What it does |
|---|---|
| `npm install` | Installs the packages. |
| `npm run dev` | Starts the dashboard at http://localhost:5173. The dashboard sends API requests to the Rozmarra service at http://127.0.0.1:8000. |
| `npm run test` | Runs the component tests with Vitest. |
| `npm run build` | Checks the TypeScript code and builds the dashboard into the `dist` folder. |

## Text and translation

All interface text lives in `src/i18n/en.json` and `src/i18n/hi.json`. Components do not contain hard-coded text. A native Hindi speaker reviews the Hindi text before the submission.
