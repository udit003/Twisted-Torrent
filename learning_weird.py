class base:
	def __init__(self):
		self.a = 10
	def dum(self):
		self.peer_obj = peer_class()


class peer_class:
	def __init__(self):
		self.b = 20

	def che(self, udit):
		print udit

if __name__ == '__main__':
	base_obj = base()
	base_obj.dum()
	base_obj.peer_obj.che(base_obj.a)
