import mysql.connector

from time import sleep

from SX127x.LoRa import *

from SX127x.board_config import BOARD

from collections import deque

import os

import glob

from tensorflow.keras.models import model_from_json

from tensorflow.keras.preprocessing import image

import numpy as np

 

BOARD.setup()

 

conn = mysql.connector.connect(host="localhost",

                               port="3306",

                               user="admin",

                               passwd="reemiscool",

                               database="server")

          

mycursor = conn.cursor()

 

sql = "DROP TABLE Entries"

mycursor.execute(sql)

 

mycursor.execute("CREATE TABLE Entries (Entry int PRIMARY KEY, Robot_ID VARCHAR(10), x VARCHAR(10), y VARCHAR(10), Crack VARCHAR(100), IMAGE LONGBLOB)")

 

# <l x y id>

queue = deque()

info_list = []

cnn_result = '' #for testing, this needs to be returned by the CNN algorithm

count = 0

 

#loading the cnn algo

# load json and create model

json_file = open('model.json', 'r')

loaded_model_json = json_file.read()

json_file.close()

loaded_model = model_from_json(loaded_model_json)

# load weights into new model

loaded_model.load_weights("model.h5")

# print("Loaded model from disk")

 

def cnn(img_path):

 

    # convert image to np array of shape (1,224,224,3)

    img = image.load_img(img_path, target_size=(224, 224))

    img_array = image.img_to_array(img)

    img_array = np.expand_dims(img_array, axis=0)

    # normalize

    img_array = img_array/255.0

 

    # use the model to predict, then get index of prediction with the maximum value

    prediction = np.argmax(loaded_model.predict(img_array))

    # convert index to string

    #(deep, shallow, clear)

    classes = {0: 'clear',

              1: 'deep',

            2: 'shallow'}

    result = classes[prediction]

    return result

 

def analyse(pay_decoded):

  while (len(queue) != 0):

    #print("Queue before popping: ", queue)

    global count

    count+=1

    mypath = '/var/www/html/uploads/*'

    #gets the oldest image in the file

    img = min(glob.glob(mypath), key=os.path.getmtime)

   

    with open(img, 'rb') as file:

        image_data = file.read()

 

   

    #pop the oldest entry in the queue

    current = queue.popleft()

    #print("Queue after popping: ", queue)

    #extract info

    l = pay_decoded.split(" ")

    print(l)

    x = l[2]

    y = l[3]

    rid = l[4]

 

    #send image for analysis

    #cnn returns string of severity or unsuccessful

    cnn_result = cnn(img)

 

    if (cnn_result == 'Clear' or cnn_result == 'clear'):

      #feedback = '< f ' + rid + ' 1 >'

      #send feedback to robot

      change_dir = "/var/www/html/no crack/" + str(count) + ".jpg"

      os.replace(img, change_dir)

      #print(change_dir)

    else:

        mycursor.execute("INSERT INTO Entries (Enrty, Robot_ID, x, y, Crack, IMAGE) VALUES (%s, %s, %s, %s, %s, %s)", (count, rid, x, y, cnn_result, image_data))

        conn.commit()

        #send back < f rid 0 > for robot to continue moving

        #send feedback to robot

        info_list.append(current)

        #print("Info list containing locations: ", info_list)

        change_dir = "/var/www/html/crack/" + str(count) + ".jpg"

        os.replace(img, change_dir)

        mycursor.close()

        conn.close()

 

   

    

 

class LoRaRcvCont(LoRa):

   

    #initialize the LoRa module

    def __init__(self, verbose=False):

        print("Initialized")

        super(LoRaRcvCont, self).__init__(verbose)

        self.set_mode(MODE.SLEEP)

       

    #configure the module as receiver and start receiving values

    def start(self):

        print("Ready to receive data")

        self.reset_ptr_rx()

        self.set_mode(MODE.RXCONT)

        while True:

            print("Listening for data")

            sleep(.5)

            rssi_value = self.get_rssi_value()

            status = self.get_modem_status()

            sys.stdout.flush()

           

    #executes after an incoming packet is read

    def on_rx_done(self):

        print("\nReceived: ")

        self.clear_irq_flags(RxDone=1)

        payload = self.read_payload(nocheck=True)

        #print(bytes(payload).decode("utf-8",'ignore'))

        global pay_decoded

        pay_decoded = bytes(payload).decode("utf-8",'ignore')

        if ((not(len(pay_decoded) == 0))):

            print(pay_decoded)

            queue.append(pay_decoded)

            analyse(pay_decoded)

        self.set_mode(MODE.SLEEP)

        self.reset_ptr_rx()

        self.set_mode(MODE.RXCONT)

 

 

lora = LoRaRcvCont(verbose=False)

lora.set_mode(MODE.STDBY)

 

#  Medium Range  Defaults after init are 434.0MHz, Bw = 125 kHz, Cr = 4/5, Sf = 128chips/symbol, CRC on 13 dBm

 

lora.set_pa_config(pa_select=1)

 

try:

    lora.start()

    print("starting lora")

except KeyboardInterrupt:

    sys.stdout.flush()

    print("")

    sys.stderr.write("KeyboardInterrupt\n")

finally:

    sys.stdout.flush()

    print("")

    lora.set_mode(MODE.SLEEP)

    BOARD.teardown()
