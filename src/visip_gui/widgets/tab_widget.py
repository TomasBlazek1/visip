import os

from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QTabWidget

from visip_gui.config.config_data import ConfigData
from visip_gui.widgets.home_tab_widget import HomeTabWidget
from visip_gui.widgets.module_view import ModuleView
from visip.dev.module import Module
from visip_gui.widgets.tab import Tab


class TabWidget(QTabWidget):
    def __init__(self, main_widget, edit_menu, parent=None):
        super(TabWidget, self).__init__(parent)
        self.cfg = ConfigData()
        self.setTabsClosable(True)
        self.setTabShape(1)
        self.tabCloseRequested.connect(self.on_close_tab)
        self.edit_menu = edit_menu
        self.edit_menu.delete.triggered.connect(self.delete_items)
        #self.edit_menu.add_random.triggered.connect(self.add_random_items)
        self.edit_menu.order_diagram.triggered.connect(self.order_diagram)
        self.currentChanged.connect(self.current_changed)
        self.tabBarClicked.connect(self.before_curr_index_change)

        self.main_widget = main_widget

        self.module_views = {}

        self.initial_tab_name = 'Home'
        self.home_tab = HomeTabWidget(self.main_widget)
        self.addTab(self.home_tab, self.initial_tab_name)

    def before_curr_index_change(self, index):
        if isinstance(self.currentWidget(), Tab):
            self.currentWidget().last_category = self.main_widget.toolbox.currentIndex()

    def _add_tab(self, module_filename, module):
        self.module_views[module_filename] = ModuleView(self, module,self.edit_menu)
        w = Tab(self.module_views[module_filename])
        #self.main_widget.toolbox.on_workspace_change(self.module_views[module_filename].module,
        #                                             self.module_views[module_filename]._current_workspace)
        for name, workspace in self.module_views[module_filename].workspaces.items():
            w.addWidget(workspace)

        self.setCurrentIndex(self.addTab(w, module_filename))

    def change_workspace(self, workspace):
        self.currentWidget().setCurrentWidget(workspace)
        workspace.workflow.update(workspace.workflow._result_call)
        self.main_widget.property_editor.clear()

    def create_new_module(self, module_name=None):
        if not isinstance(module_name, str):
            filename = QtWidgets.QFileDialog.getSaveFileName(self.parent(), "New Module", self.cfg.last_opened_directory)[0]
        if filename != "":
            self.cfg.last_opened_directory = os.path.dirname(filename)
            if not filename.endswith(".py"):
                filename = filename + ".py"
            with open(filename, "w") as file:
                file.write("import visip as wf")
            module = Module(filename)
            self._add_tab(os.path.basename(filename), module)

    def open_module(self, filename=None):
        if not isinstance(filename, str):
            filename = QtWidgets.QFileDialog.getOpenFileName(self.parent(), "Select Module", self.cfg.last_opened_directory)[0]
        if filename != "":
            self.cfg.last_opened_directory = os.path.dirname(filename)
            module = Module(filename)
            self._add_tab(os.path.basename(filename), module)

    def current_changed(self, index):
        if index != -1 and isinstance(self.widget(index), Tab):
            curr_module_view = self.module_views[self.tabText(index)]
            self.disable_everything(False)
            self.main_widget.module_dock.setWidget(curr_module_view)
            self.main_widget.toolbox_dock.setWidget(self.main_widget.toolbox)

            self.main_widget.toolbox.on_module_change(curr_module_view.module,
                                                      curr_module_view._current_workspace)
            self.main_widget.toolbox.setCurrentIndex(self.currentWidget().last_category)
            return

        self.disable_everything(True)
        self.main_widget.module_dock.setWidget(None)
        self.main_widget.toolbox_dock.setWidget(None)

    def disable_everything(self, boolean):
        self.main_widget.toolbox_dock.setDisabled(boolean)
        self.main_widget.module_dock.setDisabled(boolean)
        self.main_widget.edit_menu.setDisabled(boolean)
        self.main_widget.eval_menu.setDisabled(boolean)
        self.main_widget.property_editor.setDisabled(boolean)

    def current_module_view(self):
        return self.module_views[self.tabText(self.currentIndex())]

    def on_close_tab(self, index):
        self.module_views.pop(self.tabText(index), None)
        self.removeTab(index)

    def current_workspace(self):
        return self.currentWidget().currentWidget()

    def add_action(self):
        self.current_workspace().scene.add_action(self.current_workspace().scene.new_action_pos)

    def delete_items(self):
        self.current_workspace().scene.delete_items()

    def add_random_items(self):
        self.current_workspace().scene.add_random_items()

    def order_diagram(self):
        self.current_workspace().scene.order_diagram()


