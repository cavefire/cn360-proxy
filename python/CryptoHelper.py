import base64
from Crypto.Util.Padding import pad, unpad 
from Crypto.Cipher import AES
import json
import logging
import os

# Get logger for this module
_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(os.environ.get('LOG_LEVEL_CRYPTO', 'INFO').upper())

def decrypt_data(key: str, data_str: str) -> dict:
  if not data_str:
    _LOGGER.warning("No data to decrypt")
    return None
  try:
    key_raw = key[:16].encode("utf-8")
    cipher_text = base64.b64decode(data_str)
    cipher = AES.new(key_raw, AES.MODE_CBC, iv=key_raw)
    decrypted = unpad(
      cipher.decrypt(cipher_text), AES.block_size
    )
    decrypt_res = json.loads(decrypted.decode("utf-8"))
    _LOGGER.debug(f"Decrypted data: {decrypt_res}")
    return decrypt_res
  except Exception as err:
    _LOGGER.exception(f"Decryption error", err)
      
  return None

def encrypt_data(key: str, data: dict) -> str:
  if not data:
    _LOGGER.warning("No data to encrypt")
    return None
  try:
    key_raw = key[:16].encode("utf-8")
    cipher = AES.new(key_raw, AES.MODE_CBC, iv=key_raw)
    json_data = json.dumps(data).encode("utf-8")
    padded_data = pad(json_data, AES.block_size)
    encrypted_data = cipher.encrypt(padded_data)
    encrypted_str = base64.b64encode(encrypted_data).decode("utf-8")
    _LOGGER.debug(f"Encrypted data: {encrypted_str}")
    return encrypted_str
  except Exception as err:
    _LOGGER.exception(f"Encryption error", err)
      
  return None