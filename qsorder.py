#!/usr/bin/python

##################################################
# qsorder - A contest QSO recorder
# Title: qsorder.py
# Author: k3it
# Generated: Wed Dec 5 2012
# Version: 2.1b
##################################################

# qsorder is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# qsorder is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import subprocess
import re
import pyaudio
import wave
import time
import sys
import struct
import datetime
import threading
import string
import binascii

from optparse import OptionParser
from collections import deque
from socket import *
from xml.dom.minidom import parse, parseString

CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 2
RATE = 8000
BASENAME = "QSO"
LO = 14000
dqlength = 360 # number of chunks to store in the buffer
DELAY = 20.0
MYPORT=12060

usage = "usage: %prog [OPTION]..."
parser = OptionParser()
parser.add_option("-l", "--buffer-length", type="int", default=45,
                  help="Audio buffer length in secs [default=%default]")
parser.add_option("-d", "--delay", type="int", default=20, 
                  help="Capture x seconds after QSO log entry [default=%default]")
parser.add_option("-p", "--path", type="string", default=None,
                  help="Base directory for audio files [default=%default]")
parser.add_option("-P", "--port", type="int", default=12060,
                  help="UDP Port [default=%default]")
parser.add_option("-s", "--station-nr", type="int", default=None,
                  help="Network Station Number [default=%default]")

(options,args) = parser.parse_args()

dqlength =  int (options.buffer_length * RATE / CHUNK) + 1
DELAY = options.delay
MYPORT = options.port

if (options.path):
	os.chdir(options.path)

class wave_file:
        """
        class definition for the WAV file object
        """
        def __init__(self,samp_rate,LO,BASENAME,qso_time,contest_dir):
                #starttime/endtime
                self.create_time=time.time()
                #now=datetime.datetime.utcnow()
                now=qso_time
                #finish=now + datetime.timedelta(seconds=duration)

                self.wavfile = BASENAME + "_"
                self.wavfile += str(now.year)
                self.wavfile += str(now.month).zfill(2)
                self.wavfile += str(now.day).zfill(2)
                self.wavfile += "_"
                self.wavfile += str(now.hour).zfill(2)
                self.wavfile += str(now.minute).zfill(2)
                self.wavfile += str(now.second).zfill(2)
                self.wavfile += "Z_"
                #self.wavfile += str(int(LO/1000))
                self.wavfile += str(LO)
                self.wavfile += "MHz.wav"

		#contest directory
		contest_dir += "_" + str(now.year) 

		#fix slash in the file/directory name
		self.wavfile = self.wavfile.replace('/','-')
		contest_dir = contest_dir.replace('/','-')

		self.wavfile = contest_dir + "/" + self.wavfile

                # get ready to write wave file
                try:
			if not os.path.exists(contest_dir):
    				os.makedirs(contest_dir)
			self.w = wave.open(self.wavfile, 'wb')
                except:
                        print "unable to open WAV file for writing"
                        sys.exit()

        

                #16 bit complex samples 
                #self.w.setparams((2, 2, samp_rate, 1, 'NONE', 'not compressed'))
		self.w.setnchannels(CHANNELS)
		self.w.setsampwidth(p.get_sample_size(FORMAT))
		self.w.setframerate(RATE)
                #self.w.close()
                

        def write(self,data):
                self.w.writeframes(data)

        def close_wave(self,nextfilename=''):
                self.w.close()


def dump_audio(call,mode,freq,qso_time):
	#create the wave file
	BASENAME = call + "_" + mode 
	BASENAME = BASENAME.replace('/','-')
	w=wave_file(RATE,freq,BASENAME,qso_time,mode)
	__data = (b''.join(frames))
	bytes_written=w.write(__data)
	w.close_wave()

	#try to convert to mp3
	lame_path = os.path.dirname(os.path.realpath(__file__))
	lame_path += "\\lame.exe"
	command = [lame_path,w.wavfile]
	try:
		output=subprocess.Popen(command, \
				stderr=subprocess.STDOUT, stdout=subprocess.PIPE).communicate()[0]
		#mp3 = re.search('\S+.mp3',output)
		gain = re.search('\S*Replay.+$',output)
		print "WAV:", datetime.datetime.utcnow().strftime("%m-%d %H:%M:%S"), BASENAME[:20] + ".." + freq + "Mhz.mp3", \
				gain.group(0)
		os.remove(w.wavfile)
	except:
		print "could not convert wav to mp3", w.wavfile

        


print("\t--------------------------------")
print "v2.1b QSO Recorder for N1MM, 2012 K3IT\n"
print("\t--------------------------------")
print "Listening on UDP port", MYPORT

p = pyaudio.PyAudio()


try:
    def_index = p.get_default_input_device_info()
    print "Input Device :", def_index['name']
except IOError as e:
    print("No Input devices: %s" % e[0])


#frames = []
frames = deque('',dqlength)



# define callback
def callback(in_data, frame_count, time_info, status):
    frames.append(in_data)
    return (None, pyaudio.paContinue)


stream = p.open(format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK,
		stream_callback=callback)

# start the stream
stream.start_stream()


print "* recording", CHANNELS, "ch,", dqlength * CHUNK / RATE, "secs audio buffer, Delay:", DELAY, "secs" 
print "Output directory", os.getcwd() + "\\<contest_YEAR>"
if (options.station_nr >= 0):
	print "Recording only station", options.station_nr, "QSOs"
print("\t--------------------------------")


#listen on UDP port
# Receive UDP packets transmitted by a broadcasting service

s = socket(AF_INET, SOCK_DGRAM)
s.setsockopt(SOL_SOCKET, SO_BROADCAST, 1)
s.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
try:
        s.bind(('', MYPORT))
except:
        print "Error connecting to the UDP stream."


seen={}

while stream.is_active():
	try:
		udp_data=s.recv(2048)
		check_sum = binascii.crc32(udp_data)
		dom = parseString(udp_data)

		if check_sum in seen:
			seen[check_sum] += 1
		else:
			seen[check_sum] = 1
			try:
				dom = parseString(udp_data)
				call = dom.getElementsByTagName("call")[0].firstChild.nodeValue
				mycall = dom.getElementsByTagName("mycall")[0].firstChild.nodeValue
				mode = dom.getElementsByTagName("mode")[0].firstChild.nodeValue
				freq = dom.getElementsByTagName("band")[0].firstChild.nodeValue
				contest = dom.getElementsByTagName("contestname")[0].firstChild.nodeValue
				station = dom.getElementsByTagName("NetworkedCompNr")[0].firstChild.nodeValue
				
				# skip packet if not matching network station number specified in the command line
				if (options.station_nr >= 0):
					if (options.station_nr != station):
						print "QSO:", datetime.datetime.utcnow().strftime("%m-%d %H:%M:%S"), call, freq, "--- ignoring from stn", station
						continue

				calls = call + "_de_" + mycall
				modes = contest + "_" + mode

				t = threading.Timer( DELAY, dump_audio,[calls,modes,freq,datetime.datetime.utcnow()] )
				print "QSO:", datetime.datetime.utcnow().strftime("%m-%d %H:%M:%S"), call, freq
				t.start()
			except:
				pass # ignore, probably some other udp packet

	except (KeyboardInterrupt):
		print "73! k3it"
		stream.stop_stream()
		stream.close()
		p.terminate()
		raise


#
stream.close()
p.terminate()

