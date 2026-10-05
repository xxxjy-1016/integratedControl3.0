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
    """数组显示对话框"""

    def __init__(self, data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("旋涂参数数组")
        self.setFixedSize(600, 500)

        layout = QVBoxLayout(self)

        # 标题
        title_label = QLabel("导出的旋涂参数数组")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        # 说明
        desc_label = QLabel("以下是可以直接在其他Python代码中使用的数组：")
        desc_label.setFont(QFont("Microsoft YaHei", 10))
        layout.addWidget(desc_label)

        # 文本编辑框显示数组
        self.text_edit = QTextEdit()
        self.text_edit.setFont(QFont("Consolas", 10))  # 使用等宽字体
        self.text_edit.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)

        # 格式化显示数组
        formatted_data = self.format_array(data)
        self.text_edit.setPlainText(formatted_data)

        layout.addWidget(self.text_edit, 1)  # 添加权重使其可扩展

        # 按钮区域
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
        """格式化数组为可读的字符串"""
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
        """复制到剪贴板"""
        clipboard = QApplication.clipboard()
        clipboard.setText(self.text_edit.toPlainText())

        # 显示复制成功提示
        self.show_copy_success()

    def show_copy_success(self):
        """显示复制成功提示"""
        success_label = QLabel("✓ 已复制到剪贴板！")
        success_label.setStyleSheet("color: green; font-weight: bold;")
        success_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 临时显示提示
        layout = self.layout()
        layout.insertWidget(layout.count() - 1, success_label)  # 在按钮前插入

        # 3秒后移除提示
        QTimer.singleShot(3000, success_label.deleteLater)


class Process:
    """流程类，封装流程信息"""

    def __init__(self, name, parameters=None):
        self.name = name
        self.parameters = parameters or {}  # 存储流程参数

    def __str__(self):
        if self.parameters:
            params_str = ", ".join([f"{k}: {v}" for k, v in self.parameters.items()])
            return f"{self.name} ({params_str})"
        return self.name


class Task:
    """任务类，包含多个流程和任务执行次数"""

    def __init__(self, name, processes=None, execution_count=1, completed_count=0):
        self.name = name
        self.processes = processes or []
        self.execution_count = execution_count
        self.completed_count = completed_count  # 已完成次数

    def add_process(self, process):
        self.processes.append(process)

    @property
    def remaining_count(self):
        """计算剩余次数"""
        return max(0, self.execution_count - self.completed_count)


class SpinCoatingDialog(QDialog):
    """旋涂参数设置对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置旋涂参数")
        self.setFixedSize(400, 300)

        layout = QVBoxLayout(self)

        # 标题
        title_label = QLabel("旋涂参数设置")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        # 参数输入区域
        params_layout = QGridLayout()
        params_layout.setSpacing(15)

        # 最大速度设置
        max_speed_label = QLabel("最大速度 (rpm):")
        max_speed_label.setFont(QFont("Microsoft YaHei", 11))
        self.max_speed_spin = QDoubleSpinBox()
        self.max_speed_spin.setRange(100, 10000)
        self.max_speed_spin.setValue(3000)
        self.max_speed_spin.setSuffix(" rpm")
        self.max_speed_spin.setFont(QFont("Microsoft YaHei", 11))
        params_layout.addWidget(max_speed_label, 0, 0)
        params_layout.addWidget(self.max_speed_spin, 0, 1)

        # 旋涂时间设置
        spin_time_label = QLabel("旋涂时间 (s):")
        spin_time_label.setFont(QFont("Microsoft YaHei", 11))
        self.spin_time_spin = QDoubleSpinBox()
        self.spin_time_spin.setRange(1, 600)
        self.spin_time_spin.setValue(30)
        self.spin_time_spin.setSuffix(" s")
        self.spin_time_spin.setFont(QFont("Microsoft YaHei", 11))
        params_layout.addWidget(spin_time_label, 1, 0)
        params_layout.addWidget(self.spin_time_spin, 1, 1)

        # 加速时间设置
        accel_time_label = QLabel("加速时间 (s):")
        accel_time_label.setFont(QFont("Microsoft YaHei", 11))
        self.accel_time_spin = QDoubleSpinBox()
        self.accel_time_spin.setRange(1, 60)
        self.accel_time_spin.setValue(5)
        self.accel_time_spin.setSuffix(" s")
        self.accel_time_spin.setFont(QFont("Microsoft YaHei", 11))
        params_layout.addWidget(accel_time_label, 2, 0)
        params_layout.addWidget(self.accel_time_spin, 2, 1)

        # 减速时间设置
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

        # 按钮区域
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def get_parameters(self):
        """获取设置的参数"""
        return {
            "最大速度": self.max_speed_spin.value(),
            "旋涂时间": self.spin_time_spin.value(),
            "加速时间": self.accel_time_spin.value(),
            "减速时间": self.decel_time_spin.value()
        }


class CountEditDialog(QDialog):
    """执行次数编辑对话框"""

    def __init__(self, task_name, current_count=1, is_new_selection=False, parent=None):
        super().__init__(parent)

        if is_new_selection:
            self.setWindowTitle("设置执行次数")
            prompt = f"请设置任务 '{task_name}' 的执行次数:"
        else:
            self.setWindowTitle("修改执行次数")
            prompt = f"修改任务 '{task_name}' 的执行次数:"

        self.setFixedSize(350, 180)

        layout = QVBoxLayout(self)

        # 提示标签
        label = QLabel(prompt)
        label_font = QFont()
        label_font.setPointSize(12)
        label.setFont(label_font)
        layout.addWidget(label)

        # 输入框
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

        # 按钮
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.validate_and_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.result_count = current_count

    def validate_and_accept(self):
        """验证输入并接受"""
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
        return self.result_count


class TaskDetailWindow(QMainWindow):
    """任务详情窗口"""

    def __init__(self, task, parent=None):
        super().__init__(parent)
        self.task = task
        self.setWindowTitle(f"任务详情 - {task.name}")
        # 增大窗口尺寸确保所有内容都能完整显示
        self.setFixedSize(900, 750)

        # 设置样式
        self.setup_style()

        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 创建主布局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(12)

        # 标题栏
        title_bar = self.create_title_bar()
        main_layout.addWidget(title_bar)

        # 任务信息
        task_info = self.create_task_info()
        main_layout.addWidget(task_info)

        # 流程列表 - 给予更多空间
        process_list = self.create_process_list()
        main_layout.addWidget(process_list, 1)  # 添加权重1，使其可以扩展

        # 操作按钮区域
        operation_buttons = self.create_operation_buttons()
        main_layout.addWidget(operation_buttons)

        # 底部按钮
        bottom_buttons = self.create_bottom_buttons()
        main_layout.addWidget(bottom_buttons)

    def setup_style(self):
        """设置样式"""
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
        """创建标题栏"""
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
        """创建任务信息显示"""
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
        """创建流程列表 - 使用和工作任务列表相同的样式"""
        list_widget = QWidget()
        layout = QVBoxLayout(list_widget)
        layout.setSpacing(6)

        # 标题
        title = QLabel("任务流程列表")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet("color: white;")

        # 流程列表 - 增加高度确保能显示更多项目
        self.process_list = QListWidget()
        # 使用固定高度而不是最小/最大高度，确保显示完整
        self.process_list.setFixedHeight(400)

        # 启用拖拽排序和滚动条 - 和工作任务列表保持一致
        self.process_list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.process_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.process_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # 添加上下文菜单
        self.process_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.process_list.customContextMenuRequested.connect(self.show_process_context_menu)

        self.update_process_list()

        layout.addWidget(title)
        layout.addWidget(self.process_list)

        return list_widget

    def show_process_context_menu(self, position):
        """显示流程上下文菜单"""
        item = self.process_list.itemAt(position)
        if item:
            menu = QMenu(self)
            delete_action = menu.addAction("删除该流程")

            action = menu.exec(self.process_list.mapToGlobal(position))

            if action == delete_action:
                self.delete_process(item)

    def delete_process(self, item):
        """删除选中的流程"""
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
        """创建操作按钮区域"""
        button_widget = QWidget()
        layout = QVBoxLayout(button_widget)
        layout.setSpacing(8)

        # 标题
        title = QLabel("全部操作")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet("color: white;")
        layout.addWidget(title)

        # 操作按钮
        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        button_layout.setSpacing(15)

        # 四个预设操作按钮
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
        """创建底部按钮"""
        button_widget = QWidget()
        layout = QHBoxLayout(button_widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(20)

        # 返回按钮
        back_button = QPushButton("返回")
        back_button.setObjectName("backButton")
        back_button.setFixedSize(120, 35)
        back_button.clicked.connect(self.close)

        layout.addWidget(back_button)
        return button_widget

    def update_process_list(self):
        """更新流程列表显示 - 使用和工作任务列表相同的项目样式"""
        self.process_list.clear()

        if not self.task.processes:
            # 如果没有流程，显示提示信息
            item = QListWidgetItem("暂无流程，请点击下方操作按钮添加流程")
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setForeground(QColor(128, 128, 128))
            self.process_list.addItem(item)
        else:
            # 显示所有流程 - 使用和工作任务列表相同的项目样式
            for i, process in enumerate(self.task.processes):
                item_text = f"{i + 1}. {process}"
                item = QListWidgetItem(item_text)
                self.process_list.addItem(item)

    def add_heating(self):
        """添加加热操作"""
        self.add_operation_to_task("加热")

    def add_spin_coating(self):
        """添加旋涂操作"""
        # 弹出参数设置对话框
        dialog = SpinCoatingDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            parameters = dialog.get_parameters()
            # 创建带有参数的流程
            new_process = Process("旋涂", parameters)
            self.task.add_process(new_process)

            # 更新显示
            self.update_process_list()

            # 显示成功消息
            QMessageBox.information(self, "成功", f"已添加旋涂操作，参数: {parameters}")

    def add_vacuum(self):
        """添加抽真空操作"""
        self.add_operation_to_task("抽真空")

    def add_dripping(self):
        """添加滴液操作"""
        self.add_operation_to_task("滴液")

    def add_operation_to_task(self, operation_name):
        """添加操作到任务（无参数的操作）"""
        # 创建新的流程
        new_process = Process(operation_name)
        self.task.add_process(new_process)

        # 更新显示
        self.update_process_list()

        # 显示成功消息
        QMessageBox.information(self, "成功", f"已添加操作: {operation_name}")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("钙钛矿太阳能电池自动生产平台")
        self.setFixedSize(1000, 800)  # 增大主窗口尺寸

        # 初始化空的任务数据
        self.all_tasks = []
        self.selected_tasks = []

        # 设置样式
        self.setup_style()

        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 创建主布局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # 创建堆叠窗口
        self.stacked_widget = QStackedWidget()

        # 创建欢迎页面
        self.welcome_page = self.create_welcome_page()
        # 创建主页面
        self.main_page = self.create_main_page()

        # 添加页面到堆叠窗口
        self.stacked_widget.addWidget(self.welcome_page)
        self.stacked_widget.addWidget(self.main_page)

        main_layout.addWidget(self.stacked_widget)

        # 存储导出数据的变量
        self.exported_data = None

    def setup_style(self):
        """设置应用程序样式"""
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
        """创建欢迎页面"""
        welcome_widget = QWidget()
        layout = QVBoxLayout(welcome_widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 标题标签
        title_label = QLabel("钙钛矿太阳能电池自动生产平台")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_font = QFont()
        title_font.setPointSize(24)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: white; margin-bottom: 50px;")

        # 按钮容器
        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        button_layout.setSpacing(30)

        # 进入按钮
        enter_button = QPushButton("进入系统")
        enter_button.setObjectName("enterButton")
        enter_button.setFixedSize(120, 50)
        enter_button.clicked.connect(self.enter_system)

        # 退出按钮
        exit_button = QPushButton("退出")
        exit_button.setObjectName("exitButton")
        exit_button.setFixedSize(120, 50)
        exit_button.clicked.connect(self.close_application)

        button_layout.addWidget(enter_button)
        button_layout.addWidget(exit_button)

        # 添加到主布局
        layout.addWidget(title_label)
        layout.addStretch()
        layout.addWidget(button_container)
        layout.addStretch()

        return welcome_widget

    def create_main_page(self):
        """创建主系统页面"""
        main_widget = QWidget()
        layout = QVBoxLayout(main_widget)
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)

        # 标题栏
        title_bar = self.create_title_bar()
        layout.addWidget(title_bar)

        # 任务列表标题
        task_title = QLabel("任务列表")
        task_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        task_title_font = QFont()
        task_title_font.setPointSize(18)
        task_title_font.setBold(True)
        task_title.setFont(task_title_font)
        task_title.setStyleSheet("color: white; padding: 10px;")
        layout.addWidget(task_title)

        # 使用简单的垂直布局
        content_layout = QVBoxLayout()
        content_layout.setSpacing(15)

        # 工作任务显示区域
        selected_tasks_section = self.create_selected_tasks_section()
        content_layout.addWidget(selected_tasks_section)

        # 全部任务区域
        all_tasks_section = self.create_all_tasks_section()
        content_layout.addWidget(all_tasks_section)

        # 操作按钮
        action_buttons = self.create_action_buttons()
        content_layout.addWidget(action_buttons)

        layout.addLayout(content_layout)

        return main_widget

    def create_title_bar(self):
        """创建标题栏"""
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

        # 添加导出数据按钮
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
        """创建选中的工作任务区域"""
        section_widget = QWidget()
        layout = QVBoxLayout(section_widget)
        layout.setSpacing(8)

        # 标题
        title = QLabel("工作任务列表（双击任务修改执行次数）")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet("color: white;")

        # 选中的任务列表 - 使用固定高度确保显示完整
        self.selected_tasks_list = QListWidget()
        self.selected_tasks_list.setFixedHeight(280)

        # 启用拖拽排序和滚动条
        self.selected_tasks_list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.selected_tasks_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.selected_tasks_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # 连接双击事件
        self.selected_tasks_list.itemDoubleClicked.connect(self.on_task_double_clicked)

        layout.addWidget(title)
        layout.addWidget(self.selected_tasks_list)

        return section_widget

    def create_all_tasks_section(self):
        """创建全部任务区域"""
        section_widget = QWidget()
        layout = QVBoxLayout(section_widget)
        layout.setSpacing(8)

        # 标题
        title = QLabel("全部可用任务（右键点击查看详情，左键点击选择并设置执行次数）")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet("color: white;")

        # 全部任务列表 - 使用固定高度确保显示完整
        self.all_tasks_list = QListWidget()
        self.all_tasks_list.setFixedHeight(220)
        self.update_all_tasks_list()

        # 启用拖拽排序和滚动条
        self.all_tasks_list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.all_tasks_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.all_tasks_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # 连接点击事件
        self.all_tasks_list.itemClicked.connect(self.on_task_selected)

        # 添加上下文菜单（右键菜单）
        self.all_tasks_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.all_tasks_list.customContextMenuRequested.connect(self.show_task_context_menu)

        layout.addWidget(title)
        layout.addWidget(self.all_tasks_list)

        return section_widget

    def create_action_buttons(self):
        """创建操作按钮区域"""
        button_widget = QWidget()
        layout = QHBoxLayout(button_widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(20)

        # 新建任务按钮
        add_button = QPushButton("新建任务")
        add_button.setObjectName("addButton")
        add_button.setFixedSize(120, 40)
        add_button.clicked.connect(self.add_new_task)

        # 删除任务按钮
        delete_button = QPushButton("删除任务")
        delete_button.setObjectName("deleteButton")
        delete_button.setFixedSize(120, 40)
        delete_button.clicked.connect(self.delete_task)

        # 完成任务按钮
        complete_button = QPushButton("标记完成")
        complete_button.setObjectName("completeButton")
        complete_button.setFixedSize(120, 40)
        complete_button.clicked.connect(self.mark_task_complete)
        complete_button.setStyleSheet("background-color: #9b59b6;")

        # 重置完成按钮
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
        """显示任务上下文菜单（右键菜单）"""
        item = self.all_tasks_list.itemAt(position)
        if item:
            task_name = item.text()

            # 找到对应的任务
            for task in self.all_tasks:
                if task.name == task_name:
                    menu = QMenu(self)
                    detail_action = menu.addAction("查看任务详情")

                    # 显示菜单并获取选择
                    action = menu.exec(self.all_tasks_list.mapToGlobal(position))

                    if action == detail_action:
                        self.show_task_detail(task)
                    break

    def show_task_detail(self, task):
        """显示任务详情窗口"""
        self.detail_window = TaskDetailWindow(task, self)
        self.detail_window.show()

    def on_task_selected(self, item):
        """当任务被选中时的处理 - 选择时设置执行次数"""
        if item:
            task_name = item.text()

            # 找到对应的任务
            for task in self.all_tasks:
                if task.name == task_name:
                    # 弹出对话框设置执行次数
                    dialog = CountEditDialog(task.name, is_new_selection=True, parent=self)
                    if dialog.exec() == QDialog.DialogCode.Accepted:
                        execution_count = dialog.get_count()

                        # 创建任务副本（因为允许重复选择）
                        new_task = Task(
                            name=task.name,
                            processes=task.processes.copy(),
                            execution_count=execution_count,
                            completed_count=0
                        )

                        # 添加到选中列表
                        self.selected_tasks.append(new_task)
                        self.update_selected_tasks_display()
                        QMessageBox.information(self, "成功", f"已添加任务 '{task_name}'，执行次数: {execution_count}")
                    break

    def on_task_double_clicked(self, item):
        """当工作任务被双击时，修改执行次数"""
        if item:
            # 获取双击的任务在工作列表中的索引
            index = self.selected_tasks_list.row(item)
            if 0 <= index < len(self.selected_tasks):
                task = self.selected_tasks[index]

                # 使用自定义对话框
                dialog = CountEditDialog(task.name, task.execution_count, is_new_selection=False, parent=self)
                if dialog.exec() == QDialog.DialogCode.Accepted:
                    new_count = dialog.get_count()
                    task.execution_count = new_count
                    self.update_selected_tasks_display()
                    QMessageBox.information(self, "成功", f"已将任务 '{task.name}' 的执行次数修改为 {new_count}")

    def mark_task_complete(self):
        """标记选中任务完成一次"""
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
        """重置选中任务的完成次数"""
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
        """更新全部任务列表"""
        self.all_tasks_list.clear()
        for task in self.all_tasks:
            item = QListWidgetItem(task.name)
            self.all_tasks_list.addItem(item)

    def update_selected_tasks_display(self):
        """更新选中的任务显示"""
        self.selected_tasks_list.clear()
        for i, task in enumerate(self.selected_tasks):
            # 显示任务名称、执行次数和剩余次数
            status_text = f"剩余{task.remaining_count}次" if task.remaining_count > 0 else "已完成"

            item_text = f"{i + 1}. {task.name} → 执行: {task.execution_count}次, 完成: {task.completed_count}次, [{status_text}]"
            item = QListWidgetItem(item_text)

            # 根据剩余次数设置颜色
            if task.remaining_count == 0:
                item.setBackground(QColor(200, 255, 200))  # 浅绿色 - 已完成
            elif task.completed_count > 0:
                item.setBackground(QColor(255, 255, 200))  # 浅黄色 - 进行中
            else:
                item.setBackground(QColor(255, 255, 255))  # 白色 - 未开始

            self.selected_tasks_list.addItem(item)

    def add_new_task(self):
        """新建任务"""
        task_name, ok = QInputDialog.getText(self, "新建任务", "请输入任务名称:")
        if ok and task_name.strip():
            if any(task.name == task_name.strip() for task in self.all_tasks):
                QMessageBox.warning(self, "警告", "任务名称已存在!")
                return

            # 创建新任务，默认执行次数为1，不添加默认流程
            new_task = Task(task_name.strip(), execution_count=1)

            self.all_tasks.append(new_task)
            self.update_all_tasks_list()
            QMessageBox.information(self, "成功", f"任务 '{task_name}' 创建成功!")

    def delete_task(self):
        """删除任务"""
        current_item = self.all_tasks_list.currentItem()
        if current_item:
            task_name = current_item.text()
            reply = QMessageBox.question(self, "确认删除",
                                         f"确定要删除任务 '{task_name}' 吗？",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                # 从数据中删除
                self.all_tasks = [task for task in self.all_tasks if task.name != task_name]
                # 从选中任务中删除所有同名任务（因为允许重复）
                self.selected_tasks = [task for task in self.selected_tasks if task.name != task_name]
                # 更新显示
                self.update_all_tasks_list()
                self.update_selected_tasks_display()
        else:
            QMessageBox.warning(self, "警告", "请先选择一个要删除的任务")

    def export_spin_coating_data(self):
        """导出旋涂参数数据"""
        spin_coating_data = self.get_spin_coating_parameters()

        if not spin_coating_data:
            QMessageBox.information(self, "导出结果", "当前工作列表中没有包含旋涂操作的任务")
            self.exported_data = None
            return None

        # 显示数组对话框
        dialog = ArrayDisplayDialog(spin_coating_data, self)
        dialog.exec()

        # 存储导出的数据
        self.exported_data = spin_coating_data

        # 在控制台打印数据
        self.print_exported_data()

        return spin_coating_data

    def get_spin_coating_parameters(self):
        """
        获取工作列表中所有任务的旋涂参数

        返回值:
            list: 一个列表，其中每个元素对应工作列表中的一个任务
                  每个任务是一个列表，包含该任务中所有旋涂操作的参数
                  每个旋涂操作的参数是按顺序的列表：[最大速度, 旋涂时间, 加速时间, 减速时间]
        """
        spin_coating_data = []

        for task in self.selected_tasks:
            task_spin_operations = []

            # 遍历任务中的所有流程
            for process in task.processes:
                if process.name == "旋涂" and process.parameters:
                    # 提取旋涂参数并按指定顺序排列
                    params = process.parameters
                    spin_params = [
                        0,
                        params.get("最大速度", 0),
                        params.get("旋涂时间", 0),
                        params.get("加速时间", 0),
                        params.get("减速时间", 0)
                    ]
                    task_spin_operations.append(spin_params)

            # 如果这个任务有旋涂操作，就添加到结果中
            if task_spin_operations:
                spin_coating_data.append(task_spin_operations)

        return spin_coating_data

    def print_exported_data(self):
        """打印导出的数据到控制台"""
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
        """获取最近导出的数据"""
        return self.exported_data

    def enter_system(self):
        """进入系统"""
        self.stacked_widget.setCurrentIndex(1)

    def back_to_welcome(self):
        """返回欢迎页面"""
        self.stacked_widget.setCurrentIndex(0)

    def close_application(self):
        """关闭应用程序"""
        self.close()


def main():
    app = QApplication(sys.argv)

    font = QFont("Microsoft YaHei", 10)
    app.setFont(font)

    window = MainWindow()
    window.show()


    # 在程序退出时打印最终导出的数据
    def on_exit():
        exported_data = window.get_exported_data()
        if exported_data:
            print("\n" + "=" * 60)
            print("程序结束时的最终导出数据:")
            print("=" * 60)
            print(exported_data)
            print("=" * 60)
        else:
            print("程序结束：没有导出数据")

    # 注册退出处理
    app.aboutToQuit.connect(on_exit)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
