import socket
import logging
import threading
import os

class TCPSocketServer:
  
    def __init__(self, host:str="0.0.0.0", port:int=80, includeCustomHeader:bool=False, loggerName="TCPSocketServer") -> None:
        self.logger = logging.getLogger(loggerName)
        self.logger.setLevel(os.environ.get(f"LOG_LEVEL_{loggerName.upper()}", 'INFO').upper())
        self.host: str = host
        self.port: int = port
        self.socket: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((self.host, self.port))
        self.socket.listen(5)
        self.running: bool = False
        self.clients: list[socket.socket] = []
        
        self.data_listeners = []
        self.connection_listeners = []
        
        self.includeCustomHeader: bool = includeCustomHeader
        self.logger.info(f"Server initialized on port {self.port}")
    
    def add_data_listener(self, listener):
        """When a message is received, call the listener with the message"""
        self.data_listeners.append(listener)
        self.logger.debug("Message listener added")
        
    def add_connection_listener(self, listener):
        self.connection_listeners.append(listener)
        self.logger.debug("Connection listener added")

    def _inform_connection_listeners(self, client_socket, connected: bool):
        """Inform all connection listeners about the connection status"""
        for listener in self.connection_listeners:
            try:
                listener(client_socket, connected)
            except Exception as e:
                self.logger.error(f"Error in connection listener: {e}")
                self.logger.exception("Exception in connection listener", exc_info=True)

    def send_data(self, data: bytes):
        """Send a message to all clients"""
            
        disconnected_clients = []
        
        if self.includeCustomHeader:
            header = b'\x16\x16' + len(data).to_bytes(2, byteorder='big')
            data = header + data
            
        for client in self.clients:
            try:
                client.sendall(data)
                self.logger.debug(f"Sent {len(data)} bytes to client")
            except Exception as e:
                self.logger.error(f"Error sending to client: {e}")
                disconnected_clients.append(client)
                
        # Remove disconnected clients
        for client in disconnected_clients:
            if client in self.clients:
                self.clients.remove(client)
                self._inform_connection_listeners(client, False)
                self.logger.info(f"Removed disconnected client. {len(self.clients)} clients remaining")
                
    def _handle_client(self, client_socket, address):
        """Handle communication with a connected client"""
        self._inform_connection_listeners(client_socket, True)
        
        while self.running:
            try:
                data = client_socket.recv(1024)
                if not data:
                    self.logger.info(f"Client {address} disconnected")
                    break
                
                self.logger.debug(f"Received {len(data)} bytes from {address}")
                # Call listener if registered
                for listener in self.data_listeners:
                    listener(data)
                    
            except Exception as e:
                self.logger.error(f"Error handling client {address}: {e}")
                break
                
        # Remove client when disconnected
        if client_socket in self.clients:
            self._inform_connection_listeners(client_socket, False)
            self.clients.remove(client_socket)
            self.logger.info(f"Removed client {address}. {len(self.clients)} clients remaining")
            
        try:
            client_socket.close()
        except Exception as e:
            self.logger.error(f"Error closing client socket: {e}")
    
    def start(self):
        """Start the server in a new thread"""
        self.running = True
        self.logger.info(f"Starting server on {self.host}:{self.port}")
        server_thread = threading.Thread(target=self._accept_connections)
        server_thread.daemon = True
        server_thread.start()
        self.logger.info("Server started successfully")
    
    def _accept_connections(self):
        """Accept new client connections"""
        self.logger.info("Started accepting connections")
        while self.running:
            try:
                client_socket, address = self.socket.accept()
                self.clients.append(client_socket)
                self.logger.info(f"New client connected from {address[0]}")
                
                # Start a new thread to handle this client
                client_thread = threading.Thread(target=self._handle_client, 
                                                args=(client_socket, address))
                client_thread.daemon = True
                client_thread.start()
            except Exception as e:
                if self.running:  # Only log if not intentionally stopped
                    self.logger.error(f"Error accepting connection: {e}")
                break
                
    def stop(self):
        """Stop the server and close all connections"""
        self.logger.info("Stopping server")
        self.running = False
        
        # Close all client connections
        for client in self.clients:
            try:
                client.close()
            except Exception as e:
                self.logger.error(f"Error closing client connection: {e}")
        
        client_count = len(self.clients)
        self.clients.clear()
        self.logger.info(f"Closed {client_count} client connections")
        
        # Close server socket
        try:
            self.socket.close()
            self.logger.info("Server socket closed")
        except Exception as e:
            self.logger.error(f"Error closing server socket: {e}")
 