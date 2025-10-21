# Project: Plant ID Community

## Project Overview

This project is a transformation of the Plant ID Community from a Progressive Web App (PWA) to a dual-platform solution consisting of a Flutter-based mobile app and a Django/Wagtail-based web app.

*   **Mobile App (Flutter):** The primary application for plant identification, featuring camera-based identification, disease diagnosis, and user collections. It will be built with Flutter and use Firebase for backend services.
*   **Web App (Django/Wagtail):** A blog and forum platform with limited plant identification capabilities (image uploads only). It will be powered by a headless Django/Wagtail CMS and a React frontend.

The project is well-planned, with detailed documentation covering the technology stack, architecture, and development roadmap.

## Building and Running

### Mobile App (Flutter)

*   **Prerequisites:** Flutter SDK, Dart
*   **Setup:**
    1.  Navigate to the `mobile` directory.
    2.  Run `flutter pub get` to install dependencies.
*   **Running:**
    *   Run `flutter run` to launch the app on a connected device or emulator.

### Web App (Django/Wagtail & React)

*   **Prerequisites:** Python, Node.js, PostgreSQL
*   **Backend (Django/Wagtail):**
    1.  Navigate to the `backend` directory.
    2.  Create and activate a virtual environment.
    3.  Run `pip install -r requirements/development.txt`.
    4.  Run `python manage.py migrate`.
    5.  Run `python manage.py runserver`.
*   **Frontend (React):**
    1.  Navigate to the `frontend` directory.
    2.  Run `npm install`.
    3.  Run `npm run dev`.

## Development Conventions

*   **State Management (Flutter):** Riverpod
*   **Styling (Web):** Tailwind CSS
*   **Database:**
    *   **Mobile:** Cloud Firestore
    *   **Web:** PostgreSQL
*   **Authentication:** Firebase Authentication (shared between mobile and web)
*   **API:** The web backend will expose a REST API for the mobile app and the React frontend.
*   **Design:** The project has a defined design system with dark and light themes, documented in Figma.

## Key Files

*   `PLANNING/03_MASTER_PLAN.md`: The main planning document, outlining the project's vision, architecture, and phased roadmap.
*   `PLANNING/01_TECHNOLOGY_STACK.md`: A comprehensive list of all technologies and frameworks to be used.
*   `PLANNING/06_DATABASE_SCHEMA.md`: The database schema for both Firestore and PostgreSQL.
*   `PLANNING/07_API_DOCUMENTATION.md`: The documentation for the REST API.
*   `design_reference/`: Contains a React-based reference implementation of the design system.
