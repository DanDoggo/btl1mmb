# Format: {"username": "password"}
USERS = {
    "admin": "admin",
    "a": "a",
    "b": "b",
    "c": "c"
}

def get_password(username):
    """Retrieve password for a given username."""
    return USERS.get(username)