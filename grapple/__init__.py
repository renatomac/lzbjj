from flask import Flask, render_template, send_from_directory
from datetime import datetime
from jinja2_time import TimeExtension
import os
from grapple.config import config
# Import extensions from the new extensions.py file
from grapple.extensions import db, migrate, login_manager, bcrypt, csrf, moment, mail

def create_app(config_name=None):
    """
    Application factory function.
    Initializes and configures the Flask application.
    """
    app = Flask(__name__)
    app.jinja_env.add_extension(TimeExtension)
    app.jinja_env.add_extension('jinja2.ext.do')
    if config_name is None:
        config_name = os.environ.get('FLASK_CONFIG', 'development')
    app.config.from_object(config[config_name])

    # Initialize extensions with the app instance.
    # The extensions are imported from a separate file, so there is no
    # circular dependency when the blueprints are imported.
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    bcrypt.init_app(app)
    csrf.init_app(app)
    moment.init_app(app)
    mail.init_app(app)
    
    login_manager.login_view = 'auth.login'
    
    # Import blueprints here, AFTER the db object has been initialized
    from grapple.routes.auth import auth_bp
    from grapple.routes.dashboard import dashboard_bp
    from grapple.routes.members import members_bp
    from grapple.routes.classes import classes_bp
    from grapple.routes.attendance import attendance_bp
    from grapple.routes.billing import billing_bp
    from grapple.routes.staff import staff_bp
    from grapple.routes.reports import reports_bp
    from grapple.routes.plan import plan_bp
    from grapple.routes.settings import settings_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(members_bp)
    app.register_blueprint(classes_bp)
    app.register_blueprint(attendance_bp)
    app.register_blueprint(billing_bp)
    app.register_blueprint(staff_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(plan_bp)
    app.register_blueprint(settings_bp)

    # Import models here to ensure the `db` instance is ready
    from grapple.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    @app.route('/static/img/favicon.ico')
    def favicon():
        return send_from_directory(os.path.join(app.root_path, 'static'),'img/favicon.ico', mimetype='image/vnd.microsoft.icon')

    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template('errors/500.html'), 500

    @app.template_filter('format_date')
    def format_date(value, format='%Y-%m-%d'):
        if value is None:
            return ''
        return value.strftime(format)

    @app.template_filter('format_currency')
    def format_currency(value):
        if value is None:
            return '$0.00'
        return '${:,.2f}'.format(value)

    @app.context_processor
    def inject_now():
        return {'now': datetime.utcnow}

    def utility_processor():
        def belt_color_class(belt_rank):
            belt_colors = {
                'white': 'white',
                'gray/white': 'gray/white',
                'gray': 'gray',
                'gray/black': 'gray/black',
                'yellow/white': 'yellow/white',
                'yellow': 'yellow',
                'yellow/black': 'yellow/black',
                'orange/white': 'orange/white',
                'orange': 'orange',
                'orange/black': 'orange/black',
                'green/white': 'green/white',
                'green': 'green',
                'green/black': 'green/black',
                'blue': 'blue',
                'purple': 'purple',
                'brown': 'brown',
                'black': 'black',
            }
            return belt_colors.get(belt_rank.lower(), 'secondary')
        
        def belt_color_text(belt_rank):
            belt_colors = {
                'white': 'text-gray-800',
                'blue': 'text-blue-800',
                'purple': 'text-purple-800',
                'brown': 'text-yellow-800',
                'black': 'text-dark',
                'red_black': 'text-dark',
                'white_yellow_stripe': 'text-info',
                'yellow_stripe': 'text-warning',
                'orange_stripe': 'text-warning',
                'green_stripe': 'text-success'
            }
            return belt_colors.get(belt_rank.lower(), 'text-secondary')

        belt_stripes = {
            '1': '1',
            '2': '2',
            '3': '3',
            '4': '4',
        }

        return dict(belt_color_class=belt_color_class, belt_color_text=belt_color_text, belt_stripes=belt_stripes)

    return app

