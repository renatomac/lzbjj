from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, current_user, login_required
from grapple import db, bcrypt
from grapple.forms import LoginForm, RegistrationForm
from grapple.models import User

# Define the blueprint
auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """
    Handles user login.
    """
    # If the user is already logged in, redirect them to the dashboard
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    
    # Create the login form
    form = LoginForm()
    
    # Process the form submission
    if form.validate_on_submit():
        # Find the user by email
        user = User.query.filter_by(email=form.email.data).first()
        
        # Check if the user exists and the password is correct
        if user and bcrypt.check_password_hash(user.password_hash, form.password.data):
            # Log in the user and remember them if the checkbox is selected
            login_user(user, remember=form.remember_me.data)
            
            # Flash a success message
            flash('Logged in successfully.', 'success')
            
            # Redirect to the next page or the dashboard
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard.index'))
        else:
            # Flash an error message for invalid credentials
            flash('Invalid email or password.', 'danger')
            
    # Render the login template
    return render_template('auth/login.html', title='Login', form=form)

@auth_bp.route('/logout')
@login_required
def logout():
    """
    Logs out the current user.
    """
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """
    Handles new user registration.
    """
    # If the user is already logged in, redirect them to the dashboard
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    
    # Create the registration form
    form = RegistrationForm()
    
    # Process the form submission
    if form.validate_on_submit():
        # Hash the password for security
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        
        # Create a new User object
        user = User(
            username=form.username.data,
            email=form.email.data,
            password_hash=hashed_password
        )
        
        # Add the new user to the database session and commit
        db.session.add(user)
        db.session.commit()
        
        # Flash a success message and redirect to the login page
        flash('Congratulations, you are now a registered user!', 'success')
        return redirect(url_for('auth.login'))
        
    # Render the registration template
    return render_template('auth/register.html', title='Register', form=form)
