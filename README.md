# Health Agent Project

**Project**: Audio Data Evaluation by AI — Acts like a voice assistant and interviewer  
**Research Project**: Faculty of Medicine, Shahid Beheshti University of Tehran – Tracking Code **43014329**

**Version**: 0.0.2  
**Author**: _[Yasin]_

---

## Table of Contents

1. [Overview](#overview)  
2. [Features](#features)  
3. [Installation](#installation)  
   - [Prerequisites](#prerequisites)  
   - [Using Docker](#using-docker)  
4. [Usage](#usage)  
5. [Contributing](#contributing)  
6. [License](#license)

---

## Overview

This project is designed for **audio data evaluation using artificial intelligence**, functioning like both a **voice assistant** and an **interviewer**. It serves as a research initiative under the **Faculty of Medicine at Shahid Beheshti University of Tehran**, with tracking code **43014329**.

---

## Features

- Processes audio inputs
- Performs AI-driven evaluation and feedback
- Operates interactively as a voice-based assistant/interviewer
- Configurable through environment variables and templates

---

## Installation

### Prerequisites

- Docker installed on your system  
- Docker Compose (if not included with Docker)

### Using Docker

The project includes a **Dockerfile** and a **docker-compose.yml** for easy setup and deployment.

#### Steps:

1. Clone the repository:  
   ```bash
   git clone https://github.com/yas3in/health-agent.git
   cd health-agent
   ```

2. Build the Docker image (if needed):  
   ```bash
   docker build
   ```

3. Run the project using Docker Compose:  
   ```bash
   docker compose up
   ```

   Alternatively, if your system has the older Docker Compose syntax:  
   ```bash
   docker-compose up
   ```

4. (Optional) Run in detached mode:  
   ```bash
   docker compose up -d
   ```

5. To stop and remove containers, networks, etc.:  
   ```bash
   docker compose down
   ```
   Or:
   ```bash
   docker-compose down
   ```

---

## Usage

Once the container is running, access the service according to the configuration in your `docker-compose.yml` (for example, `http://localhost:8000` if defined).  
Adjust environment variables in `.env.dev` or `docker-compose.yml` as needed. You may refer to `.env.example` for reference.

---

## Contributing

Contributions, issues, and feature requests are welcome! Please fork the repo and create your pull requests.

---

## License

Specify the license here (e.g., MIT, Apache-2.0) or leave blank if undecided.
