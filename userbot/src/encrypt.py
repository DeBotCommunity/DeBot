class CryptoUtils:
    @staticmethod
    def generate_vigenere_tableau():
        """
        Generates a Vigenère tableau that includes both letters and digits.
        """
        tableau = []
        for i in range(36):
            row = []
            for j in range(36):
                if 0 <= i < 26:
                    if 0 <= j < 26:
                        row.append(chr((i + j) % 26 + 65))
                    else:
                        row.append(str((j + i - 26) % 10))
                else:
                    if 0 <= j < 26:
                        row.append(chr((j + i - 10) % 26 + 65))
                    else:
                        row.append(str((i + j - 36) % 10))
            tableau.append(row)
        return tableau

    @staticmethod
    def encrypt(text: str, keyword: str) -> str:
        """
        Encrypts a given text using the extended Vigenère cipher algorithm that includes digits.

        :param text: The text to encrypt.
        :param keyword: The keyword used for encryption.
        :return: The encrypted text.
        """
        tableau = CryptoUtils.generate_vigenere_tableau()
        keyword_repeated = (keyword * (len(text) // len(keyword) + 1))[:len(text)]
        result = ""

        for i, char in enumerate(text):
            if char.isalpha() or char.isdigit():
                text_index = ord(char.upper()) - 65 if char.isalpha() else ord(char) - 22
                keyword_index = ord(keyword_repeated[i].upper()) - 65 if keyword_repeated[i].isalpha() else ord(keyword_repeated[i]) - 22
                result += tableau[keyword_index][text_index]
            else:
                result += char

        return result

    @staticmethod
    def decrypt(text: str, keyword: str) -> str:
        """
        Decrypts the given text using the extended Vigenère cipher algorithm that includes digits.

        :param text: The text to decrypt.
        :param keyword: The keyword used for decryption.
        :return: The decrypted text.
        """
        tableau = CryptoUtils.generate_vigenere_tableau()
        keyword_repeated = (keyword * (len(text) // len(keyword) + 1))[:len(text)]
        result = ""

        for i, char in enumerate(text):
            if char.isalpha() or char.isdigit():
                keyword_index = ord(keyword_repeated[i].upper()) - 65 if keyword_repeated[i].isalpha() else ord(keyword_repeated[i]) - 22
                if char.isalpha():
                    text_row = tableau[keyword_index]
                    col_index = text_row.index(char.upper())
                    result += chr(col_index + 65) if col_index < 26 else chr(col_index + 22)
                else:
                    text_row = tableau[keyword_index][26:]
                    col_index = text_row.index(char)
                    result += chr(col_index + 65) if col_index < 26 else chr(col_index + 22)
            else:
                result += char

        return result
