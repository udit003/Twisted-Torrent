#torrent.py
# Torrent file related utilities

from hashlib import md5, sha1
from random import choice
import socket
from struct import pack, unpack
from threading import Thread
from time import sleep, time
import types
from urllib import urlencode, urlopen
from util import collapse, slice

from bencode import decode, encode

CLIENT_NAME = "pytorrent"
CLIENT_ID = "PY"
CLIENT_VERSION = "0001"

def make_info_dict(file):
	""" Returns the info dictionary for a torrent file. """

	with open(file) as f:
		contents = f.read()

	piece_length = 524288	# TODO: This should change dependent on file size

	info = {}

	info["piece length"] = piece_length
	info["length"] = len(contents)
	info["name"] = file
	info["md5sum"] = md5(contents).hexdigest()

	# Generate the pieces
	pieces = slice(contents, piece_length)
	pieces = [ sha1(p).digest() for p in pieces ]
	info["pieces"] = ''.join([p for p in pieces])
	return info

def make_torrent_file(file = None, tracker = None, comment = None):
	""" Returns the bencoded contents of a torrent file. """

	if not file:
		raise TypeError("make_torrent_file requires at least one file, non given.")
	if not tracker:
		raise TypeError("make_torrent_file requires at least one tracker, non given.")

	torrent = {}

	# We only have one tracker, so that's the announce
	if type(tracker) != list:
		torrent["announce"] = tracker
	# Multiple trackers, first is announce, and all go in announce-list
	elif type(tracker) == list:
		torrent["announce"] = tracker[0]
		# And for some reason, each needs its own list
		torrent["announce-list"] = [[t] for t in tracker]

	torrent["creation date"] = int(time())
	torrent["created by"] = CLIENT_NAME
	if comment:
		torrent["comment"] = comment

	torrent["info"] = make_info_dict(file)
	#print(torrent)

	return encode(torrent)

def write_torrent_file(torrent = None, file = None, tracker = None, \
	comment = None):
	""" Largely the same as make_torrent_file(), except write the file
	to the file named in torrent. """

	if not torrent:
		raise TypeError("write_torrent_file() requires a torrent filename to write to.")

	data = make_torrent_file(file = file, tracker = tracker, \
		comment = comment)
	with open(torrent, "w") as torrent_file:
		torrent_file.write(data)

def read_torrent_file(torrent_file):
	""" Given a .torrent file, returns its decoded contents. """

	with open(torrent_file) as file:
		return decode(file.read())

if __name__ == '__main__':
	write_torrent_file("first.torrent","intro.txt","10.0.0.0:8000","whooa")
	print read_torrent_file("first.torrent")

