import hashlib

plain_text: str = "Une chaine de caractère à hacher."
hashed_text: str = hashlib.sha256(plain_text.encode()).hexdigest()