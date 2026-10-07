import sys
import json
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QLabel, QStackedWidget,
                             QListWidget, QListWidgetItem, QMessageBox,
                             QLineEdit, QInputDialog, QDialog, QDialogButtonBox,
                             QMenu, QGridLayout, QDoubleSpinBox, QTextEdit)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor


class ArrayDisplayDialog(QDialog):
    """Display an array with clipboard-copy controls."""

    def __init__(self, data, parent=None):
        """Initialize array display dialog dependencies and internal state."""
        super().__init__(parent)
        self.setWindowTitle("旋涂参数数组")
        self.setFixedSize(600, 500)

        layout = QVBoxLayout(self)

        # Title.
        title_label = QLabel("导出的旋涂参数数组")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        # Description.
        desc_label = QLabel("以下是可以直接在其他Python代码中使用的数组：")
        desc_label.setFont(QFont("Microsoft YaHei", 10))
        layout.addWidget(desc_label)

        # Display the array in a text editor.
        self.text_edit = QTextEdit()
        self.text_edit.setFont(QFont("Consolas", 10))  # Use a monospaced font.
        self.text_edit.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)

        # Format the array for display.
        formatted_data = self.format_array(data)
        self.text_edit.setPlainText(formatted_data)

        layout.addWidget(self.text_edit, 1)  # Set stretch weights to permit expansion.

        # Button area.
        button_layout = QHBoxLayout()

        copy_button = QPushButton("复制到剪贴板")
        copy_button.setFixedSize(120, 35)
        copy_button.clicked.connect(self.copy_to_clipboard)

        close_button = QPushButton("关闭")
        close_button.setFixedSize(120, 35)
        close_button.clicked.connect(self.close)

        button_layout.addWidget(copy_button)
        button_layout.addStretch()
        button_layout.addWidget(close_button)

        layout.addLayout(button_layout)

        self.data = data

    def format_array(self, data):
        """Format an array as readable text."""
        if not data:
            return "# 当前没有旋涂参数数据\n[]"

        result = ["# 旋涂参数数组结构说明:"]
        result.append("# 外层列表: 所有工作任务")
        result.append("# 内层列表: 单个任务中的所有旋涂操作")
        result.append("# 最内层列表: [最大速度(rpm), 旋涂时间(s), 加速时间(s), 减速时间(s)]")
        result.append("")
        result.append("spin_coating_parameters = [")

        for i, task_data in enumerate(data):
            result.append("    [  # 任务 {}".format(i + 1))
            for j, spin_params in enumerate(task_data):
                result.append("        [{}, {}, {}, {}],  # 旋涂操作 {}".format(
                    spin_params[0], spin_params[1], spin_params[2], spin_params[3], j + 1
                ))
            if i < len(data) - 1:
                result.append("    ],")
            else:
                result.append("    ]")

        result.append("]")

        return "\n".join(result)

    def copy_to_clipboard(self):
        """Copy the displayed array to the clipboard."""
        clipboard = QApplication.clipboard()
        clipboard.setText(self.text_edit.toPlainText())

        # Display confirmation of clipboard copying.
        self.show_copy_success()

    def show_copy_success(self):
        """Temporarily display confirmation that copying succeeded."""
        success_label = QLabel("✓ 已复制到剪贴板！")
        success_label.setStyleSheet("color: green; font-weight: bold;")
        success_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Show a temporary confirmation.
        layout = self.layout()
        layout.insertWidget(layout.count() - 1, success_label)  # Insert the message before the button.

        # Remove the confirmation after 3 seconds.
        QTimer.singleShot(3000, success_label.deleteLater)


class Process:
    """Store one legacy process operation and its parameters."""

    def __init__(self, name, parameters=None):
        """Initialize process dependencies and internal state."""
        self.name = name
        self.parameters = parameters or {}  # Store process parameters.

    def __str__(self):
        """Str."""
        if self.parameters:
            params_str = ", ".join([f"{k}: {v}" for k, v in self.parameters.items()])
            return f"{self.name} ({params_str})"
        return self.name


class Task:
    """Group legacy processes with an execution repetition count."""

    def __init__(self, name, processes=None, execution_count=1, completed_count=0):
        """Initialize task dependencies and internal state."""
        self.name = name
        self.processes = processes or []
        self.execution_count = execution_count
        self.completed_count = completed_count  # Completed repetition count.

    def add_process(self, process):
        """Add process."""
        self.processes.append(process)

    @property
    def remaining_count(self):
        """Return the number of task repetitions still required."""
        return max(0, self.execution_count - self.completed_count)


class SpinCoatingDialog(QDialog):
    """Collect and validate spin coating parameters in a dialog."""

    def __init__(self, parent=None):
        """Initialize spin coating dialog dependencies and internal state."""
        super().__init__(parent)
        self.setWindowTitle("设置旋涂参数")
        self.setFixedSize(400, 300)

        layout = QVBoxLayout(self)

        # Title.
        title_label = QLabel("旋涂参数设置")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        # Parameter input area.
        params_layout = QGridLayout()
        params_layout.setSpacing(15)

        # Maximum speed setting.
        max_speed_label = QLabel("最大速度 (rpm):")
        max_speed_label.setFont(QFont("Microsoft YaHei", 11))
        self.max_speed_spin = QDoubleSpinBox()
        self.max_speed_spin.setRange(100, 10000)
        self.max_speed_spin.setValue(3000)
        self.max_speed_spin.setSuffix(" rpm")
        self.max_speed_spin.setFont(QFont("Microsoft YaHei", 11))
        params_layout.addWidget(max_speed_label, 0, 0)
        params_layout.addWidget(self.max_speed_spin, 0, 1)

        # Spin duration setting.
        spin_time_label = QLabel("旋涂时间 (s):")
        spin_time_label.setFont(QFont("Microsoft YaHei", 11))
        self.spin_time_spin = QDoubleSpinBox()
        self.spin_time_spin.setRange(1, 600)
        self.spin_time_spin.setValue(30)
        self.spin_time_spin.setSuffix(" s")
        self.spin_time_spin.setFont(QFont("Microsoft YaHei", 11))
        params_layout.addWidget(spin_time_label, 1, 0)
        params_layout.addWidget(self.spin_time_spin, 1, 1)

        # Acceleration time setting.
        accel_time_label = QLabel("加速时间 (s):")
        accel_time_label.setFont(QFont("Microsoft YaHei", 11))
        self.accel_time_spin = QDoubleSpinBox()
        self.accel_time_spin.setRange(1, 60)
        self.accel_time_spin.setValue(5)
        self.accel_time_spin.setSuffix(" s")
        self.accel_time_spin.setFont(QFont("Microsoft YaHei", 11))
        params_layout.addWidget(accel_time_label, 2, 0)
        params_layout.addWidget(self.accel_time_spin, 2, 1)

        # Deceleration time setting.
        decel_time_label = QLabel("减速时间 (s):")
        decel_time_label.setFont(QFont("Microsoft YaHei", 11))
        self.decel_time_spin = QDoubleSpinBox()
        self.decel_time_spin.setRange(1, 60)
        self.decel_time_spin.setValue(5)
        self.decel_time_spin.setSuffix(" s")
        self.decel_time_spin.setFont(QFont("Microsoft YaHei", 11))
        params_layout.addWidget(decel_time_label, 3, 0)
        params_layout.addWidget(self.decel_time_spin, 3, 1)

        layout.addLayout(params_layout)

        # Button area.
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def get_parameters(self):
        """Return the parameters currently entered in the dialog."""
        return {
            "最大速度": self.max_speed_spin.value(),
            "旋涂时间": self.spin_time_spin.value(),
            "加速时间": self.accel_time_spin.value(),
            "减速时间": self.decel_time_spin.value()
        }


class CountEditDialog(QDialog):
    """Edit a task repetition count."""

    def __init__(self, task_name, current_count=1, is_new_selection=False, parent=None):
        """Initialize count edit dialog dependencies and internal state."""
        super().__init__(parent)

        if is_new_selection:
            self.setWindowTitle("设置执行次数")
            prompt = f"请设置任务 '{task_name}' 的执行次数:"
        else:
            self.setWindowTitle("修改执行次数")
            prompt = f"修改任务 '{task_name}' 的执行次数:"

        self.setFixedSize(350, 180)

        layout = QVBoxLayout(self)

        # Hint label.
        label = QLabel(prompt)
        label_font = QFont()
        label_font.setPointSize(12)
        label.setFont(label_font)
        layout.addWidget(label)

        # Input field.
        input_layout = QHBoxLayout()
        input_label = QLabel("执行次数:")
        input_label.setFont(QFont("Microsoft YaHei", 12))

        self.count_edit = QLineEdit(str(current_count))
        self.count_edit.setFont(QFont("Microsoft YaHei", 12))
        self.count_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.count_edit.setFixedWidth(80)

        input_layout.addWidget(input_label)
        input_layout.addWidget(self.count_edit)
        input_layout.addStretch()

        layout.addLayout(input_layout)

        # Buttons.
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.validate_and_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.result_count = current_count

    def validate_and_accept(self):
        """Validate input fields and accept the dialog on success."""
        try:
            text = self.count_edit.text().strip()
            if text:
                count = int(text)
                if count > 0 and count <= 1000:
                    self.result_count = count
                    self.accept()
                else:
                    QMessageBox.warning(self, "输入错误", "执行次数必须在1-1000之间")
            else:
                QMessageBox.warning(self, "输入错误", "请输入执行次数")
        except ValueError:
            QMessageBox.warning(self, "输入错误", "请输入有效的数字")

    def get_count(self):
        """Get count."""
        return self.result_count


class TaskDetailWindow(QMainWindow):
    """Display and edit the processes belonging to a task."""

    def __init__(self, task, parent=None):
        """Initialize task detail window dependencies and internal state."""
        super().__init__(parent)
        self.task = task
        self.setWindowTitle(f"任务详情 - {task.name}")
        # Enlarge the window so all content is visible.
        self.setFixedSize(900, 750)

        # Apply the style.
        self.setup_style()

        # Create the central widget.
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Create the main layout.
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(12)

        # Title bar.
        title_bar = self.create_title_bar()
        main_layout.addWidget(title_bar)

        # Task information.
        task_info = self.create_task_info()
        main_layout.addWidget(task_info)

        # Give the process list more space.
        process_list = self.create_process_list()
        main_layout.addWidget(process_list, 1)  # Use stretch weight 1 so the area can expand.

        # Operation button area.
        operation_buttons = self.create_operation_buttons()
        main_layout.addWidget(operation_buttons)

        # Bottom buttons.
        bottom_buttons = self.create_bottom_buttons()
        main_layout.addWidget(bottom_buttons)

    def setup_style(self):
        """Apply the widget styles used by this window."""
        self.setStyleSheet("""
            QMainWindow {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                          stop:0 #2c3e50, stop:1 #3498db);
            }
            QPushButton {
                background-color: #2980b9;
                border: none;
                color: white;
                padding: 8px 16px;
                font-size: 14px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #3498db;
            }
            QPushButton:pressed {
                background-color: #21618c;
            }
            QPushButton#backButton {
                background-color: #e74c3c;
            }
            QPushButton#backButton:hover {
                background-color: #c0392b;
            }
            QPushButton#operationButton {
                background-color: #27ae60;
            }
            QPushButton#operationButton:hover {
                background-color: #2ecc71;
            }
            QListWidget::item {
                padding: 8px;
            }
        """)

    def create_title_bar(self):
        """Build the title bar and its controls."""
        title_bar = QWidget()
        title_bar.setFixedHeight(45)
        title_bar.setStyleSheet("background-color: rgba(0, 0, 0, 0.3); border-radius: 6px;")
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(15, 8, 15, 8)

        title_label = QLabel(f"任务详情 - {self.task.name}")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: white;")

        title_layout.addWidget(title_label)
        title_layout.addStretch()

        return title_bar

    def create_task_info(self):
        """Build the task information display."""
        info_widget = QWidget()
        info_layout = QVBoxLayout(info_widget)

        info_label = QLabel(
            f"任务名称: {self.task.name} | 执行次数: {self.task.execution_count} | 已完成: {self.task.completed_count} | 剩余: {self.task.remaining_count}")
        info_label.setFont(QFont("Microsoft YaHei", 11))
        info_label.setStyleSheet(
            "color: white; background-color: rgba(0, 0, 0, 0.2); padding: 8px; border-radius: 4px;")

        info_layout.addWidget(info_label)
        return info_widget

    def create_process_list(self):
        """Build the process list using the work-task list style."""
        list_widget = QWidget()
        layout = QVBoxLayout(list_widget)
        layout.setSpacing(6)

        # Title.
        title = QLabel("任务流程列表")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet("color: white;")

        # Increase the process-list height to show more items.
        self.process_list = QListWidget()
        # Use a fixed height to keep the complete list area visible.
        self.process_list.setFixedHeight(400)

        # Enable drag reordering and scrolling consistently with the work-task list.
        self.process_list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.process_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.process_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # Add a context menu.
        self.process_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.process_list.customContextMenuRequested.connect(self.show_process_context_menu)

        self.update_process_list()

        layout.addWidget(title)
        layout.addWidget(self.process_list)

        return list_widget

    def show_process_context_menu(self, position):
        """Show the context menu for the selected process."""
        item = self.process_list.itemAt(position)
        if item:
            menu = QMenu(self)
            delete_action = menu.addAction("删除该流程")

            action = menu.exec(self.process_list.mapToGlobal(position))

            if action == delete_action:
                self.delete_process(item)

    def delete_process(self, item):
        """Remove the selected process from the task."""
        index = self.process_list.row(item)
        if 0 <= index < len(self.task.processes):
            process_name = self.task.processes[index].name
            reply = QMessageBox.question(self, "确认删除",
                                         f"确定要删除流程 '{process_name}' 吗？",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self.task.processes.pop(index)
                self.update_process_list()
                QMessageBox.information(self, "成功", f"已删除流程: {process_name}")

    def create_operation_buttons(self):
        """Build the process operation buttons."""
        button_widget = QWidget()
        layout = QVBoxLayout(button_widget)
        layout.setSpacing(8)

        # Title.
        title = QLabel("全部操作")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet("color: white;")
        layout.addWidget(title)

        # Operation buttons.
        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        button_layout.setSpacing(15)

        # Four preset operation buttons.
        operations = [
            ("加热", self.add_heating),
            ("旋涂", self.add_spin_coating),
            ("抽真空", self.add_vacuum),
            ("滴液", self.add_dripping)
        ]

        for op_name, op_slot in operations:
            button = QPushButton(op_name)
            button.setObjectName("operationButton")
            button.setFixedSize(120, 35)
            button.clicked.connect(op_slot)
            button_layout.addWidget(button)

        layout.addWidget(button_container)
        return button_widget

    def create_bottom_buttons(self):
        """Build the bottom navigation buttons."""
        button_widget = QWidget()
        layout = QHBoxLayout(button_widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(20)

        # Back button.
        back_button = QPushButton("返回")
        back_button.setObjectName("backButton")
        back_button.setFixedSize(120, 35)
        back_button.clicked.connect(self.close)

        layout.addWidget(back_button)
        return button_widget

    def update_process_list(self):
        """Refresh process items using the work-task list style."""
        self.process_list.clear()

        if not self.task.processes:
            # Show a hint when no processes are present.
            item = QListWidgetItem("暂无流程，请点击下方操作按钮添加流程")
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setForeground(QColor(128, 128, 128))
            self.process_list.addItem(item)
        else:
            # Display processes with the same item style as the work-task list.
            for i, process in enumerate(self.task.processes):
                item_text = f"{i + 1}. {process}"
                item = QListWidgetItem(item_text)
                self.process_list.addItem(item)

    def add_heating(self):
        """Append a heating operation to the task."""
        self.add_operation_to_task("加热")

    def add_spin_coating(self):
        """Collect spin parameters and append a spin coating operation."""
        # Open the parameter dialog.
        dialog = SpinCoatingDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            parameters = dialog.get_parameters()
            # Create a parameterized process.
            new_process = Process("旋涂", parameters)
            self.task.add_process(new_process)

            # Refresh the display.
            self.update_process_list()

            # Show a success message.
            QMessageBox.information(self, "成功", f"已添加旋涂操作，参数: {parameters}")

    def add_vacuum(self):
        """Append a vacuum operation to the task."""
        self.add_operation_to_task("抽真空")

    def add_dripping(self):
        """Append a dispensing operation to the task."""
        self.add_operation_to_task("滴液")

    def add_operation_to_task(self, operation_name):
        """Append an operation that requires no additional parameters."""
        # Create a new process.
        new_process = Process(operation_name)
        self.task.add_process(new_process)

        # Refresh the display.
        self.update_process_list()

        # Show a success message.
        QMessageBox.information(self, "成功", f"已添加操作: {operation_name}")


class MainWindow(QMainWindow):
    """Represent main window and its associated operations."""
    def __init__(self):
        """Initialize main window dependencies and internal state."""
        super().__init__()
        self.setWindowTitle("钙钛矿太阳能电池自动生产平台")
        self.setFixedSize(1000, 800)  # Enlarge the main window.

        # Initialize an empty task collection.
        self.all_tasks = []
        self.selected_tasks = []

        # Apply the style.
        self.setup_style()

        # Create the central widget.
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Create the main layout.
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # Create the stacked widget.
        self.stacked_widget = QStackedWidget()

        # Create the welcome page.
        self.welcome_page = self.create_welcome_page()
        # Create the main page.
        self.main_page = self.create_main_page()

        # Add pages to the stacked widget.
        self.stacked_widget.addWidget(self.welcome_page)
        self.stacked_widget.addWidget(self.main_page)

        main_layout.addWidget(self.stacked_widget)

        # Store the exported data.
        self.exported_data = None

    def setup_style(self):
        """Apply the widget styles used by this window."""
        self.setStyleSheet("""
            QMainWindow {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                          stop:0 #2c3e50, stop:1 #3498db);
            }
            QPushButton {
                background-color: #2980b9;
                border: none;
                color: white;
                padding: 8px 16px;
                font-size: 14px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #3498db;
            }
            QPushButton:pressed {
                background-color: #21618c;
            }
            QPushButton#exitButton {
                background-color: #e74c3c;
            }
            QPushButton#exitButton:hover {
                background-color: #c0392b;
            }
            QPushButton#addButton {
                background-color: #27ae60;
            }
            QPushButton#addButton:hover {
                background-color: #2ecc71;
            }
            QPushButton#deleteButton {
                background-color: #e67e22;
            }
            QPushButton#deleteButton:hover {
                background-color: #f39c12;
            }
            QPushButton#detailButton {
                background-color: #9b59b6;
            }
            QPushButton#detailButton:hover {
                background-color: #8e44ad;
            }
            QListWidget {
                background-color: white;
                border: 2px solid #34495e;
                border-radius: 6px;
                font-size: 14px;
                outline: none;
            }
            QListWidget::item {
                padding: 10px;
                border-bottom: 1px solid #ecf0f1;
                min-height: 20px;
            }
            QListWidget::item:selected {
                background-color: #3498db;
                color: white;
            }
            QListWidget::item:hover {
                background-color: #ecf0f1;
            }
        """)

    def create_welcome_page(self):
        """Build the welcome page."""
        welcome_widget = QWidget()
        layout = QVBoxLayout(welcome_widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Title label.
        title_label = QLabel("钙钛矿太阳能电池自动生产平台")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_font = QFont()
        title_font.setPointSize(24)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: white; margin-bottom: 50px;")

        # Button container.
        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        button_layout.setSpacing(30)

        # Enter button.
        enter_button = QPushButton("进入系统")
        enter_button.setObjectName("enterButton")
        enter_button.setFixedSize(120, 50)
        enter_button.clicked.connect(self.enter_system)

        # Exit button.
        exit_button = QPushButton("退出")
        exit_button.setObjectName("exitButton")
        exit_button.setFixedSize(120, 50)
        exit_button.clicked.connect(self.close_application)

        button_layout.addWidget(enter_button)
        button_layout.addWidget(exit_button)

        # Add to the main layout.
        layout.addWidget(title_label)
        layout.addStretch()
        layout.addWidget(button_container)
        layout.addStretch()

        return welcome_widget

    def create_main_page(self):
        """Build the main task-management page."""
        main_widget = QWidget()
        layout = QVBoxLayout(main_widget)
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)

        # Title bar.
        title_bar = self.create_title_bar()
        layout.addWidget(title_bar)

        # Task-list title.
        task_title = QLabel("任务列表")
        task_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        task_title_font = QFont()
        task_title_font.setPointSize(18)
        task_title_font.setBold(True)
        task_title.setFont(task_title_font)
        task_title.setStyleSheet("color: white; padding: 10px;")
        layout.addWidget(task_title)

        # Use a simple vertical layout.
        content_layout = QVBoxLayout()
        content_layout.setSpacing(15)

        # Work-task display area.
        selected_tasks_section = self.create_selected_tasks_section()
        content_layout.addWidget(selected_tasks_section)

        # All-task area.
        all_tasks_section = self.create_all_tasks_section()
        content_layout.addWidget(all_tasks_section)

        # Operation buttons.
        action_buttons = self.create_action_buttons()
        content_layout.addWidget(action_buttons)

        layout.addLayout(content_layout)

        return main_widget

    def create_title_bar(self):
        """Build the title bar and its controls."""
        title_bar = QWidget()
        title_bar.setFixedHeight(50)
        title_bar.setStyleSheet("background-color: rgba(0, 0, 0, 0.3); border-radius: 6px;")
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(15, 8, 15, 8)

        title_label = QLabel("钙钛矿太阳能电池自动生产平台")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: white;")

        # Add a data export button.
        export_button = QPushButton("导出旋涂参数")
        export_button.setFixedSize(120, 35)
        export_button.clicked.connect(self.export_spin_coating_data)

        back_button = QPushButton("返回")
        back_button.setFixedSize(80, 35)
        back_button.clicked.connect(self.back_to_welcome)

        title_layout.addWidget(title_label)
        title_layout.addStretch()
        title_layout.addWidget(export_button)
        title_layout.addWidget(back_button)

        return title_bar

    def create_selected_tasks_section(self):
        """Build the selected work-task area."""
        section_widget = QWidget()
        layout = QVBoxLayout(section_widget)
        layout.setSpacing(8)

        # Title.
        title = QLabel("工作任务列表（双击任务修改执行次数）")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet("color: white;")

        # Give the selected-task list a fixed height to keep its area visible.
        self.selected_tasks_list = QListWidget()
        self.selected_tasks_list.setFixedHeight(280)

        # Enable drag reordering and scrolling.
        self.selected_tasks_list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.selected_tasks_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.selected_tasks_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # Connect the double-click event.
        self.selected_tasks_list.itemDoubleClicked.connect(self.on_task_double_clicked)

        layout.addWidget(title)
        layout.addWidget(self.selected_tasks_list)

        return section_widget

    def create_all_tasks_section(self):
        """Build the available-task area."""
        section_widget = QWidget()
        layout = QVBoxLayout(section_widget)
        layout.setSpacing(8)

        # Title.
        title = QLabel("全部可用任务（右键点击查看详情，左键点击选择并设置执行次数）")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet("color: white;")

        # Give the all-task list a fixed height to keep its area visible.
        self.all_tasks_list = QListWidget()
        self.all_tasks_list.setFixedHeight(220)
        self.update_all_tasks_list()

        # Enable drag reordering and scrolling.
        self.all_tasks_list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.all_tasks_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.all_tasks_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # Connect the click event.
        self.all_tasks_list.itemClicked.connect(self.on_task_selected)

        # Add a right-click context menu.
        self.all_tasks_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.all_tasks_list.customContextMenuRequested.connect(self.show_task_context_menu)

        layout.addWidget(title)
        layout.addWidget(self.all_tasks_list)

        return section_widget

    def create_action_buttons(self):
        """Build task creation, deletion, completion, and reset buttons."""
        button_widget = QWidget()
        layout = QHBoxLayout(button_widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(20)

        # New-task button.
        add_button = QPushButton("新建任务")
        add_button.setObjectName("addButton")
        add_button.setFixedSize(120, 40)
        add_button.clicked.connect(self.add_new_task)

        # Delete-task button.
        delete_button = QPushButton("删除任务")
        delete_button.setObjectName("deleteButton")
        delete_button.setFixedSize(120, 40)
        delete_button.clicked.connect(self.delete_task)

        # Complete-task button.
        complete_button = QPushButton("标记完成")
        complete_button.setObjectName("completeButton")
        complete_button.setFixedSize(120, 40)
        complete_button.clicked.connect(self.mark_task_complete)
        complete_button.setStyleSheet("background-color: #9b59b6;")

        # Reset-completion button.
        reset_button = QPushButton("重置完成")
        reset_button.setObjectName("resetButton")
        reset_button.setFixedSize(120, 40)
        reset_button.clicked.connect(self.reset_task_completion)
        reset_button.setStyleSheet("background-color: #e67e22;")

        layout.addWidget(add_button)
        layout.addWidget(delete_button)
        layout.addWidget(complete_button)
        layout.addWidget(reset_button)

        return button_widget

    def show_task_context_menu(self, position):
        """Show the right-click menu for a task."""
        item = self.all_tasks_list.itemAt(position)
        if item:
            task_name = item.text()

            # Find the corresponding task.
            for task in self.all_tasks:
                if task.name == task_name:
                    menu = QMenu(self)
                    detail_action = menu.addAction("查看任务详情")

                    # Display the menu and read the selection.
                    action = menu.exec(self.all_tasks_list.mapToGlobal(position))

                    if action == detail_action:
                        self.show_task_detail(task)
                    break

    def show_task_detail(self, task):
        """Open the selected task detail window."""
        self.detail_window = TaskDetailWindow(task, self)
        self.detail_window.show()

    def on_task_selected(self, item):
        """Add a selected task after obtaining its repetition count."""
        if item:
            task_name = item.text()

            # Find the corresponding task.
            for task in self.all_tasks:
                if task.name == task_name:
                    # Open a dialog to set the repetition count.
                    dialog = CountEditDialog(task.name, is_new_selection=True, parent=self)
                    if dialog.exec() == QDialog.DialogCode.Accepted:
                        execution_count = dialog.get_count()

                        # Copy the task because repeated selection is allowed.
                        new_task = Task(
                            name=task.name,
                            processes=task.processes.copy(),
                            execution_count=execution_count,
                            completed_count=0
                        )

                        # Add to the selected list.
                        self.selected_tasks.append(new_task)
                        self.update_selected_tasks_display()
                        QMessageBox.information(self, "成功", f"已添加任务 '{task_name}'，执行次数: {execution_count}")
                    break

    def on_task_double_clicked(self, item):
        """Edit the repetition count of a double-clicked work task."""
        if item:
            # Find the double-clicked task index in the work list.
            index = self.selected_tasks_list.row(item)
            if 0 <= index < len(self.selected_tasks):
                task = self.selected_tasks[index]

                # Use the custom dialog.
                dialog = CountEditDialog(task.name, task.execution_count, is_new_selection=False, parent=self)
                if dialog.exec() == QDialog.DialogCode.Accepted:
                    new_count = dialog.get_count()
                    task.execution_count = new_count
                    self.update_selected_tasks_display()
                    QMessageBox.information(self, "成功", f"已将任务 '{task.name}' 的执行次数修改为 {new_count}")

    def mark_task_complete(self):
        """Mark one repetition of the selected task as completed."""
        current_item = self.selected_tasks_list.currentItem()
        if current_item:
            index = self.selected_tasks_list.row(current_item)
            if 0 <= index < len(self.selected_tasks):
                task = self.selected_tasks[index]
                if task.remaining_count > 0:
                    task.completed_count += 1
                    self.update_selected_tasks_display()

                    if task.remaining_count == 0:
                        QMessageBox.information(self, "完成", f"任务 '{task.name}' 已完成所有执行次数！")
                    else:
                        QMessageBox.information(self, "成功",
                                                f"任务 '{task.name}' 完成一次，剩余 {task.remaining_count} 次")
                else:
                    QMessageBox.warning(self, "警告", f"任务 '{task.name}' 已完成所有执行次数")
        else:
            QMessageBox.warning(self, "警告", "请先在工作列表中选择一个任务")

    def reset_task_completion(self):
        """Reset the selected task completed repetition count."""
        current_item = self.selected_tasks_list.currentItem()
        if current_item:
            index = self.selected_tasks_list.row(current_item)
            if 0 <= index < len(self.selected_tasks):
                task = self.selected_tasks[index]
                task.completed_count = 0
                self.update_selected_tasks_display()
                QMessageBox.information(self, "成功", f"已重置任务 '{task.name}' 的完成次数")
        else:
            QMessageBox.warning(self, "警告", "请先在工作列表中选择一个任务")

    def update_all_tasks_list(self):
        """Refresh the list of available tasks."""
        self.all_tasks_list.clear()
        for task in self.all_tasks:
            item = QListWidgetItem(task.name)
            self.all_tasks_list.addItem(item)

    def update_selected_tasks_display(self):
        """Refresh selected tasks and their completion indicators."""
        self.selected_tasks_list.clear()
        for i, task in enumerate(self.selected_tasks):
            # Display the task name, repetition count, and remaining count.
            status_text = f"剩余{task.remaining_count}次" if task.remaining_count > 0 else "已完成"

            item_text = f"{i + 1}. {task.name} → 执行: {task.execution_count}次, 完成: {task.completed_count}次, [{status_text}]"
            item = QListWidgetItem(item_text)

            # Choose a color based on the remaining count.
            if task.remaining_count == 0:
                item.setBackground(QColor(200, 255, 200))  # Light green indicates completion.
            elif task.completed_count > 0:
                item.setBackground(QColor(255, 255, 200))  # Light yellow indicates progress.
            else:
                item.setBackground(QColor(255, 255, 255))  # White indicates a task that has not started.

            self.selected_tasks_list.addItem(item)

    def add_new_task(self):
        """Create an empty task with one requested repetition."""
        task_name, ok = QInputDialog.getText(self, "新建任务", "请输入任务名称:")
        if ok and task_name.strip():
            if any(task.name == task_name.strip() for task in self.all_tasks):
                QMessageBox.warning(self, "警告", "任务名称已存在!")
                return

            # Create a task with one repetition and no default processes.
            new_task = Task(task_name.strip(), execution_count=1)

            self.all_tasks.append(new_task)
            self.update_all_tasks_list()
            QMessageBox.information(self, "成功", f"任务 '{task_name}' 创建成功!")

    def delete_task(self):
        """Remove a task and matching entries from the selected work list."""
        current_item = self.all_tasks_list.currentItem()
        if current_item:
            task_name = current_item.text()
            reply = QMessageBox.question(self, "确认删除",
                                         f"确定要删除任务 '{task_name}' 吗？",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                # Remove from the data collection.
                self.all_tasks = [task for task in self.all_tasks if task.name != task_name]
                # Remove every selected task with the same name; duplicates are allowed.
                self.selected_tasks = [task for task in self.selected_tasks if task.name != task_name]
                # Refresh the display.
                self.update_all_tasks_list()
                self.update_selected_tasks_display()
        else:
            QMessageBox.warning(self, "警告", "请先选择一个要删除的任务")

    def export_spin_coating_data(self):
        """Collect spin parameters and display the exported array."""
        spin_coating_data = self.get_spin_coating_parameters()

        if not spin_coating_data:
            QMessageBox.information(self, "导出结果", "当前工作列表中没有包含旋涂操作的任务")
            self.exported_data = None
            return None

        # Display the array dialog.
        dialog = ArrayDisplayDialog(spin_coating_data, self)
        dialog.exec()

        # Store the exported data.
        self.exported_data = spin_coating_data

        # Print data to the console.
        self.print_exported_data()

        return spin_coating_data

    def get_spin_coating_parameters(self):
        """Return spin parameters grouped by work task and spin operation.

        Each operation contains maximum speed, spin duration, acceleration time, and deceleration time, in that order."""
        spin_coating_data = []

        for task in self.selected_tasks:
            task_spin_operations = []

            # Visit all processes in the task.
            for process in task.processes:
                if process.name == "旋涂" and process.parameters:
                    # Extract spin parameters in the specified order.
                    params = process.parameters
                    spin_params = [
                        0,
                        params.get("最大速度", 0),
                        params.get("旋涂时间", 0),
                        params.get("加速时间", 0),
                        params.get("减速时间", 0)
                    ]
                    task_spin_operations.append(spin_params)

            # Add the task to the result if it contains a spin operation.
            if task_spin_operations:
                spin_coating_data.append(task_spin_operations)

        return spin_coating_data

    def print_exported_data(self):
        """Print the most recently exported spin data to the console."""
        if self.exported_data:
            print("\n" + "=" * 60)
            print("导出的旋涂参数数组:")
            print("=" * 60)
            print("返回的数组结构:")
            print(f"类型: {type(self.exported_data)}")
            print(f"长度: {len(self.exported_data)} (工作任务数量)")

            for i, task_data in enumerate(self.exported_data):
                print(f"\n任务 {i + 1}:")
                print(f"  旋涂操作数量: {len(task_data)}")
                for j, spin_params in enumerate(task_data):
                    print(f"    旋涂操作 {j + 1}: {spin_params}")

            print(f"\n完整数组:")
            print(self.exported_data)
            print("=" * 60)
        else:
            print("没有导出的数据")

    def get_exported_data(self):
        """Return the most recently exported data."""
        return self.exported_data

    def enter_system(self):
        """Switch from the welcome page to the task-management page."""
        self.stacked_widget.setCurrentIndex(1)

    def back_to_welcome(self):
        """Switch back to the welcome page."""
        self.stacked_widget.setCurrentIndex(0)

    def close_application(self):
        """Close the application window."""
        self.close()


def main():
    """Run the ui command-line entry point."""
    app = QApplication(sys.argv)

    font = QFont("Microsoft YaHei", 10)
    app.setFont(font)

    window = MainWindow()
    window.show()


    # Print the final exported data at application exit.
    def on_exit():
        """On exit."""
        exported_data = window.get_exported_data()
        if exported_data:
            print("\n" + "=" * 60)
            print("程序结束时的最终导出数据:")
            print("=" * 60)
            print(exported_data)
            print("=" * 60)
        else:
            print("程序结束：没有导出数据")

    # Register the exit handler.
    app.aboutToQuit.connect(on_exit)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
