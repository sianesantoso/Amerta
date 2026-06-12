import bcrypt

password = "admin123"  # Ganti dengan password yang ingin di-hash
hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

# Konversi hasil hash dari bytes ke string
hashed_password_str = hashed_password.decode('utf-8')

print("Hash Password (String):", hashed_password_str)
