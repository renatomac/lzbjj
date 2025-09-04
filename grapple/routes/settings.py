# grapple/routes/plan.py
from flask import Blueprint, render_template
from flask_login import login_required
from grapple.decorators import admin_required


# Ensure the blueprint name and url_prefix match your project's conventions
settings_bp = Blueprint('settings', __name__, url_prefix='/settings')

@settings_bp.route('/')
@login_required
def index():

    """Render the settings index page for admin users."""
    return render_template('settings/index.html')

