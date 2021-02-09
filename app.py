import kivy   
from kivy.app import App 
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout 
from kivy.uix.textinput import TextInput
from kivy.config import Config
from client import Client
from functools import partial
from pprint import pprint
import sounddevice as sd
import threading
import time
import json

Config.set('graphics', 'width', '800')
Config.set('graphics', 'height', '800')
Config.set('graphics', 'resizable', True)
Config.write()

class MyApp(App):

    def _on_name_enter(self, instance, value):
        self._client.change_name(value)

    def _change_room(self, room, instance):
        if instance.state == 'down':
            success = self._client.change_room(room)
            if not success:
                instance.state = 'normal'
        else:
            self._client.drop_room()

    def _talk_switch_change(self, instance):
        if instance.state == 'down':
            self._client.set_talking_mode()
        else:
            self._client.turn_down_talking_mode()

    def _handle_audio(self):
        with sd.Stream(samplerate = 44100, blocksize = 11360, channels = 1,
                                         callback = self._client.callback):
            while not self._client.closed:
                time.sleep(0.5)

    def _pull_other_users(self):
        self._client.pull_other_users()
        user_data = self._client._other_users
        self.room_1_users.text = user_data['room_0']
        self.room_2_users.text = user_data['room_1']
        self.room_3_users.text = user_data['room_2']
        threading.Timer(0.5, self._pull_other_users).start()
    
    def _exit_app(self, instance):
        self.stop()
  
    def build(self): 
        self._client = Client(rate = 44100, channels = 1, chunk_size = 1160)
        threading.Thread(target = self._handle_audio).start()
    
        Fl = FloatLayout() 

        btn_1 = ToggleButton(text = 'Select room 1', size_hint = (.25, .2), 
                     background_color =(.3, .6, .7, 1), 
                     pos_hint = {'x':.05, 'y':.4 },
                     group ='rooms')

        btn_2 = ToggleButton(text ='Select room 2', size_hint = (.25, .2), 
                     background_color =(.3, .6, .7, 1), 
                     pos_hint = {'x':.375, 'y':.4 },
                     group ='rooms') 

        btn_3 = ToggleButton(text = 'Select room 3', size_hint = (.25, .2), 
                     background_color =(.3, .6, .7, 1), 
                     pos_hint = {'x':.7, 'y':.4 },
                     group ='rooms')

        btn_1.bind(on_press = partial(self._change_room, 1))
        btn_2.bind(on_press = partial(self._change_room, 2))
        btn_3.bind(on_press = partial(self._change_room, 3))

        talk_btn = ToggleButton(text = 'Talk', size_hint = (.25, .1), 
                                    background_color =(.3, .6, .7, 1), 
                                    pos_hint = {'x':.375, 'y':.7 },
                                    group ='talk')
        talk_btn.bind(on_press = self._talk_switch_change)

        exit_btn = Button(text = 'Exit', size_hint = (.25, .1), 
                        background_color =(.3, .6, .7, 1), 
                        pos_hint = {'x':.7, 'y':.7 })
        exit_btn.bind(on_press = self._exit_app)

        textinput = TextInput(text = 'Guest', multiline = False,
                              size_hint = (.25, .06),
                              pos_hint = {'x':.05, 'y':.72 },
                              font_size = 32)
        textinput.bind(text = self._on_name_enter)

        self.room_1_users = TextInput(text = '', multiline = True,
                              size_hint = (.25, .25),
                              pos_hint = {'x':.05, 'y':.1 },
                              font_size = 18, disabled = True
                              )

        self.room_2_users = TextInput(text = '', multiline = True,
                              size_hint = (.25, .25),
                              pos_hint = {'x':.375, 'y':.1 },
                              font_size = 18, disabled = True
                              )

        self.room_3_users = TextInput(text = '', multiline = True,
                              size_hint = (.25, .25),
                              pos_hint = {'x':.7, 'y':.1 },
                              font_size = 18, disabled = True
                              )

        threading.Thread(target = self._pull_other_users).start()

        Fl.add_widget(btn_1)
        Fl.add_widget(btn_2)
        Fl.add_widget(btn_3)
        Fl.add_widget(textinput)
        Fl.add_widget(talk_btn)
        Fl.add_widget(exit_btn)
        Fl.add_widget(self.room_1_users)
        Fl.add_widget(self.room_2_users)
        Fl.add_widget(self.room_3_users)
        return Fl 

    def shutdown(self):
        self._client.shutdown()

if __name__ == "__main__": 
    root = MyApp()
    root.run()
    root.shutdown()
    