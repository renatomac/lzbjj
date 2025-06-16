from werkzeug.security import generate_password_hash
admin_password = generate_password_hash('adminpassword')
print(admin_password)