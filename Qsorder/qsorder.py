#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Docstring"""

# pylint: disable=unused-import, c-extension-no-member, no-member, invalid-name, too-many-lines, no-name-in-module, bare-except
# pylint: disable=consider-using-enumerate

##################################################
# qsorder - A contest QSO recorder
# Title: qsorder.py
# Author: k3it
# Generated: Fri, Mar 27 2020
# Version: 2.15
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

# import string
import binascii
import os
import re
import subprocess
import sys

# import struct
import threading
import time
import wave

# try:
#     import keyboard

#     nopyhk = False
# except:
#     nopyhk = True

import argparse
import ctypes
import datetime
import logging
import platform
import socket
import xml.parsers.expat
from collections import deque

# from socket import *
from xml.dom.minidom import parseString

import dateutil.parser
import sounddevice as sd

# import soundfile as sf

NOPYHK = True
CHUNK = 1024
FORMAT = "int16"
CHANNELS = 1
BASENAME = "QSO"
LO = 14000
DEBUG_FILE = "qsorder-debug-log.txt"
options = None
RATE = None
HOTKEY = None
frames = None
REPLAY_FRAMES = None


class WaveFile:
    """
    class definition for the WAV file object
    """

    def __init__(self, samp_rate, LO, BASENAME, qso_time, contest_dir, mode, sampwidth):
        now = qso_time

        self.wavfile = BASENAME + "_"
        self.wavfile += str(now.year)
        self.wavfile += str(now.month).zfill(2)
        self.wavfile += str(now.day).zfill(2)
        self.wavfile += "_"
        self.wavfile += str(now.hour).zfill(2)
        self.wavfile += str(now.minute).zfill(2)
        self.wavfile += str(now.second).zfill(2)
        self.wavfile += "Z_"
        # self.wavfile += str(int(LO/1000))
        self.wavfile += str(LO)
        self.wavfile += "MHz.wav"

        # contest directory
        self.contest_dir = contest_dir
        self.contest_dir += "_" + str(now.year)

        # fix slash in the file/directory name
        self.wavfile = self.wavfile.replace("/", "-")
        self.contest_dir = self.contest_dir.replace("/", "-")

        self.wavfile = self.contest_dir + "/" + self.wavfile
        print(self.wavfile)
        # get ready to write wave file
        try:
            if not os.path.exists(self.contest_dir):
                os.makedirs(self.contest_dir)
            self.w = wave.open(self.wavfile, "wb")
        except:
            print("unable to open WAV file for writing")
            sys.exit()
        # 16 bit complex samples
        # self.w.setparams((2, 2, samp_rate, 1, 'NONE', 'not compressed'))
        self.w.setnchannels(CHANNELS)
        self.w.setsampwidth(sampwidth)
        self.w.setframerate(RATE)
        # self.w.close()

    def write(self, data):
        """insert docstring"""
        self.w.writeframes(data)

    def close_wave(self, nextfilename=""):
        """insert docstring"""
        self.w.close()


def dump_audio(call, contest, mode, freq, qso_time, radio_nr, sampwidth):
    """create the wave file"""
    BASENAME = call + "_" + contest + "_" + mode
    BASENAME = BASENAME.replace("/", "-")
    w = WaveFile(RATE, freq, BASENAME, qso_time, contest, mode, sampwidth)
    __data = b"".join(frames)
    w.close_wave()

    # try to convert to mp3
    lame_path = "/usr/bin/lame"

    if not os.path.isfile(lame_path):
        # try to use one in the system path
        lame_path = "lame"

    artist = "QSO Audio"
    title = os.path.basename(w.wavfile).replace(".wav", "")
    year = str(qso_time.year)

    if options.so2r and radio_nr == "1":
        command = [lame_path]
        arguments = [
            "--tt",
            title,
            "--ta",
            artist,
            "--ty",
            year,
            "-h",
            "-m",
            "l",
            w.wavfile,
        ]
        command.extend(arguments)
    elif options.so2r and radio_nr == "2":
        command = [lame_path]
        arguments = [
            "--tt",
            title,
            "--ta",
            artist,
            "--ty",
            year,
            "-h",
            "-m",
            "r",
            w.wavfile,
        ]
        command.extend(arguments)
    else:
        command = [lame_path]
        arguments = ["--tt", title, "--ta", artist, "--ty", year, "-h", w.wavfile]
        command.extend(arguments)

    if options.debug:
        logging.debug(command[0].encode("utf-8"))  # , command[1:])

    try:
        output = subprocess.Popen(
            command, stderr=subprocess.STDOUT, stdout=subprocess.PIPE
        ).communicate()[0]
        gain = re.search("\S*Replay.+", output.decode())
        print(
            "WAV:",
            datetime.datetime.utcnow().strftime("%m-%d %H:%M:%S"),
            BASENAME[:20] + ".." + str(freq) + "Mhz.mp3",
            gain.group(0),
        )
        os.remove(w.wavfile)
    except:
        print("could not convert wav to mp3", w.wavfile)


def manual_dump():
    """insert docstring"""
    print(
        "QSO:", datetime.datetime.utcnow().strftime("%m-%d %H:%M:%S"), "HOTKEY pressed"
    )
    dump_audio("HOTKEY", "AUDIO", "RF", 0, datetime.datetime.utcnow(), 73, 2)


def hotkey():
    """doc"""
    if NOPYHK:
        return
    # add hotkey
    # try:
    #     keyboard.add_hotkey("ctrl+alt+" + HOTKEY.lower(), manual_dump)
    # except:
    #     NOPYHK = True


def get_free_space_mb(folder):
    """Return folder/drive free space (in bytes)"""
    if platform.system() == "Windows":
        free_bytes = ctypes.c_ulonglong(0)
        ctypes.windll.kernel32.GetDiskFreeSpaceExW(
            ctypes.c_wchar_p(folder), None, None, ctypes.pointer(free_bytes)
        )
        return free_bytes.value / 1024 / 1024
    st = os.statvfs(folder)
    return st.f_bavail * st.f_frsize / 1024 / 1024


def start_new_lame_stream():
    """try to convert to mp3"""
    lame_path = "/usr/bin/lame"

    if not os.path.isfile(lame_path):
        # try to use one in the system path
        lame_path = "lame"

    # print "CTL: Starting new mp3 file", datetime.datetime.utcnow.strftime("%m-%d %H:%M:%S")
    now = datetime.datetime.utcnow()
    contest_dir = "AUDIO_" + str(now.year)
    if not os.path.exists(contest_dir):
        os.makedirs(contest_dir)

    globals()["BASENAME"] = "CONTEST_AUDIO"
    filename = contest_dir + "/" + BASENAME + "_"
    filename += str(now.year)
    filename += str(now.month).zfill(2)
    filename += str(now.day).zfill(2)
    filename += "_"
    filename += str(now.hour).zfill(2)
    filename += str(now.minute).zfill(2)
    filename += "Z"
    filename += ".mp3"
    command = [lame_path]
    arguments = [
        "-r",
        "-s",
        str(RATE),
        "-h",
        "--flush",
        "--quiet",
        "--tt",
        "Qsorder Contest Recording",
        "--ty",
        str(now.year),
        "--tc",
        os.path.basename(filename),
        "-",
        filename,
    ]
    command.extend(arguments)
    try:
        mp3handle = subprocess.Popen(
            command,
            stderr=subprocess.STDOUT,
            stdout=subprocess.PIPE,
            stdin=subprocess.PIPE,
        )
    except:
        print("CTL error starting mp3 recording.  Exiting..")
        exit(-1)

    print(
        "CTL:",
        str(now.hour).zfill(2)
        + ":"
        + str(now.minute).zfill(2)
        + "Z started new .mp3 file: ",
        filename,
    )
    print(f"CTL: Disk free space: {get_free_space_mb(contest_dir) / 1024.0} GB")
    if get_free_space_mb(contest_dir) < 100:
        print("CTL: WARNING: Low Disk space")
    return mp3handle, filename


# write continious mp3 stream to disk in a separate worker thread
def writer():
    """start new lame recording"""
    now = datetime.datetime.utcnow()
    utchr = now.hour
    utcmin = now.minute
    (lame, filename) = start_new_lame_stream()
    start = time.perf_counter()
    bytes_written = 0
    while True:
        # open a new file on top of the hour
        now = datetime.datetime.utcnow()
        if utchr != now.hour:
            # sleep some to flush out buffers
            time.sleep(5)
            lame.terminate()
            utchr = now.hour
            (lame, filename) = start_new_lame_stream()
        if len(REPLAY_FRAMES) > 0:
            data = REPLAY_FRAMES.popleft()
            lame.stdin.write(data)
            bytes_written += sys.getsizeof(data)
        else:
            end = time.perf_counter()
            if end - start > 60000:
                elapsed = end - start
                sampling_rate = bytes_written / 4 / elapsed
                print(
                    bytes_written,
                    "bytes in ",
                    elapsed,
                    "ms. Sampling rate:",
                    sampling_rate,
                    "kHz",
                )
                start = end
                bytes_written = 0
            time.sleep(1)
        if utcmin != now.minute and now.minute % 10 == 0 and now.minute != 0:
            print(
                "CTL:",
                str(now.hour).zfill(2)
                + ":"
                + str(now.minute).zfill(2)
                + "Z ...recording:",
                filename,
            )
            contest_dir = "AUDIO_" + str(now.year)
            if get_free_space_mb(contest_dir) < 100:
                print("CTL: WARNING: Low Disk space")
            utcmin = now.minute


def main(argslist=None):
    """insert docstring"""
    # usage = "usage: %prog [OPTION]..."
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-D",
        "--debug",
        action="store_true",
        default=False,
        help="Save debug info[default=%(default)s]",
    )
    parser.add_argument(
        "-d",
        "--delay",
        type=int,
        default=20,
        help="Capture x seconds after QSO log entry [default=%(default)s]",
    )
    parser.add_argument(
        "-i",
        "--device-index",
        type=int,
        default=None,
        help="Index of the recording input (use -q to list) [default=%(default)s]",
    )
    parser.add_argument(
        "-k",
        "--hot-key",
        type=str,
        default="O",
        help="Hotkey for manual recording Ctrl-Alt-<hot_key> [default=%(default)s]",
    )
    parser.add_argument(
        "-l",
        "--buffer-length",
        type=int,
        default=45,
        help="Audio buffer length in secs [default=%(default)s]",
    )
    parser.add_argument(
        "-C",
        "--continuous",
        action="store_true",
        default=False,
        help="Record continuous audio stream in addition to individual QSOs[default=%(default)s]",
    )
    parser.add_argument(
        "-P", "--port", type=int, default=12060, help="UDP Port [default=%(default)s]"
    )
    parser.add_argument(
        "-p",
        "--path",
        type=str,
        default=None,
        help="Base directory for audio files [default=%(default)s]",
    )
    parser.add_argument(
        "-q",
        "--query-inputs",
        action="store_true",
        default=False,
        help="Query and print input devices [default=%(default)s]",
    )
    parser.add_argument(
        "-S",
        "--so2r",
        action="store_true",
        default=False,
        help="SO2R mode, downmix to mono: Left Ch - Radio1 QSOs, Right Ch - Radio2 QSOs [default=%("
        "default)s]",
    )
    parser.add_argument(
        "-s",
        "--station-nr",
        type=int,
        default=None,
        help="Network Station Number [default=%(default)s]",
    )
    parser.add_argument(
        "-r",
        "--radio-nr",
        type=int,
        default=None,
        help="Radio Number [default=%(default)s]",
    )
    parser.add_argument(
        "-R",
        "--sample-rate",
        type=int,
        default=11025,
        help="Audio sampling rate [default=%(default)s]",
    )

    # arglist can be passed from another python script or at the command line
    globals()["options"] = parser.parse_args(argslist)

    globals()["RATE"] = options.sample_rate
    dqlength = int(options.buffer_length * RATE / CHUNK) + 1
    DELAY = options.delay
    MY_PORT = options.port

    if options.path:
        os.chdir(options.path)

    if len(options.hot_key) == 1:
        globals()["HOTKEY"] = options.hot_key.upper()
    else:
        print("Hotkey should be a single character")
        parser.print_help()
        exit(-1)

    if options.debug:
        logging.basicConfig(
            filename=DEBUG_FILE, level=logging.DEBUG, format="%(asctime)s %(message)s"
        )
        logging.debug("debug log started")
        logging.debug("qsorder options:")
        logging.debug(options)

    # start hotkey monitoring thread
    # FIXME no hoykey
    if not NOPYHK:
        thread_timer = threading.Thread(target=hotkey)
        thread_timer.daemon = True
        thread_timer.start()

    print("-------------------------------------------------------")
    print("|\tv2.15 QSO Recorder for N1MM Logger+, 2020 K3IT\t")
    print("-------------------------------------------------------")

    # global p
    # p = pyaudio.PyAudio()
    devs = sd.query_devices()

    if options.query_inputs:
        print("\nDevice index Description")
        print("------------ -----------")
        # devs = sd.query_devices()

        for i in range(len(devs)):
            if devs[i]["max_input_channels"] > 0:
                try:
                    sd.check_input_settings(device=i, channels=CHANNELS, dtype=FORMAT)
                    print(
                        "\t",
                        i,
                        "\t",
                        devs[i]["name"],
                        " - ",
                        sd.query_hostapis(devs[i]["hostapi"])["name"],
                    )
                except:
                    pass
        exit(0)

    if options.device_index:
        try:
            def_index = sd.query_devices(device=options.device_index, kind="input")
            print("| Input Device :", def_index["name"])
            DEVINDEX = options.device_index
        except IOError as ioerror:
            print((f"Invalid Input device: {ioerror}"))
            os._exit(-1)

    else:
        try:
            def_index = sd.query_devices(device=sd.default.device, kind="input")
            print(
                "| Input Device :",
                def_index["name"],
                sd.query_hostapis(def_index["hostapi"])["name"],
            )
            DEVINDEX = sd.default.device
        except IOError as ioerror:
            print((f"No Input devices: {ioerror}"))
            os._exit(-1)

    # queue for chunked recording
    # global frames
    globals()["frames"] = deque("", dqlength)

    # queue for continous recording
    globals()["REPLAY_FRAMES"] = deque("", dqlength)

    print("| Listening on UDP port", MY_PORT)

    # define callback
    def callback(in_data, frame_count, time_info, status):
        frames.append(in_data)
        # add code for continous recording here
        REPLAY_FRAMES.append(in_data)
        # return None, pyaudio.paContinue

    stream = sd.RawInputStream(
        dtype=FORMAT,
        channels=CHANNELS,
        device=DEVINDEX,
        samplerate=RATE,
        blocksize=CHUNK,
        callback=callback,
    )

    # start the stream
    stream.start()

    sampwidth = stream.samplesize

    print(
        f"| {CHANNELS} ch x {dqlength * CHUNK / RATE} secs audio buffer\n| Delay: {DELAY} secs"
    )
    print("| Output directory", os.getcwd() + "/<contest...>")
    if NOPYHK:
        print("| Hotkey functionality is disabled")
    else:
        print("| Hotkey: CTRL+ALT+" + HOTKEY)
    if options.station_nr and options.station_nr >= 0:
        print("| Recording only station", options.station_nr, "QSOs")
    if options.continuous:
        print("| Full contest recording enabled.")
    print("-------------------------------------------------------\n")
    print("   QSOrder recordings can be shared with the World at:")
    print("\thttps://qsorder.hamradiomap.com\n")

    # start continious mp3 writer thread
    if options.continuous:
        mp3 = threading.Thread(
            target=writer,
            daemon=True,
        )
        mp3.start()

    # listen on UDP port
    # Receive UDP packets transmitted by a broadcasting service

    stream_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    stream_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    stream_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        stream_socket.bind(("", MY_PORT))
    except:
        print("Error connecting to the UDP stream.")

    seen = {}

    # this is needed to control loop exit from the unit tests
    def true_func():
        return True

    while stream.active and true_func:
        try:
            udp_data = stream_socket.recv(2048)
            check_sum = binascii.crc32(udp_data)
            try:
                dom = parseString(udp_data)
            except xml.parsers.expat.ExpatError:
                ...

            try:
                if "qsorder_exit_loop_DEADBEEF" in udp_data.decode():
                    print("Received magic Exit packet")
                    break
            except:
                ...

            if options.debug:
                logging.debug("UDP Packet Received:")
                logging.debug(udp_data)

            # skip packet if duplicate
            if check_sum in seen:
                seen[check_sum] += 1
                if options.debug:
                    logging.debug("DUPE packet skipped")
            else:
                seen[check_sum] = 1
                try:
                    now = datetime.datetime.utcnow()

                    # read UDP fields
                    dom = parseString(udp_data)
                    call = dom.getElementsByTagName("call")[0].firstChild.nodeValue
                    mycall = dom.getElementsByTagName("mycall")[0].firstChild.nodeValue
                    mode = dom.getElementsByTagName("mode")[0].firstChild.nodeValue
                    freq = dom.getElementsByTagName("band")[0].firstChild.nodeValue
                    contest = dom.getElementsByTagName("contestname")[
                        0
                    ].firstChild.nodeValue
                    station = dom.getElementsByTagName("NetworkedCompNr")[
                        0
                    ].firstChild.nodeValue
                    qso_timestamp = dom.getElementsByTagName("timestamp")[
                        0
                    ].firstChild.nodeValue
                    radio_nr = dom.getElementsByTagName("radionr")[
                        0
                    ].firstChild.nodeValue

                    # convert qso_timestamp to datetime object
                    timestamp = dateutil.parser.parse(qso_timestamp)

                    # verify that month matches, if not, give DD-MM-YY format precendense
                    if timestamp.strftime("%m") != now.strftime("%m"):
                        timestamp = dateutil.parser.parse(qso_timestamp, dayfirst=True)

                    # skip packet if not matching network station number specified in the command line
                    if options.station_nr and options.station_nr >= 0:
                        if options.station_nr != int(station):
                            print(
                                "QSO:",
                                timestamp.strftime("%m-%d %H:%M:%S"),
                                call,
                                freq,
                                "--- ignoring from stn",
                                station,
                            )
                            continue

                    # skip packet if not matching radio number specified in the command line
                    if options.radio_nr and options.radio_nr >= 0:
                        if options.radio_nr != int(radio_nr):
                            print(
                                "QSO:",
                                timestamp.strftime("%m-%d %H:%M:%S"),
                                call,
                                freq,
                                "--- ignoring from radio/VFO",
                                radio_nr,
                            )
                            continue

                    # skip packet if QSO was more than DELAY seconds ago
                    t_delta = (now - timestamp).total_seconds()
                    if t_delta > DELAY:
                        print(
                            "---:",
                            timestamp.strftime("%m-%d %H:%M:%S"),
                            call,
                            freq,
                            "--- ignoring ",
                            t_delta,
                            "sec old QSO. Check clock settings?",
                        )
                        continue
                    elif t_delta < -DELAY:
                        print(
                            "---:",
                            timestamp.strftime("%m-%d %H:%M:%S"),
                            call,
                            freq,
                            "--- ignoring ",
                            -t_delta,
                            "sec QSO in the 'future'. Check clock settings?",
                        )
                        continue

                    calls = call + "_de_" + mycall

                    thread_timer = threading.Timer(
                        DELAY,
                        dump_audio,
                        [calls, contest, mode, freq, timestamp, radio_nr, sampwidth],
                    )
                    print("QSO:", timestamp.strftime("%m-%d %H:%M:%S"), call, freq)
                    thread_timer.start()
                except:
                    if options.debug:
                        logging.debug("Could not parse previous packet")
                        logging.debug(sys.exc_info())

        except KeyboardInterrupt:
            print("73! K3IT")
            stream.stop()
            stream.close()
            sys.exit(0)

    stream.close()
    sys.exit(0)


if __name__ == "__main__":
    main()
