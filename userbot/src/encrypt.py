import uuid

class CryptoUtils:
    @staticmethod
    def crypto_xor(message: str, secret: str) -> str:
        """
        Encrypts or decrypts a message using the XOR cipher.

        Parameters:
            - message (str): The message to be encrypted or decrypted.
            - secret (str): The secret key used for encryption or decryption.

        Returns:
            - str: The encrypted or decrypted message.
        """
        new_chars = list()
        i = 0

        for num_chr in (ord(c) for c in message):
            num_chr ^= ord(secret[i])
            new_chars.append(num_chr)

            i += 1
            if i >= len(secret):
                i = 0

        return "".join(chr(c) for c in new_chars)

    @staticmethod
    def encrypt_xor(message: str, secret: str) -> str:
        """
        Encrypts a message using XOR encryption with a secret key.

        Args:
            message (str): The message to be encrypted.
            secret (str): The secret key used for encryption.

        Returns:
            str: The encrypted message as a hexadecimal string.
        """
        return CryptoUtils.crypto_xor(message, secret).encode("utf-8").hex()

    @staticmethod
    def decrypt_xor(message_hex: str, secret: str) -> str:
        """
        Decrypts a message encrypted using XOR encryption.

        Args:
            message_hex (str): The hexadecimal string representation of the encrypted message.
            secret (str): The secret key used for encryption.

        Returns:
            str: The decrypted message.

        Raises:
            None
        """
        message = bytes.fromhex(message_hex).decode("utf-8")
        return CryptoUtils.crypto_xor(message, secret)

    @staticmethod
    def get_mac_address():
        """
        Returns the MAC address of the current machine.

        :return: A string representing the MAC address.
        """
        return hex(uuid.getnode()).split('x')[-1]
