from time import sleep
from datetime import datetime

own_cnt = 0
rec_cnt = 0
'''
i =0
	if i is 0:
		print "reactor called", rec_cnt
		rec_cnt += 1
	else:
		print "recursion call ", own_cnt
		own_cnt += 1
	#sleep(5)
	#reactor.callLater(1,delay_func,1)

'''
def delay_func(i):
	global rec_cnt,own_cnt
	if i == 0:
		print "reactor called", rec_cnt,datetime.now()
		rec_cnt += 1
	else:
		print "recursion call ", own_cnt,datetime.now()
		own_cnt += 1
	#sleep(4)
	reactor.callLater(1,delay_func,1)
	

from twisted.internet import reactor
from twisted.internet.task import LoopingCall

lc = LoopingCall(delay_func,(0))
lc.start(6,now=True)

reactor.run()