import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import AutoMinorLocator, FixedLocator
import pprint

import datetime
from matplotlib.widgets import Button, TextBox
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
import certifi

#%matplotlib auto

class BGInteractor:
    epsilon = 20  # max pixel distance to count as a vertex hit
    y_offset = 4 # display distance from BG for carbs and insulin (should use display coords instead)
    td = float(360) # duration
    tp = float(75) # activity peak
    date = '2023-09-01'
    time = '07:00'
    timespan_minutes = 60*6 # minutes, although user input is hours
    timespanmax_minutes = 60*48
    utcoffset = -6 # mdt is -6
    isf = 176
    addbolus = 0.2  
    accumulated_insulin = 0.0  # total of insulin accumulated with 'a'
    
    def __init__(self,uri,minBolus_to_load):
        self.minBolus_to_load = minBolus_to_load  
        self.uri = uri
        
        self.fig, self.ax = plt.subplots(figsize=(9,6))
        self.fig.subplots_adjust(bottom=0.2)        
        # self.ax.set_ylim(55,220)
        self.ax.grid(True)
        self.ax.set_xlabel('Time (minutes)')
        self.ax.set_ylabel('BG (mg/dL)')
        self.ax.set_title('Load Data to Get Started')        

        self.axisf_txt_box = self.fig.add_axes([0.16, 0.02, 0.06, 0.04])
        self.isf_text_box = TextBox(self.axisf_txt_box, 'ISF (mg/dL/U) ', textalignment="left")
        self.isf_text_box.on_submit(self.validate_isf_textbox_string)
        self.isf_text_box.set_val(str(self.isf))
        
        self.axtimespan_txt_box = self.fig.add_axes([0.54, 0.07, 0.08, 0.04])
        self.timespan_text_box = TextBox(self.axtimespan_txt_box, 'Span (hr) ', textalignment="left")
        self.timespan_text_box.on_submit(self.validate_timespan_textbox_string)
        self.timespan_text_box.set_val(str(self.timespan_minutes/60))
        
        self.axdate_txt_box = self.fig.add_axes([0.16, 0.07, 0.11, 0.04])
        self.date_text_box = TextBox(self.axdate_txt_box, 'YYYY-MM-DD ', textalignment="left")
        self.date_text_box.on_submit(self.validate_date_textbox_string)
        self.date_text_box.set_val(str(self.date))

        self.axtime_txt_box = self.fig.add_axes([0.36, 0.07, 0.08, 0.04])
        self.time_text_box = TextBox(self.axtime_txt_box, 'HH:mm ', textalignment="left")
        self.time_text_box.on_submit(self.validate_time_textbox_string)
        self.time_text_box.set_val(str(self.time))

        self.axutcoffset_txt_box = self.fig.add_axes([0.36, 0.02, 0.08, 0.04])
        self.utcoffset_text_box = TextBox(self.axutcoffset_txt_box, 'UTC Offset (hr) ', textalignment="left")
        self.utcoffset_text_box.on_submit(self.validate_utcoffset_textbox_string)
        self.utcoffset_text_box.set_val(str(self.utcoffset))
        
        self.axload = self.fig.add_axes([0.54, 0.02, 0.08, 0.04])   # rect : tuple (left, bottom, width, height)
        self.bload = Button(self.axload, "Load!")
        self.bload.on_clicked(self.load)

        self.axbolus_txt_box = self.fig.add_axes([0.861, 0.07, 0.08, 0.04])
        self.bolus_text_box = TextBox(self.axbolus_txt_box, 'Bolus to  \nInsert (U) ', textalignment="left")
        self.bolus_text_box.on_submit(self.validate_bolus_textbox_string)
        self.bolus_text_box.set_val(str(self.addbolus))                        
        
        self._ind = None
        self.canvas = self.fig.canvas
        
        self.load() # Load with defaults       
        
    def connect_to_mongodb(self):
        # Create a new client and connect to the server
        try:
            ca = certifi.where()
            self.client = MongoClient(self.uri, server_api=ServerApi('1'),tlsCAFile=ca)
        except:
            self.client = MongoClient(self.uri, server_api=ServerApi('1'))
        
        # Send a ping to confirm a successful connection
        try:
            self.client.admin.command('ping')
            print("Successful connection to MongoDB!")
        except Exception as e:
            print(e)
    
    def get_data_from_mongodb(self):

        db = self.client.test
        entries_col = db.entries
        treatments_col = db.treatments
        
        timeStart = datetime.datetime.fromisoformat(self.date + 'T' + self.time) - datetime.timedelta(hours=(self.utcoffset))        
        timeStop = timeStart + datetime.timedelta(minutes=self.timespan_minutes)                
                
        myBGs = entries_col.find({
            "$and": [
                {"sysTime" : { "$gt" : timeStart.isoformat() }},
                {"sysTime" : { "$lt" : timeStop.isoformat() }}
                ]
            })    
        myCarbs = treatments_col.find({
            "$and": [
                {"$or":[{"eventType":"Carb Correction"},{"eventType":"Meal Bolus"},{"eventType":"Snack Bolus"}]},
                {"timestamp" : { "$gt" : timeStart.isoformat() }},
                {"timestamp" : { "$lt" : timeStop.isoformat() }}
                ]
            })
        
        myBoluses = treatments_col.find({
            "$and": [
                {"eventType":"Correction Bolus"},
                {"timestamp" : { "$gt" :  timeStart.isoformat() }},
                {"timestamp" : { "$lt" :  timeStop.isoformat() }}
                ]
            })
        
        # Initial extraction (leftover from initial testing -- need to clean this up a bit)
        BG_times = np.array([datetime.datetime.fromisoformat(myBG.get('sysTime')) for myBG in myBGs])
        BG_values = np.array([myBG.get('sgv') for myBG in myBGs.rewind()])
        bgNoneFilt = np.where(np.array(BG_values) != None)[0]
        BG_times = BG_times[bgNoneFilt]
        BG_values = BG_values[bgNoneFilt] 
    
        carb_times = np.array([datetime.datetime.fromisoformat(myCarb.get('timestamp')) for myCarb in myCarbs])
        carb_values = np.array([myCarb.get('carbs') for myCarb in myCarbs.rewind()])
        
        bolus_times = np.array([datetime.datetime.fromisoformat(myBolus.get('timestamp')) for myBolus in myBoluses])
        bolus_values = np.array([myBolus.get('insulin') for myBolus in myBoluses.rewind()])
        minBolusFilt = (bolus_values > self.minBolus_to_load)  # Threshold to prevent autoboluses from cluttering things up
        bolus_times = bolus_times[minBolusFilt]
        bolus_values = bolus_values[minBolusFilt]                
        
        # load initial BG
        t0 = BG_times[0]
        self.x_BG = np.array([t.total_seconds() for t in (BG_times-t0)])/60       
        self.y_BG = BG_values.copy()
        
        #load initial carbs (this will remain fixed)
        self.x_carb = np.array([t.total_seconds() for t in (carb_times-t0)])/60
        self.y_carb = 0*carb_values + 50  # for initialization only
        self.z_carb = carb_values.copy() # carb amounts (grams)
        
        #load initial bolus insulin (these can be dragged)
        self.x_bolus = np.array([t.total_seconds() for t in (bolus_times-t0)])/60
        self.y_bolus = 0*bolus_values + 0 # for initialization only
        self.z_bolus = bolus_values.copy() # insulin amount (Units)                
        
        self.calculate_insulin_counteraction()
        
    def display_data(self):                

        self.ax.plot(self.x_BG,self.y_BG,color="grey", zorder=.1)                
        self.sc_BG = self.ax.scatter(self.x_BG,self.y_BG,alpha = 0.75,color="blue", zorder=.2)
        self.sc_carb = self.ax.scatter(self.x_carb,self.y_carb,self.z_carb*150/20, alpha = 0.8, color='orange', zorder=.3)
        self.sc_bolus = self.ax.scatter(self.x_bolus,self.y_bolus,self.z_bolus*150, alpha = 0.8, color = 'green', zorder=.4)
        
        self.my_carb_annotations=[]
        self.my_bolus_annotations=[]        
        
        self.ax.set_xlabel('Time (minutes)')
        self.ax.set_ylabel('BG (mg/dL)')
        self.ax.set_title("TinkerBolus\nDrag, Delete (press 'd'), Accumulate ('a'), or Insert ('i') Insulin Entries")
        
        self.ax.grid(True)
        
        self.transform_data_to_display = self.ax.transData
        self.move_y_bolus_and_carb_to_y_BG()    
        #self.ax.xaxis.set_major_locator(FixedLocator(np.arange(0,self.ax.get_xlim()[1],60)))        

        plt.show()

    def connect_handlers(self):
        self.canvas.mpl_connect('button_press_event', self.on_button_press)
        self.canvas.mpl_connect('button_release_event', self.on_button_release)
        self.canvas.mpl_connect('motion_notify_event', self.on_mouse_move)
        self.canvas.mpl_connect('key_press_event', self.on_key_press)

    def disconnect_handlers(self):
        self.canvas.mpl_disconnect('button_press_event')
        self.canvas.mpl_disconnect('button_release_event')
        self.canvas.mpl_disconnect('motion_notify_event')
        self.canvas.mpl_disconnect('key_press_event')    
          
    def load(self,*args):  
          self.accumulated_insulin = 0
          self.ax.clear()
          self.disconnect_handlers()          
          self.connect_to_mongodb()
          self.get_data_from_mongodb()
          self.display_data()
          self.connect_handlers()
        
    def calculate_insulin_counteraction(self):
        # determine initial insulin-only BG curve        
        self.y_BG_insulin_only = 0.0*self.y_BG
        for idx,x in enumerate(self.x_bolus):           
            self.y_BG_insulin_only += self.z_bolus[idx]*self.isf*(-1 + np.array([self.scalable_exp_iob(t, self.tp, self.td) for t in (self.x_BG-x)]))           
            
        # determine ICE-only BG (which will remain constant)
        self.y_BG_no_insulin = self.y_BG - self.y_BG_insulin_only;        
                
    def validate_bolus_textbox_string(self, *args):
        expression = self.bolus_text_box.text
        if expression == '':
            self.bolus_text_box.set_val(str(self.addbolus))
            return(str(self.addbolus))
        try:
            self.bolus_text_box.set_val(str(float(expression)))
            self.addbolus = float(expression);
            return(str(float(expression)))
        except:
            self.bolus_text_box.set_val(str(self.addbolus))
            return(str(self.addbolus))

    def validate_isf_textbox_string(self, *args):
        expression = self.isf_text_box.text
        if expression == '':
            self.isf_text_box.set_val(str(self.isf))
            return(str(self.isf))   
        try:
            self.isf_text_box.set_val(str(float(expression)))  
            self.isf = float(expression)
            return(str(self.isf))
        except:
            self.isf_text_box.set_val(str(self.isf))
            return(str(self.isf))        
        
    def validate_timespan_textbox_string(self, *args):
        expression = self.timespan_text_box.text
        if expression == '':
            self.timespan_text_box.set_val(str(self.timespan_minutes))
            return(str(self.timespan_minutes/60))   
        try:
            timespan_test_value = float(expression)
            if timespan_test_value > self.timespanmax_minutes/60:
                timespan_test_value = self.timespanmax_minutes/60        
            timespan_test_string = (str(timespan_test_value))
            self.timespan_text_box.set_val(timespan_test_string)  
            self.timespan_minutes = timespan_test_value*60            
            
            return(str(self.timespan_minutes))
        except:
            self.timespan_text_box.set_val(str(self.timespan_minutes))
            return(str(self.timespan_minutes/60))            

    def validate_date_textbox_string(self, *args):
        expression = self.date_text_box.text
        if expression == '':
            self.date_text_box.set_val(self.date)
            return(self.date)   
        try:
            datetime_test = datetime.datetime.fromisoformat(expression + 'T' + self.time);
            date_test_string = "{:04d}-{:02d}-{:02d}".format(datetime_test.year, datetime_test.month, datetime_test.day)
            self.date_text_box.set_val(date_test_string)   
            self.date = date_test_string                   
            return(date_test_string)
        except:
            self.date_text_box.set_val(self.date)
            return(self.date)        

    def validate_time_textbox_string(self, *args):
        expression = self.time_text_box.text
        if expression == '':
            self.time_text_box.set_val(self.time)
            return(self.time)   
        try:            
            datetime_test = datetime.datetime.fromisoformat(self.date + 'T' + expression);
            time_test_string = "{:02d}:{:02d}".format(datetime_test.hour, datetime_test.minute)
            self.date_text_box.set_val(time_test_string)   
            self.time = time_test_string
            return(time_test_string)                        
        except:
            self.time_text_box.set_val(self.time)
            return(self.time)    

    def validate_utcoffset_textbox_string(self, *args):
        expression = self.utcoffset_text_box.text
        if expression == '':
            self.utcoffset_text_box.set_val(str(self.utcoffset))
            return(str(self.utcoffset))   
        try:
            self.utcoffset_text_box.set_val(str(int(expression))) 
            self.utcoffset = int(expression)
            return(str(self.utcoffset))
        except:
            self.utcoffset_text_box.set_val(str(self.utcoffset))
            return(str(self.utcoffset))    

    def scalable_exp_iob(self,t, tp, td):
        if t < 0:     # equation isn't valid outside of range [0,td]
            return 1
        if t > td:
            return 0        
        tau = tp*(1-tp/td)/(1-2*tp/td)
        a = 2*tau/td
        S = 1/(1-a+(1+a)*np.exp(-td/tau))
        return 1-S*(1-a)*((pow(t,2)/(tau*td*(1-a)) - t/tau - 1)*np.exp(-t/tau)+1)
             
    def set_y_BG_insulin_only(self):
        # # determine insulin-only BG curve        
        self.y_BG_insulin_only = 0.0*self.y_BG
        for idx, x in enumerate(self.x_bolus):           
            self.y_BG_insulin_only += self.z_bolus[idx]*self.isf*(-1 + np.array([self.scalable_exp_iob(t, self.tp, self.td) for t in (self.x_BG-x)]))           
                
    def move_y_bolus_and_carb_to_y_BG(self):        
        # move y_bolus and y_carb to be near BG plot
        
        # prevent boluses and carbs from leaving the plot
        y_min, y_max = self.ax.get_ylim()  
        edge_delta = (y_max-y_min)*.04
        y_min_with_delta = y_min + edge_delta
        y_max_with_delta = y_max - edge_delta
                
        y_BG_temp = np.array([float(x) for x in self.y_BG])
        
        self.y_bolus = self.y_offset + np.interp(self.x_bolus,self.x_BG,y_BG_temp)
        self.y_bolus[self.y_bolus<y_min] = y_min_with_delta
        self.y_bolus[self.y_bolus>y_max] = y_max_with_delta
        self.y_carb[self.y_carb<y_min] = y_min_with_delta
        self.y_carb[self.y_carb>y_max] = y_max_with_delta                
            
        self.y_carb = -self.y_offset + np.interp(self.x_carb,self.x_BG,y_BG_temp)        
        self.sc_bolus.set_offsets(np.c_[self.x_bolus,self.y_bolus])
        self.sc_carb.set_offsets(np.c_[self.x_carb,self.y_carb])
        self.update_annotations()
        self.fig.canvas.draw_idle()      
    
    def remove_annotations_from_plot(self):
        # removes annotations from plot
        for i, txt in enumerate(self.my_carb_annotations):    
            self.my_carb_annotations[i].remove()
        for i, txt in enumerate(self.my_bolus_annotations):    
            self.my_bolus_annotations[i].remove()               
    
    def update_annotations(self):
        self.remove_annotations_from_plot()
        self.my_carb_annotations.clear()
        for i, txt in enumerate(self.z_carb):
            self.my_carb_annotations.append(self.ax.annotate(str(round(txt,2)) +  ' g', ((self.x_carb[i]), self.y_carb[i])))          
        self.my_bolus_annotations.clear()
        for i, txt in enumerate(self.z_bolus):
            self.my_bolus_annotations.append(self.ax.annotate(str(round(txt,2)) +  ' U', ((self.x_bolus[i]), self.y_bolus[i])))        

    def get_ind_under_point(self, event):
        # Return the index of the point closest to the event position or *None* if no point is within ``self.epsilon`` to the event position.    
        if np.size(self.x_bolus) == 0:
            return None
        
        # display coordinate system
        display_bolus_xy = self.transform_data_to_display.transform(list(zip(self.x_bolus,self.y_bolus)))        
        d = np.hypot(np.array([x for x,y in display_bolus_xy]) - event.x, np.array([y for x,y in display_bolus_xy]) - event.y)
        
        indseq, = np.nonzero(d == d.min())
        ind = indseq[0]
        if d[ind] >= self.epsilon:
            ind = None
        return ind

    def on_button_press(self, event):
        """Callback for mouse button presses."""
        if event.inaxes is None:
            return
        if event.button != 1:
            return        
        self._ind = self.get_ind_under_point(event)    
        
        
    def on_button_release(self, event):
        """Callback for mouse button releases."""
        if event.button != 1:
            return
        self.move_y_bolus_and_carb_to_y_BG()                 
        self._ind = None

    def on_mouse_move(self, event):
        """Callback for mouse movements."""
        if self._ind is None:
            return
        if event.inaxes is None:
            return
        if event.button != 1:
            return
                
        self.x_bolus[self._ind] = event.xdata;
        self.y_bolus[self._ind] = event.ydata;        
        self.sc_bolus.set_offsets(np.c_[self.x_bolus,self.y_bolus])
        self.redraw_BG()
                
    def delete_insulin(self,event):
        ind = self.get_ind_under_point(event)
        if ind is not None:                
            self.x_bolus = np.delete(self.x_bolus, ind)
            self.y_bolus = np.delete(self.y_bolus, ind)
            self.z_bolus = np.delete(self.z_bolus, ind)
        # self.sc_bolus.set_offsets(np.c_[self.x_bolus,self.y_bolus])
        self.redraw_bolus()
        self.redraw_BG()                
        self.move_y_bolus_and_carb_to_y_BG()    
        
    def insert_insulin(self,event):
        expression = self.validate_bolus_textbox_string()                                   
        self.x_bolus = np.append(self.x_bolus,event.xdata)
        self.y_bolus = np.append(self.y_bolus,0)
        self.z_bolus = np.append(self.z_bolus,float(expression))
        # self.sc_bolus.set_offsets(np.c_[self.x_bolus,self.y_bolus])    
        self.redraw_bolus()
        self.redraw_BG() 
        self.move_y_bolus_and_carb_to_y_BG()                        
        self.fig.canvas.draw_idle()   
        self.accumulated_insulin = 0
        
    def accumulate_insulin_for_bolus(self,event):
        ind = self.get_ind_under_point(event)
        if ind is not None:                
            self.accumulated_insulin += self.z_bolus[ind]
        self.delete_insulin(event)
        self.bolus_text_box.set_val(str(round(self.accumulated_insulin,2)))
        self.addbolus = float(self.accumulated_insulin);
        
    def on_key_press(self, event):
        """Callback for key presses."""
        if not event.inaxes in [self.ax]: 
            return
        elif event.key == 'd' or event.key == 'delete':
            self.delete_insulin(event)                
        elif event.key == 'i':
            self.insert_insulin(event)
        elif event.key == 'a':
            self.accumulate_insulin_for_bolus(event)            
                                               
    def redraw_BG(self):        
        self.set_y_BG_insulin_only()  # set the new insulin BG curves
        self.y_BG = self.y_BG_no_insulin + self.y_BG_insulin_only
        self.sc_BG.set_offsets(np.c_[self.x_BG,self.y_BG])
        self.fig.canvas.draw_idle()
        
    def redraw_bolus(self):     # need this instead of set_offsets for the z_bolus sizing to update correctly   
        self.sc_bolus.remove()
        self.sc_bolus = self.ax.scatter(self.x_bolus,self.y_bolus,self.z_bolus*150, alpha = 0.8, color = 'green', zorder=.4)
        self.fig.canvas.draw_idle()        
         

# main stuff here
if __name__ == '__main__':

    # set uri to read-only test database
    mongodb_uri = "mongodb+srv://test_pymongo_user:dwmgIlvrLC9mYIEu@cluster0.dbhmgel.mongodb.net"    
    minBolus_to_load = 0.0  # Threshold to prevent autoboluses from cluttering things up (although it's more fun with this set to 0)
    bgi = BGInteractor(mongodb_uri,minBolus_to_load)


    

