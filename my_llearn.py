from twisted.internet.protocol import Protocol, Factory


class PeerProtocol(Protocol):
	def connectionMade(self):
		print "hii"

class Torrent_Peer_Factory(Factory):

	protocol = PeerProtocol


from twisted.internet import reactor
conn = Torrent_Peer_Factory(self)
my_connector = reactor.connectTCP(127.0.0.1, self.peer_port,self.conn)

			pass
		else:
			from twisted.internet import reactor
			self.conn = Torrent_Peer_Factory(self,client_handshake)
			self.connector = reactor.connectTCP(self.peer_ip, self.peer_port,self.conn)

	def destroy_connection(self):
		self.connector.disconnect()
		self.connection_status=False
