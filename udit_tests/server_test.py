from twisted.internet.protocol import ClientFactory, Protocol 
class my_protocol(Protocol):
	def connectionMade(self):
		print "Connection from", self.transport.getPeer()
		self.transport.loseConnection()
		#pass

	def dataReceived(self,data):
		print data

	def connectionLost(self,reason):
		print "hahahha"
		print reason


class MyFactory(ClientFactory):

	protocol = my_protocol

	def startedConnecting(self, connector):
		 print "Started to connect."

if __name__ == '__main__':
	from twisted.internet import reactor
	reactor.listenTCP(9999,MyFactory())
	reactor.run()
	