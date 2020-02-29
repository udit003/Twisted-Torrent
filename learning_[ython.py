class abc:
	d = 10
	def __init__(self):
		self.val = 5
		self.change_val()

	def change_val(self):
		self.val = 6



def alph(a = 10):
	print a

if __name__ == '__main__':
	alph()