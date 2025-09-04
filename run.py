# run.py
import os
from grapple import create_app

# The create_app function is called here to create the app instance.
# This ensures all extensions, including db, are properly initialized.
app = create_app()

# You can run the application directly from this file.
if __name__ == '__main__':
    # Set FLASK_APP to the name of this file (e.g., 'run.py')
    os.environ['FLASK_APP'] = 'run.py'
    app.run(debug=True)

