#
# Graphical User Interface for XPD
#

import os
import sys
import glob
import copy
import pygtk
import gtk
import gobject
import glib
import gio
from xpdm import VERSION, FNENC, comports, infineon


#-----------------------------------------------------------------------------
#                          The GUI application class
#-----------------------------------------------------------------------------
class Application:
    def __init__ (self, textdomain):
        self.Dead = False

        # Figure out our installation paths
        self.DATADIR = os.path.join (os.path.dirname (os.path.abspath (
            sys.argv [0])), "share").decode (FNENC)
        if not os.path.exists (self.DATADIR):
            self.DATADIR = os.path.join (os.path.normpath (sys.prefix),
                "share/xpd").decode (FNENC)
            if not os.path.exists (self.DATADIR):
                self.DATADIR = os.path.join (os.path.normpath (os.path.join (
                    os.path.dirname (os.path.abspath (sys.argv [0])), "..")),
                    "share/xpd").decode (FNENC)

        if not os.path.exists (self.DATADIR):
            raise SystemExit, _("FATAL: Could not find data directory")

        self.CONFIGDIR = os.path.join (glib.get_user_data_dir ().decode (FNENC), "xpd")
        if not os.access (self.CONFIGDIR, os.F_OK):
            os.makedirs (self.CONFIGDIR, 0700)

        # Load the widgets from the GtkBuilder file
        self.builder = gtk.Builder ()
        self.builder.set_translation_domain (textdomain);
        try:
            self.builder.add_from_file (self.DATADIR + "/gui.xml")
        except RuntimeError, e:
            raise SystemExit (str (e))

        self.builder.connect_signals (self);

        # Cache most used widgets into variables
        for widget in "MainWindow", "AboutDialog", "StatusBar", "ComPortsList", \
            "ProfileList", "EditProfileDialog", "ProfileName", "ParamDescLabel", \
            "ParamVBox" :
            setattr (self, widget, self.builder.get_object (widget))

        # Due to a bug in libglade we can't embed controls into the status bar
        self.ButtonCancelUpload = gtk.Button (stock="gtk-cancel")
        self.StatusBar.pack_end (self.ButtonCancelUpload, False, True, 0)
        self.ButtonCancelUpload.connect ("clicked", self.on_ButtonCancelUpload_clicked)

        alignment = gtk.Alignment (0.5, 0.5)
        self.StatusBar.pack_end (alignment, False, True, 0)
        alignment.show ()

        self.ProgressBar = gtk.ProgressBar ()
        alignment.add (self.ProgressBar)

        self.StatusCtx = self.StatusBar.get_context_id ("")

        self.builder.connect_signals (self);

        self.InitProfileList ()
        self.ScanComPorts ()
        self.LoadProfiles ()

        self.MainWindow.show ()

        self.SetStatus (_("Ready"))


# -- # -- # -- # -- # -- # -- # -- # -- # -- # -- # -- # -- # -- # -- # -- #


    def ClearChildren (self, widget, vbox):
        vbox.remove (widget)


    def SetStatus (self, msg):
        if not self.Dead:
            self.StatusBar.pop (self.StatusCtx)
            self.StatusBar.push (self.StatusCtx, msg)


    def Message (self, typ, msg):
        d = gtk.MessageDialog (None, gtk.DIALOG_MODAL, typ, gtk.BUTTONS_CLOSE, msg)
        d.run ()
        d.destroy ()


    def InitProfileList (self):
        self.ProfileListStore = gtk.ListStore (str, str, str, object)

        self.ProfileList.set_model (self.ProfileListStore)

        column = gtk.TreeViewColumn (_("Family"), gtk.CellRendererText (), text = 0)
        column.set_sizing (gtk.TREE_VIEW_COLUMN_FIXED)
        column.set_resizable (True)
        column.set_sort_column_id (0)
        column.set_min_width (100)
        self.ProfileList.append_column (column)

        column = gtk.TreeViewColumn (_("Model"), gtk.CellRendererText (), text = 1)
        column.set_sizing (gtk.TREE_VIEW_COLUMN_FIXED)
        column.set_resizable (True)
        column.set_sort_column_id (1)
        column.set_min_width (120)
        self.ProfileList.append_column (column)

        column = gtk.TreeViewColumn (_("Description"), gtk.CellRendererText (), text = 2)
        column.set_sizing (gtk.TREE_VIEW_COLUMN_FIXED)
        column.set_resizable (True)
        column.set_sort_column_id (2)
        self.ProfileList.append_column (column)

        self.ProfileListStore.set_sort_column_id (1, gtk.SORT_ASCENDING)


    def ScanComPorts (self):
        store = gtk.ListStore (str)
        cell = gtk.CellRendererText ()
        self.ComPortsList.pack_start (cell, True)
        self.ComPortsList.add_attribute (cell, 'text', 0)

        for order, port, desc, hwid in sorted (comports ()):
            store.append ([port])

        self.ComPortsList.set_model (store)
        self.ComPortsList.set_active (0)


    def UpdateProgress (self, pos = None, msg = None):
        if msg != None:
            self.SetStatus (msg)
        if pos == None:
            self.ProgressBar.pulse ()
        else:
            self.ProgressBar.set_fraction (pos)
        while gtk.events_pending ():
            gtk.main_iteration ()

        return not (self.UploadCancelled or self.Dead)


    def EditProfile (self, prof, isnew):
        self.ProfileName.set_text (prof.Description)
        prof.FillParameters (self.ParamVBox)

        self.EditProfileDialog.show ()
        if self.EditProfileDialog.run () == gtk.RESPONSE_APPLY:
            if isnew:
                prof.SetFileName (os.path.join (self.CONFIGDIR, \
                    self.ProfileName.get_text ().strip () + ".asv"))

            prof.SaveParameters ()
            lines = prof.Save ()

            # Save profile, if we have enough access rights
            try:
                f = open (prof.FileName, "wb")
                f.write ('\n'.join (lines) + '\n')
                f.close ()
                self.SetStatus (_("Profile saved"))
            except IOError, e:
                self.Message (gtk.MESSAGE_ERROR, \
                    _("Failed to save profile %(desc)s:\n%(msg)s") % \
                    { "desc" : prof.Description, "msg" : e })
                self.SetStatus (_("Failed to save profile"))

            # Rename profile, if profile name changed
            try:
                newname = self.ProfileName.get_text ().strip ()
                if newname != prof.Description:
                    prof.Rename (newname, True)
                    self.SetStatus (_("Profile renamed"))
            except OSError, e:
                self.Message (gtk.MESSAGE_ERROR, \
                    _("Failed to rename profile %(desc)s:\n%(msg)s") % \
                    { "desc" : prof.Description, "msg" : e })
                self.SetStatus (_("Failed to rename profile"))

            self.RefreshProfiles ()

        self.EditProfileDialog.hide ()

        self.ParamVBox.foreach (self.ClearChildren, self.ParamVBox)


    def LoadProfiles (self, sel=None):
        model = self.ProfileList.get_model ()
        if not sel:
            sel = self.ProfileList.get_selection ().get_selected () [1]
            if sel:
                sel = model [sel] [2]

        self.ProfileListStore.clear ()
        for x in glob.glob (os.path.join (self.DATADIR, "*.asv")) + \
                 glob.glob (os.path.join (self.CONFIGDIR, "*.asv")):
            try:
                prof = self.LoadProfile (x, infineon.Profile)
                self.ProfileListStore.append ((_("Infineon"), \
                    prof.GetModel (), prof.Description, prof))
            except ValueError, e:
                self.Message (gtk.MESSAGE_WARNING, \
                    _("Failed to load profile %(fn)s:\n%(msg)s") % \
                    { "fn" : x, "msg" : e })

        if sel:
            i = model.get_iter_first ()
            while i:
                if model [i] [2] == sel:
                    self.ProfileList.get_selection ().select_iter (i)
                    break
                i = model.iter_next (i)


    def RefreshProfiles (self):
        for x in self.ProfileListStore:
            x [1] = x [3].GetModel ()
            x [2] = x [3].Description


    def LoadProfile (self, fn, profclass):
        f = file (fn, "r")
        prof = profclass (fn)
        prof.Load (f.readlines ())

        return prof


# -- # -- # -- # -- # -- # -- # -- # -- # -- # -- # -- # -- # -- # -- # -- #


    def on_MainWindow_destroy (self, win):
        self.Dead = True
        self.UploadCancelled = True
        gtk.main_quit ()


    def on_ButtonCancelUpload_clicked (self, but):
        self.UploadCancelled = True


    def on_ButtonApply_clicked (self, but):
        sel = self.ProfileList.get_selection ().get_selected () [1]
        if not sel:
            self.SetStatus (_("No profile selected"))
            return

        serport = self.ComPortsList.get_active_text ()
        if not serport:
            self.SetStatus (_("No serial port selected"))
            return

        prof = self.ProfileListStore [sel] [3]

        self.UploadCancelled = False
        self.SetStatus (_("Uploading settings to controller"))
        self.ProgressBar.show ()
        self.ButtonCancelUpload.show ()
        self.ButtonCancelUpload.grab_add ()
        self.MainWindow.set_deletable (False)

        try:
            if prof.Upload (serport, self.UpdateProgress):
                self.SetStatus (_("Settings uploaded successfully"))

        except Exception, e:
            self.SetStatus (_("Upload failed: %(msg)s") % { "msg" : str (e) })

        self.MainWindow.set_deletable (True)
        self.ButtonCancelUpload.grab_remove ()
        self.ButtonCancelUpload.hide ()
        self.ProgressBar.hide ()


    def on_ButtonEdit_clicked (self, but):
        sel = self.ProfileList.get_selection ().get_selected () [1]
        if not sel:
            return

        prof = self.ProfileListStore [sel] [3]
        self.EditProfile (prof, False)


    def on_ButtonCreate_clicked (self, but):
        prof = infineon.Profile (_("New profile"))
        self.EditProfile (prof, True)
        self.LoadProfiles (prof.Description)


    def on_ButtonCopy_clicked (self, but):
        sel = self.ProfileList.get_selection ().get_selected () [1]
        if not sel:
            return

        prof = copy.copy (self.ProfileListStore [sel] [3])
        prof.Description = _("New ") + prof.Description
        self.EditProfile (prof, True)
        self.LoadProfiles (prof.Description)


    def on_ButtonDelete_clicked (self, but):
        sel = self.ProfileList.get_selection ().get_selected () [1]
        if not sel:
            return

        prof = self.ProfileListStore [sel] [3]

        d = gtk.MessageDialog (None, \
            gtk.DIALOG_MODAL, gtk.MESSAGE_WARNING, gtk.BUTTONS_OK_CANCEL, \
            _("Are you sure you want to delete profile \"%s\"?") % prof.Description)
        rc = d.run ()
        d.destroy ()
        if rc == gtk.RESPONSE_OK:
            try:
                prof.Remove ()
                self.ProfileListStore.remove (sel)
                self.SetStatus (_("Profile deleted"))
            except:
                self.Message (gtk.MESSAGE_ERROR, \
                    _("Failed to remove profile file %(fn)s") % \
                    { "fn" : prof.FileName })
                self.SetStatus (_("Failed to delete profile"))


    def on_ButtonAbout_clicked (self, but):
        self.AboutDialog.set_version (VERSION)
        self.AboutDialog.run ()
        self.AboutDialog.hide ()
