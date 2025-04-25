import json
from CryptoHelper import decrypt_data, encrypt_data
import random
import logging
import os

# Get logger for this module
_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(os.environ.get('LOG_LEVEL_PACKET', 'INFO').upper())

class Server_Packet:
  
  def __init__(self, data: bytearray, push_key: str = None) -> None:
    _LOGGER.debug(f"Initializing Server_Packet with data length: {len(data) if data is not None else 'None'}")
    self._push_key = push_key
    _LOGGER.debug(f"Push key length: {len(push_key) if push_key is not None else 'None'}")
    if data is not None:
      self.data: dict = data
      self._offset: int = 0
      self.payload_json: dict = None
      
      self.magic_bytes: int = self._get_bytes(2)
      if self.magic_bytes != 0x0005:
        _LOGGER.error(f"Invalid magic bytes: {self.magic_bytes}")
        raise Exception(f"Invalid magic bytes: {self.magic_bytes}")
      self.type: int = self._get_bytes(2)
      if self.type != 0x0003:
        _LOGGER.debug(f"Packet type {self.type} is not 0x0003")
        return
      
      self.len_ack: int = self._get_bytes(2)
      self.ack_nr: int = self._get_bytes(self.len_ack, False).decode("utf-8")[4:]
      
      self.remaining_size: int = self._get_bytes(4)
      self.seq_nr: int = self._get_bytes(8)
      self.product_id: int = self._get_bytes(4)
      self.payload_size: int = self._get_bytes(4)
      
      self.payload: bytes = self._get_bytes(self.payload_size, False)
      if int.from_bytes(self.payload[:4], byteorder='big') == 0x0000:
        _LOGGER.error("Encapsulated packet detected. Not supported yet!")
        raise Exception("Encapsulated packet detected. Not supported yet!")

      try:
        self.payload_json: dict = json.loads(self.payload.decode("utf-8"))
        if self.payload_json.get("encrypt", 0) == 1:
          self._decrypt()
      except json.JSONDecodeError:
        self.payload_json = None
        _LOGGER.warning("Failed to decode payload as JSON")
      except Exception as e:
        _LOGGER.error(f"Error decrypting payload: {e}")
    
  def build(self, data: dict, last_seq_id: int = 0x5A61FFFFFFFFFFFF, encrypt: bool = True, product_id: int = 60008) -> bytes:
    _LOGGER.debug(f"Building packet with data: {data}")
    if encrypt:
      data = encrypt_data(self._push_key, data)
    self.payload_json = {
        "data": data,
        "devType": 3,
        "encrypt": 1 if encrypt else 0
    }
    self.payload = json.dumps(self.payload_json).encode('utf-8')
    self.payload_size = len(self.payload)
    
    _LOGGER.debug(f"Payload size: {self.payload_size}")
    self.ack_nr = random.randint(1000, 99999)
    
    self.product_id = product_id
    self.seq_nr = (last_seq_id + self.ack_nr) & 0xFFFFFFFFFFFFFFFF
    _LOGGER.debug(f"Seq ID: {self.seq_nr}")
    
    self.remaining_size = self.payload_size + 16
    
    self.len_ack = len(str(self.ack_nr)) + 4
    
    self.magic_bytes = 0x0005
    self.type = 0x0003
    
    return self._build_packet()
  
  def _build_packet(self) -> bytes:
    if not self.payload:
      _LOGGER.error("Payload not set")
      raise Exception("Payload not set")
    
    packet = bytearray()
    packet.extend(self.magic_bytes.to_bytes(2, byteorder='big'))
    packet.extend(self.type.to_bytes(2, byteorder='big'))
    packet.extend(self.len_ack.to_bytes(2, byteorder='big'))
    packet.extend(("ack:" + str(self.ack_nr)).encode('utf-8'))
    packet.extend(self.remaining_size.to_bytes(4, byteorder='big'))
    packet.extend(self.seq_nr.to_bytes(8, byteorder='big'))
    packet.extend(self.product_id.to_bytes(4, byteorder='big'))
    packet.extend(self.payload_size.to_bytes(4, byteorder='big'))
    packet.extend(self.payload)
    
    _LOGGER.debug(f"Built packet with size: {len(packet)} bytes")
    return bytes(packet)
    
    
  def _decrypt(self) -> None:
    if not self._push_key:
      _LOGGER.error("Push key not set")
      raise Exception("Push key not set")
    
    encrypted_data = self.payload_json.get("data", None)
    if not encrypted_data:
      _LOGGER.error("No data to decrypt")
      raise Exception("No data to decrypt")
    
    decrypted_data = decrypt_data(self._push_key, encrypted_data)
    if not decrypted_data:
      _LOGGER.error("Failed to decrypt data")
      raise Exception("Failed to decrypt data")
    
    self.payload_json.update({"data": decrypted_data})
    _LOGGER.info(f"Decrypted payload data: {decrypted_data}")
    _LOGGER.debug("Successfully decrypted payload data")
    
  def _get_bytes(self, length: int, asInt: bool = True) -> bytes | int:
    if self._offset + length > len(self.data):
      error_msg = f"Offset {self._offset} + length {length} exceeds data size {len(self.data)}"
      _LOGGER.error(error_msg)
      raise Exception(error_msg)
    bytes_data = self.data[self._offset:self._offset + length]
    self._offset += length
    if asInt:
      return int.from_bytes(bytes_data, byteorder='big')
    return bytes_data
    
  def __str__(self) -> str:
    return f"Ack Number: {self.ack_nr}, Sequence Number: {self.seq_nr}, Payload Size: {self.payload_size}, Payload: {self.payload}, Data: {self.payload_json}"