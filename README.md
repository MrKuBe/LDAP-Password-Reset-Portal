# README.md

# LDAP Password Reset Portal

## Overview
A Flask / Python / Fomantic UI script that facilitates Active Directory password reset requests through a secure workflow involving a sponsor system.

## Screenshots

### Login Windows
<img width="385" alt="2025-04-02_17h22_11" src="https://github.com/user-attachments/assets/0edcb4d9-c50e-492d-960a-e600f7cecf03" />

### Menu
<img width="679" alt="2025-04-02_17h22_32" src="https://github.com/user-attachments/assets/984ab17e-d3b2-452a-b3b5-ada0dcd32e2d" />

### Password Reset Page
<img width="678" alt="2025-04-02_17h22_50" src="https://github.com/user-attachments/assets/a6d462f7-a4f1-4f9e-8082-3499510aed06" />

### Notification sent after reset
<img width="563" alt="2025-04-02_17h23_51" src="https://github.com/user-attachments/assets/9e3c8c44-ce44-4ce5-a4b0-3f52aafe8353" />

## Project Structure
- `src/app.py`: Main entry point of the Flask application.
- `src/templates/`: Contains HTML templates for the application.
  - `base.html`: Base template with Fomantic-UI integration.
  - `index.html`: Homepage content extending the base template.
- `src/static/`: Contains static files such as CSS and JavaScript.
  - `css/custom.css`: Custom styles for the application.
  - `js/custom.js`: Custom JavaScript for interactivity.
- `tests/test_app.py`: Unit tests for the application.
- `requirements.txt`: Lists project dependencies.
- `.env`: Environment variables for configuration.
- `.gitignore`: Specifies files to ignore in version control.

## Setup Instructions
1. Clone the repository:
   ```
   git clone <repository-url>
   cd flask-fomantic-ui
   ```

2. Create a virtual environment:
   ```
   python -m venv venv
   ```

3. Activate the virtual environment:
   - On Windows:
     ```
     venv\Scripts\activate
     ```
   - On macOS/Linux:
     ```
     source venv/bin/activate
     ```

4. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

5. Set up environment variables in the `.env` file as needed.

## Running the Application
To run the application, execute the following command:
```
python src/app.py
```
The application will be available at `http://127.0.0.1:5000`.

## Deployment
For local deployment, ensure that the environment is set up as described above. For production deployment, consider using a WSGI server like Gunicorn or uWSGI behind a reverse proxy such as Nginx.

## License
This project is licensed under the MIT License. See the LICENSE file for details.
