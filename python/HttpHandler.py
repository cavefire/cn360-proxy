from mitmproxy import http
from urllib.parse import parse_qs
import logging
import json
import EchoServer
import os

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(os.environ.get('LOG_LEVEL_HTTP', 'INFO').upper())

def request(echo_server: EchoServer, flow: http.HTTPFlow) -> None:
    if flow.request.path in [
        "/clean/dev/event",
        "/clean/cmd/response"
    ]:
        _handle_event_request(echo_server, flow)
    elif flow.request.path == "/clean/dev/reportMaterialStatus":
        _handle_material_status(echo_server, flow)
    elif flow.request.path.startswith("/list/get"):
        _handle_ip_request(echo_server, flow)
    elif "." in flow.request.path.split("/")[-1] and os.environ.get("CACHE_STATIC", "true").lower() == "true":
        _handle_static_file_request(echo_server, flow)
        
def response(echo_server: EchoServer, flow: http.HTTPFlow) -> None:
    if flow.request.path == "/clean/dev/register":
        _handle_register_response(echo_server, flow)
    elif flow.request.path.startswith("/list/get"):
        _handle_ip_response(echo_server, flow)
    elif flow.request.path == "/upgrade/getNewVersion":
        _handle_update_response(echo_server, flow)
    elif flow.request.path == "/clean/dev/sync":
        _handle_sync_response(echo_server, flow)
    elif "." in flow.request.path.split("/")[-1] and os.environ.get("CACHE_STATIC", "true").lower() == "true":
        _handle_static_file_response(echo_server, flow)
        
        
def _handle_register_response(echo_server: EchoServer, flow: http.HTTPFlow) -> None:
    _LOGGER.info(f"Robot got register response: {flow.response.text}")
    try:
        json_response = flow.response.json()
    except ValueError:
        _LOGGER.error("Failed to parse JSON response for device register")    
        return
    
    if json_response.get("errno") == 0:
        echo_server.set_push_key(json_response["data"].get("pushKey", echo_server.push_key))
        echo_server.session_id = json_response["data"].get("sid")
    else:
        _LOGGER.error(f"Failed to register with server: {json_response.get('msg', 'Unknown error')}")
        return
    
def _handle_ip_request(echo_server: EchoServer, flow: http.HTTPFlow) -> None:
    product_id = flow.request.query.get("product", echo_server.product_id)
    echo_server.set_product_id(int(product_id))
    _LOGGER.info(f"Robot requesting IP for product ID: {product_id}")
    
def _handle_ip_response(echo_server: EchoServer, flow: http.HTTPFlow) -> None:
    _LOGGER.info(f"Robot got ips for socket connection: {flow.response.text}")
    text = flow.response.text
    
    if "\n" in text:
        remote = text.split("\n")[0]
    else:
        remote = text
        
    _LOGGER.info(f"Connecting proxy to {remote}")
    parts = remote.split(":")
    if len(parts) == 2:
        host, port = parts[0], int(parts[1])
        echo_server.set_remote_server(host, port)
        
    ip = os.environ.get("LOCAL_PROXY_IP", "192.168.0.254")
    port = os.environ.get("ROBOT_PORT", "80")
    
    flow.response.set_text(f"{ip}:{port}\n{ip}:{port}")
    flow.response.headers["Content-Length"] = str(len(flow.response.text))
    _LOGGER.info(f"Overriding response to: {flow.response.text}")
    
def _handle_update_response(echo_server: EchoServer, flow: http.HTTPFlow) -> None:
    _LOGGER.debug(f"Robot got update response: {flow.response.text}")
    
    if os.environ.get("BLOCK_UPDATE", "true").lower() == "true":
        with open("update.json", "w") as f:
            f.write(flow.response.text)
    
        _LOGGER.warning("Blocking update response")
        flow.response.set_text(json.dumps({"errorCode": 0,"errorMsg": "成功","result": {"hasNew": 0}}))
        return
    
    _LOGGER.warning("Update response has not been blocked! Your robot may be updated and this could stop working!")
    
def _handle_material_status(echo_server: EchoServer, flow: http.HTTPFlow) -> None:
    params = parse_qs(flow.request.text, keep_blank_values=True)
        
    data = {
        "materialStatus": {
            "filterTotal": int(params.get("filterTotal")[0]),
            "filterConsume": int(params.get("filterConsume")[0]),
            "mainBrushTotal": int(params.get("mainBrushTotal")[0]),
            "mainBrushConsume": int(params.get("mainBrushConsume")[0]),
            "sideBrushTotal": int(params.get("sideBrushTotal")[0]),
            "sideBrushConsume": int(params.get("sideBrushConsume")[0]),
            "sensorTotal": int(params.get("sensorTotal")[0]),
            "sensorConsume": int(params.get("sensorConsume")[0])
        }
    }
    
    # calculate percentages
    data["materialStatus"]["percent"] = {
        "filter": data["materialStatus"]["filterConsume"] / data["materialStatus"]["filterTotal"],
        "mainBrush": data["materialStatus"]["mainBrushConsume"] / data["materialStatus"]["mainBrushTotal"],
        "sideBrush": data["materialStatus"]["sideBrushConsume"] / data["materialStatus"]["sideBrushTotal"],
        "sensor": data["materialStatus"]["sensorConsume"] / data["materialStatus"]["sensorTotal"]
    }
    
    echo_server.update_local_control(data)
    
def _handle_event_request(echo_server: EchoServer, flow: http.HTTPFlow) -> None:
    params = parse_qs(flow.request.text, keep_blank_values=True)

    data_list = params.get('data')
    if not data_list:
        _LOGGER.warning("No 'data' parameter found in request")
        return
    
    sn_list = params.get("sn")
    if sn_list and len(sn_list) > 0:
        echo_server.sn = sn_list[0]
    
    data = data_list[0]
    
    _LOGGER.debug("Forwarding Roboter event to local control")
    
    try:
        data = json.loads(data)
    except json.JSONDecodeError:
        _LOGGER.error("Failed to decode JSON data")
        return
    
    echo_server.update_local_control(data)
    
def _handle_sync_response(echo_server: EchoServer, flow: http.HTTPFlow) -> None:    
    data = json.loads(flow.response.text)
    # set mapIntv, pathIntv, statusIntv to 1
    if data.get("errno") == 0:
        data = data.get("data", {})
        if data.get("setting"):
            try:
                settings = json.loads(data["setting"])
                settings["mapIntv"] = int(os.environ.get("MAP_INTV", 1))
                settings["pathIntv"] = int(os.environ.get("PATH_INTV", 1))
                settings["statusIntv"] = int(os.environ.get("STATUS_INTV", 1))
                data["setting"] = json.dumps(settings)
            except json.JSONDecodeError:
                _LOGGER.error("Failed to decode JSON settings")
        else:
            _LOGGER.error("No settings found in sync response")
        flow.response.set_text(json.dumps(data))
    else:
        _LOGGER.error(f"Failed to sync with server: {data.get('errmsg', 'Unknown error')}")
        return
    
def _get_static_file_path(flow: http.HTTPFlow) -> str | None:
    data_path = os.environ.get("DATA_PATH", os.path.join(os.path.dirname(__file__), "data"))
    filename = flow.request.pretty_host + "/" + flow.request.path[1:]
    if not filename:
        _LOGGER.error("No filename found in request")
        return None
    
    _LOGGER.debug(f"Static file path: {os.path.join(data_path, filename)}")
    return os.path.join(data_path, filename)
    
def _handle_static_file_request(echo_server: EchoServer, flow: http.HTTPFlow) -> None:
    _LOGGER.debug(f"Robot requesting static file: {flow.request.path}")
    
    filepath = _get_static_file_path(flow)
    
    if os.path.isfile(filepath):
        _LOGGER.debug(f"Static file cached: {filepath}")
        f = open(filepath, "rb")
        content = f.read()
        flow.response = http.Response.make(
            200, content, {"cached": "true"}
        )
            
def _handle_static_file_response(echo_server: EchoServer, flow: http.HTTPFlow) -> None:
    filepath = _get_static_file_path(flow)
    
    if flow.response.headers.get("cached", "false") == "true":
        return
    
    _LOGGER.debug(f"Robot got static file response for file: {filepath}")
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w") as f:
        f.write(flow.response.text)
    _LOGGER.warning(f"Saved static file to {filepath}")