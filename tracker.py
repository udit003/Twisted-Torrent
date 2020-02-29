 # pytorrent-tracker.py
# A bittorrent tracker

from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
import threading
from SocketServer import ThreadingMixIn
from logging import basicConfig, info, INFO
from pickle import dump, load
from socket import inet_aton
from struct import pack
from urllib import urlopen
from urlparse import parse_qs
from time import time , sleep 

from bencode import encode

data_lock = threading.Lock()
meta_data_lock = threading.Lock()

def decode_request(path):
	""" Return the decoded request string. """

	# Strip off the start characters
	if path[:1] == "?":
		path = path[1:]
	elif path[:2] == "/?":
		path = path[2:]

	return parse_qs(path)


def process_request(torrents,client_ip,package,meta_data):

	# Get the necessary info out of the request
	info_hash = package["info_hash"][0]
	compact = bool(package["compact"][0])
	event = "regular"   
	"""if it is a regular update packet then even field is not sent but when the client
	 starts : package['event'] = "started", when client closes : package['event'] = 
	 "stopped",when client completes the download : package['event'] = "downloaded"   """
	if 'event' in package:
		event = package['event'][0]
	port = package["port"][0]
	peer_id = package["peer_id"][0]
	download_amt = package["downloaded"][0]
	upload_amt = package["uploaded"][0]
	left_amt = package["left"][0]

	cur_time = time()
	# If we've heard of this, just add the peer
	data_lock.acquire()
	if info_hash in torrents:
		#print torrents[info_hash]
		# Only add the peer if they're not already in the database
		found  = False
		for peers in torrents[info_hash]:
			if (peers[0]==peer_id and peers[1]==client_ip and peers[2]==port):
				peers[3] = upload_amt
				peers[4] = download_amt
				peers[5] = left_amt
				peers[6] = cur_time
				meta_data_lock.acquire()
				if(event=="downloaded"):
					meta_data['completed'] += 1
				elif(event=="stopped") :
					torrents[info_hash].remove(peers)
					if(left_amt==0):
						meta_data['completed'] -= 1
					else:
						meta_data['not_completed'] -= 1
				meta_data_lock.release()
				found = True
				break
		if not found and event!="stopped":
			torrents[info_hash].append([peer_id, client_ip, port,upload_amt,download_amt,left_amt \
										, cur_time])
	# Otherwise, add the info_hash and the peer
	else:
		torrents[info_hash] = [[peer_id, client_ip, port,upload_amt,download_amt,left_amt,cur_time]]
	data_lock.release()
	if(event=="started"):
		meta_data_lock.acquire()
		if(left_amt!=0):
			meta_data['not_completed'] += 1
		else:
			meta_data['completed'] +=1
		meta_data_lock.release()
	


#-----------------------------------------------------------------

##note this function "make compact_peer_list" is incomplete , see make_peer_list for references

def make_compact_peer_list(peer_list,own_peer_id):
	""" Return a compact peer string, given a list of peer details. """

	peer_string = ""
	for peer in peer_list:
		ip = inet_aton(peer[1])
		port = pack(">H", int(peer[2]))

		peer_string += (ip + port)

	return peer_string

def make_peer_list(peer_list,own_peer_id):
	""" Return an expanded peer list suitable for the client, given
	the peer list. """

	peers = []
	for peer in peer_list:
		if peer[0] == own_peer_id:
			continue
		p = {}
		p["peer_id"] = peer[0]
		p["ip"] = peer[1]
		p["port"] = int(peer[2])
		p["upload_amt"] = peer[3]
		p["download_amt"] = peer[4]
		p["left_amt"] = peer[5]

		peers.append(p)
	return peers

def peer_list(peer_list, compact, own_peer_id):
	""" Depending on compact, dispatches to compact or expanded peer
	list functions. """

	#if compact:
		#return make_compact_peer_list(peer_list,own_peer_id)
	#else:
	return make_peer_list(peer_list,own_peer_id)

class RequestHandler(BaseHTTPRequestHandler):
	def do_GET(s):
		""" Take a request, do some some database work, return a peer
		list response. """

		# Decode the request
		package = decode_request(s.path)
		if not package:
			s.send_error(403)
			return
		ip = s.client_address[0]
		print ip,package["port"][0]
		process_request(s.server.torrents,ip,package,s.server.meta_data) 
		"""inside this add_peer, remove peer, do all db_ops and then generate the response
		so add peer can go inside this function only """
		# Generate a response
		if 'event' in package and package['event'][0]=="stopped":
			response = {}
		else:
			response = {}
			response["interval"] = s.server.interval
			meta_data_lock.acquire()
			response["complete"] = s.server.meta_data['completed']
			response["incomplete"] = s.server.meta_data['not_completed']
			meta_data_lock.release()
			data_lock.acquire()
			print s.server.torrents[package['info_hash'][0]]
			all_peers_for_this_file = s.server.torrents[package['info_hash'][0]]
			data_lock.release()
			response["peers"] = peer_list( \
			all_peers_for_this_file, bool(package['compact'][0]),package["peer_id"][0])

			#print response["peers"]
		# Send off the response
		s.send_response(200)
		s.end_headers()
		s.wfile.write(encode(response))

		# Log the request, and what we send back
		info("PACKAGE: %s", package)
		info("RESPONSE: %s", response)

	def log_message(self, format, *args):
		""" Just supress logging. """

		return

class ThreadHTTPServer(ThreadingMixIn,HTTPServer):
	"This is an HTTPServer that supports thread-based concurrency."


class Tracker():
	def __init__(self, host = "", port = 8010, interval = 10, \
		torrent_db = "tracker.db", log = "tracker.log", \
		inmemory = True):
		""" Read in the initial values, load the database. """

		self.host = host
		self.port = port

		self.inmemory = inmemory

		self.server_class = ThreadHTTPServer
		self.httpd = self.server_class((self.host, self.port),RequestHandler)

		self.running = False	# We're not running to begin with

		self.server_class.interval = interval
		self.server_class.meta_data = {'completed':0,'not_completed':0}

		# Set logging info
		basicConfig(filename = 'tracker.log',filemode='w', level = INFO)

		# If not in memory, give the database a file, otherwise it
		# will stay in memory
		if self.inmemory:
			self.server_class.torrents = {}


	def maintain_latest_data(self,timeout_duration):  # set timeout_duration to be high
		""" remove the entries of the client which are not updateing for long duration"""
		#print "I AM ALIVE ***********************************"	
		if(self.running):
			new_thread = threading.Timer(timeout_duration,self.maintain_latest_data,[timeout_duration])
			new_thread.start()

		with data_lock:
			cur_time = time()
			for i in self.server_class.torrents:
				for peers in self.server_class.torrents[i]:
					if(cur_time - peers[6]> timeout_duration):  #peers[6] is the timestamp field
						with meta_data_lock:
							if peers[5]==0:
								self.server_class.meta_data['completed'] -= 1
							else:
								self.server_class.meta_data['not_completed'] -= 1
						self.server_class.torrents[i].remove(peers)
		#there is a doubt that which position thread should be joined
		new_thread.join()				


	def runner(self):
		""" Keep handling requests, until told to stop. """

		while self.running:
			self.httpd.handle_request()

	def run(self):
		""" Start the runner, in a seperate thread. """

		if not self.running:
			self.running = True

			self.request_thread = threading.Thread(target = self.runner)
			self.request_thread.start()
			self.maintainer_thread = threading.Thread(target = self.maintain_latest_data,args=([2*self.server_class.interval]))
			self.maintainer_thread.start()


	def send_dummy_request(self):
		""" Send a dummy request to the server. """

		# To finish off httpd.handle_request()
		address = "http://127.0.0.1:" + str(self.port)
		urlopen(address)

	def stop(self):
		""" Stop the thread, and join to it. """

		if self.running:
			self.running = False

			self.send_dummy_request()
			self.request_thread.join()
			self.maintainer_thread.join()

	def __del__(self):
		""" Stop the tracker thread, write the database. """

		self.stop()
		self.httpd.server_close()

if __name__ == '__main__':
	#instantiate a tracker object and run the tracker server
	tracker = Tracker()
	tracker.run()
	print "Press 0 to exit\n"
	p = raw_input().strip()
	print p
	if int(p)==0:
		del tracker