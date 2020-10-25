#!/usr/bin/python3
# -*- coding: utf-8 -*-
# -------------------------------------------------------------
# main.py :
#   - lecture et affichage des mesures d'une balance Adam Highland Series
#   - enregistrement dans un fichier pour import sur un tableur
#
#     v1.0 : Version initiale
#   
#      Olivier boesch(c)2019
# -------------------------------------------------------------

__version__ = '0.8'

# log level
# import os
# os.environ["KCFG_KIVY_LOG_LEVEL"] = "trace"

# data orange in the data directory
from kivy.resources import resource_add_path
resource_add_path("/home/olivier/PycharmProjects/balance/src/")

from kivy.utils import platform

# ------------ modules
if platform in ['windows', 'linux']:
    import serial
    from serial.tools import list_ports
    from serial.serialutil import SerialException
    # -- kivy config
    from kivy.config import Config
    Config.set('kivy', 'desktop', 1)  # desktop app (not mobile)
    # Config.set('graphics','window_state','maximized')
    # Config.set('graphics','fullscreen','auto')
    Config.set('input', 'mouse', 'mouse,disable_multitouch')  # disable multi touch

    def get_serial_ports_list():
        ports = list_ports.comports()
        return [item.device for item in ports]

elif platform == 'android':
    from usb4a import usb

    def get_serial_ports_list():
        usb_device_list = usb.get_usb_device_list()
        return [device.getDeviceName() for device in usb_device_list]

from kivy.app import App
from kivy.uix.popup import Popup
from kivy.clock import Clock
from kivy.logger import Logger
# --time utilities
import time
import datetime

# ----------- parameters
__read_interval__ = 0.1  # s - time between two reads
__save_interval__ = 1.0  # s - time between two saves on file
# serial port configuration : 9600bds - 8N1
__device_speed__ = 9600
__device_bits__ = 8
__device_parity__ = 'N'
__device_stop_bits__ = 1


# --------------- message popup window class
class PopupMessage(Popup):
    """PopupMessage : display a message box"""

    def set_message(self, title, text):
        """ set_message : set title and message for the window"""
        self.title = title
        self.ids['message_content_lbl'].text = text

    def get_message(self):
        """get_message: get title and text as a tuple"""
        return (self.title, self.ids['message_content_lbl'].text)

    def close_after(self, waitfor=1.):
        """close popup automaticaly after a short time (default : 1s)"""
        Clock.schedule_once(lambda dt: self.dismiss(), waitfor)


# ---------------- App class
class BalanceApp(App):
    """ Application class """
    serialconn = None  # serial connection object
    val = 0.0  # value as a float (for saving in data file)
    save_started = False  # True if saving in a file
    start_time = 0  # unix timespamp - when saving as started (to calculate elapsed time)
    data_file = None  # file object
    save_event = None  # kivy event called each time data should be saved
    read_event = None  # kivy event called each time data should be read from the device
    update_ports_list_event = None  # kivy event called each time serial ports list should be refreshed

    def build(self):
        # update ports_list values now and schedule for every 5s
        self.update_ports_list()
        self.update_ports_list_event = Clock.schedule_interval(lambda dt: self.update_ports_list(), 5.)

    def on_ports_list_text(self, spin, val):
        """ on_ports_list_text : user selected a serial port from the spinner """
        self.port = spin.text

    def update_ports_list(self):
        """ update_ports_list : get available serial ports and set ports_list spinner values"""
        # make a tuple and set spinner values
        ports_found = tuple(get_serial_ports_list())
        self.root.ids['ports_list'].values = ports_found
        Logger.info("Serial: {:d} ports found ({:s})".format(len(ports_found),str(ports_found)))
        # if current value is not in list then go back to default
        if self.root.ids['ports_list'].text not in self.root.ids['ports_list'].values:
            self.root.ids['ports_list'].text = 'Port Série'
            self.port = None
        # if no available serial port then tell the user
        if len(self.root.ids['ports_list'].values) == 0:
            self.root.ids['ports_list'].text = 'Pas de port Série'
            self.port = None
        # if only one port available select it by default
        if len(self.root.ids['ports_list'].values) == 1:
            self.root.ids['ports_list'].text = self.root.ids['ports_list'].values[0]
            self.port = self.root.ids['ports_list'].values[0]

    def on_stop(self):
        """ on_stop : what to do when app is about to stop """
        # if serial port opened -> try to close it
        if self.serialconn is not None:
            try:
                self.serialconn.close()
                del self.serialconn
            except:
                pass

    def on_start_stop_btn_press(self):
        """ on_start_stop_btn_press : what to do when user press start or stop saving button """
        # if saving not started then start it
        if not self.save_started:
            # tell saving is started
            self.save_started = True
            # remember the time it has started
            self.start_time = time.time()
            # open file to save data
            self.data_file = open("data.txt", 'w')
            # write file header (start time, column meaning)
            self.data_file.write(f"# debut : {datetime.datetime.now()}\n")
            self.data_file.write("# temps (s); masse (g)\n")
            # schedule saving data
            self.save_event = Clock.schedule_interval(lambda dt: self.save_data(), __save_interval__)
            # update button text
            self.root.ids['start_stop_btn'].text = 'Arr\u00eat Enr.'
            # display a message box to tell it's ok
            p = PopupMessage()
            p.open()
            p.set_message("Enregistrement", "D\u00e9marrage de la sauvegarde")
            p.close_after(1.)
            Logger.info("Recording: Start recording values")
        # if saving started then stop it
        else:
            # tell saving is stopped
            self.save_started = False
            # stop saving data scheduling
            self.save_event.cancel()
            # close data file
            self.data_file.close()
            # update button text
            self.root.ids['start_stop_btn'].text = 'Enregistrer'
            # display a message box to tell it's ok
            p = PopupMessage()
            p.open()
            p.set_message("Enregistrement", "Arrêt de la sauvegarde")
            p.close_after(1.)
            Logger.info("Recording: Stop recording values")

    def save_data(self):
        """save_data : save a line of data in the data file"""
        # format the line
        line = f"{time.time() - self.start_time:.2f};{self.val:.2f}\n".replace('.', ',')
        # write it
        self.data_file.write(line)
        Logger.info("Recording: Saving data {:s}".format(line))

    def on_connect_btn_press(self):
        """ on_connect_btn_press : what to do when user press connect button """
        # if port is None (if no port selected or present) then dont connect
        Logger.info("Serial: trying to connect")
        if self.port is None:
            # tell user we cant connect and return
            p = PopupMessage()
            p.open()
            p.set_message("Erreur", "Choisir un port de connexion")
            p.close_after(3.)
            Logger.warning("Serial: no serial port to connect to")
            return
        # if there a port already opened then try to close
        if self.serialconn is not None:
            # try to close port
            Logger.info("Serial: trying to close port first")
            try:
                self.serialconn.close()
                del self.serialconn
            except:
                Logger.info("Serial: failed to close port")
            # set ui state as disconnected
            self.set_as_disconnected()
            self.serialconn = None
        # a port that is not opened then open it
        else:
            # try to connect and catch any exception
            try:
                # config:
                # serial port : 9600bauds, 8N1 (as configured on device)
                # timeout 90% of read interval
                Logger.info("Serial: connecting to {:s}".format(self.port))
                self.serialconn = serial.Serial(self.port,
                                                baudrate=__device_speed__,
                                                bytesize=__device_bits__,
                                                parity=__device_parity__,
                                                stopbits=__device_stop_bits__,
                                                timeout=__read_interval__ * 0.9)
                # set ui state as connected
                self.set_as_connected()
                Logger.info("Serial: Connected.")
                # tell user it's ok
                p = PopupMessage()
                p.open()
                p.set_message("Balance", "Connexion Ok")
                p.close_after(1.)
            # if connection failed
            except SerialException as e:
                Logger.error("Serial: failed to connect ({:s})".format(e.strerror))
                # tell user we cant connect
                p = PopupMessage()
                p.open()
                p.set_message("Erreur", "Connexion impossible \n(Erreur n°" + str(e.errno) + ")")
                p.close_after(3.)

    def set_as_connected(self):
        """ set_as_connected : set ui state in connected state """
        # stop serial ports list update
        self.update_ports_list_event.cancel()
        # start schedule reading from device
        self.read_event = Clock.schedule_interval(lambda dt: self.read_data(), __read_interval__)
        # update connect button text
        self.root.ids['connect_btn'].text = 'Déconnecter'
        # update label text
        self.root.ids['display_lbl'].text = "Attente données"
        # enable saving button
        self.root.ids['start_stop_btn'].disabled = False

    def set_as_disconnected(self):
        """ set_as_disconnected : set ui state in disconnected state"""
        # stop reading from device
        self.read_event.cancel()
        # start schedule serial ports list update
        self.update_ports_list_event = Clock.schedule_interval(lambda dt: self.update_ports_list(), 5.)
        # update connect button text
        self.root.ids['connect_btn'].text = 'Connecter'
        # update label text
        self.root.ids['display_lbl'].text = "Non Connecté"
        # disable saving
        self.root.ids['start_stop_btn'].disabled = True

    def read_data(self):
        """ read_data : read data from device """
        # if a port is opened we can read
        Logger.info("Serial: trying to read data from port")
        if self.serialconn is not None:
            # try read a line
            try:
                s = self.serialconn.readline()
            # failed then we disconnect the port
            except:
                Logger.warning("Serial: can't read data (mark as disconnected)")
                self.set_as_disconnected()
                del self.serialconn
                self.serialconn = None
                return
            # if no timeout happened (empty string), display result and store value for saving on file
            if len(s) != 0:
                # output "format 2" : as configured on device -> "± _ _ _ _ _ _ 1 2 3 . 4 5 _ g _ <cr> <lf>"
                s = s[:-2].decode()  # remove cr et lf at the end of string
                s = s[0] + s[1:].lstrip()  # remove spaces on left of number but keep the sign
                self.val = float(s[:-3])  # remove unit and store internally as a float
                self.root.ids['display_lbl'].text = s  # update display
                self.root.ids['led_in'].state = 'on'  # show com led as receiving
                Logger.info("Serial: data read from port (raw: {:s}, float: {:f}g)".format(s,self.val))
            else:
                Logger.info("Serial: No data read (timeout)")


# create app object
wapp = BalanceApp()
# run it
wapp.run()
