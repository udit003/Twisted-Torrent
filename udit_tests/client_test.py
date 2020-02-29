from twisted.internet.protocol import ClientFactory, Protocol 
from twisted.internet.endpoints import TCP4ClientEndpoint, connectProtocol
class my_protocol(Protocol):
	def connectionMade(self):
		print "Connection from", self.transport.getPeer()
		#pass

	def dataReceived(self,data):
		print data

	def send_handshake(self):
		self.transport.write("hello")

	def connectionLost(self,reason):
		print reason

def Client_connection_success(p):
	p.send_handshake()

def Client_connection_failed(err):
	print "connection could not be establised :" , err.getErrorMessage()

if __name__ == '__main__':
	from twisted.internet import reactor
	point = TCP4ClientEndpoint(reactor, "127.0.0.1", 9999)
	d = connectProtocol(point, my_protocol())
	d.addCallback(Client_connection_success)
	d.addErrback(Client_connection_failed)
	reactor.run()