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
import smtplib
from email.mime.text import MIMEText

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

def check_user_exists(conn: Connection, samAccountName: str) -> bool:
    """Check if user exists in AD."""
    search_filter = f'(sAMAccountName={escape_filter_chars(samAccountName)})'
    conn.search(
        config['search_base'],
        search_filter,
        search_scope=SUBTREE,
        attributes=['employeeID']
    )
    return len(conn.entries) > 0

def verify_employee_id(conn: Connection, samAccountName: str, employeeID: str) -> bool:
    """Verify if employeeID matches the user."""
    search_filter = f'(&(sAMAccountName={escape_filter_chars(samAccountName)})(employeeID={escape_filter_chars(employeeID)}))'
    conn.search(
        config['search_base'],
        search_filter,
        search_scope=SUBTREE,
        attributes=['employeeID']
    )
    return len(conn.entries) > 0

def verify_user_service(conn: Connection, samAccountName: str, serviceCode: str) -> bool:
    """Verify if user belongs to the specified service code (department)."""
    try:
        search_filter = f'(sAMAccountName={escape_filter_chars(samAccountName)})'
        conn.search(
            config['search_base'],
            search_filter,
            search_scope=SUBTREE,
            attributes=['department']
        )
        
        if len(conn.entries) == 0:
            log_debug(f"User {samAccountName} not found")
            return False
            
        user_department = conn.entries[0].department.value
        log_debug(f"User department: {user_department}, Required service: {serviceCode}")
        
        # Check if department matches service code
        return user_department == serviceCode
        
    except Exception as e:
        logging.error(f"Error verifying user service: {str(e)}")
        return False

def is_operator(conn: Connection, username: str) -> bool:
    """Check if user is member of the operator group."""
    try:
        # Get user's DN first
        search_filter = f'(sAMAccountName={escape_filter_chars(username)})'
        conn.search(
            config['search_base'],
            search_filter,
            search_scope=SUBTREE,
            attributes=['memberOf']
        )
        
        if not conn.entries:
            log_debug(f"User {username} not found")
            return False
        
        # Check if user is member of operator group
        member_of = conn.entries[0].memberOf.values if hasattr(conn.entries[0], 'memberOf') else []
        operator_group = config['ldap']['operatorGroup']
        
        log_debug(f"User groups: {member_of}")
        log_debug(f"Required group: {operator_group}")
        
        return operator_group in member_of
        
    except Exception as e:
        logging.error(f"Error checking operator status: {str(e)}")
        return False

def is_vip_user(conn: Connection, username: str) -> bool:
    """Check if user is member of VIP group or has admin privileges."""
    try:
        search_filter = f'(sAMAccountName={escape_filter_chars(username)})'
        conn.search(
            config['search_base'],
            search_filter,
            search_scope=SUBTREE,
            attributes=['memberOf', 'adminCount']
        )
        
        if not conn.entries:
            log_debug(f"User {username} not found")
            return False
        
        # Check VIP group membership
        member_of = conn.entries[0].memberOf.values if hasattr(conn.entries[0], 'memberOf') else []
        vip_group = config['ldap']['vipGroup']
        is_vip = vip_group in member_of
        
        # Check admin privileges
        has_admin = hasattr(conn.entries[0], 'adminCount') and conn.entries[0].adminCount.value == 1
        
        log_debug(f"User {username} - VIP: {is_vip}, Admin: {has_admin}")
        return is_vip or has_admin
        
    except Exception as e:
        logging.error(f"Error checking VIP status: {str(e)}")
        return False

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

def send_notification_email(parrain: dict, user_details: dict) -> bool:
    """Send notification email to parrain and IT service."""
    try:
        # Create message for parrain
        subject = f"Password reset request for {user_details['user_samAccountName']}"
        body = f"""
        Hello {parrain['samAccountName']},
        
        A password reset request has been submitted with the following details:
        - User: {user_details['user_samAccountName']}
        - Service Code: {user_details['serviceCode']}
        - Employee ID: {user_details['employeeID']}
        
        The IT service has been notified and will process your request.
        """
        
        # Create email message
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = config['smtp']['fromAddress']
        msg['To'] = parrain['email']
        msg['Cc'] = config['itServiceEmail']
        
        # Connect to SMTP server and send
        with smtplib.SMTP(config['smtp']['server'], config['smtp']['port']) as server:
            if config['smtp']['use_tls']:
                server.starttls()
            
            recipients = [parrain['email'], config['itServiceEmail']]
            server.sendmail(config['smtp']['fromAddress'], recipients, msg.as_string())
            
        log_debug(f"Notification email sent to {parrain['email']} and {config['itServiceEmail']}")
        return True
        
    except Exception as e:
        logging.error(f"Error sending notification email: {str(e)}")
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
                # Check if user is an operator
                if is_operator(conn, username):
                    session['username'] = username
                    session['password'] = password
                    session['email'] = f"{username}{config['ldap']['emailDomain']}"
                    flash('Login successful!', 'success')
                    return redirect(url_for('index'))
                else:
                    flash('Access denied. You must be a member of the operator group. Please contact IT Service.', 'error')
                    logging.warning(f"Unauthorized access attempt by {username} - not a member of operator group")
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

        try:
            conn = get_ldap_connection(session['username'], session.get('password', ''))
            if not conn:
                flash('Unable to verify user information. Please try again.', 'error')
                return render_template('reset_password.html', form=form)

            # Check if target user exists
            if not check_user_exists(conn, user_details['user_samAccountName']):
                flash('Target user does not exist.', 'error')
                return render_template('reset_password.html', form=form)

            # Check if target user is VIP or admin
            if is_vip_user(conn, user_details['user_samAccountName']):
                flash('Password reset not allowed for VIP or admin users. Please contact IT Service.', 'error')
                logging.warning(f"Attempt to reset password for VIP/admin user {user_details['user_samAccountName']} by {parrain['samAccountName']}")
                return render_template('reset_password.html', form=form)

            # Verify employee ID matches the user
            if not verify_employee_id(conn, user_details['user_samAccountName'], user_details['employeeID']):
                flash('Employee ID does not match the specified user.', 'error')
                return render_template('reset_password.html', form=form)

            # Verify user's service code matches department
            if not verify_user_service(conn, user_details['user_samAccountName'], user_details['serviceCode']):
                flash('Service code does not match user\'s department.', 'error')
                return render_template('reset_password.html', form=form)

            # All checks passed, create the reset request
            if create_json(parrain, user_details):
                if send_notification_email(parrain, user_details):
                    flash('Password reset request submitted and notifications sent!', 'success')
                else:
                    flash('Request submitted but email notification failed.', 'warning')
                return redirect(url_for('index'))
            else:
                flash('Error creating password reset request.', 'error')

        except Exception as e:
            logging.error(f"Error processing reset request: {str(e)}")
            flash('An error occurred while processing your request.', 'error')
            
    return render_template('reset_password.html', form=form)

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)