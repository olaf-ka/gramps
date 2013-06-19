#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2013       Benny Malengier
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#

# $Id$

#-------------------------------------------------------------------------
#
# Python modules
#
#-------------------------------------------------------------------------
from gramps.gen.const import GRAMPS_LOCALE as glocale
_ = glocale.translation.gettext

#-------------------------------------------------------------------------
#
# GTK libraries
#
#-------------------------------------------------------------------------
from gi.repository import Gdk
from gi.repository import Gtk

#-------------------------------------------------------------------------
#
# Gramps libraries
#
#-------------------------------------------------------------------------
from gramps.gen.lib.srcattrtype import (SrcAttributeType, REF_TYPE_F, 
                                REF_TYPE_S, REF_TYPE_L, EMPTY)
from gramps.gen.lib import SrcAttribute, SrcTemplate
from ...autocomp import StandardCustomSelector
from ...widgets.srctemplatetreeview import SrcTemplateTreeView
from ...widgets import UndoableEntry, MonitoredEntryIndicator
from .grampstab import GrampsTab

#-------------------------------------------------------------------------
#
# Classes
#
#-------------------------------------------------------------------------
class SrcTemplateTab(GrampsTab):
    """
    This class provides the tabpage for template generation of attributes.
    """
    def __init__(self, dbstate, uistate, track, src, glade,
                 callback_src_changed):
        """
        @param dbstate: The database state. Contains a reference to
        the database, along with other state information. The GrampsTab
        uses this to access the database and to pass to and created
        child windows (such as edit dialogs).
        @type dbstate: DbState
        @param uistate: The UI state. Used primarily to pass to any created
        subwindows.
        @type uistate: DisplayState
        @param track: The window tracking mechanism used to manage windows.
        This is only used to pass to generted child windows.
        @type track: list
        @param src: source which we manage in this tab
        @type src: gen.lib.Source
        @param glade: glade objects with the needed widgets
        """
        self.src = src
        self.glade = glade
        self.callback_src_changed = callback_src_changed
        self.readonly = dbstate.db.readonly

        self.autoset_title = False

        GrampsTab.__init__(self, dbstate, uistate, track, _("Source Template"))
        eventbox = Gtk.EventBox()
        widget = self.glade.get_object('gridtemplate')
        eventbox.add(widget)
        self.pack_start(eventbox, True, True, 0)
        self._set_label(show_image=False)
        widget.connect('key_press_event', self.key_pressed)
        
        self.tmplfields = TemplateFields(self.dbstate.db,
                self.glade.get_object('gridfields'),
                self.src, None, self.callback_src_changed, None)
        self.autotitle = self.glade.get_object("autotitle_checkbtn")
        #self.vbox_fields_label = self.glade.get_object('fields_01')
        #self.vbox_fields_input = self.glade.get_object('fields_02')
        self.setup_interface(self.glade.get_object('scrolledtemplates'))
        self.show_all()

    def make_active(self):
        """
        Called by using editor to focus on correct field in the tab
        """
        self.temp_tv.grab_focus()

    def is_empty(self):
        """
        Override base class
        """
        return False

    def setup_interface(self, scrolled):
        """
        Set all information on the widgets
        * template selection
        * setting attribute fields
        
        :param scrolled: GtkScrolledWindow to which to add treeview with templates
        """
        srcattr = SrcAttributeType()
        templ = self.src.get_source_template()
        self.temp_tv = SrcTemplateTreeView(templ[2],
                                sel_callback=self.on_template_selected)
        scrolled.add(self.temp_tv)
        
        #autotitle checkbox
        self.autotitle.set_active(self.autotitle_get_orig_val())
        self.autotitle.set_sensitive(not self.dbstate.db.readonly)
        self.autotitle.connect('toggled', self.autotitle_on_toggle)

    def autotitle_get_orig_val(self):
        """
        If title of the source is what we would set with autotitle, we set
        the checkbox to true. Otherwise to False
        """
        srctemp = SrcTemplate(self.src.get_source_template()[0])
        srctemp.set_attr_list(self.src.get_attribute_list())
        title = srctemp.title_gedcom()
        if self.src.get_title() == title:
            self.autoset_title = True
        else:
            self.autoset_title = False
        return self.autoset_title

    def autotitle_on_toggle(self, obj):
        """ the autoset_title attribute will be used in editsource to 
        determine that title must be set
        """
        self.autoset_title = obj.get_active()
        #it might be that the title must be changed, so we trigger the callback
        # which will update the title in the source object
        self.callback_src_changed()

    def on_template_selected(self, index, key):
        """
        Selected template changed, we save this and update interface
        """
        self.src.set_source_template(index, key)
        self.callback_src_changed(templatechanged=True)
        
        #a predefined template, 
        self.tmplfields.reset_template_fields(index)

#-------------------------------------------------------------------------
#
# TemplateFields Class
#
#-------------------------------------------------------------------------
class TemplateFields(object):
    """
    Class to manage fields of a source template.
    Can be used on source and on citation level.
    """
    def __init__(self, db, grid, src, cite, callback_src_changed,
                 callback_cite_changed):
        """
        grid: The Gtk.Grid that should hold the fields
        src : The source to which the fields belong
        cite: The citation to which the fields belong (set None if only source)
        """
        self.gridfields = grid
        self.db = db
        self.src = src
        self.cite = cite
        self.callback_src_changed = callback_src_changed
        self.callback_cite_changed = callback_cite_changed
        
        #storage
        self.lbls = []
        self.inpts = []
        self.monentry = []

    def reset_template_fields(self, index):
        """
        Method that constructs the actual fields where user can enter data.
        Template must be the index of the template.
        """
        #obtain the template of the index
        srcattr = SrcAttributeType()
        if index in srcattr.EVIDENCETEMPLATES:
            #a predefined template, 
            template = srcattr.EVIDENCETEMPLATES[index]
        else:
            return
        
        # first remove old fields
        for lbl in self.lbls:
            self.gridfields.remove(lbl)
        for inpt in self.inpts:
            self.gridfields.remove(inpt)
        for mon in self.monentry:
            del mon
        self.lbls = []
        self.inpts = []
        self.monentry = []
        row = 1
        # now add new fields
        fieldsL = []
        for fielddef in template[REF_TYPE_L]:
            hint = fielddef[9] or SrcAttributeType.get_default_hint(fielddef[1])
            
            fieldsL.append(fielddef[1])
            if self.cite is None:
                #these are source fields
                self._add_entry(row, fielddef[1], fielddef[2],
                    fielddef[9] or SrcAttributeType.get_default_hint(fielddef[1]),
                    fielddef[10] or SrcAttributeType.get_default_tooltip(fielddef[1]))
                row += 1

        tempsattrt = SrcAttributeType()
        # now add optional short citation values
        if self.cite is None:
            fieldsS = [fielddef for fielddef in template[REF_TYPE_S] 
                            if fielddef[1] in fieldsL and fielddef[7]==EMPTY]
            if fieldsS:
                self.gridfields.insert_row(row)
                lbl = Gtk.Label('')
                lbl.set_markup(_("<b>Optional Short Versions:</b>"))
                lbl.set_halign(Gtk.Align.START)
                self.gridfields.attach(lbl, 0, row-1, 2, 1)
                self.lbls.append(lbl)
                row += 1
            for fielddef in fieldsS:
                lblval = fielddef[2]
                if lblval:
                    lblval = _('%(normal_version_label)s (Short)') % {
                                'normal_version_label': lblval}
                self._add_entry(row, tempsattrt.short_version(fielddef[1]), lblval)
                row += 1

        # now add citation values (optional on source level)
        fieldsF = [fielddef for fielddef in template[REF_TYPE_F] 
                                            if fielddef[1] not in fieldsL]
        if fieldsF and self.cite is None:
            self.gridfields.insert_row(row)
            lbl = Gtk.Label('')
            lbl.set_markup(_("<b>Optional Default Citation Fields:</b>"))
            lbl.set_halign(Gtk.Align.START)
            self.gridfields.attach(lbl, 0, row-1, 2, 1)
            self.lbls.append(lbl)
            row += 1
        for fielddef in fieldsF:
            self._add_entry(row, fielddef[1], fielddef[2],
                    fielddef[9] or SrcAttributeType.get_default_hint(fielddef[1]),
                    fielddef[10] or SrcAttributeType.get_default_tooltip(fielddef[1]))
            row += 1
        fieldsS = [fielddef for fielddef in template[REF_TYPE_S] 
                            if fielddef[1] not in fieldsL and fielddef[7]==EMPTY]
        if not self.cite is None:
            #we indicate with a text these are the short versions
            if fieldsS:
                self.gridfields.insert_row(row)
                lbl = Gtk.Label('')
                lbl.set_markup(_("<b>Optional Short Versions:</b>"))
                lbl.set_halign(Gtk.Align.START)
                self.gridfields.attach(lbl, 0, row-1, 2, 1)
                self.lbls.append(lbl)
                row += 1
        for fielddef in fieldsS:
            lblval = fielddef[2]
            if lblval:
                lblval = _('%(normal_version_label)s (Short)') % {
                                'normal_version_label': lblval}
            self._add_entry(row, tempsattrt.short_version(fielddef[1]), lblval)
            row += 1

        self.gridfields.show_all()

    def _add_entry(self, row, srcattrtype, alt_label, hint=None, tooltip=None):
        """
        Add an entryfield to the grid of fields at row row, to edit the given
        srcattrtype value. Use alt_label if given to indicate the field
        (otherwise the srcattrtype string description is used)
        Note srcattrtype should actually be the integer key of the type!
        """
        self.gridfields.insert_row(row)
        field = srcattrtype
        #setup label
        if alt_label:
            label = alt_label
        else:
            srcattr = SrcAttributeType(field)
            label = str(srcattr)
        lbl = Gtk.Label(_("%s:") % label)
        lbl.set_halign(Gtk.Align.START)
        self.gridfields.attach(lbl, 0, row-1, 1, 1)
        self.lbls.append(lbl)
        #setup entry
        inpt = UndoableEntry()
        inpt.set_halign(Gtk.Align.FILL)
        inpt.set_hexpand(True)
        if tooltip:
            inpt.set_tooltip_text(tooltip)
        self.gridfields.attach(inpt, 1, row-1, 1, 1)
        self.inpts.append(inpt)
        if self.cite:
            MonitoredEntryIndicator(inpt, self.set_cite_field, self.get_cite_field,
                           hint or "",
                           read_only=self.db.readonly, 
                           parameter=srcattrtype)
        else:
            MonitoredEntryIndicator(inpt, self.set_src_field, self.get_src_field,
                           hint or "",
                           read_only=self.db.readonly, 
                           parameter=srcattrtype)

    def get_src_field(self, srcattrtype):
        return self.__get_field(srcattrtype, self.src)

    def get_cite_field(self, srcattrtype):
        return self.__get_field(srcattrtype, self.cite)

    def __get_field(self, srcattrtype, obj):
        """
        Obtain srcattribute with type srcattrtype, where srcattrtype is an
        integer key!
        """
        val = ''
        for attr in obj.attribute_list:
            if int(attr.get_type()) == srcattrtype:
                val = attr.get_value()
                break
        return val

    def set_src_field(self, value, srcattrtype):
        self.__set_field(value, srcattrtype, self.src)
        #indicate source object changed
        self.callback_src_changed()

    def set_cite_field(self, value, srcattrtype):
        self.__set_field(value, srcattrtype, self.cite)
        #indicate source object changed
        self.callback_cite_changed()

    def __set_field(self, value, srcattrtype, obj):
        """
        Set attribute of source of type srcattrtype (which is integer!) to 
        value. If not present, create attribute. If value == '', remove
        """
        value = value.strip()
        foundattr = None
        for attr in obj.attribute_list:
            if int(attr.get_type()) == srcattrtype:
                attr.set_value(value)
                foundattr = attr
                break
        if foundattr and value == '':
            obj.remove_attribute(foundattr)
        if foundattr is None and value != '':
            foundattr = SrcAttribute()
            foundattr.set_type(srcattrtype)
            foundattr.set_value(value)
            obj.add_attribute(foundattr)

##    def setup_autocomp_combobox(self):
##        """
##        Experimental code to set up a combobox with all templates.
##        This is too slow, we use treeview in second attempt
##        """
##        self.srctempcmb = Gtk.ComboBox(has_entry=True)
##        ignore_values = []
##        custom_values = []
##        srcattr = SrcAttributeType()
##        default = srcattr.get_templatevalue_default()
##        maptempval = srcattr.get_templatevalue_map().copy()
##        if ignore_values :
##            for key in list(maptempval.keys()):
##                if key in ignore_values and key not in (None, default):
##                    del map[key]
##
##        self.sel = StandardCustomSelector(
##            maptempval, 
##            self.srctempcmb, 
##            srcattr.get_custom(), 
##            default, 
##            additional=custom_values)
##
##        templ = self.src.get_source_template()
##        self.sel.set_values((templ[0], templ[1]))
##        self.srctempcmb.set_sensitive(not self.readonly)
##        self.srctempcmb.connect('changed', self.on_change_template)
##        srctemphbox.pack_start(self.srctempcmb, False, True, 0)
##        
##        return topvbox

##    def fix_value(self, value):
##        if value[0] == SrcAttributeType.CUSTOM:
##            return value
##        else:
##            return (value[0], '')
##
##    def on_change_template(self, obj):
##        #value = self.fix_value(self.srctempcmb.get_values())
##        value = self.sel.get_values()
##        self.src.set_source_template(value[0], value[1])
