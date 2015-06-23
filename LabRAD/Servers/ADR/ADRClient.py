# Copyright (C) 2015  Chris Wilen
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


"""
### BEGIN NODE INFO
[info]
name = ADR Controller GUI
version = 1.3.2-no-refresh
description = This is a simple labrad client that gives a GUI interface to ADRServer, which controls our ADRs

[startup]
cmdline = %PYTHON% %FILE%
timeout = 20

[shutdown]
message = 987654321
timeout = 20
### END NODE INFO
"""
ADR_SETTINGS_PATH = ['','ADR Settings','ADR Shasta']  # path in registry

import matplotlib as mpl
mpl.use('TkAgg')
import pylab, numpy
import datetime
import Tkinter
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2TkAgg
import labrad
from labrad.server import (inlineCallbacks, returnValue)
from twisted.internet import tksupport, reactor

class EntryWithAlert(Tkinter.Entry):
    """Inherited from the Tkinter Entry widget, this just turns red when a limit is reached"""
    def __init__(self, *args, **kwargs):
        self.upper_limit = kwargs.pop('upper_limit',False)
        self.lower_limit = kwargs.pop('lower_limit',False)
        self.variable = kwargs['textvariable']
        self.variable.trace('w',self.callback)
        Tkinter.Entry.__init__(self,*args,**kwargs)
        self.naturalBGColor = self.cget('disabledbackground')
    def callback(self,*dummy):
        if self.upper_limit != False or self.lower_limit != False:
            x = self.variable.get()
            if x == '' or x == 'PS OFF' or float(x) > float(self.upper_limit) or float(x) < float(self.lower_limit):
                self.configure(disabledbackground='red')
            else:
                self.configure(disabledbackground=self.naturalBGColor)

class LogBox(Tkinter.Text):
    """This class inherits a Tkinter Text widget to make a simple log box.  It will log an entry,
    and set the color to red if alert is set to True.  A time stamp is automatically added."""
    def __init__(self, *args, **kwargs):
        Tkinter.Text.__init__(self,*args,**kwargs)
        self.tag_config("redAlert", background="red")
        self.configure(state=Tkinter.DISABLED)
    def log(self, message, alert=False):
        self.configure(state=Tkinter.NORMAL)
        self.insert(1.0,message+'\n')
        if alert: self.tag_add("redAlert", '1.0', '1.end')
        self.configure(state=Tkinter.DISABLED)


class ADRController(object):#Tkinter.Tk):
    """Provides a GUI for the ADRServer"""
    name = 'ADR Controller GUI'
    ID = 6116
    
    def __init__(self,parent,peripheralDict):
        #Tkinter.Tk.__init__(self,parent)
        self.parent = parent
        #initialize and start measurement loop
        self.connect()
    @inlineCallbacks
    def connect(self,cxn=None):
        """Connects to labrad, loads the last 20 log messages, and starts listening for messages from the adr server."""
        if cxn == None:
            #make an asynchronous connection to LabRAD
            from labrad.wrappers import connectAsync
            self.cxn = yield connectAsync(name = self.name)
        else:self.cxn = cxn
        yield self.initializeWindow()
        try: #adr_server may not be open yet
            logMessages = yield self.cxn.adr_server.get_log(20) #only load last 20 messages
            for (m,a) in logMessages:
                self.updateLog(m,a)
        except Exception as e: pass
        self.startListening()
    @inlineCallbacks
    def startListening(self):
        """The ADR Server sends out named messages every time the state is changed, the log is updated, or magging or regulation cycles complete.  This function starts the listeners for them.  Note: We used named messages instead of Signals because Signals are registered directly with the server instead of the manager (like named messages), so if the adr server disconnects and reconnects, the signals will no longer be sent here."""
        mgr = self.cxn.manager
        # example of Signal processing:
        # server = self.cxn.adr_server
        # update_state = lambda c, payload: self.updateInterface()
        # yield server.signal_state_changed(self.ID)
        # yield server.addListener(listener = update_state, source=None,ID=self.ID)
        
        # state update
        update_state = lambda c, (s,payload): self.updateInterface()
        self.cxn._cxn.addListener(update_state, source=mgr.ID, ID=101)
        yield mgr.subscribe_to_named_message('State Changed', 101, True)
        # log update
        update_log = lambda c, (s,(m,a)): self.updateLog(m,a)
        self.cxn._cxn.addListener(update_log, source=mgr.ID, ID=102)
        yield mgr.subscribe_to_named_message('Log Changed', 102, True)
        # magging up stopped
        mag_stop = lambda c, (s,payload): self.magUpStopped()
        self.cxn._cxn.addListener(mag_stop, source=mgr.ID, ID=103)
        yield mgr.subscribe_to_named_message('MagUp Stopped', 103, True)
        # regulation stopped
        reg_stop = lambda c, (s,payload): self.regulationStopped()
        self.cxn._cxn.addListener(reg_stop, source=mgr.ID, ID=104)
        yield mgr.subscribe_to_named_message('Regulation Stopped', 104, True)
        # magging up started
        mag_start = lambda c, (s,payload): self.magUpStarted()
        self.cxn._cxn.addListener(mag_start, source=mgr.ID, ID=105)
        yield mgr.subscribe_to_named_message('MagUp Started', 105, True)
        # regulation started
        reg_start = lambda c, (s,payload): self.regulationStarted()
        self.cxn._cxn.addListener(reg_start, source=mgr.ID, ID=106)
        yield mgr.subscribe_to_named_message('Regulation Started', 106, True)
    @inlineCallbacks
    def initializeWindow(self):
        """Creates the GUI."""
        root = self.parent
        reg = self.cxn.registry
        reg.cd(ADR_SETTINGS_PATH)
        try: magVLimit = yield reg.get('magnet_voltage_limit')
        except Exception as e: magVLimit = 0.1
        try: PSILimit = yield reg.get('current_limit')
        except Exception as e: PSILimit = 9
        try: PSVLimit = yield reg.get('voltage_limit')
        except Exception as e: PSVLimit = 2
        #set up window
        root.wm_title('ADR Magnet Controller')
        root.title('ADR Controller')
        w, h = root.winfo_screenwidth(), root.winfo_screenheight()
        root.geometry("%dx%d+0+0" % (w/2, 0.9*h))
        #error/message box log
        self.log = LogBox(master=root, height=5)
        self.log.pack(side=Tkinter.TOP, fill=Tkinter.X)
        addToLogFrame = Tkinter.Frame(root)
        addToLogFrame.pack(side=Tkinter.TOP, fill=Tkinter.X)
        addToLogButton = Tkinter.Button(addToLogFrame, text='Add', command=self.addToLog)
        addToLogButton.pack(side=Tkinter.RIGHT)
        self.addToLogField = Tkinter.Text(addToLogFrame,height=1)
        self.addToLogField.pack(side=Tkinter.RIGHT, fill=Tkinter.X)
        # temp plot
        self.fig = pylab.figure()
        self.ax = self.fig.add_subplot(111)
        #self.ax2 = self.ax.twinx()
        self.ax.set_title('Realtime Temperature Readout\n\n\n')
        self.ax.set_xlabel('Time')
        self.ax.set_ylabel('Temparture [K]')
        self.stage60K, = self.ax.plot_date([],[],'-')
        self.stage03K, = self.ax.plot_date([],[],'-')
        self.stageGGG, = self.ax.plot_date([],[],'-')
        self.stageFAA, = self.ax.plot_date([],[],'-')
        self.canvas = FigureCanvasTkAgg(self.fig, master=root)
        self.canvas.show()
        self.canvas.get_tk_widget().pack(side=Tkinter.TOP, fill=Tkinter.BOTH, expand=1)
        #temp plot toolbar at bottom
        self.toolbar = NavigationToolbar2TkAgg( self.canvas, root )
        self.toolbar.update()
        #self.toolbar.pack(side=Tkinter.BOTTOM, fill=Tkinter.X)
        self.canvas._tkcanvas.pack(side=Tkinter.TOP, fill=Tkinter.BOTH, expand=1)
        #which temp plots should I show? (checkboxes)
        tempSelectFrame = Tkinter.Frame(root)
        tempSelectFrame.pack(side=Tkinter.TOP)
        self.t60K = Tkinter.IntVar()
        self.t3K = Tkinter.IntVar()
        self.tGGG = Tkinter.IntVar()
        self.tFAA = Tkinter.IntVar()
        self.t60K.set(0)
        self.t3K.set(1)
        self.tGGG.set(0)
        self.tFAA.set(1)
        t1checkbox = Tkinter.Checkbutton(tempSelectFrame, text = '60K Stage', variable=self.t60K, fg='blue')
        t1checkbox.pack(side=Tkinter.LEFT)
        t2checkbox = Tkinter.Checkbutton(tempSelectFrame, text = '3K Stage', variable=self.t3K, fg='forest green')
        t2checkbox.pack(side=Tkinter.LEFT)
        t3checkbox = Tkinter.Checkbutton(tempSelectFrame, text = '1K Stage (GGG)', variable=self.tGGG, fg='red', state=Tkinter.DISABLED)
        t3checkbox.pack(side=Tkinter.LEFT)
        t4checkbox = Tkinter.Checkbutton(tempSelectFrame, text = '50mK Stage (FAA)', variable=self.tFAA, fg='dark turquoise')
        t4checkbox.pack(side=Tkinter.LEFT)
        #scale to adjust time shown in temp plot
        wScaleOptions = ('10 minutes','1 hour','6 hours','24 hours','All')
        self.wScale = Tkinter.StringVar(root)
        self.wScale.set(wScaleOptions[1])
        apply(Tkinter.OptionMenu,(root,self.wScale)+wScaleOptions).pack(side=Tkinter.TOP)
        refreshInstrButton = Tkinter.Button(root, text='Refresh Instruments', command=self.refreshInstruments)
        refreshInstrButton.pack(side=Tkinter.TOP)
        #frame for mag up and regulate controls
        magControlsFrame = Tkinter.Frame(root)
        magControlsFrame.pack(side=Tkinter.TOP)
        #mag up button
        self.magUpButton = Tkinter.Button(master=magControlsFrame, text='Mag Up', command=self.magUp)
        self.magUpButton.pack(side=Tkinter.LEFT)
        #regulate button and temp field
        self.regulateButton = Tkinter.Button(master=magControlsFrame, text='Regulate', command=self.regulate)
        self.regulateButton.pack(side=Tkinter.LEFT)
        Tkinter.Label(magControlsFrame, text=" at ").pack(side=Tkinter.LEFT)
        self.regulateTempField = Tkinter.Entry(magControlsFrame, validate='focusout', validatecommand=self.regulate)
        self.regulateTempField.pack(side=Tkinter.LEFT)
        self.regulateTempField.insert(0, "0.1")
        Tkinter.Label(magControlsFrame, text="K").pack(side=Tkinter.LEFT)
        mUp = yield self.cxn.adr_server.get_state_var('maggingUp')
        reg = yield self.cxn.adr_server.get_state_var('regulating')
        try:
            if mUp:
                self.magUpButton.configure(text='Stop Magging Up', command=self.cancelMagUp)
                self.regulateButton.configure(state=Tkinter.DISABLED)
            if reg:
                self.regulateButton.configure(text='Stop Regulating', command=self.cancelRegulate)
                self.magUpButton.configure(state=Tkinter.DISABLED)
        except Exception as e: pass #if not connected to ADRServer
        #shows current values for backEMF, current, voltage
        monitorFrame = Tkinter.Frame(root)
        monitorFrame.pack(side=Tkinter.TOP)
        self.currentBackEMF = Tkinter.StringVar() #current as in now, not as in amps
        self.currentI = Tkinter.StringVar()
        self.currentV = Tkinter.StringVar()
        Tkinter.Label(monitorFrame, text="Back EMF = ").pack(side=Tkinter.LEFT)
        backEMFField = EntryWithAlert(monitorFrame, textvariable=self.currentBackEMF, state=Tkinter.DISABLED, upper_limit=magVLimit)
        backEMFField.pack(side=Tkinter.LEFT)
        Tkinter.Label(monitorFrame, text="(V)   I = ").pack(side=Tkinter.LEFT)
        currentIField = EntryWithAlert(monitorFrame, textvariable=self.currentI, state=Tkinter.DISABLED, upper_limit=PSILimit)
        currentIField.pack(side=Tkinter.LEFT)
        Tkinter.Label(monitorFrame, text="(A)   V = ").pack(side=Tkinter.LEFT)
        currentVField = EntryWithAlert(monitorFrame, textvariable=self.currentV, state=Tkinter.DISABLED, upper_limit=PSVLimit)
        currentVField.pack(side=Tkinter.LEFT)
        Tkinter.Label(monitorFrame, text="(V)").pack(side=Tkinter.LEFT)
        self.fig.tight_layout()
        root.protocol("WM_DELETE_WINDOW", self._quit) #X BUTTON
    def refreshInstruments(self):
        self.cxn.adr_server.refresh_instruments()
    @inlineCallbacks
    def updateInterface(self):
        """ update interface to reflect system state """
        p = self.cxn.adr_server.packet()
        p.magnetv().pscurrent().psvoltage()
        p.time()
        p.temperatures()
        state = yield p.send()
        temps = {}
        stages = ('T_60K','T_3K','T_GGG','T_FAA')
        for i in range(len(stages)):
            temps[stages[i]] = state['temperatures'][i]
            #if temps[stages[i]] == 'nan': temps[stages[i]] = numpy.nan
        self.currentBackEMF.set( "{0:.3f}".format(state['magnetv']) )
        if numpy.isnan(state['pscurrent']): psI = 'PS OFF'
        else: psI = "{0:.3f}".format(state['pscurrent'])
        if numpy.isnan(state['psvoltage']): psV = 'PS OFF'
        else: psV = "{0:.3f}".format(state['psvoltage'])
        self.currentI.set( psI )
        self.currentV.set( psV )
        # update plot:
        # change data to plot
        self.stage60K.set_xdata(numpy.append(self.stage60K.get_xdata(),mpl.dates.date2num(state['time'])))
        self.stage60K.set_ydata(numpy.append(self.stage60K.get_ydata(),temps['T_60K']))
        self.stage03K.set_xdata(numpy.append(self.stage03K.get_xdata(),mpl.dates.date2num(state['time'])))
        self.stage03K.set_ydata(numpy.append(self.stage03K.get_ydata(),temps['T_3K']))
        self.stageGGG.set_xdata(numpy.append(self.stageGGG.get_xdata(),mpl.dates.date2num(state['time'])))
        self.stageGGG.set_ydata(numpy.append(self.stageGGG.get_ydata(),temps['T_GGG']))
        self.stageFAA.set_xdata(numpy.append(self.stageFAA.get_xdata(),mpl.dates.date2num(state['time'])))
        self.stageFAA.set_ydata(numpy.append(self.stageFAA.get_ydata(),temps['T_FAA']))
        # set x limits
        timeDisplayOptions = {'10 minutes':10,'1 hour':60,'6 hours':6*60,'24 hours':24*60,'All':0}
        lastDatetime = mpl.dates.num2date(self.stage60K.get_xdata()[-1])
        firstDatetime = mpl.dates.num2date(self.stage60K.get_xdata()[0])
        xMin = lastDatetime-datetime.timedelta(minutes=timeDisplayOptions[self.wScale.get()])
        xMin = max([ firstDatetime, xMin ])
        if self.wScale.get() == 'All': xMin = firstDatetime
        xMinIndex = numpy.searchsorted( self.stage60K.get_xdata(), mpl.dates.date2num(xMin) )
        # rescale axes, with the x being scaled by the slider
        if self.toolbar._active == 'HOME' or self.toolbar._active == None:
            ymin,ymax = 10000000, -10000000
            lineAndVar = {self.stage60K:self.t60K, self.stage03K:self.t3K, self.stageGGG:self.tGGG, self.stageFAA:self.tFAA}
            for line in lineAndVar.keys():
                if lineAndVar[line].get() == 0: line.set_visible(False)
                else:
                    line.set_visible(True)
                    ydata = line.get_ydata()[xMinIndex:-1]
                    try:
                        ymin = min(ymin, numpy.nanmin(ydata))
                        ymax = max(ymax, numpy.nanmax(ydata))
                    except ValueError as e: pass
            if len(self.stage60K.get_xdata())>1: 
                self.ax.set_xlim(xMin,lastDatetime)
                self.ax.set_ylim(ymin - (ymax-ymin)/10, ymax + (ymax-ymin)/10)
                self.fig.autofmt_xdate()
        # update legend
        labelOrder = ['T_60K','T_3K','T_GGG','T_FAA']
        lines = [self.stage60K,self.stage03K,self.stageGGG,self.stageFAA]
        labels = [l.strip('T_')+' ['+"{0:.3f}".format(temps[l])+'K]' for l in labelOrder]
        labels = [s.replace('1.#QOK','OoR') for s in labels]
        #self.ax.legend(lines,labels,loc=0)#,bbox_to_anchor=(1.01, 1)) #legend in upper right
        self.ax.legend(lines,labels,bbox_to_anchor=(0., 1.02, 1., .102), loc=3,
           ncol=4, mode="expand", borderaxespad=0.) #legend on top (if not using this, delete \n in title)
        #draw
        self.canvas.draw()
    def updateLog(self,message=None,alert=False):
        if message:
            self.log.log(message,alert)
    def addToLog(self):
        text = str( self.addToLogField.get(1.0, Tkinter.END) )
        try:
            self.cxn.adr_server.add_to_log(text)
            self.addToLogField.delete(1.0, Tkinter.END)
        except Exception as e: pass
    def magUp(self):
        self.cxn.adr_server.mag_up()
    def magUpStarted(self):
        self.magUpButton.configure(text='Stop Magging Up', command=self.cancelMagUp)
        self.regulateButton.configure(state=Tkinter.DISABLED)
    def cancelMagUp(self):
        self.cxn.adr_server.cancel_mag_up()
    def magUpStopped(self):
        self.magUpButton.configure(text='Mag Up', command=self.magUp)
        self.regulateButton.configure(state=Tkinter.NORMAL)
    def regulate(self): 
        T_target = float(self.regulateTempField.get())
        self.cxn.adr_server.regulate(T_target)
    def regulationStarted(self):
        self.regulateButton.configure(text='Stop Regulating', command=self.cancelRegulate)
        self.magUpButton.configure(state=Tkinter.DISABLED)
    def cancelRegulate(self):
        self.cxn.adr_server.cancel_regulation()
    def regulationStopped(self):
        self.regulateButton.configure(text='Regulate', command=self.regulate)
        self.magUpButton.configure(state=Tkinter.NORMAL)
    def _quit(self):
        """ called when the window is closed."""
        self.parent.quit()     # stops mainloop
        self.parent.destroy()  # this is necessary on Windows to prevent
                               # Fatal Python Error: PyEval_RestoreThread: NULL tstate
        reactor.stop()
        
if __name__ == "__main__":
    """Define your instruments here.  This allows for easy exchange between different
    devices to monitor temperature, etc.  For example, the new and old ADR's use two
    different instruments to measure temperature: The SRS module and the Lakeview 218."""
    peripheralDict = {  'Ruox Temperature Monitor':['SIM921 Server','SIM900 SRS Mainframe - GPIB0::2::SIM900::1'],
                        'Diode Temperature Monitor':['SIM922 Server','SIM900 SRS Mainframe - GPIB0::2::SIM900::5'],
                        'Power Supply':['Agilent 6641A PS','mcdermott5125 GPIB Bus - GPIB0::5'],
                        'Magnet Voltage Monitor':['SIM922 Server','SIM900 SRS Mainframe - GPIB0::2::SIM900::5'] } #{'device',['name','addr']}
    mstr = Tkinter.Tk()
    tksupport.install(mstr)
    app = ADRController(mstr,peripheralDict)
    reactor.run()