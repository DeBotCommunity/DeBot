import base64

class CryptoUtils:
    @staticmethod
    def encrypt(text: str, shift: int = 33) -> str:
        """
        Encrypts a given text using the Caesar cipher algorithm.

        :param text: The text to encrypt.
        :type text: str
        :param shift: The number of positions to shift each character in the text. Default is 33.
        :type shift: int
        :return: The encrypted text.
        :rtype: str
        """
        result = ""

        for i in range(len(text)):
            char = text[i]

            if char.isupper():
                result += chr((ord(char) + shift - 65) % 26 + 65)
            else:
                result += chr((ord(char) + shift - 97) % 26 + 97)

        return result

    @staticmethod
    def decrypt(text: str, shift: int = 33) -> str:
        """
        Decrypts the given text using the Caesar cipher algorithm.

        Parameters:
            text (str): The text to be decrypted.
            shift (int): The number of positions to shift each character in the text. Default is 33.

        Returns:
            str: The decrypted text.
        """
        return CryptoUtils.encrypt(text, -shift)
  