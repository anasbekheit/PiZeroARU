import pyaudio
import wave
import time
import datetime
import os

def init_pyaudio():

	p = pyaudio.PyAudio()
	print ('------------------------------')
	return p


def determine_USB_index(p):
	index_to_use = -1

	for ii in range(p.get_device_count()):
		if 'USB Audio Device' in str(p.get_device_info_by_index(ii).get('name')):
			index_to_use = ii
			break
	return index_to_use

def create_folder_structure_and_save_text_file(FORMAT, CHANNELS, RATE, frames, p):

	# Get the current date and time
	now = datetime.datetime.now()

	# Create a folder for the current day
	day_folder = os.path.join("Recordings",now.strftime("%Y-%m-%d"))
	if not os.path.exists(day_folder):
		os.makedirs(day_folder)

	# Create a folder for the current hour inside the day folder
	hour_folder = os.path.join(day_folder, now.strftime("%H"))
	if not os.path.exists(hour_folder):
		os.makedirs(hour_folder)

	# Generate a filename based on the current minute and second
	print('writing to file')
	wavefile = wave.open(os.path.join(hour_folder, timestamp()+'.wav'),'wb')
	print('location', wavefile)
	wavefile.setnchannels(CHANNELS)
	wavefile.setsampwidth(p.get_sample_size(FORMAT))
	wavefile.setframerate(RATE)
	wavefile.writeframes(b''.join(frames))
	wavefile.close()
	print('writing close')

def record_audio(p, FORMAT, CHANNELS, RATE, chunk, record_secs, dev_index):
	stream = p.open(format = FORMAT,
		channels = CHANNELS,
		rate = RATE,
		input = True,
		frames_per_buffer = chunk,
		input_device_index = dev_index)

	print("recording")
	frames = []

	# loop through stream and append audio chunks to frame array
	for ii in range(0,int((RATE/chunk)*record_secs)):
		data = stream.read(chunk)
		frames.append(data)

	print("finished recording")

	# stop the stream, close it, and terminate the pyaudio instantiation
	stream.stop_stream()
	stream.close()
	p.terminate()
	create_folder_structure_and_save_text_file(FORMAT, CHANNELS, RATE, frames, p)
	print('done saving')
	
def timestamp():

	currentDT = datetime.datetime.now()
	 
	print ("Current Year is: %d" % currentDT.year)
	print ("Current Month is: %d" % currentDT.month)
	print ("Current Day is: %d" % currentDT.day)
	print ("Current Hour is: %d" % currentDT.hour)
	print ("Current Minute is: %d" % currentDT.minute)
	print ("Current Second is: %d" % currentDT.second)

	return '{}-{}-{}={}:{}:{}'.format(currentDT.day, currentDT.month, currentDT.year, currentDT.hour, currentDT.minute, currentDT.second)

def execute_rec():
	try:
		FORMAT= pyaudio.paInt16 # 16-bit resolution
		CHANNELS = 1 # 1 channel
		RATE = 44100 # 44.1kHz sampling rate
		chunk = 4096 # 2^12 samples for buffer
		record_secs = 30 # seconds to record
		p =  init_pyaudio()
		dev_index = determine_USB_index(p)
		record_audio(p, FORMAT, CHANNELS, RATE, chunk, record_secs, dev_index)
		return True
	except:
		return False

print('Begin')
tries = 1200

for i in range (0, tries):
	print ('Iteration:', i)
	execute_rec()
	time.sleep(5)
