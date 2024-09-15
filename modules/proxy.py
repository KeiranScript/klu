import http.server
import socketserver
import http.client
from urllib.parse import urlparse
import ssl


class ReverseProxyHTTPRequestHandler(http.server.BaseHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        self.proxy_host = 'localhost'
        self.proxy_port = 8000
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

        while True:
            chunk = response.read(8192)
            if not chunk:
                break
            self.wfile.write(chunk)

        conn.close()


PORT = 443  # Change to 443 for HTTPS

httpd = socketserver.TCPServer(("", PORT), ReverseProxyHTTPRequestHandler)

# Create an SSL context
context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
context.load_cert_chain(certfile="server.crt", keyfile="server.key")

# Wrap the server socket with SSL
httpd.socket = context.wrap_socket(httpd.socket, server_side=True)

print(f"Serving at port {PORT} with SSL")
httpd.serve_forever()
