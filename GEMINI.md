# Aelyra Project Technical Overview

This document provides a technical summary of the Aelyra project, an AI-powered Spotify playlist generator.

## Project Description

Aelyra is a full-stack web application designed to generate Spotify playlists for users based on their preferences, using an AI service (likely OpenAI) to interpret user requests and the Spotify API to create and manage playlists.

## Core Technologies

### Backend

*   **Framework**: Python with FastAPI
*   **Dependencies**:
    *   `fastapi`: Core web framework
    *   `uvicorn`: ASGI server
    *   `SQLAlchemy`: Database ORM
    *   `alembic`: Database migrations
    *   `openai`: For AI-powered playlist generation
    *   `requests`: For making HTTP requests to the Spotify API
    *   `python-dotenv`: For managing environment variables
*   **Database**: The specific database is not explicitly defined, but it is accessed via SQLAlchemy.
*   **API**: The backend exposes a RESTful API for the frontend to consume.

### Frontend

*   **Framework**: JavaScript with React
*   **Dependencies**:
    *   `react`: Core UI library
    *   `axios`: For making HTTP requests to the backend API
    *   `vite`: Build tool and development server
*   **Package Manager**: npm

## Project Structure

*   **`app/`**: Contains the backend Python/FastAPI application.
    *   **`app/routers/`**: Defines the API endpoints.
    *   **`app/services/`**: Contains the business logic, including interactions with the OpenAI and Spotify APIs.
    *   **`app/models/`**: Defines the data models (Pydantic and SQLAlchemy).
    *   **`app/database.py`**: Configures the database connection.
*   **`frontend/`**: Contains the frontend React application.
    *   **`frontend/src/components/`**: Reusable React components.
*   **`alembic/`**: Manages database migrations.
*   **`utils/`**: Contains utility scripts for development and deployment.

## Development Setup & Commands

### Backend

*   **Dependencies**: Installed from `requirements.txt` using `pip install -r requirements.txt`.
*   **Running**: The backend is started with `python main.py`. It runs on `http://127.0.0.1:5988` by default.

### Frontend

*   **Dependencies**: Installed from `frontend/package.json` using `npm install` in the `frontend` directory.
*   **Running**: The frontend is started with `npm start` in the `frontend` directory. It runs on `http://localhost:3000` by default and proxies API requests to the backend.

### Full-Stack (Development)

The entire application can be launched for development using the `utils/launch-dev.sh` script. This script starts both the backend and frontend servers.
