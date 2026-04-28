# SMU Smart Classroom Management System

An IoT-based system for SMU (Mediterranean Institute of Technology) that automates student attendance tracking via face recognition, monitors classroom environmental conditions in real time (temperature, humidity, air quality, sound), controls AC and lighting through relay modules, and streams all data to a professor-facing React dashboard — all running on a Raspberry Pi 4 with no cloud dependency.

## Prerequisites

- [Docker](https://www.docker.com/) & Docker Compose (for PostgreSQL, Redis, Moodle)
- Python 3.11 (for the FastAPI backend)
- Node.js 18+ (for the React frontend)
- `make` (available on Linux/macOS; on Windows use Git Bash or WSL)

## Quick Start

```bash
# 1. Clone the repo and enter the directory
git clone <repo-url> smart-classroom
cd smart-classroom

# 2. Copy environment file and fill in your values
cp .env.example .env

# 3. Start all infrastructure services (PostgreSQL, Redis, Moodle)
make up

# 4. Install backend and frontend dependencies
make install

# 5. Start the backend API server (in one terminal)
make backend

# 6. Start the frontend dev server (in another terminal)
make frontend
```

The dashboard will be available at `http://localhost:5173`.
The API will be running at `http://localhost:8000`.
Moodle will be available at `http://localhost:8080` (admin / admin123).

## Project Structure

```
smart-classroom/
├── firmware/       ESP32 Arduino sketch (sensor node + relay control)
├── backend/        Python FastAPI application
├── frontend/       React + Vite + Tailwind dashboard
├── docs/           MQTT schema, API contracts, wiring diagrams
└── docker-compose.yml
```

## Team

Ben Jemaa · Jallouli · Saadaoui · Ouertani · Day — SMU MedTech Freshman ISS
