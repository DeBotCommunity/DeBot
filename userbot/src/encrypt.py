class CryptoUtils:
    @staticmethod
    def encrypt(text: str, keyword: str = 'DeBot_33') -> str:
        """
        Encrypts a given text using the Vigenère cipher algorithm.
        This version supports both letters and digits.
        """
        result = ""
        keyword_repeated = (keyword * (len(text) // len(keyword) + 1))[:len(text)]
        alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
        len_alphabet = len(alphabet)

        for i, char in enumerate(text):
            try:
                text_index = alphabet.index(char.upper())
                keyword_index = alphabet.index(keyword_repeated[i].upper())
                encrypted_index = (text_index + keyword_index) % len_alphabet
                result += alphabet[encrypted_index]
            except ValueError:
                result += char

        return result

    @staticmethod
    def decrypt(ciphertext: str, keyword: str = 'DeBot_33') -> str:
        """
        Decrypts the given text using the extended Vigenère cipher algorithm that includes digits.

        :param text: The text to decrypt.
        :param keyword: The keyword used for decryption.
        :return: The decrypted text.
        """
        result = ""
        keyword_repeated = (keyword * (len(ciphertext) // len(keyword) + 1))[:len(ciphertext)]
        alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
        len_alphabet = len(alphabet)

        for i, char in enumerate(ciphertext):
            if char.upper() in alphabet:
                text_index = alphabet.index(char.upper())
                keyword_index = alphabet.index(keyword_repeated[i].upper())
                decrypted_index = (text_index - keyword_index) % len_alphabet
                result += alphabet[decrypted_index]
            else:
                result += char  # Non-alphanumeric characters are added unchanged

        return result
