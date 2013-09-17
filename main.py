from collections import namedtuple
import socket
from threading import Lock


AuthData = namedtuple('AuthData', 'id login email full_name')


socket_lock = Lock()
HOST = 'www.yandex.ru'
PORT = 80


def send_data(environ):
    auth_data = AuthData(environ.get('ADFS_PERSONID', '0'),
                         environ.get('ADFS_LOGIN', 'Tester'),
                         environ.get('ADFS_EMAIL', 'xni@github.com'),
                         environ.get('ADFS_FULLNAME', 'Konstantin Nikitin'))
    with socket_lock:
        request_template = ('{method} {path} HTTP/1.1\r\n'
                            'Connection: close\r\n'
                            'Host: {host}\r\n'
                            '{headers}\r\n')
        black_list_headers = frozenset(('HOST', 'CONNECTION', 'COOKIE'))
        headers_list = []
        for key, value in environ.iteritems():
            if not key.startswith('HTTP'):
                continue
            if key.rsplit('_', 1)[-1] in black_list_headers:
                continue
            headers_list.append((key[5:].replace('_', '-').lower(), value))
        headers_list.append(('X-Auth-UID', auth_data.id))
        headers_list.append(('X-Auth-Login', auth_data.login))
        headers_list.append(('X-Auth-Email', auth_data.email))
        headers_list.append(('X-Auth-Fullname', auth_data.full_name))
        if 'CONTENT_TYPE' in environ:
            headers_list.append(('Content-Type', environ['CONTENT_TYPE']))
        header_template = '{name}: {value}\r\n'
        headers_str = ''.join(header_template.format(name=h[0], value=h[1])
                              for h in headers_list)
        request = request_template.format(
            method=environ['REQUEST_METHOD'],
            path=environ['REQUEST_URI'],
            host=HOST,
            headers=headers_str)
        g_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        g_socket.connect((HOST, PORT))
        g_socket.sendall(request)
        response = ''
        while True:
            data = g_socket.recv(4096)
            if not data:
                break
            response += data
        g_socket.close()
        return response


def check_environ(environ):
    return True
    return (environ.get('ADFS_PERSONID', '').isdigit() and
            'ADFS_LOGIN' in environ and
            'ADFS_EMAIL' in environ and
            'ADFS_FULLNAME' in environ)


def application(environ, start_response):
    if not check_environ(environ):
        output = ('Apache Environment is invalid. '
                  'Check your webserver\'s settings.')
        start_response('401 Unauthorized',
                       [('Content-Length', str(len(output)))])
        yield output
    else:
        response = send_data(environ).split('\r\n\r\n', 1)
        raw_headers = response[0].split('\r\n')
        _, status_line = raw_headers[0].split(' ', 1)
        headers = [tuple(p.strip() for p in h.split(':', 1))
                   for h in raw_headers[1:]]
        start_response(status_line, headers)
        if len(response) > 1:
            yield response[1]
        else:
            yield ''
        