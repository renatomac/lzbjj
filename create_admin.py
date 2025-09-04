import os
import sys
from getpass import getpass
from grapple import create_app, db
from grapple.models import User, Staff

# Set the Flask app configuration to 'development'
os.environ['FLASK_CONFIG'] = 'development'
app = create_app()

with app.app_context():
    # Prompt the user for all necessary information
    email = 'renato.2208@gmail.com' #input('Enter the user\'s email: ')
    username = 'renato'# input('Enter the user\'s username: ')
    role = 'admin' # input('Enter the user\'s role (admin, coach, staff): ')
    password = 'adminpass' # getpass('Enter the user\'s password: ')

    # Check for an existing user with the provided email
    if User.query.filter_by(email=email).first():
        print(f'A user with the email {email} already exists.')
        sys.exit()

    try:
        # Create a new User object
        user = User(
            username=username,
            email=email,
            role=role
        )
        # Set the password using the model's method, which now handles hashing
        user.set_password(password)

        # Add the user to the session and commit to the database
        db.session.add(user)
        db.session.commit()

        # If the user is a staff or coach, create a Staff record and associate it
        if role in ['coach', 'staff']:
            first_name = input('Enter the staff member\'s first name: ')
            last_name = input('Enter the staff member\'s last name: ')
            phone = input('Enter the staff member\'s phone (optional): ')
            is_coach = (role == 'coach')

            staff = Staff(
                first_name=first_name,
                last_name=last_name,
                phone=phone,
                is_coach=is_coach,
                user_id=user.id
            )
            db.session.add(staff)
            db.session.commit()
            print(f'{role.capitalize()} staff record created for {staff.full_name()}.')

        print(f'User created successfully: {user.username} with role {user.role}.')

    except Exception as e:
        # Rollback the session in case of any error
        db.session.rollback()
        print(f'An error occurred: {e}')
        sys.exit(1)
