import http.server
import socketserver
import http.client
from urllib.parse import urlparse


class ReverseProxyHTTPRequestHandler(http.server.BaseHTTPRequestHandler):
    proxy_host = 'localhost'
    proxy_port = 8000

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


PORT = 80  # Only accepting requests on port 80


class ThreadedHTTPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    pass


httpd = ThreadedHTTPServer(("", PORT), ReverseProxyHTTPRequestHandler)

print(f"Serving at port {PORT}")
httpd.serve_forever()
