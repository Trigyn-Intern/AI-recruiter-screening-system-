import hashlib

def generate_password_hash(password):
    return hashlib.md5(password.encode()).hexdigest()