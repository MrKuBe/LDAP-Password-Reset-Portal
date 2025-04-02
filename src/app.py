from flask import Flask, render_template, request, flash, redirect, url_for, session
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email
import json
import os
from datetime import datetime, timedelta
from ldap3 import Server, Connection, SUBTREE, ALL
from ldap3.utils.conv import escape_filter_chars
from ldap3.core.exceptions import LDAPSocketOpenError
import logging
import time
import uuid
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'default-secret-key')

# Load config from JSON
try:
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    with open(config_path) as f:
        config = json.load(f)
    print(f"Config loaded successfully from: {config_path}")  # Ligne de debug
except FileNotFoundError:
    logging.error("Configuration file not found. Please ensure config.json exists in the src directory.")
    raise
except json.JSONDecodeError:
    logging.error("Invalid JSON in configuration file.")
    raise

# Configure logging
logging.basicConfig(level=logging.INFO if config.get('verbose', False) else logging.WARNING)

# Form Classes
class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class PasswordResetForm(FlaskForm):
    user_samAccountName = StringField('User SAM Account Name', validators=[DataRequired()])
    employeeID = StringField('Employee ID', validators=[DataRequired()])
    serviceCode = StringField('Service Code', validators=[DataRequired()])
    submit = SubmitField('Reset Password')

def log_debug(message: str, *args):
    """Conditional logging function."""
    if config.get('verbose', True):
        logging.info(message, *args)

def get_ldap_connection(samAccountName: str, password: str, max_retries: int = 3):
    """Establishes secure LDAP connection with retries."""
    retries = 0
    retry_delay = config.get('ldap', {}).get('retryDelay', 5)
    connect_timeout = config.get('ldap', {}).get('connectTimeout', 30)
    receive_timeout = config.get('ldap', {}).get('receiveTimeout', 30)

    while retries < max_retries:
        try:
            log_debug(f"Attempting LDAP connection (attempt {retries + 1}/{max_retries})")
            server = Server(
                config['ldap']['server'], 
                use_ssl=True, 
                get_info=ALL,
                mode='IP_V4_ONLY',
                connect_timeout=connect_timeout
            )
            
            # Use standard domain\username format for Windows AD
            domain = config['ldap']['domain'].split('.')[0]
            user_dn = f"{domain}\\{samAccountName}"
            log_debug(f"Binding with user: {user_dn}")
            
            conn = Connection(
                server, 
                user=user_dn,
                password=password, 
                authentication='SIMPLE',
                receive_timeout=receive_timeout,
                auto_bind=False
            )

            if conn.bind():
                log_debug("LDAPS connection successful")
                return conn
            else:
                log_debug(f"LDAPS bind failed: {conn.result}")
                return None
            
        except LDAPSocketOpenError as e:
            retries += 1
            log_debug(f"Connection attempt failed: {str(e)}")
            if retries < max_retries:
                time.sleep(retry_delay)
            else:
                raise
                
        except Exception as e:
            logging.error(f"LDAP connection error: {str(e)}")
            raise
    
    return None

def create_json(parrain: dict, user_details: dict) -> bool:
    """
    Create JSON file for password reset request with specific filename format:
    YYYYMMDD_HHMMSS_password_reset_PARRAIN_FILLEUL.json
    """
    try:
        # Generate timestamp and filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_password_reset_{parrain['samAccountName']}_{user_details['user_samAccountName']}.json"
        
        # Prepare data structure
        data = {
            "samAccountName": parrain['samAccountName'],
            "email": parrain['email'],
            "user_samAccountName": user_details['user_samAccountName'],
            "serviceCode": user_details['serviceCode'],
            "employeeID": user_details['employeeID']
        }
        
        # Create full path using config
        filepath = os.path.join(
            config['share']['path'],
            filename
        )
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        # Write JSON file
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)
            
        log_debug(f"Password reset request file created: {filepath}")
        return True
        
    except Exception as e:
        logging.error(f"Error creating password reset request: {str(e)}")
        return False

@app.route('/')
def index():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        
        try:
            conn = get_ldap_connection(username, password)
            if conn and conn.bind():
                session['username'] = username
                session['email'] = f"{username}{config['ldap']['emailDomain']}"
                flash('Login successful!', 'success')
                return redirect(url_for('index'))
            else:
                flash('Invalid credentials.', 'error')
        except Exception as e:
            logging.error(f"Login error: {str(e)}")
            flash('An error occurred during login.', 'error')
    
    return render_template('login.html', form=form)

@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    form = PasswordResetForm()
    if form.validate_on_submit():
        user_details = {
            'user_samAccountName': form.user_samAccountName.data,
            'employeeID': form.employeeID.data,
            'serviceCode': form.serviceCode.data
        }
        
        parrain = {
            'samAccountName': session['username'],
            'email': session['email']
        }
        
        # Process password reset request
        create_json(parrain, user_details)
        flash('Password reset request submitted successfully!', 'success')
        return redirect(url_for('index'))
    
    return render_template('reset_password.html', form=form)

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)