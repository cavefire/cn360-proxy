from TCPClient import TCPSocketClient
from TCPServer import TCPSocketServer
import json
import uuid
from PacketParser import Server_Packet
import logging
from socket import socket
import os

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(os.environ.get('LOG_LEVEL_ECHO', 'INFO').upper())

class EchoServer:
  
  def __init__(self):
    self.remote_ip: str = None
    self.remote_port: int = None
    self.last_seq_id: int = 0x5A61111111111111
    self.data_cache: dict = {}
    self.sn: str = None
    
    self.push_key: str = None
    self.session_id: str = None
    
    self.robot_connected: bool = False
    self.cloud_connected: bool = False
    
    self.local_ack_nr: list[int] = []
    self.product_id: int = None
    
    self._load_push_key()
    self._load_product_id()
    
    self.cloud_client: TCPSocketClient = None
    self.robot_socket: TCPSocketServer = TCPSocketServer(os.environ.get("LOCAL_PROXY_IP", "0.0.0.0"), int(os.environ.get("ROBOT_PORT", "80")), loggerName="RobotSocketServer")
    self.robot_socket.add_data_listener(self._handle_robot_data)
    self.robot_socket.add_connection_listener(self._handle_robot_connection)
    self.robot_socket.start()
    _LOGGER.info("Robot server started on port 80")
    
    self.local_control_socket: TCPSocketServer = TCPSocketServer(os.environ.get("LOCAL_CONTROL_HOST", "0.0.0.0"), int(os.environ.get("LOCAL_CONTROL_PORT", "4468")), includeCustomHeader=True, loggerName="LocalControlSocketServer")
    self.local_control_socket.add_data_listener(self._handle_local_data)
    self.local_control_socket.add_connection_listener(self._handle_local_connection)
    self.local_control_socket.start()
    _LOGGER.info("Local control server started on port 4468")
    
    _LOGGER.info("------------------------------------------------")
    _LOGGER.info("Proxy ready! Waiting for connection from robot...")
    _LOGGER.info("------------------------------------------------")
    
  
  def _load_push_key(self) -> None:
    """Load push key from file if available"""
    try:
      with open("pushkey.txt", "r") as f:
        self.push_key = f.read().strip()
        _LOGGER.info(f"Push key loaded from file: {self.push_key[:8]}...")
    except FileNotFoundError:
      _LOGGER.warning("No push key file found")
    except Exception as e:
      _LOGGER.error(f"Error loading push key: {e}")
  
  def _load_product_id(self) -> None:
    """Load product ID from file if available"""
    try:
      with open("product_id.txt", "r") as f:
        self.product_id = int(f.read().strip())
        _LOGGER.info(f"Product ID loaded from file: {self.product_id}")
    except FileNotFoundError:
      _LOGGER.warning("No product ID file found")
    except Exception as e:
      _LOGGER.error(f"Error loading product ID: {e}")
  
  def set_remote_server(self, host, port) -> None:
    """Set the remote server IP and port"""
    if self.cloud_client:
      _LOGGER.warning(f"Disconnecting from existing server {self.remote_ip}:{self.remote_port}")
      self.cloud_client.disconnect()
      
    self.remote_ip = host
    self.remote_port = port
    
    _LOGGER.info(f"Connecting to remote server {host}:{port}")
    self._connect_cloud_server()
  
  def set_push_key(self, push_key: str) -> None:
    """Set and save the push key"""
    self.push_key = push_key
    try:
      with open("pushkey.txt", "w") as f:
        f.write(push_key)
      _LOGGER.info(f"Push key set and saved: {push_key[:8]}...")
    except Exception as e:
      _LOGGER.error(f"Error saving push key: {e}")
  
  def set_product_id(self, product_id: int) -> None:
    """Set and save the product ID"""
    if product_id is None:
      _LOGGER.error("Product ID cannot be None")
      return
    self.product_id = product_id
    try:
      with open("product_id.txt", "w") as f:
        f.write(str(product_id))
      _LOGGER.info(f"Product ID set and saved: {product_id}")
    except Exception as e:
      _LOGGER.error(f"Error saving product ID: {e}")
    self.update_local_control()
  
  
  # -------------------------------------
  # Local Control Server functions  
  
  def _handle_local_connection(self, client: socket, connected: bool) -> None:
    _LOGGER.info(f"Local control is {'connected' if connected else 'disconnected'}")
    if connected:
      self.update_local_control(None)
    
  def _handle_local_data(self, message: bytes) -> None:
    """Handle messages from local control"""
    message_str = message.decode("utf-8")
    if "}{" in message_str:
      messages = message_str.split("}{", maxsplit=1)
      messages[0] = messages[0] + "}"
      messages[1] = "{" + messages[1]
      for msg in messages:
        self._handle_local_data(msg.encode("utf-8"))
      return
    
    try:
      user_data = json.loads(message.decode("utf-8"))
      
      data = {
        "data": json.dumps(user_data.get("data", {})),
        "extend": {
          "taskid": str(uuid.uuid4()),
          "usid": "admin",
        },
        "infoType": str(user_data.get("infoType", "30000")),
        "sn": self.sn
      }
      
      packet = Server_Packet(None, self.push_key)
      to_send = packet.build(
        data=data,
        encrypt=True if user_data.get("encrypt", 1) else False,
        last_seq_id=self.last_seq_id,
        product_id=self.product_id if self.product_id else 60008,
      )
      _LOGGER.debug(f"Built packet for local control message: seq={packet.seq_nr}, ack_nr={packet.ack_nr}, data={data}")
      self.local_ack_nr.append(int(packet.ack_nr))
      
      self.robot_socket.send_data(to_send)
      _LOGGER.debug("Forwarded local control message to robot")
    except Exception as e:
      _LOGGER.exception(f"Error handling local control message: {message}")
      
  def update_local_control(self, toSend: dict = None, origin: str = "robot") -> None:
    """Update local control connection status"""
    data = {
      "origin": origin,
      "sn": self.sn,
      "robot_connected": self.robot_connected,
      "cloud_connected": self.cloud_connected,
    }
    if toSend is not None:
      data["data"] = toSend
      self.data_cache.update(toSend)
    else:
      data["cache"] = self.data_cache
      
    _LOGGER.debug(f"Sending local control update: {data}")
    
    self.local_control_socket.send_data(json.dumps(data).encode('utf-8'))
    
    
  # -------------------------------------
  # Cloud Client functions  
  
  def _handle_cloud_connection(self, connected) -> None:
    self.cloud_connected = connected
    if connected:
      _LOGGER.info(f"Connected to remote server {self.remote_ip}:{self.remote_port}")
    else:
      _LOGGER.warning(f"Disconnected from remote server {self.remote_ip}:{self.remote_port}")
    self.update_local_control()
    
  def _connect_cloud_server(self):
    try:
      self.cloud_client = TCPSocketClient(self.remote_ip, self.remote_port, loggerName="CloudSocket")
      self.cloud_client.set_data_listener(self._handle_cloud_data)
      self.cloud_client.set_connection_listener(self._handle_cloud_connection)
      
      if not self.cloud_client.connect():
        _LOGGER.error(f"Failed to connect to remote server {self.remote_ip}:{self.remote_port}")
        raise Exception("Failed to connect to remote server")
      
      _LOGGER.info(f"Connected to remote server {self.remote_ip}:{self.remote_port}")
    except Exception as e:
      _LOGGER.error(f"Error connecting to remote server: {e}")
      raise
    
  def _handle_cloud_data(self, message) -> None:
    """Handle messages from cloud"""
    
    # Forward message from Server to Robot
    self.robot_socket.send_data(message)
    
    # Decrypt the message and process it
    try:
      packet = Server_Packet(message, self.push_key)
      if packet.type != 0x0003:
        _LOGGER.debug(f"Forwarded server message to robot with packet type {packet.type}")
        return
      
      _LOGGER.info(f"Forwarded server message to robot: {len(message)} bytes")
      
      self.last_seq_id = packet.seq_nr
      _LOGGER.debug(f"Server packet: seq={packet.seq_nr}, payload={packet.payload_json}")
      
      payload_data = packet.payload_json.get("data", {})
      if isinstance(payload_data, str):
        try:
          payload_data = json.loads(payload_data)
        except json.JSONDecodeError:
          _LOGGER.error("Failed to decode payload data as JSON")
      
      data = {
        "origin": "server",
        "data": payload_data
      }
      if data.get("data", None) is None:
        return
        
      self.update_local_control(payload_data, origin="server")
      _LOGGER.info(f"Forwarded decrypted server payload to local control")
      
      with open("server_requests.txt", "a") as f:
        f.write(f"{json.dumps(payload_data)}\n")
      
    except Exception as e:
      _LOGGER.error(f"Error handling server message: {e}")
      
      
    
  # -------------------------------------
  # Robot Server functions  
  
  def _handle_robot_connection(self, client, connected) -> None:
    self.robot_connected = connected
    if connected:
      _LOGGER.info("Robot connected")
      if not self.cloud_connected:
        _LOGGER.info("Connecting to remote server")
        self._connect_cloud_server()
    else:
      _LOGGER.warning("Robot disconnected")
      
    _LOGGER.info("------------------------------------------------")
    self.update_local_control()
    
  def _handle_robot_data(self, message: bytes) -> None:
    """Handle messages from robot clients"""
    if not self.cloud_client:
      _LOGGER.error("No server connected, cannot forward client message")
      raise Exception("No server connected")
  
    if message[:4] == b'\x00\x05\x00\x04':
      ack_len = int.from_bytes(message[4:6], byteorder='big')
      ack = message[6:6 + ack_len].decode('utf-8')
      ack_nr = int(ack.split(":")[1])
      
      if ack_nr in self.local_ack_nr:
        self.local_ack_nr.remove(ack_nr)
        return
  
    self.cloud_client.send_data(message)
    _LOGGER.debug(f"Forwarded message to server: {len(message)} bytes")
