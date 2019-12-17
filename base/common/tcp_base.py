import socket
import time
import traceback
import asyncio
import multiprocessing as mp
import threading

from base import settings
from base import logger
from base.exceptions import TCPServerNotFoundException, TCPWrongMessageException
from base.solid import get_implementer
from base.constants import DEFAULT_CONNECTION_TIMEOUT, DEFAULT_DATA_LENGTH, DEFAULT_TCP_POOL_LIMIT


class TCPBase:

    def __init__(self, webhook, retry_wait=5):
        self._webhook = webhook
        self._implementer = get_implementer()
        self._tcp_settings = settings.config_tcp
        self.retry_wait = retry_wait

    @property
    def webhook(self):
        return self._webhook

    @property
    def implementer(self):
        return self._implementer

    @property
    def tcp_settings(self):
        return self._tcp_settings

    @staticmethod
    def _clear_threads(thread_list):
        logger.debug("CLEANING THREADS")
        for t in thread_list:
            t.join()
        thread_list.clear()

    def kickoff(self):
        tcp_thread = mp.Process(target=self.launch_server, name="tcp_thread")
        tcp_thread.start()

    def handle_connection(self, connection, client_address):
        logger.debug("[TCP] HANDLE_CONNECTION")
        try:
            conn_timeout = self.tcp_settings.get('connection_timeout', DEFAULT_CONNECTION_TIMEOUT)
            data_length = self.tcp_settings.get('data_length', DEFAULT_DATA_LENGTH)
            logger.debug(f'Connection from: {client_address}')

            # Receive the data in small chunks and retransmit it
            while True:
                connection.settimeout(int(conn_timeout))
                data = connection.recv(data_length)
                logger.debug(f'TCP DATA received "{data}"')
                if data:
                    result = self.handle_data(data)
                    for res_ in result:
                        logger.debug('Sending data back to the client')
                        connection.sendall(res_.encode())
                        logger.debug(f'Data sent: {res_}')
                else:
                    logger.debug(f'no more data from: {client_address}')
                    break
        except socket.timeout:
            logger.debug(f'No response from  {client_address}. Connection will close')
            connection.sendall('Closing connection due to inactivity'.encode())
        except TCPWrongMessageException as e:
            connection.sendall(e.__str__().encode())
        except Exception as e:
            logger.alert(f'Unexpected error from {connection}; address: {client_address}; '
                         f'{traceback.format_exc(limit=5)}')
        finally:
            logger.debug("Closing connection")
            # Clean up the connection
            connection.close()

    def handle_data(self, data):
        tcp_result = self.implementer.tcp_message(data)
        if tcp_result:
            self.webhook.handle_request(tcp_result)
            return [res['response'] for res in tcp_result]

        return tcp_result

    def launch_server(self):
        logger.notice('Starting TCP server')
        tcp_settings = settings.config_tcp
        if 'ip_address' not in self.tcp_settings or 'port' not in self.tcp_settings:
            raise TCPServerNotFoundException("TCP server address or port not found in config file")

        # Create a TCP/IP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        # Bind the socket to the port
        server_address = (self.tcp_settings['ip_address'], int(self.tcp_settings['port']))
        logger.info(f'starting up on {server_address[0]} port {server_address[1]}')
        try:
            sock.bind(server_address)
            # Listen for incoming connections
            sock.listen(1)

            thread_list = []
            while True:
                if len(thread_list) >= self.tcp_settings.get('thread_pool_limit', DEFAULT_TCP_POOL_LIMIT):
                    self._clear_threads(thread_list)
                # Wait for a connection
                logger.info('Waiting for connection')
                connection, client_address = sock.accept()
                thread_ = threading.Thread(target=self.handle_connection, args=(connection, client_address))
                thread_.start()
                thread_list.append(thread_)

            self._clear_threads(thread_list)
        except OSError as e:
            logger.critical(f"Error connecting TCP. Probably because address already in use. "
                            f"Will try to reconnect in {self.retry_wait}; Error: {e}")
        except Exception as e:
            logger.alert(f"Unexpected error while open TCP socket: {e}; {traceback.format_exc(limit=5)}")
        finally:
            time.sleep(self.retry_wait)
            logger.warning("Recreating TCP server")
            self.kickoff()

