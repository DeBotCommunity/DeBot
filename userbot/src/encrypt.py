import os
import wmi
import hashlib

class CryptoUtils:
    @staticmethod
    def crypto_xor(message: str, secret: str) -> str:
        new_chars = list()
        i = 0

        for num_chr in (ord(c) for c in message):
            num_chr ^= ord(secret[i])
            new_chars.append(num_chr)

            i += 1
            if i >= len(secret):
                i = 0

        return ''.join(chr(c) for c in new_chars)

    @staticmethod
    def encrypt_xor(message: str, secret: str) -> str:
        return CryptoUtils.crypto_xor(message, secret).encode('utf-8').hex()

    @staticmethod
    def decrypt_xor(message_hex: str, secret: str) -> str:
        message = bytes.fromhex(message_hex).decode('utf-8')
        return CryptoUtils.crypto_xor(message, secret)

    @staticmethod
    def get_hwid():
        if os.name == 'nt':
            c = wmi.WMI()
            for item in c.Win32_ComputerSystemProduct():
                return item.UUID
        else:
            return ':'.join(['{:12X}'.format(hashlib.md5(h.encode()).hexdigest()) for h in hashlib.md5(b"".join([open('/etc/machine-id', 'rb').read() for _ in range(3)])).digest()])
