#!/usr/bin/python3
# -*- coding: utf-8 -*-
#-------------------------------------------------------------
# balance.py : 
#   - lecture et affichage des mesures d'une balance Adam Highland Series
#   - enregistrement dans un fichier pour import sur un tableur
#
#     v1.0 : Version initiale
#   
#      Olivier boesch(c)2019
#-------------------------------------------------------------

#------------ modules
#-- serial ports comm and enumeration
import serial
import serial.tools.list_ports
#-- kivy config
from kivy.config import Config
Config.set('kivy','desktop',1) #desktop app (not mobile)
# Config.set('graphics','window_state','maximized')
# Config.set('graphics','fullscreen','auto')
Config.set('input','mouse','mouse,disable_multitouch') #disable multitouch
#-- kivy
import kivy
kivy.require('1.10.1')
from kivy.app import App
from kivy.uix.popup import Popup
from kivy.clock import Clock
#--time utilities
import time
import datetime

#----------- parameters
__read_interval__ = 0.1 #s - time between two reads
__save_interval__ = 1.0 #s - time between two saves on file
# serial port configuration : 9600bds - 8N1
__device_speed__ = 9600
__device_bits__ = serial.EIGHTBITS
__device_parity__ = serial.PARITY_NONE
__device_stop_bits__ = serial.STOPBITS_ONE

#--------------- message popup window class
class PopupMessage(Popup):
  """PopupMessage : display a message box"""

  def set_message(self,title,text):
    """ set_message : set title and message for the window"""
    self.title = title
    self.ids['message_content_lbl'].text = text

  def get_message(self):
    """get_message: get title and text as a tuple"""
    return (self.title,self.ids['message_content_lbl'].text)
    
  def close_after(self,waitfor = 1.):
    """close popup automaticaly after a short time (default : 1s)"""
    Clock.schedule_once(lambda dt: self.dismiss(),waitfor)
    
#---------------- App class
class BalanceApp(App):
  """ Application class """
  serialconn = None # serial connection object
  val = 0.0 # value as a float (for saving in data file
  save_started = False # True if saving in a file
  start_time = 0 # unix timespamp - when saving as started (to calculate elapsed time)
  data_file = None # file object
  save_event = None # kivy event called each time data should be saved
  read_event = None # kivy event called each time data should be read from the device
  update_ports_list_event = None # kivy event called each time serial ports list should be refreshed
  
  def build(self):
    # update ports_list values now and schedule for every 5s
    self.update_ports_list()
    self.update_ports_list_event = Clock.schedule_interval(lambda dt: self.update_ports_list(),5.)
    # bindings
    self.root.ids['quit_btn'].bind(on_press=self.on_quit_btn_press)  
    self.root.ids['connect_btn'].bind(on_press=self.on_connect_btn_press)
    self.root.ids['ports_list'].bind(text=self.on_ports_list_text)
    self.root.ids['start_stop_btn'].bind(on_press=self.on_start_stop_btn_press)
    
  def on_ports_list_text(self,spin,val):
    """ on_ports_list_text : user selected a serial port from the spinner """
    self.port = spin.text
    
  def update_ports_list(self):
    """ update_ports_list : get available serial ports and set ports_list spinner values"""
    # get an iterator with available serial ports
    comportslist=serial.tools.list_ports.comports()
    # make a tuple and set spinner values
    self.root.ids['ports_list'].values = tuple([item.device for item in comportslist])
    # if current value is not in list then go back to default
    if self.root.ids['ports_list'].text not in self.root.ids['ports_list'].values:
      self.root.ids['ports_list'].text = 'Port S\u00e9rie'
      self.port = None
    # if no available serial port then tell the user
    if len(self.root.ids['ports_list'].values) == 0:
      self.root.ids['ports_list'].text = 'Pas de port S\u00e9rie'
      self.port = None
    # if only one port available select it by default
    if len(self.root.ids['ports_list'].values) == 1:
      self.root.ids['ports_list'].text = self.root.ids['ports_list'].values[0]
      self.port = self.root.ids['ports_list'].values[0]
      
  def on_quit_btn_press(self,btn):
    """ on_quit_btn_press : stop the app when user press quit button """
    self.stop()
    
  def on_stop(self):
    """ on_stop : what to do when app is about to stop """
    #if serial port opened -> try to close it
    if self.serialconn is not None:
      try:
        self.serialconn.close()
        del self.serialconn
      except:
        pass
        
  def on_start_stop_btn_press(self,btn):
    """ on_start_stop_btn_press : what to do when user press start or stop saving button """
    #if saving not started then start it
    if not self.save_started :
      #tell saving is started
      self.save_started = True
      #remember the time it has started
      self.start_time = time.time()
      #open file to save data
      self.data_file = open("data.txt",'w')
      #write file header (start time, column meaning)
      self.data_file.write(f"# debut : {datetime.datetime.now()}\n")
      self.data_file.write("# temps (s); masse (g)\n")
      #schedule saving data
      self.save_event  = Clock.schedule_interval(lambda dt: self.save_data(),__save_interval__)
      #update button text
      self.root.ids['start_stop_btn'].text = 'Arr\u00eat Enr.'
      #display a message box to tell it's ok
      p = PopupMessage()
      p.open()
      p.set_message("Enregistrement","D\u00e9marrage de la sauvegarde")
      p.close_after(1.)
    #if saving started then stop it
    else:
      #tell saving is stopped
      self.save_started = False
      #stop saving data scheduling
      self.save_event.cancel()
      #close data file
      self.data_file.close()
      #update button text
      self.root.ids['start_stop_btn'].text = 'Enregistrer'
      #display a message box to tell it's ok
      p = PopupMessage()
      p.open()
      p.set_message("Enregistrement","Arr\u00eat de la sauvegarde")
      p.close_after(1.)

  def save_data(self):
    """save_data : save a line of data in the data file"""
    #format the line
    line = f"{time.time()-self.start_time:.2f};{self.val:.2f}\n".replace('.',',')
    #write it
    self.data_file.write(line)
    
  def on_connect_btn_press(self,btn):
    """ on_connect_btn_press : what to do when user press connect button """
    # if port is None (if no port selected or present) then dont connect
    if self.port is None:
      # tell user we cant connect and return
      p = PopupMessage()
      p.open()
      p.set_message("Erreur","Choisir un port de connexion")
      p.close_after(3.)
      return
    #if there a port already opened then try to close
    if self.serialconn is not None:
      #try to close port
      try:
        self.serialconn.close()
        del self.serialconn
      except:
        pass
      #set ui state as disconnected
      self.set_as_disconnected()
      self.serialconn = None
    #a port is not opened then open it
    else:
      # try to connect and catch any exception
      try:
        # config: 
        # serial port : 9600bauds, 8N1 (as configured on device)
        # timeout 90% of read interval
        self.serialconn = serial.Serial(self.port,
                                        baudrate = __device_speed__,
                                        bytesize=__device_bits__,
                                        parity=__device_parity__,
                                        stopbits=__device_stop_bits__,
                                        timeout=__read_interval__*0.9)
        #set ui state as connected
        self.set_as_connected()
        #tell user it's ok
        p = PopupMessage()
        p.open()
        p.set_message("Balance","Connexion Ok")
        p.close_after(1.)
      #if connection failed
      except:
        #tell user we cant connect
        p = PopupMessage()
        p.open()
        p.set_message("Erreur","Connexion impossible")
        p.close_after(3.)
    
  def set_as_connected(self):
    """ set_as_connected : set ui state in connected state """
    #stop serial ports list update
    self.update_ports_list_event.cancel()
    #start schedule reading from device
    self.read_event  = Clock.schedule_interval(lambda dt: self.read_data(),__read_interval__)
    #update connect button text
    self.root.ids['connect_btn'].text = 'D\u00e9connecter'
    #update label text
    self.root.ids['display_lbl'].text = "Attente donn\u00e9es"
    #enable saving button
    self.root.ids['start_stop_btn'].disabled = False
    
  def set_as_disconnected(self):
    """ set_as_disconnected : set ui state in disconnected state"""
    #stop reading from device
    self.read_event.cancel()
    #start schedule serial ports list update
    self.update_ports_list_event = Clock.schedule_interval(lambda dt: self.update_ports_list(),5.)
    #update connect button text
    self.root.ids['connect_btn'].text = 'Connecter'
    #update label text
    self.root.ids['display_lbl'].text = "Non Connect\u00e9"
    #disable saving
    self.root.ids['start_stop_btn'].disabled = True
      
  def read_data(self):
    """ read_data : read data from device """
    #if a port is opened we can read
    if self.serialconn is not None:
      #try read a line
      try:
        s = self.serialconn.readline()
      #failed then we disconnect the port
      except:
        self.set_as_disconnected()
        del self.serialconn
        self.serialconn = None
        return
      #if no timeout happened (empty string), display result and store value for saving on file
      if len(s)!= 0:
        # output "format 2" : as configured on device -> "± _ _ _ _ _ _ 1 2 3 . 4 5 _ g _ <cr> <lf>"
        s = s[:-2].decode() #remove cr et lf at the end of string
        s = s[0] + s[1:].lstrip() #remove spaces on left of number but keep the sign
        self.val = float(s[:-3]) #remove unit and store internally as a float
        self.root.ids['display_lbl'].text = s #update display
        self.root.ids['led_in'].state = 'on'  # show com led as receiving
      
#create app object
wapp = BalanceApp()
#run it
wapp.run()