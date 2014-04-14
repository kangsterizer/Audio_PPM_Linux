#!/usr/bin/python
# Licensed under the terms of the GPLv3
# Copyright 2010 kang@insecure.ws
# See http://www.gnu.org/licenses/gpl-3.0.txt or the LICENSE file
__version__='1.0'
__author__='kang'

import wave, math
from struct import pack
from alsaaudio import *
import os
import pygame
from pygame import locals
import threading, thread, sys, Queue, signal

try:
	import pygtk
	pygtk.require("2.6")
except: pass
try:
	import gtk, gobject
except:
	sys.exit(1)

gobject.threads_init()
pygame.init()
pygame.joystick.init()

class SoundFile:
   def  __init__(self, signal, path):
       self.file = wave.open(path, 'wb')
       self.signal = signal
       self.sr = 44100

   def write(self):
       self.file.setparams((2, 2, self.sr, 192000*4, 'NONE', 'noncompressed'))
       self.file.writeframes(self.signal)
       self.file.close()

#some functions i didn't use after all. :P
def getsign(i):
	if i == 0: return 0
	if i > 0: return 1
	if i < 0: return -1

def getsignal(i):
	return -i

class GenSignal:
	signal = ""
	duration = 0.0225 # seconds
	mmdiv = 4.4 #0.1ms
	mmdiv = 19.2
	samplerate = 44100 # Hz
	samplerate = 192000
	samples = int(duration*samplerate) #992.25
#	amplitude = 32760 #max volume
	amplitude = 20262

	channels = {1: 0.0, #throttle
		2: 50.0,
		3: 50.0,
		4: 50.0,
		5: 0.0,
		6: 0.0,
		7: 0.0,
		8: 0.0,
	}

	def generate(self):
		clist = []
		#start with a stop
		clist += [-self.amplitude]*int(self.mmdiv*4)
		for i in self.channels:
			#ppm base (0.7ms)
			clist += [self.amplitude]*int(self.mmdiv*7)
			#ppm signal (1.7ms max)
			servo = self.channels[i]*0.75/100
			signal = (self.mmdiv*10)*servo
			clist += [self.amplitude]*int( signal )
			clist += [-self.amplitude]*int(self.mmdiv*4)

		#complete the ppm signal with a starting null signal that fill in the 22.5ms frame (here f.ex 992 self.samples)
		list = []
		for i in range(0, self.samples-len(clist)):
			list += [0]

		#add our ppm channels
		list += clist

		s=pack('<'+self.samples*'l',*list)
		self.signal = s
class PPM:
	xmlfile = "ppm.xml"
	builder = gtk.Builder()
	builder.add_from_file(xmlfile)

	def __init__(self):
		self.builder.get_object("window1")
		self.channels = {
				1: self.builder.get_object("hscale1"),
				2: self.builder.get_object("hscale2"),
				3: self.builder.get_object("hscale3"),
				4: self.builder.get_object("hscale4"),
				5: self.builder.get_object("hscale5"),
				6: self.builder.get_object("hscale6"),
				7: self.builder.get_object("hscale7"),
				8: self.builder.get_object("hscale8"),
			}
		dict = {"on_hscale1_value_changed": self.hscale,
				"on_hscale2_value_changed": self.hscale,
				"on_hscale3_value_changed": self.hscale,	
				"on_hscale4_value_changed": self.hscale,	
				"on_hscale5_value_changed": self.hscale,	
				"on_hscale6_value_changed": self.hscale,	
				"on_hscale7_value_changed": self.hscale,	
				"on_hscale8_value_changed": self.hscale,	
				"on_window1_delete_event": self.quit,
				"on_button1_clicked": self.quit,
				"on_button2_clicked": self.wave,
				"gtk_main_quit": self.quit,
				"on_imagemenuitem10_activate": self.about,
				"on_entry1_editing_done": self.setamp,
			}
		self.builder.connect_signals(dict)

		#start the PPM stream
		gen.generate()
		q.put_nowait(gen.signal)

	def setamp(self, widget):
		gen.amplitude = int(self.builder.get_object("entry1").get_text())
		gen.generate()
		q.put_nowait(gen.signal)
		print "New amplitude set to ", gen.amplitude

	def about(self, widget):
		about = self.builder.get_object("aboutdialog1")
		about.run()
		about.hide()

	def quit(self, widget, event=None):
		print "Quitting"
		q.put_nowait(1)
		q1.put_nowait(1)
		gtk.main_quit(widget)

	def wave(self, widget):
		#yeah, fixed name! 
		path = "test.wav"
		f= SoundFile(gen.signal, path)
		f.write()

	def hscale(self, widget):
		#bar moved, change servo position
		val = widget.get_value()
		for c in self.channels:
			if self.channels[c] == widget:
#				print "Channel", c, "changed to", val
				gen.channels[c] = val
				gen.generate()
				q.put_nowait(gen.signal)

class Joystick(threading.Thread):
	def __init__(self, q, q1):
		self.q = q
		self.q1 = q1
		threading.Thread.__init__(self)

		try:
			j = pygame.joystick.Joystick(0)
			j.init()
			print "I decided to enable your first joystick:", j.get_name()
		except pygame.error:
			print "No joystick found, plug one and restart this program if you want :p"

	def run(self):
		while 1:
			try:
				item = self.q1.get_nowait()
				if type(item) is int:
					break
			except Queue.Empty:
				pass
			for e in pygame.event.get():
				if e.type == pygame.locals.JOYAXISMOTION:
					#hardcoded mapping!
					x, y, z, t = j.get_axis(0), j.get_axis(1), j.get_axis(2), j.get_axis(3)
					gen.channels[0] = t
					gen.channels[1] = z
					gen.channels[2] = x
					gen.channels[3] = y
					q.put_nowait(gen.signal)

class Signal(threading.Thread):
	"""This class is the thread generating the audio ppm sound"""
	signal = ""
	card = PCM(type=PCM_PLAYBACK, mode=PCM_NONBLOCK, card='default')
	card.setchannels(2)
	card.setrate(192000)
	card.setformat(PCM_FORMAT_S16_LE)
	card.setperiodsize(192000)
	print "Sound card initialized"

	def __init__(self, q):
		self.queue_in = q
		threading.Thread.__init__(self)
	

	def run(self):
		item = None
		while True:
			try:
				item = self.queue_in.get_nowait()
				if type(item) is not int:
					self.signal = item
				else:
					break
			except Queue.Empty:
				pass
			self.card.write(self.signal)
q = Queue.Queue(0)
q1 = Queue.Queue(0)
s = Signal(q)
j = Joystick(q, q)
gen = GenSignal()

def app_terminated(arg1=1, arg2=2, arg3=3):
        app_terminate = True
	q.put_nowait(1)
	q1.put_nowait(1)
        sys.exit()

if __name__ == "__main__":
	signal.signal(signal.SIGQUIT, app_terminated)
	signal.signal(signal.SIGTERM, app_terminated)
	signal.signal(signal.SIGINT, app_terminated)
	s.start()
	j.start()
	app = PPM()
	try:
		gtk.main()
	except:
		app_terminated()
