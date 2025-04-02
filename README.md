# README.md

# Flask Fomantic-UI Web Application

## Overview
A Flask / Python / Fomantic UI script that facilitates Active Directory password reset requests through a secure workflow involving a sponsor system.

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