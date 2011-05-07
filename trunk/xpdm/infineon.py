# -*- coding: utf-8 -*-
# Infineon-style e-bike controller profile
#

import os
import gtk
import ctypes
import math
import serial

# -- # Constants # -- #

# Controller type descriptions
ControllerTypeDesc = [
    {
        # User-visible controller model name
        "Name"             : "EB206",
        # How to translate phase current to a raw value that controller understands (0-255)
        "PhaseCurrent2Raw" : lambda I: I * 1.25 - 0.2,
        # The reverse transform: given a raw value, convert to current
        "Raw2PhaseCurrent" : lambda V: 0.16 + (0.8 * V),
        # How to translate battery current to a raw value in the range 0-255
        "BattCurrent2Raw"  : lambda I: I * 1.256 + 1.25,
        # How to translate a raw value to battery current
        "Raw2BattCurrent"  : lambda V: (0.796 * V) - 0.995,
        # How to translate a voltage to a raw value
        "Voltage2Raw"      : lambda U: U * 3.283,
        # How to translate a raw value to actual voltage
        "Raw2Voltage"      : lambda V: V / 3.283,
    },
    {
        "Name"             : "EB209",
        "PhaseCurrent2Raw" : lambda I: I * 1.25 - 19.2,
        "Raw2PhaseCurrent" : lambda V: 15.36 + (0.8 * V),
        "BattCurrent2Raw"  : lambda I: I * 1.256 - 2.8,
        "Raw2BattCurrent"  : lambda V: 2.229 + (0.796 * V),
        "Voltage2Raw"      : lambda U: U * 3.283,
        "Raw2Voltage"      : lambda V: V / 3.283,
    },
    {
        "Name"             : "EB212",
        "PhaseCurrent2Raw" : lambda I: I * 0.625 - 7,
        "Raw2PhaseCurrent" : lambda V: 11.2 + (1.6 * V),
        "BattCurrent2Raw"  : lambda I: I * 0.624 - 1.5,
        "Raw2BattCurrent"  : lambda V: 2.404 + (1.603 * V),
        "Voltage2Raw"      : lambda U: U * 3.283,
        "Raw2Voltage"      : lambda V: V / 3.283,
    },
    {
        "Name"             : "EB215",
        "PhaseCurrent2Raw" : lambda I: I * 0.416 - 18.9,
        "Raw2PhaseCurrent" : lambda V: 45.4327 + (2.4038 * V),
        "BattCurrent2Raw"  : lambda I: I * 0.425 - 3.3,
        "Raw2BattCurrent"  : lambda V: 7.765 + (2.353 * V),
        "Voltage2Raw"      : lambda U: U * 3.283,
        "Raw2Voltage"      : lambda V: V / 3.283,
    },
    {
        "Name"             : "EB218",
        "PhaseCurrent2Raw" : lambda I: I * 0.187 - 0.1,
        "Raw2PhaseCurrent" : lambda V: 0.5348 + (5.3476 * V),
        "BattCurrent2Raw"  : lambda I: I * 0.213 + 0.1,
        "Raw2BattCurrent"  : lambda V: (4.695 * V) - 0.469,
        "Voltage2Raw"      : lambda U: U * 3.283,
        "Raw2Voltage"      : lambda V: V / 3.283,
    },
];

# Motor sensor angle
SA_120 = 0
SA_60 = 1
SA_COMPAT = 2

SensorAngleDesc = [ "120°", "60°", _("Auto") ]

# Three-speed switch modes
SSM_SELECT = 0
SSM_TOGGLE = 1

SpeedSwitchModeDesc = [ _("Select"), _("Toggle") ]

# LED indicator mode
IM_COMM_VCC = 0
IM_COMM_GND = 1
# "164 Mode P1-DAT P2-CLK"
IM_164 = 2

IndicatorModeDesc = [ _("Common VCC"), _("Common GND"), _("164 Mode P1-DAT P2-CLK") ]

# Slip charge mode
SCM_ENABLE = 0
SCM_DISABLE = 1

SlipChargeModeDesc = [ _("Enable"), _("Disable") ]

# EBS level
EBS_DISABLED = 0
EBS_MODERATE = 1
EBS_STRONG = 2

EBSLevelDesc = [ _("Disabled"), _("Moderate"), _("Strong") ]

# Guard mode signal polarity (anti-theft)
GP_LOW = 0
GP_HIGH = 1

GuardLevelDesc = [ _("Low"), _("High") ]

# Throttle blowout protect
TBP_DISABLE = 0
TBP_ENABLE = 1

ThrottleProtectDesc = [ _("Disabled"), _("Enabled") ]

# Pedal Assisted Sensor mode
PAS_FAST = 0
PAS_SLOW = 1

PASModeDesc = [ _("Fast"), _("Slow") ]

# P3 LED indicator mode
P3M_CRUISE = 0
P3M_CRUISE_FAIL = 1

P3MModeDesc = [ _("Cruise"), _("Cruise & Failure code") ]


# -- # -- # -- # -- # -- # -- # -- # -- # -- # -- # -- # -- #

# Parameter widget types for editing
PWT_COMBOBOX = 0
PWT_SPINBUTTON = 1

# This array describes all the controller parameters
ControllerParameters = {
    # The name of the variable to hold this parameter
    "ControllerType" :
    {
        # Parameter type
        "Type"        : "i",
        # A short user-friendly parameter description
        "Name"        : _("Controller type"),
        # Long parameter description
        "Description" : _("""\
The type of your controller. This influences the coefficients assumed for \
various parts of the controller, e.g. shunts, resistive dividers. If you \
have a non-standard controller, you may create your own type in infineon.py\
"""),
        # Default parameter value (when creating a new profile)
        "Default"     : 1,
        # The widget type used to edit this parameter
        "Widget"      : PWT_COMBOBOX,
        # This field contains the (min, max) values tuple for current parameter
        "Range"       : (1, len (ControllerTypeDesc)),
        # This function translates the numeric param value to a user-friendly string
        "GetDisplay"  : lambda prof, v: ControllerTypeDesc [v - 1]["Name"],
    },

    "PhaseCurrent" :
    {
        "Type"        : "f",
        "Name"        : _("Phase current limit"),
        "Description" : _("""\
The current limit in motor phase wires. Since the e-bike controller is, \
in a sense, a step-down DC-DC converter, the motor current can actually be \
much higher than the battery current. When setting this parameter, make \
sure you don't exceed the capabilities of the MOSFETs in your controller.\
"""),
        "Default"     : 30,
        # A list of parameters this one depends on
        "Depends"     : [ "ControllerType" ],
        # The measurement units for this parameter
        "Units"       : _("A"),
        "Widget"      : PWT_SPINBUTTON,
        "Range"       : (1, 255),
        # This function converts the raw value to displayed value (in amps)
        "GetDisplay"  : lambda prof, v: prof.GetController () ["Raw2PhaseCurrent"] (v),
        # This function converts the displayed value to raw (when user enters the value directly)
        "SetDisplay"  : lambda prof, v: round (prof.GetController () ["PhaseCurrent2Raw"] (v)),
    },

    "BatteryCurrent" :
    {
        "Type"        : "f",
        "Name"        : _("Battery current limit"),
        "Description" : _("""\
The limit for the current drawn out of the battery. Make sure this does \
not exceed the specs for your battery, otherwise you will lose a lot of \
energy heating up the battery (and may blow it, too).\
"""),
        "Default"     : 14,
        "Depends"     : [ "ControllerType" ],
        "Units"       : _("A"),
        "Widget"      : PWT_SPINBUTTON,
        "Range"       : (1, 255),
        "GetDisplay"  : lambda prof, v: prof.GetController () ["Raw2BattCurrent"] (v),
        "SetDisplay"  : lambda prof, v: round (prof.GetController () ["BattCurrent2Raw"] (v)),
    },

    "HaltVoltage" :
    {
        "Type"        : "f",
        "Name"        : _("Battery low voltage"),
        "Description" : _("""\
The voltage at which controller cuts of the power. Make sure this is \
at least equal to lowest_cell_voltage x cell_count (e.g. for a \
12S LiFePO4 battery this would be 2.6 * 12 = 31.2V). This does not \
matter much if you use a BMS, since it will cut the power as soon \
as *any* cell reaches the lowest voltage, which is much better for \
the health of your battery.\
"""),
        "Default"     : 32.5,
        "Depends"     : [ "ControllerType" ],
        "Units"       : _("V"),
        "Widget"      : PWT_SPINBUTTON,
        "Range"       : (1, 255),
        "GetDisplay"  : lambda prof, v: prof.GetController () ["Raw2Voltage"] (v),
        "SetDisplay"  : lambda prof, v: round (prof.GetController () ["Voltage2Raw"] (v)),
    },

    "VoltageTolerance" :
    {
        "Type"        : "f",
        "Name"        : _("Battery low voltage threshold"),
        "Description" : _("""\
The amount of volts for the battery voltage to rise after a cutoff \
due to low voltage for the controller to restore power back. This is \
most useful for plumbum batteries, as they tend to restore voltage \
after a bit of rest.\
"""),
        "Default"     : 1.0,
        "Depends"     : [ "ControllerType" ],
        "Units"       : _("V"),
        "Widget"      : PWT_SPINBUTTON,
        "Range"       : (1, 255),
        "GetDisplay"  : lambda prof, v: prof.GetController () ["Raw2Voltage"] (v),
        "SetDisplay"  : lambda prof, v: round (prof.GetController () ["Voltage2Raw"] (v)),
    },

    "SpeedSwitchMode" :
    {
        "Type"        : "i",
        "Name"        : _("Speed switch mode"),
        "Description" : _("""\
The way how the speed switch functions. When in 'switch' mode you may \
use a three-position switch connected to X1, X2 and X3 to select between \
three speed limits. In 'toggle' mode by connecting (with a momentary \
switch) X1 to ground will toggle between speeds 1 and 2.\
"""),
        "Default"     : SSM_SELECT,
        "Widget"      : PWT_COMBOBOX,
        "Range"       : (0, 1),
        "GetDisplay"  : lambda prof, v: SpeedSwitchModeDesc [v],
    },

    "Speed1" :
    {
        "Type"        : "i",
        "Name"        : _("Speed 1"),
        "Description" : _("""\
The first speed limit.(see comment to 'speed switch mode').\
"""),
        "Default"     : 100,
        "Units"       : "%",
        "Widget"      : PWT_SPINBUTTON,
        "Precision"   : 0,
        "Range"       : (1, 95),
        "GetDisplay"  : lambda prof, v: v * 1.27,
        "SetDisplay"  : lambda prof, v: round (v / 1.27),
    },

    "Speed2" :
    {
        "Type"        : "i",
        "Name"        : _("Speed 2"),
        "Description" : _("""\
The second speed limit.(see comment to 'speed switch mode').\
"""),
        "Default"     : 100,
        "Units"       : "%",
        "Widget"      : PWT_SPINBUTTON,
        "Precision"   : 0,
        "Range"       : (1, 95),
        "GetDisplay"  : lambda prof, v: v * 1.27,
        "SetDisplay"  : lambda prof, v: round (v / 1.27),
    },

    "Speed3" :
    {
        "Type"        : "i",
        "Name"        : _("Speed 3"),
        "Description" : _("""\
The third speed limit.(see comment to 'speed switch mode').\
"""),
        "Default"     : 100,
        "Units"       : "%",
        "Widget"      : PWT_SPINBUTTON,
        "Precision"   : 0,
        "Range"       : (1, 95),
        "GetDisplay"  : lambda prof, v: v * 1.27,
        "SetDisplay"  : lambda prof, v: round (v / 1.27),
    },

    "LimitedSpeed" :
    {
        "Type"        : "i",
        "Name"        : _("Limited speed"),
        "Description" : _("""\
The speed corresponding to 100% throttle when the 'speed limit' \
switch/wires are enabled (when the 'SL' board contact is connected \
to ground).\
"""),
        "Default"     : 100,
        "Units"       : "%",
        "Widget"      : PWT_SPINBUTTON,
        "Precision"   : 0,
        "Range"       : (1, 127),
        "GetDisplay"  : lambda prof, v: v / 1.27,
        "SetDisplay"  : lambda prof, v: round (v * 1.27),
    },

    "ReverseSpeed" :
    {
        "Type"        : "i",
        "Name"        : _("Reverse speed"),
        "Description" : _("""\
The speed at which motor runs in reverse direction when the DX3 \
board contact is connected to ground.\
"""),
        "Default"     : 35,
        "Units"       : "%",
        "Widget"      : PWT_SPINBUTTON,
        "Precision"   : 0,
        "Range"       : (1, 127),
        "GetDisplay"  : lambda prof, v: v / 1.27,
        "SetDisplay"  : lambda prof, v: round (v * 1.27),
    },

    "BlockTime" :
    {
        "Type"        : "f",
        "Name"        : _("Overcurrent detection delay"),
        "Description" : _("""\
The amount of time before the phase current limit takes effect  \
Rising this parameter will help you start quicker from a dead stop, \
but don't set this too high as you risk blowing out your motor - \
at high currents it will quickly heat up.\
"""),
        "Default"     : 1.0,
        "Units"       : _("s"),
        "Widget"      : PWT_SPINBUTTON,
        "Range"       : (10, 100),
        "GetDisplay"  : lambda prof, v: v / 10,
        "SetDisplay"  : lambda prof, v: round (v * 10),
    },

    "AutoCruisingTime" :
    {
        "Type"        : "f",
        "Name"        : _("Auto cruising time"),
        "Description" : _("""\
The amount of seconds to hold the throttle position unchanged \
before the 'cruising' mode will be enabled. For this to work \
you need to connect the CR contact on the board to ground.\
"""),
        "Default"     : 15.0,
        "Units"       : _("s"),
        "Widget"      : PWT_SPINBUTTON,
        "Range"       : (10, 150),
        "GetDisplay"  : lambda prof, v: v / 10,
        "SetDisplay"  : lambda prof, v: round (v * 10),
    },

    "SlipChargeMode" :
    {
        "Type"        : "i",
        "Name"        : _("Slip charge mode"),
        "Description" : _("""\
This parameter controls regen from the throttle. If you enable it, \
throttling back will enable regen (and thus will brake) until the \
electronic braking becomes ineffective (at about 15% of full speed).\
"""),
        "Default"     : SCM_DISABLE,
        "Widget"      : PWT_COMBOBOX,
        "Range"       : (0, 1),
        "GetDisplay"  : lambda prof, v: SlipChargeModeDesc [v],
    },

    "IndicatorMode" :
    {
        "Type"        : "i",
        "Name"        : _("LED indicator mode"),
        "Description" : _("""\
This sets the mode of the P1, P2 and P3 contacts on the board. \
The connected LEDs may use either a common GND or common VCC.\
"""),
        "Default"     : IM_COMM_GND,
        "Widget"      : PWT_COMBOBOX,
        "Range"       : (0, 2),
        "GetDisplay"  : lambda prof, v: IndicatorModeDesc [v],
    },

    "EBSLevel" :
    {
        "Type"        : "i",
        "Name"        : _("EBS level"),
        "Description" : _("""\
Electronic braking level. Choose 'Moderate' for smaller wheel diameters, \
and 'Strong' for 26" and up. The larger is the level, the more effective \
is braking.\
"""),
        "Default"     : EBS_DISABLED,
        "Widget"      : PWT_COMBOBOX,
        "Range"       : (0, 2),
        "GetDisplay"  : lambda prof, v: EBSLevelDesc [v],
        # This member, if defined, tells how to translate setting to raw value
        "ToRaw"       : lambda prof, v: v * 4,
    },

    "EBSLimVoltage" :
    {
        "Type"        : "f",
        "Name"        : _("EBS limit voltage"),
        "Description" : _("""\
When regen is enabled (also known as electronic braking system) \
the controller effectively acts as a step-up DC-DC converter, \
transferring energy from the motor into the battery. This sets \
the upper voltage limit for this DC-DC converter, which is needed \
to prevent blowing out the controller MOSFETs.\
"""),
        "Default"     : 75,
        "Depends"     : [ "ControllerType" ],
        "Units"       : _("V"),
        "Widget"      : PWT_SPINBUTTON,
        "Range"       : (1, 255),
        "GetDisplay"  : lambda prof, v: prof.GetController () ["Raw2Voltage"] (v),
        "SetDisplay"  : lambda prof, v: round (prof.GetController () ["Voltage2Raw"] (v)),
    },

    "GuardLevel" :
    {
        "Type"        : "i",
        "Name"        : _("Guard signal polarity"),
        "Description" : _("""\
The polarity of the Guard signal, which should be connected to the \
TB pin on the board  When Guard is active, controller will prevent \
rotating the wheel in any direction. This is useful if used together \
with a motorcycle alarm or something like that.\
"""),
        "Default"     : GP_LOW,
        "Widget"      : PWT_COMBOBOX,
        "Range"       : (0, 1),
        "GetDisplay"  : lambda prof, v: GuardLevelDesc [v],
    },

    "ThrottleProtect" :
    {
        "Type"        : "i",
        "Name"        : _("Throttle blowout protect"),
        "Description" : _("""\
Enable this parameter to let the controller check if your \
throttle output is sane (e.g. if the Hall sensor in the throttle \
is not blown out). If it is broken, you might get a constant \
full-throttle condition, which might be not very pleasant.\
"""),
        "Default"     : TBP_ENABLE,
        "Widget"      : PWT_COMBOBOX,
        "Range"       : (0, 1),
        "GetDisplay"  : lambda prof, v: ThrottleProtectDesc [v],
    },

    "PASMode" :
    {
        "Type"        : "i",
        "Name"        : _("PAS mode"),
        "Description" : _("""\
Pedal Assisted Sensor mode.\
"""),
        "Default"     : PAS_FAST,
        "Widget"      : PWT_COMBOBOX,
        "Range"       : (0, 1),
        "GetDisplay"  : lambda prof, v: PASModeDesc [v],
    },

    "P3Mode" :
    {
        "Type"        : "i",
        "Name"        : _("P3 mode"),
        "Description" : _("""\
An additional setting for the P3 LED output. You may select \
between displaying only the "Cruise" mode on this LED, or both \
"Cruise" and fault conditions.\
"""),
        "Default"     : P3M_CRUISE,
        "Widget"      : PWT_COMBOBOX,
        "Range"       : (0, 1),
        "GetDisplay"  : lambda prof, v: P3MModeDesc [v],
    },

    "SensorAngle" :
    {
        "Type"        : "i",
        "Name"        : _("Hall sensors angle"),
        "Description" : _("""\
The (electric) angle between Hall sensors in your motor. Most \
motors use sensors at 120 degrees, but sometimes this may differ. \
Choose "Auto" if you want the controller to detect this \
automatically.\
"""),
        "Default"     : SA_COMPAT,
        "Widget"      : PWT_COMBOBOX,
        "Range"       : (0, 2),
        "GetDisplay"  : lambda prof, v: SensorAngleDesc [v],
    },
}


class Profile:
    FileName = None
    Description = None

    # Parameter order when loading from .asv files
    ParamLoadOrder = [
        "ControllerType", "PhaseCurrent", "BatteryCurrent", "HaltVoltage", \
        "VoltageTolerance", "LimitedSpeed", "SpeedSwitchMode", "Speed1", "Speed2", \
        "Speed3", "BlockTime", "AutoCruisingTime", "SlipChargeMode", \
        "IndicatorMode", "EBSLevel", "ReverseSpeed", "EBSLimVoltage", \
        "GuardLevel", "ThrottleProtect", "PASMode", "P3Mode", "SensorAngle"
    ]

    # The order of parameters in the profile edit dialog
    ParamEditOrder = [
        [ _("Hardware type") ],
        "ControllerType",

        [ _("Current/Voltage design") ],
        "BatteryCurrent",
        "PhaseCurrent",
        "BlockTime",
        "HaltVoltage",
        "VoltageTolerance",

        [ _("Speed modes") ],
        "SpeedSwitchMode",
        "Speed1",
        "Speed2",
        "Speed3",
        "LimitedSpeed",
        "ReverseSpeed",

        [ _("Regeneration") ],
        "EBSLevel",
        "EBSLimVoltage",
        "SlipChargeMode",

        [ _("External devices") ],
        "SensorAngle",
        "AutoCruisingTime",
        "GuardLevel",
        "ThrottleProtect",
        "PASMode",
        "IndicatorMode",
        "P3Mode",
    ]

    # The order of parameters in raw binary data sent to controller
    ParamRawOrder = [
        2,
        15,
        "PhaseCurrent",
        "BatteryCurrent",
        "HaltVoltage",
        "VoltageTolerance",
        "LimitedSpeed",
        "SpeedSwitchMode",
        "Speed1",
        "Speed2",
        "Speed3",
        "BlockTime",
        "AutoCruisingTime",
        "SlipChargeMode",
        "IndicatorMode",
        "EBSLevel",
        "ReverseSpeed",
        "EBSLimVoltage",
        "GuardLevel",
        "ThrottleProtect",
        "PASMode",
        "P3Mode",
        "SensorAngle",
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
    ]



    def __init__ (self, fn):
        self.SetFileName (fn)
        for parm, desc in ControllerParameters.items ():
            setattr (self, parm, desc ["Default"])


    def SetFileName (self, fn):
        self.FileName = fn
        self.Description = os.path.splitext (os.path.basename (fn)) [0]


    def Load (self, lines):
        vi = 0
        for l in lines:
            # Remove extra shit from the string
            l = l.strip ()
            try:
                l = l [:l.index (":")]
            except ValueError:
                pass

            if vi >= len (ControllerParameters):
                if len (l):
                    raise ValueError, \
                        _("Extra data at the end of file:\n'%(data)s'") % \
                        { "data" : l }
            else:
                parm = self.ParamLoadOrder [vi]
                desc = ControllerParameters [parm]
                if desc ["Type"].find ('i') >= 0:
                    setattr (self, parm, int (l))
                elif desc ["Type"].find ('f') >= 0:
                    setattr (self, parm, float (l))

            vi = vi + 1


    def Save (self):
        lines = []
        for parm in self.ParamLoadOrder:
            desc = ControllerParameters [parm]
            if desc ["Type"].find ('i') >= 0:
                lines.append ("%d" % getattr (self, parm))
            elif desc ["Type"].find ('f') >= 0:
                mask = "%%.%df" % desc.get ("Precision", 1)
                lines.append (mask % getattr (self, parm))

            # Append a CR since the file uses windows line endings
            lines [-1] += '\r'

        return lines


    def GetModel (self):
        if (self.ControllerType > 0) and (self.ControllerType <= len (ControllerTypeDesc)):
            return ControllerTypeDesc [self.ControllerType - 1]["Name"]

        return "???"


    def Remove (self):
        if self.FileName:
            os.remove (self.FileName)


    def Rename (self, newname, isname):
        # If this is just the new profile name, reconstruct dir & extension
        if isname:
            newname = os.path.join (os.path.dirname (self.FileName), \
                newname + os.path.splitext (self.FileName) [1])
        os.rename (self.FileName, newname)
        self.SetFileName (newname)


    def FillParameters (self, vbox):
        rowcidx = 0
        rowcolors = [ gtk.gdk.Color (1.0, 1.0, 1.0), gtk.gdk.Color (1.0, 0.94, 0.86) ]

        self.EditParameters = {}
        self.EditWidgets = {}

        for parm in self.ParamEditOrder:
            if type (parm) == list:
                expd = gtk.Expander (parm [0])
                expd.set_expanded (True)
                expd_vbox = gtk.VBox (False, 1)
                expd.add (expd_vbox)
                vbox.pack_start (expd, False, True, 0)
                continue

            desc = ControllerParameters [parm]

            # Make a copy of parameters for editing
            self.EditParameters [parm] = getattr (self, parm)

            # Place the hbox in a event box to be able to change background color
            evbox = gtk.EventBox ()
            hbox = gtk.HBox (False, 5)
            evbox.add (hbox)
            evbox.set_tooltip_text (desc ["Description"])
            expd_vbox.pack_start (evbox, False, True, 0)

            label = gtk.Label (desc ["Name"])
            label.set_alignment (0.0, 0.5)

            evbox.modify_bg (gtk.STATE_NORMAL, rowcolors [rowcidx])
            rowcidx ^= 1
            hbox.pack_start (label, True, True, 0)

            if desc ["Widget"] == PWT_COMBOBOX:
                minv, maxv = desc ["Range"]
                cb = gtk.combo_box_new_text ()
                for i in range (minv, maxv + 1):
                    cb.append_text (desc ["GetDisplay"] (self, i))
                cb.set_active (self.EditParameters [parm] - minv)
                hbox.pack_start (cb, False, True, 0)
                cb.connect ("changed", self.ComboBoxChangeValue, parm, desc)
                self.EditWidgets [parm] = cb

            elif desc ["Widget"] == PWT_SPINBUTTON:
                minv, maxv = desc ["Range"]
                spin = gtk.SpinButton (climb_rate = 1.0)
                val = desc ["SetDisplay"] (self, self.EditParameters [parm])
                spin.get_adjustment ().configure (val, minv, maxv, 1, 5, 0)
                spin.set_width_chars (7)
                hbox.pack_start (spin, False, True, 0)
                spin.connect ("output", self.SpinButtonOutput, parm, desc)
                spin.connect ("input", self.SpinButtonInput, parm, desc)
                spin.connect ("value-changed", self.SpinButtonValueChanged, parm, desc)
                self.EditWidgets [parm] = spin

        vbox.show_all ()


    def SaveParameters (self):
        for parm, val in self.EditParameters.items ():
            setattr (self, parm, val)


    def ComboBoxChangeValue (self, cb, parm, desc):
        minv, maxv = desc ["Range"]
        self.EditParameters [parm] = minv + cb.get_active ()
        # Check if any depending controls needs updating
        for iparm, idesc in ControllerParameters.items ():
            if idesc.has_key ("Depends"):
                if parm in idesc ["Depends"]:
                    self.EditWidgets [iparm].update ()


    def SpinButtonOutput (self, spin, parm, desc):
        desc = ControllerParameters [parm]
        mask = "%%.%df %s" % (desc.get ("Precision", 1), desc.get ("Units", "").replace ('%', '%%'))
        spin.set_text (mask % desc ["GetDisplay"] (self, spin.props.adjustment.value))
        return True


    # gptr hack, see http://www.mail-archive.com/pygtk@daa.com.au/msg16384.html
    def SpinButtonInput (self, spin, gptr, parm, desc):
        text = spin.get_text ().strip ()
        if desc.has_key ("Units"):
            try:
                text = text [:text.rindex (desc ["Units"])]
            except ValueError:
                pass
        try:
            val = float (desc ["SetDisplay"] (self, float (text.strip ())))
        except ValueError:
            val = spin.props.adjustment.value

        double = ctypes.c_double.from_address (hash (gptr))
        double.value = val
        return True


    # don't allow the displayed value to go below zero
    def SpinButtonValueChanged (self, spin, parm, desc):
        while desc ["GetDisplay"] (self, spin.props.adjustment.value) < 0:
            spin.props.adjustment.value += 1
        val = desc ["GetDisplay"] (self, spin.props.adjustment.value)
        prec = desc.get ("Precision", 1)
        val = round (val * math.pow (10, prec)) / math.pow (10, prec)
        self.EditParameters [parm] = val


    def GetController (self):
        return ControllerTypeDesc [self.EditParameters ["ControllerType"] - 1]


    def BuildRaw (self):
        # Make sure GetController() works correctly
        self.EditParameters = { "ControllerType" : self.ControllerType }

        data = bytearray ()

        for x in self.ParamRawOrder:
            if type (x) == str:
                if ControllerParameters [x].has_key ("ToRaw"):
                    x = ControllerParameters [x]["ToRaw"] (self, getattr (self, x))
                elif ControllerParameters [x]["Widget"] == PWT_COMBOBOX:
                    x = round (getattr (self, x))
                elif ControllerParameters [x]["Widget"] == PWT_SPINBUTTON:
                    x = ControllerParameters [x]["SetDisplay"] (self, getattr (self, x))

            data.append (int (x))

        crc = 0
        for x in data:
            crc = crc ^ x
        data.append (crc)

        return data


    def Upload (self, com_port, progress_func):
        data = self.BuildRaw ()

        try:
            ser = serial.Serial (com_port, 9600, serial.EIGHTBITS, serial.PARITY_NONE,
                serial.STOPBITS_ONE, timeout=0.2)

            progress_func (msg = _("Waiting for controller ready"))
            # Sent '8's and wait for the 'U' response
            while True:
                ser.write ('8')
                c = ser.read ()
                if c == 'U':
                    break

                if len (c) > 0:
                    progress_func (msg = _("Invalid reply byte '%(chr)02x'") % { "chr" : c })
                    return False

                if not progress_func ():
                    return False

            progress_func (msg = _("Waiting acknowledgement"))
            ser.write (data)
            while True:
                c = ser.read ()
                if c == 'U':
                    return True

                if len (c) > 0:
                    progress_func (msg = _("Invalid reply byte '%(chr)02x'") % { "chr" : c })
                    return False

                if not progress_func ():
                    return False

        except serial.SerialException:
            pass

        return False
