import base64

class CryptoUtils:
   @staticmethod
   def encrypt(text: str) -> str:
       """
       Encrypts a given text using base64 encoding.
       """
       encoded_bytes = text
       base64_bytes = base64.b64encode(encoded_bytes)
       return base64_bytes

   @staticmethod
   def decrypt(ciphertext: str) -> str:
       """
       Decrypts the given text using base64 decoding.
       """
       base64_bytes = ciphertext
       decoded_bytes = base64.b64decode(base64_bytes)
       return decoded_bytes
