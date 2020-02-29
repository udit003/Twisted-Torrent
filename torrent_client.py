#this is the client code , here there are four major activities :
""" 1. keep communicating with the tracker """

import sys
import torrent
from bitarray import bitarray	
from util import slice
from math import ceil
import peer_protocol
from bencode import decode,encode
from urllib import urlencode, urlopen  
from hashlib import md5, sha1
from twisted.internet.endpoints import TCP4ServerEndpoint

class Torrent_Client():
	def __init__(self, torrent_file,port_no):
		self.running = False
		self.max_unchoked = 4
		self.data = torrent.read_torrent_file(torrent_file)
		self.info_hash = sha1(encode(self.data["info"])).digest()
		self.peer_id = torrent.generate_peer_id()
		self.handshake = torrent.generate_handshake(self.info_hash, self.peer_id)
		self.downloaded = 0
		self.uploaded = 0
		self.port_no = port_no
		self.current_peers = {}
		self.load_initial_pieces()
		#print "initial bitmap" , self.pieces_bitmap
		print "setup done"

	def load_initial_pieces(self):
		self.piece_size = self.data["info"]["piece length"]
		self.num_pieces = int(ceil((self.data["info"]["length"]+0.000000)/self.piece_size))
		#print self.data["info"]["length"], self.num_pieces
		self.pieces_bitmap = self.num_pieces*bitarray('0')
		try:
			f = open(self.data["info"]["name"], "r")
		except IOError:
			self.seeder = False
			self.pieces_data = [None for i in range(self.num_pieces)]
			self.pieces_count = 0
			self.left = self.data["info"]["length"]
		else:
			self.seeder = True
			self.pieces_data = slice(f.read(),self.piece_size)
			f.close()
			self.pieces_bitmap.setall('1')
			self.pieces_count = self.num_pieces
			self.left = 0
		finally:
			self.loading_initial_peers_setup()


	def loading_initial_peers_setup(self):
		self.peers_bitmap = []
		for _ in range(self.num_pieces):
			self.peers_bitmap.append({'already_have_count':0,'last_requested':None,'timestamp':None })

		self.num_unchoked = 0

	def validate_piece_received(self,piece_indx, data):
		hash_val = sha1(data).digest()
		if self.data["info"]["pieces"][20*piece_indx:20*(piece_indx+1)] == hash_val:
			return True
		else:
			return False

	def check_if_completed(self):
		if self.pieces_bitmap.all():
			with open(self.data["info"]["name"], "w") as my_file:
				data = ""
				for i in self.pieces_data:
					data += i
				my_file.write(data)
			print "Yay your file has been downloaded !! You ca find it in the same directory."
			self.print_stats()

	def print_stats(self):
		print "UPLOADED : ",self.uploaded, "    DOWNLOADED : ",self.downloaded

		
	def handle_peers(self,all_peers):

	  # this does not handle compact peer for now

	  #adding the peer which are new , or updating the old peers 
	  
		for peer in all_peers:
			print peer["port"]
			if peer["peer_id"] in self.current_peers:
				old_ins = self.current_peers[peer["peer_id"]]
				old_ins.peer_upload= peer["upload_amt"]	
				old_ins.peer_download = peer["download_amt"]
				old_ins.peer_left = peer["left_amt"]
			else:
				self.current_peers[peer["peer_id"]] = peer_protocol.my_peers(peer,self)
			print "------------------------------------------"

		#remove the peers which are no longer available	, talk to ones which are there	

		for peer_id in self.current_peers:
			flag = False
			for av_peers in all_peers:
				if peer_id==av_peers["peer_id"]:
					flag = True
					break

			if flag is False:
				self.current_peers[peer_id].stop_talking()
			else:
				#print "start talking called"
				self.current_peers[peer_id].start_talking()


	def perform_tracker_request(self,event="regular"):
		""" Make a tracker request to url, every interval seconds, using
		the info_hash and peer_id, and decode the peers on a good response. """

		"""NOTE:THIS FUNCTION CALL IS ACTUALLY A BLOCKING,NEEDS TO MAKE A TWISTED WEB CLIENT"""

		tracker_response = self.make_tracker_request(event) 
		#print tracker_response
		if "failure reason" not in tracker_response:
			self.handle_peers(tracker_response["peers"])  #this part is pending
		if self.running:
			from twisted.internet import reactor
			reactor.callLater(tracker_response["interval"],self.perform_tracker_request)


	def make_tracker_request(self,event):
	# Generate a tracker GET request.
		payload = {"info_hash" : self.info_hash,
				"peer_id" : self.peer_id,
				"port" : self.port_no,
				"uploaded" : self.uploaded,
				"downloaded" : self.downloaded,
				"left" : self.left,
				"compact" : 0}  #the concept of compact is withheld for now 
	#add event field and change the uploaded , downloaded , left field
		if event != "regular":
			payload["event"] = event
		payload = urlencode(payload)
		#print payload
		response = urlopen(self.data["announce"] + "?" + payload).read()
		#print "response received from tracker"
		return decode(response)

	def run(self):
		""" Start the torrent running. """
		from twisted.internet import reactor
		reactor.callWhenRunning(self.perform_tracker_request,"started")
		endpoint = TCP4ServerEndpoint(reactor, self.port_no)
		endpoint.listen(peer_protocol.Torrent_Server_Factory(self))
		if not self.running:
			self.running = True
			reactor.run()


	def stop(self):
		""" Stop the torrent from running. """

		if self.running:
			self.running = False
			reactor.stop()

	def __del__(self):
		self.stop()

if __name__ == '__main__':
	torrent_file = sys.argv[1]
	my_port = int(sys.argv[2])
	bitorrenter = Torrent_Client(torrent_file,my_port)
	bitorrenter.run()



