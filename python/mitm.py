import os
import logging
from mitmproxy import http, tcp
from EchoServer import EchoServer
import HttpHandler
import logging
from CustomFormatter import CustomFormatter

sh = logging.StreamHandler()
sh.setLevel(os.environ.get('LOG_LEVEL_MITM', 'INFO').upper())
sh.setFormatter(CustomFormatter())

os.makedirs(os.environ.get("LOG_PATH", "/root/logs"), exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)',
    handlers=[
      sh, 
      logging.FileHandler(os.path.join(os.environ.get("LOG_PATH", "/root/logs"), "360proxy.log"))
    ]
)

_LOGGER = logging.getLogger("CN360_mitm")
_LOGGER.addHandler(sh)

class TcpPacketAddon:
  def __init__(self):
    # Initialize the EchoServer instance
    self.echo_server = EchoServer()
      
  def tcp_start(self, flow: tcp.TCPFlow):
    """Robot should only be able to connect to local echo server."""
    if flow.server_conn.address[0] != os.environ.get("LOCAL_PROXY_IP", "192.168.0.254"):
      _LOGGER.warning(f"Robot tried to connect to non-local server: {flow.server_conn.address}")
      if flow.killable:
        flow.kill()
      os.system(f"iptables -A FORWARD -s \"{flow.client_conn.address[0]}\" -d \"{flow.server_conn.address[0]}\" -p tcp --dport \"{flow.server_conn.address[1]}\" -j REJECT")
      _LOGGER.warning(f"Blocked connection from {flow.client_conn.address[0]} to {flow.server_conn.address[0]}")
      return
    
  def tcp_message(self, flow: tcp.TCPFlow):
    """Clear messages for remote echo server communication."""
    if flow.server_conn.address[0] != os.environ.get("LOCAL_PROXY_IP", "192.168.0.254") and flow.messages[-1].content[0:2] == b'\x00\x05':
      _LOGGER.warning(f"Robot tried to send messages to non-local server: {flow.server_conn.address}")
      if flow.killable:
        flow.kill()
      flow.messages.clear()
      return
    
  def request(self, flow: http.HTTPFlow):
    """Handle HTTP requests and serve the local CA certificate."""
    if flow.request.path == "/ca/cacert.pem":
      # Serve the local mitmproxy CA certificate
      ca_file = os.path.expanduser("~/.mitmproxy/mitmproxy-ca-cert.pem")
      try:
        with open(ca_file, "rb") as f:
          cert = f.read()
        flow.response = http.Response.make(
          200,
          cert,
          {"Content-Type": "application/x-pem-file"}
        )
      except FileNotFoundError:
        _LOGGER.error(f"CA file not found: {ca_file}")
    else:
      HttpHandler.request(self.echo_server, flow)

  def response(self, flow: http.HTTPFlow):
    """Handle HTTP responses and process the data."""
    HttpHandler.response(self.echo_server, flow)

addons = [
  TcpPacketAddon()
]
