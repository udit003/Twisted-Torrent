from twisted.internet.protocol import Factory
from twisted.protocols.basic import Int32StringReceiver
from twisted.internet.endpoints import TCP4ClientEndpoint, connectProtocol
from datetime import datetime
from bitarray import bitarray
import torrent
from logging import basicConfig, info, INFO  
basicConfig(filename = 'client.log',filemode='w', level = INFO)
#info("PACKAGE: %s", package)
#info("RESPONSE: %s", response) 


class PeerProtocol(Int32StringReceiver):

	def connectionMade(self):
		print "Connection from", self.transport.getPeer()

	def connectionLost(self,reason):
		print "connection with ",self.transport.getPeer() , "is closed"
		try:
			print self.amt_up,"uploaded to this peer: "
			print self.amt_down,"downloaded from this peer"
		except AttributeError:
			pass
		try:
			if self.peer_obj.connection_status != "malicious_peer":
				self.peer_obj.connection_status = 'no_connection'
		except AttributeError:
			pass


	def send_handshake(self):
		self.sendString(self.peer_obj.client_obj.handshake)

	def send_bitfield_map(self):
		bitmap_str_format = ''
		for i in self.peer_obj.client_obj.pieces_bitmap:
			if i:
				bitmap_str_format += '1'
			else:
				bitmap_str_format += '0'
		bitmap_str_format = '05' + bitmap_str_format
		#print "bitmap" , bitmap_str_format
		self.sendString(bitmap_str_format)
		

	def handle_handshaking(self,msg):
		remote_peer_id = msg[-20:]
		try:
			remote_peer = self.peer_obj
		except AttributeError:
			try:
				remote_peer = self.factory.client_obj_ref.current_peers[remote_peer_id]
			except KeyError:
				print "I dont know this peer\n"
				self.close_connection()
				return 0
			else:
				self.peer_obj = remote_peer
				remote_peer.protocol_ins = self

		if self.peer_obj.connection_status=='malicious_peer':
			self.close_connection_permanently()
			return 0
		if self.peer_obj.connection_status == 'no_connection':
			self.peer_obj.connection_status = 'handshaked'
			self.send_handshake()
		elif self.peer_obj.connection_status == 'one-way-hs':
			self.peer_obj.connection_status = 'handshaked'
			self.send_bitfield_map()
			self.peer_obj.connection_status = 'bitfield-shared'
			self.am_choking = True
			self.peer_choking = True
			self.am_interested = False
			self.peer_interested = False
			self.start_time = datetime.now()
			self.amt_up = 0
			self.amt_down = 0
		else:
			pass


	def check_validity(self):
		if self.peer_obj.connection_status != 'bitfield-shared':
			return False
	
	def handle_bitfield_msg(self,msg):
		if self.peer_obj.connection_status == 'handshaked':
			self.peer_bitarray = bitarray(msg)
			self.send_bitfield_map()
			self.peer_obj.connection_status = 'bitfield-shared'
			self.am_choking = True
			self.peer_choking = True
			self.am_interested = False
			self.peer_interested = False
			self.start_time = datetime.now()
			self.amt_up = 0
			self.amt_down = 0
			
		self.peer_bitarray = bitarray(msg)
		for i in range(self.peer_obj.client_obj.num_pieces): 
			if msg[i]=='1':
				self.peer_obj.client_obj.peers_bitmap[i]['already_have_count'] += 1

		if self.am_i_interested():
			self.sendString('02')
			self.am_interested = True

		if self.am_interested == True:
			self.unchoke_this_peer()
		else:
			self.try_unchoking_peer()

	def choke_this_peer(self):
		self.am_choking = True
		self.peer_obj.client_obj.num_unchoked -= 1
		self.sendString('10')
		from twisted.internet import reactor
		reactor.callLater(20,self.try_unchoking_peer())


	def unchoke_this_peer(self):
		self.am_choking = False
		self.peer_obj.client_obj.num_unchoked += 1
		self.sendString('01')


	def try_unchoking_peer(self):
		if self.am_choking is True:
			if self.am_interested is True:
				self.unchoke_this_peer()
			else:
				if self.peer_obj.client_obj.num_unchoked < self.peer_obj.client_obj.max_unchoked:
					self.unchoke_this_peer()
				else:
					speed = 99999999999999
					temp = None
					for p,p_o in self.peer_obj.client_obj.current_peers.iteritems():
						if p_o.connection_status=='bitfield-shared':
							duration = (datetime.now() - p_o.protocol_ins.start_time).total_seconds
							if  duration> 30:
								my_speed = (p_o.protocol_ins.amt_down+0.000)/duration
								if my_speed < speed:
									speed = my_speed
									temp = p_o.protocol_ins

					if temp is None:
						from twisted.internet import reactor
						reactor.callLater(20,self.try_unchoking_peer())
					else:
						temp.choke_this_peer()
						self.unchoke_this_peer()


		

	def try_to_request_a_piece(self):
		if self.peer_choking is False and self.am_interested is True:
			indx = self.piece_to_request()
			if indx != -1:
				self.peer_obj.client_obj.peers_bitmap[indx]['last_requested'] = self.peer_obj.peer_id
				self.peer_obj.client_obj.peers_bitmap[indx]['timestamp'] = datetime.now()
				self.sendString('06'+str(indx))


	def handle_choking(self,msg):
		if self.check_validity() is False:
				self.close_connection()
				return 0
		self.peer_choking = True
		if self.am_interested is False:
			self.choke_this_peer()


	def handle_unchoking(self,msg):
		if self.check_validity() is False:
				self.close_connection()
				return 0
		self.peer_choking = False
		self.try_to_request_a_piece()


	def handle_interested(self,msg):
		if self.check_validity() is False:
				self.close_connection()
				return 0
		self.peer_interested = True

	def handle_not_interested(self,msg):
		if self.check_validity() is False:
				self.close_connection()
				return 0
		self.peer_interested = False



	def am_i_interested(self):
		for i in range(self.peer_obj.client_obj.num_pieces):
			if self.peer_obj.client_obj.pieces_bitmap[i] is False and self.peer_bitarray[i] is True:
				return True

		return False


	def handle_request_msg(self,msg):
		if self.check_validity() is False:
				self.close_connection()
				return 0
		if self.am_choking == False and self.peer_interested == True:
			piece_indx = int(msg)
			if piece_indx < self.peer_obj.client_obj.num_pieces and self.peer_obj.client_obj.pieces_bitmap[piece_indx] is True:
				self.serve_a_request(piece_indx)

	def serve_a_request(self,indx):
		self.amt_up += self.peer_obj.client_obj.piece_size
		self.peer_obj.client_obj.uploaded += self.peer_obj.client_obj.piece_size
		self.sendString('07'+str(indx)+'-'+self.peer_obj.client_obj.pieces_data[indx])
		print "sent piece index",indx, "to ",self.transport.getPeer() 

	def send_not_interested(self):
		self.am_interested = False
		self.sendString('03')


	def try_sending_not_interested(self):
		for p,p_o in self.peer_obj.client_obj.current_peers.iteritems():
			if p_o.connection_status=='bitfield-shared' and p_o.protocol_ins.am_interested is True:
				temp = False
				for i in range(self.peer_obj.client_obj.num_pieces):
					if p_o.protocol_ins.peer_bitarray[i] is True and self.peer_obj.client_obj.pieces_bitmap[i] is False:
						temp = True
						break

				if temp is False:
					p_o.protocol_ins.send_not_interested()


	def handle_piece_msg(self,msg):
		if self.check_validity() is False:
				self.close_connection()
				return 0
		data = msg.split("-", 1)  #data[0] is index , data[1] is piece
		if self.peer_obj.client_obj.pieces_bitmap[int(data[0])] is False:
			if self.peer_obj.client_obj.validate_piece_received(int(data[0]),data[1]):
				self.peer_obj.client_obj.pieces_data[int(data[0])] = data[1]
				self.peer_obj.client_obj.pieces_bitmap[int(data[0])] = '1'
				print "received piece index",int(data[0]),"from ", self.transport.getPeer()
				self.amt_down += self.peer_obj.client_obj.piece_size
				self.peer_obj.client_obj.downloaded += self.peer_obj.client_obj.piece_size
				self.peer_obj.client_obj.left -= self.peer_obj.client_obj.piece_size
				self.broadcast_have_msg(int(data[0]))
				self.try_sending_not_interested()
				self.try_to_request_a_piece()
				self.peer_obj.client_obj.check_if_completed()
			else:
				self.close_connection_permanently()


	def broadcast_have_msg(self,indx):
		for p,p_o in self.peer_obj.client_obj.current_peers.iteritems():
			if p_o.connection_status=='bitfield-shared':
				p_o.protocol_ins.sendString('04'+str(indx))

	def handle_have_msg(self,msg):
		if self.check_validity() is False:
				self.close_connection()
				return 0
		self.peer_bitarray[int(msg)] = '1'
		self.peer_obj.client_obj.peers_bitmap[int(msg)]['already_have_count'] += 1
		if self.am_i_interested() is True and self.am_interested is False:
			self.sendString('02')
			self.am_interested = True
		

	def piece_to_request(self):
		min_num = 9999999
		temp_time = datetime(3000,1,1)
		temp_index = -1
		my_list = []
		for i in range(self.peer_obj.client_obj.num_pieces):
			if ((self.peer_bitarray[i] is True) and (self.peer_obj.client_obj.pieces_bitmap[i] is False)):
				if self.peer_obj.client_obj.peers_bitmap[i]["last_requested"] is None:
					my_list.append(i)
		if my_list:
			import random
			return random.choice(my_list)
		else:
			for i in range(self.peer_obj.client_obj.num_pieces):
				if ((self.peer_bitarray[i] is True) and (self.peer_obj.client_obj.pieces_bitmap[i] is False)):
					if self.peer_obj.client_obj.peers_bitmap[i]['already_have_count']<min_num:
						temp_index = i
						temp_time = self.peer_obj.client_obj.peers_bitmap[i]["timestamp"]
					elif self.peer_obj.client_obj.peers_bitmap[i]['already_have_count']==min_num and self.peer_obj.client_obj.peers_bitmap[i]["timestamp"]< temp_time:
						temp_time = self.peer_obj.client_obj.peers_bitmap[i]["timestamp"]
						temp_index = i
			return temp_index
		

	def close_connection(self):
		try:
			self.peer_obj.connection_status = 'no_connection'
		except AttributeError:
			pass
		finally:
			print "i closed the connection with ", self.transport.getPeer()
			self.transport.loseConnection()

	def close_connection_permanently(self):
		self.peer_obj.connection_status = "malicious_peer"
		print self.transport.getPeer() , "seems malicious ..closing conn permanently"
		self.transport.loseConnection()


	def stringReceived(self,string):
		#print string[:2] , "received from ", self.transport.getPeer()
		try:
			msg_type = torrent.message_id_to_type[string[:2]]
		except KeyError:
			self.close_connection()
		else:
			msg_to_msg_handlers[msg_type](self,string[2:])



msg_to_msg_handlers = {'handshake':PeerProtocol.handle_handshaking,'bitfield':PeerProtocol.handle_bitfield_msg,'request':PeerProtocol.handle_request_msg,'piece':PeerProtocol.handle_piece_msg,'have':PeerProtocol.handle_have_msg,'interested':PeerProtocol.handle_interested,'not_interested':PeerProtocol.handle_not_interested,'choking':PeerProtocol.handle_choking,'unchoking':PeerProtocol.handle_unchoking }


#class to build the server part of a client 
class Torrent_Server_Factory(Factory):
	protocol = PeerProtocol # tell base class what proto to build
	def __init__(self,clo):
		self.client_obj_ref = clo


class my_peers():
	def __init__(self,peer_data,client_obj):
		self.peer_id = peer_data["peer_id"]
		self.peer_ip = peer_data["ip"]
		self.peer_port = peer_data["port"]
		self.peer_upload= peer_data["upload_amt"]	
		self.peer_download = peer_data["download_amt"]
		self.peer_left = peer_data["left_amt"]
		self.connection_status = 'no_connection'
		self.client_obj = client_obj

	def Client_connection_success(self,p):
		p.peer_obj = self
		self.protocol_ins = p
		#print " i sent the handshake" , datetime.now()
		p.send_handshake()
		self.connection_status = 'one-way-hs'

	def Client_connection_failed(self,err):
		pass
		#enter the data into logging file with self.peer_id details


	def start_talking(self):
		#print self.connection_status
		""" this is a hacky part , in order to create two tcp connection between same paor of clients , only client with larger peer_id is allowed to initiate the connection"""


		'''connection_status = ['no_connection','one-way-hs','handshaked']'''

		if ((int(self.client_obj.peer_id[-12:])>int(self.peer_id[-12:])) and (self.connection_status in ['no_connection','one-way-hs'])):
			print "i am trying to talk to ", self.peer_port
			from twisted.internet import reactor
			point = TCP4ClientEndpoint(reactor, self.peer_ip, self.peer_port)
			d = connectProtocol(point,PeerProtocol())
			d.addCallback(self.Client_connection_success)
			d.addErrback(self.Client_connection_failed)

	def stop_talking(self):
		if self.connection_status != 'no_connection':
			self.protocol_ins.close_connection()
		#print "I no longer know client",self.peer_ip,self.peer_port
		del self
		#pass			

