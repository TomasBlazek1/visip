from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QTreeWidget
from pyqtgraph import parametertree, TreeWidget
from pyqtgraph.parametertree import ParameterItem

from common import Value
from common.action_instance import ActionInstance
from frontend.graphical_items.g_action import GAction
from frontend.menu.param_menu import ParamMenu
from frontend.parameter_tree_custom.root_param import RootParam
from frontend.parameter_tree_custom.slot_param import SlotParam



class PropertyEditor(parametertree.ParameterTree):
    def __init__(self, g_action=None, parent=None):
        super(PropertyEditor, self).__init__(parent)
        self.g_action = g_action
        self.workflow = None
        self.setHeaderHidden(True)
        self.menu = ParamMenu()
        self.menu.const_val.triggered.connect(self.on_const_val_triggered)
        self.itemDoubleClicked.connect(self.double_clicked)

    def contextMenuEvent(self, ev):
        if len(self.selectedItems()) == 1:
            #self.menu.const_val.setEnabled(not self.g_action.has_const_params())

            self.menu.exec_(ev.globalPos())

    def set_action(self, workflow, g_action):
        if isinstance(g_action, GAction):
            self.workflow = workflow
            self.g_action = g_action
            if g_action is not None:
                action = g_action.w_data_item
                self._action = action
                params = []
                self.update_editor()
            else:
                self._action = None
        else:
            self._action = None
            self.clear()

    def insert_item(self, arg, name="", idx=None):
        temp = SlotParam(arg, name=name, type='group')
        temp.sig_value_changed.connect(self.on_value_changed)
        temp.sig_constant_changed.connect(self.on_constant_changed)
        self.root_item.insertChild(len(self.root_item.children()), temp)

    def update_editor(self):
        i = 0
        self.root_item = RootParam(self.g_action.name)
        for arg in self.g_action.w_data_item.arguments:
            self.insert_item(arg, arg.parameter.name or self.g_action.in_ports[i].name)
            i += 1

        if not self.g_action.has_const_params():
            self.insert_item(None, "Appending Port")
        self.setParameters(self.root_item, showTop=True)

    def on_const_val_triggered(self):
        item = self.selectedItems()[0]
        action = ActionInstance.create(Value(0))
        action.name = 'Value_1'
        i = 2
        while action.name in self.workflow._actions:
            action.name = 'Value_' + str(i)
            i += 1
        if item.param.arg is None:
            i = len(self.g_action.w_data_item.arguments)
            self.workflow.set_action_input(self.g_action.w_data_item, i, action)
        else:
            if not isinstance(item.param.arg.value.action, Value):
                i = self.g_action.w_data_item.arguments.index(item.param.arg)
                conn = self.g_action.in_ports[i].connections[0]
                self.g_action.scene()._delete_connection(conn)
                self.workflow.set_action_input(self.g_action.w_data_item, i, action)
            else:
                item.showEditor()
                return

        self.g_action.scene().data_changed()
        self.update_editor()

    def on_constant_changed(self, param, val: bool):
        action = ActionInstance.create(Value(None)) if not val else None
        i = self.g_action.w_data_item.arguments.index(param.arg)
        self.workflow.set_action_input(self.g_action.w_data_item, i, action)
        temp = self.g_action.childItems()
        self.g_action.update_ports()
        self.update_editor()

    def on_value_changed(self, param, val):
        i = self.g_action.w_data_item.arguments.index(param.arg)
        action = ActionInstance.create(Value(val))
        self.workflow.set_action_input(self.g_action.w_data_item, i, action)
        param.arg = self.g_action.w_data_item.arguments[i]


    def add_argument(self):
        action = ActionInstance.create(Value(None))
        i = len(self.g_action.w_data_item.arguments)
        self.workflow.set_action_input(self.g_action.w_data_item, i, action)
        self.g_action.scene().data_changed()
        self.update_editor()

    def wheelEvent(self, ev):
        pass

    def double_clicked(self, index, col):
        sel = self.selectedItems()
        if len(sel) != 1:
            sel = None
        if self.lastSel is not None and isinstance(self.lastSel, ParameterItem):
            self.lastSel.selected(False)
        if sel is None:
            self.lastSel = None
            return
        self.lastSel = sel[0]
        if hasattr(sel[0], 'selected'):
            sel[0].selected(True)


    def selectionChanged(self, *args):
        sel = self.selectedItems()
        if len(sel) != 1:
            sel = None
        if self.lastSel is not None and isinstance(self.lastSel, ParameterItem):
            self.lastSel.selected(False)
        if sel is None:
            self.lastSel = None
            return
        return TreeWidget.selectionChanged(self, *args)

    def keyPressEvent(self, event):
        if event.key() in [Qt.Key_Enter]:
            self.currentItem().hideEditor()


