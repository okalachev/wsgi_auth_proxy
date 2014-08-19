from collections import namedtuple
import socket
from threading import Lock


AuthData = namedtuple('AuthData', 'id login email full_name cern_project')


socket_lock = Lock()
#HOST = 'w80.cern.yandex.net'
HOST = 'cern-ei01.vs.os.yandex.net'
PORT = 80


def send_data(environ):
    auth_data = AuthData(environ.get('ADFS_PERSONID', '0'),
                         environ.get('ADFS_LOGIN', 'Tester'),
                         environ.get('ADFS_EMAIL', 'xni@github.com'),
                         environ.get('ADFS_FULLNAME', 'Konstantin Nikitin'),
                         environ.get('CERN_PROJECT', 'lhcb'))
    with socket_lock:
        request_template = ('{method} {path} HTTP/1.1\r\n'
                            'Connection: close\r\n'
                            'Host: {host}\r\n'
                            '{headers}\r\n'
                            '{data}')
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
        headers_list.append(('X-Cern-Project', auth_data.cern_project))
        if 'CONTENT_TYPE' in environ:
            headers_list.append(('Content-Type', environ['CONTENT_TYPE']))
        input_file = environ['wsgi.input'].read()
        if input_file:
            headers_list.append(('Content-Length', str(len(input_file))))
        header_template = '{name}: {value}\r\n'
        headers_str = ''.join(header_template.format(name=h[0], value=h[1])
                              for h in headers_list)
        request = request_template.format(
            method=environ['REQUEST_METHOD'],
            path=environ['REQUEST_URI'],
            host=HOST,
            headers=headers_str,
            data=input_file)
        print request
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
    return (environ.get('ADFS_PERSONID', '').isdigit() and
            'ADFS_LOGIN' in environ and
            'ADFS_EMAIL' in environ and
            'ADFS_FULLNAME' in environ)


def process_chunks(data, is_chunked_encoding):
    if not is_chunked_encoding:
        return data
    result = ''
    while True:
        chunk_length, value = data.split('\r\n', 1)
        chunk_length_res = int(chunk_length, 16)
        if chunk_length_res == 0:
            return result
        result += value[:chunk_length_res]
        data = value[chunk_length_res + 2:]


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
        headers = []
        blacklisted_headers = frozenset(['set-cookie', 'connection',
                                         'transfer-encoding'])
        is_chunked_encoding = False
        for header in raw_headers[1:]:
            header_name, header_value = \
                [h.strip() for h in header.split(':', 1)]
            if header_name and header_name.lower() not in blacklisted_headers:
                headers.append((header_name, header_value))
            if (header_name.lower() == 'transfer-encoding' and
                    header_value.lower() == 'chunked'):
                is_chunked_encoding = True
        start_response(status_line, headers)
        if len(response) > 1:
            yield process_chunks(response[1], is_chunked_encoding)
        else:
            yield ''

