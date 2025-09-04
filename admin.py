from grapple import create_app, db
from grapple.models import User
from werkzeug.security import generate_password_hash

app = create_app()
with app.app_context():
    admin = User.query.filter_by(username='renato').first()
    if not admin:
        admin = User(
            username='renato',
            email='admin@example.com',
            password_hash=generate_password_hash('adminpass'),  # Add a comma here
            role='admin'
        )
        db.session.add(admin)
        db.session.commit()
        print("Admin user created.")
    else:
        print("Admin user already exists.")