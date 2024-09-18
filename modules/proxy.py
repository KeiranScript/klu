import http.server
import socketserver
import http.client
from urllib.parse import urlparse
import ssl
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class ReverseProxyHTTPRequestHandler(http.server.BaseHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        self.proxy_host = os.getenv('HOST', 'localhost')
        self.proxy_port = int(os.getenv('PORT', 8000))
        super().__init__(*args, **kwargs)

    def do_GET(self):
        self.forward_request()

    def do_POST(self):
        self.forward_request()

    def do_PUT(self):
        self.forward_request()

    def do_DELETE(self):
        self.forward_request()

    def do_HEAD(self):
        self.forward_request()

    def forward_request(self):
        url = urlparse(self.path)
        path = url.path
        if url.query:
            path += '?' + url.query

        conn = http.client.HTTPConnection(self.proxy_host, self.proxy_port)
        headers = {key: value for key, value in self.headers.items()}
        body = None

        if self.command in ['POST', 'PUT']:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)

        conn.request(self.command, path, body, headers)
        response = conn.getresponse()

        self.send_response(response.status)
        for key, value in response.getheaders():
            self.send_header(key, value)
        self.end_headers()

        self.wfile.write(response.read())

        conn.close()


PORT = int(os.getenv('PORT', 443))  # Default to 443 if not set in .env

class ThreadedHTTPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    pass

httpd = ThreadedHTTPServer(("", PORT), ReverseProxyHTTPRequestHandler)

# Create an SSL context
context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
context.load_cert_chain(certfile=os.getenv('SSL_CERTFILE', "/etc/letsencrypt/live/kuuichi.xyz/fullchain.pem"),
                        keyfile=os.getenv('SSL_KEYFILE', "/etc/letsencrypt/live/kuuichi.xyz/privkey.pem"))

# Wrap the server socket with SSL
httpd.socket = context.wrap_socket(httpd.socket, server_side=True)

print(f"Serving at port {PORT} with SSL")
httpd.serve_forever()