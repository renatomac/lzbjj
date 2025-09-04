# grapple/seed_staff.py
from app import create_app
from app.models import db, RolePermission
app = create_app()
with app.app_context():
    defaults = {
        'Coach': ['attendance','members','reports'],
        'Assistant': ['attendance','members'],
        'Auxiliar': ['members','billing'],
        'Admin': ['attendance','billing','members','reports','staff','settings'],
        'Front Desk': ['members','billing'],
    }
    for role, perms in defaults.items():
        rp = RolePermission.query.filter_by(role=role).first()
        if not rp:
            db.session.add(RolePermission(role=role, permissions=perms))
        else:
            rp.permissions = perms
    db.session.commit()
    print('Seeded role permissions.')