import argparse
import asyncio
import websockets
import json
import ssl
from flask import Flask, request, jsonify
from datetime import datetime
import re
from waitress import serve
import requests

class WebSocketClient:
    def __init__(self, uri, token):
        self.uri = uri
        self.token = token
        self.ssl_context = ssl._create_unverified_context()  # Create an SSL context that does not verify certificates

    async def initialize_connection(self):
        try:
            async with websockets.connect(self.uri, ssl=self.ssl_context) as websocket:
                # Send authentication request
                auth_request = {
                    "RQT": "version",
                    "VN": "1.00",
                    "TK": self.token
                }
                
                log_info(f"Sending authentication request: {auth_request}")
                
                await websocket.send(json.dumps(auth_request))
                auth_response = await websocket.recv()
                
                log_info(f"Received authentication response: {auth_response}")
                
                auth_response_data = json.loads(auth_response)
                
                if auth_response_data.get("RES") == "OK":      
                    log_info(f"Authentication success: {auth_response_data}")
                else:  
                    log_info(f"Authentication failed: {auth_response_data}")
        except Exception as e:
            log_info(f"Authentication error: {e}")
                
    async def send_request(self, message):
        retry_attempts = 5
        retry_delay = 5
        
        for attempt in range(retry_attempts):
            try:
                async with websockets.connect(self.uri, ssl=self.ssl_context) as websocket:
                    log_info(f"Sending request: {message}")
                    
                    await websocket.send(json.dumps(message))
                    response = await websocket.recv()
                    
                    log_info(f"Received response: {response}")
                    
                    response_data = json.loads(response)
                    
                    if response_data.get("RES") == "OK":      
                        log_info(f"Request success: {response_data}")
                        break
                    else:  
                        log_info(f"Request failed: {response_data}")
                        if attempt < retry_attempts - 1:
                            log_info(f"Retrying... ({attempt + 1}/{retry_attempts})")
                            await asyncio.sleep(retry_delay)  # Wait before retrying
                        else:
                            log_info("All retry attempts failed.")
            except Exception as e:
                log_info(f"Request error: {e}")
                if attempt < retry_attempts - 1:
                    log_info(f"Retrying... ({attempt + 1}/{retry_attempts})")
                    await asyncio.sleep(retry_delay)  # Wait before retrying
                else:
                    log_info("All retry attempts failed.")

class FlaskApp:
    def __init__(self, host, port, debug, ws_url, token):
        self.app = Flask(__name__)
        self.host = host
        self.port = port
        self.debug = debug
        self.ws_url = ws_url
        self.token = token
        self.routes()
        # Authenticate with QST server
        self.ws_client = WebSocketClient(ws_url, token)
        asyncio.run(self.ws_client.initialize_connection())
        

    def routes(self):
        @self.app.route('/alert', methods=['POST'])
        def alert():
            try:
                alert_data = request.json
                log_info(f"Received alert from TradingView: {alert_data}")
                
                # Generate qst api from tradingview api
                #qst_api = generate_qst_api(alert_data)
                
                #log_info(f"Generated QST API: {qst_api}")
                             
                request_data = alert_data
                
                # Send order request with generated qst api
                asyncio.run(self.ws_client.send_request(request_data))
                
                return jsonify({
                    "Request success": request_data,
                })
            except Exception as e:
                log_info(f"Error: {e}")
                return jsonify({
                    "Request error": str(e),
                })
    
def log_info(message):
    discord_webhook = "https://discord.com/api/webhooks/1321613723298824264/ritBy2KredUVBPyd7x8ROQJGuQj6odMWC07QH9XawULI-hMKge1Akk8CPgTWv8peK5__"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_message = f"{timestamp} INFO: {message}"
    print(log_message)
    chat_message = {
        "username": "AlertBot",
        "content": f"{log_message}"
    }
    with open("C:/QST-Extension/QST-log.txt", "a") as file:
        file.write(log_message + "\n")
    requests.post(discord_webhook, json=chat_message)
    
def generate_qst_api(tradingview_api):
    action  = tradingview_api['strategy']['order_action']
    price  = tradingview_api['strategy']['order_price']
    ticker  = tradingview_api['ticker']

    qst_api = {
        "RQT": "place_order", #request
        "PV": "PTS", #provider
        "AC": "39477@RHB - PAPER TRADING", #account
        "SD": "B" if action == "buy" else "S",
        "QT": "1", #quantity
        "INS": ticker, #instrument
        "TP": "MKT", #order type (LMT, MKT, STOP, STL, STWL)
        "PR": price, #price
        "LM": price, #limit 
        "LF": "DAY", #time in force (DAY, GTC, GTD)
        "CNF": "OFF"
    }
    return qst_api

def create_app(host, port, debug, ws_url, token):
    flask_app = FlaskApp(host, port, debug, ws_url, token)
    return flask_app.app

def main():
    # Create an argument parser
    parser = argparse.ArgumentParser(description="Middleware for TradingView and QST")

    # Define arguments
    parser.add_argument("--host", default="127.0.0.1", help="The host address to bind to (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=5000, help="The port to bind to (default: 5000)")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--ws-url", default="wss://localhost:8888/websocket", help="WebSocket server URL")

    # Token received from QST extension
    parser.add_argument("token", help="Token used for QST communication")

    # Parse the arguments
    args = parser.parse_args()
    
    # Extract the token from the parameter
    token = re.sub(r'\D', '', args.token)
    
    version = "2.4"
    
    log_info(f"Starting Flask app on {args.host}:{args.port} with WSGI server")
    log_info(f"Version: {version}")
    log_info(f"Received token: {token}")
    log_info(f"WebSocket server URL: {args.ws_url}")

    # Create Flask app
    app = create_app(args.host, args.port, args.debug, args.ws_url, token)
    
    # Run the Flask app with waitress
    serve(app, host=args.host, port=args.port)
    
if __name__ == '__main__':
    main()