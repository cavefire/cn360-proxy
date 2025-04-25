import socket
import threading
import logging
import os
   
class TCPSocketClient:
    def __init__(self, host, port, loggerName="TCPSocketClient") -> None:
        self.logger = logging.getLogger(loggerName)
        self.logger.setLevel(os.environ.get(f"LOG_LEVEL_{loggerName.upper()}", 'INFO').upper())

        self.host: str = host
        self.port: int = port
        self.socket: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.running: bool = False
        self.data_listener = None
        self.connection_listener = None
        self.logger.info(f"Client initialized with target {host}:{port}")
    
    def set_data_listener(self, listener) -> None:
        """Saves the listener into a variable and calls it when a message is received"""
        self.data_listener = listener
        self.logger.debug("Message listener added")
    
    def set_connection_listener(self, listener) -> None:
        """Saves the listener into a variable and calls it when a connection is made"""
        self.connection_listener = listener
        self.logger.debug("Connection listener added")
    
    def send_data(self, data: bytes) -> None:
        """Sends a message to the remote server"""
        if not self.running:
            self.logger.error("Cannot send message: not connected")
            return False
            
        try:
            self.socket.sendall(data)
            self.logger.debug(f"Sent {len(data)} bytes to server")
            return True
        except Exception as e:
            self.logger.error(f"Error sending message: {e}")
            self.disconnect()
            
            try:
                self.connection_listener(False)
            except Exception as e:
                self.logger.error(f"Error in connection listener: {e}")
            return False
    
    def connect(self) -> bool:
        """Connect to the server"""
        try:
            self.logger.info(f"Connecting to {self.host}:{self.port}")
            self.socket.connect((self.host, self.port))
            self.running = True
            self.logger.info("Connected successfully")
            try:
                self.connection_listener(True)
            except Exception as e:
                self.logger.error(f"Error in connection listener: {e}")
            
            # Start the receiving thread
            receive_thread = threading.Thread(target=self._receive_data)
            receive_thread.daemon = True
            receive_thread.start()
            return True
        except Exception as e:
            self.logger.exception(f"Connection failed", exc_info=e)
            return False
            
    def _receive_data(self) -> None:
        """Receive messages from the server in a loop"""
        self.logger.info("Started receiving messages")
        while self.running:
            try:
                data = self.socket.recv(1024)
                if not data:
                    self.logger.info("Server closed connection")
                    break
                    
                self.logger.debug(f"Received {len(data)} bytes from server")
                # Call listener if registered
                self.logger.debug("Calling message listener")
                try:
                    self.data_listener(data)
                except Exception as e:
                    self.logger.error(f"Error in message listener: {e}")
                        
            except ConnectionResetError as e:
                self.logger.error(f"Connection reset by server: {e}")
                break
            except Exception as e:
                self.logger.error(f"Error receiving data: {e}")
                break

        # Only now do we tear everything down
        self.disconnect()
        try:
            self.connection_listener(True)
        except Exception as e:
            self.logger.error(f"Error in connection listener: {e}")
    
    def disconnect(self) -> None:
        """Disconnect from the server"""
        if not self.running:
            return
            
        self.logger.info("Disconnecting from server")
        self.running = False
        try:
            self.socket.close()
            self.logger.info("Socket closed")
        except Exception as e:
            self.logger.error(f"Error closing socket: {e}")