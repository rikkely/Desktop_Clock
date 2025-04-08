import os
import platform
import subprocess
import threading
import time
import winreg

from PyQt5.QtCore import (QTimer, QTime, Qt, QPoint, QPropertyAnimation,
                          QEasingCurve, QPointF, QParallelAnimationGroup, pyqtSignal, QDateTime)
from PyQt5.QtGui import (QPainter, QColor, QPen, QPolygonF, QRadialGradient,
                         QConicalGradient, QPalette, QIcon, QGuiApplication)
from PyQt5.QtWidgets import (QApplication, QWidget, QFrame, QLCDNumber,
                             QGridLayout, QHBoxLayout, QAction, QStyleFactory, qApp, QMenu, QSystemTrayIcon, QLabel,
                             QDialogButtonBox, QLineEdit, QSpinBox, QVBoxLayout, QGroupBox, QCheckBox, QWidgetAction,
                             QSlider)
import images


# 添加CPU占用控制类
class CPULoadGenerator:
    def __init__(self):
        self.running = False
        self.load_percent = 0
        self.threads = []
        self.stop_event = threading.Event()
        self.lock = threading.Lock()
        self.num_cores = os.cpu_count() or 1
        self.adjustment_factor = 1.0  # 动态调整因子

    def set_load(self, percent):
        """设置总CPU占用百分比(0-100)"""
        with self.lock:
            # 计算每个核心需要的负载，考虑动态调整因子
            target_load = max(0, min(100, percent))
            self.load_percent = (target_load / self.num_cores) * self.adjustment_factor

        if not self.running and percent > 0:
            self.stop_event.clear()
            self.running = True
            # 为每个核心创建一个线程
            self.threads = []
            for _ in range(self.num_cores):
                t = threading.Thread(target=self._generate_load)
                t.daemon = True
                t.start()
                self.threads.append(t)
        elif self.running and percent == 0:
            self.stop_event.set()
            self.running = False
            for t in self.threads:
                t.join(timeout=1)
            self.threads = []

    def _generate_load(self):
        """改进的多核CPU负载生成方法"""
        # 设置低优先级 (仅限Windows)
        if platform.system() == 'Windows':
            import win32api, win32process, win32con
            handle = win32api.GetCurrentThread()
            win32process.SetThreadPriority(handle, win32process.THREAD_PRIORITY_LOWEST)

        last_time = time.time()
        measured_load = 0

        while not self.stop_event.is_set():
            with self.lock:
                target_load = self.load_percent

            if target_load <= 0:
                time.sleep(0.1)
                continue

            # 更精确的负载控制
            interval = 0.05  # 50ms控制周期
            busy_time = interval * (target_load / 100.0)
            idle_time = interval - busy_time

            # 忙等待
            end_time = time.time() + busy_time
            while time.time() < end_time and not self.stop_event.is_set():
                pass

            # 动态调整因子计算
            if time.time() - last_time > 2:  # 每2秒校准一次
                actual_load = measured_load / 2 * 100  # 转换为百分比
                if actual_load > 0:
                    with self.lock:
                        if target_load > 5:  # 避免除零和小负载时的抖动
                            self.adjustment_factor *= (target_load / actual_load)
                            self.adjustment_factor = max(0.5, min(1.5, self.adjustment_factor))
                last_time = time.time()
                measured_load = 0

            measured_load += busy_time

            # 空闲等待
            if idle_time > 0 and not self.stop_event.is_set():
                time.sleep(idle_time)

class DrawClock(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(90, 90)
        self.setMaximumSize(90, 90)
        # 背景色
        self.bg_color = QColor(230, 230, 230, 220)

        # 指针形状定义
        self.hourHand = [
            QPointF(4, 0),
            QPointF(-4, 0),
            QPointF(-4, -50),
            QPointF(4, -50)
        ]
        self.minuteHand = [
            QPointF(3, 0),
            QPointF(-3, 0),
            QPointF(-3, -80),
            QPointF(3, -80)
        ]
        self.secondHand = [
            QPointF(1, 0),
            QPointF(-1, 0),
            QPointF(-1, -100),
            QPointF(1, -100)
        ]

        self.time = QTime.currentTime()

    def set_time(self, time):
        self.time = time
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)

        # 居中坐标系
        painter.translate(self.width() / 2, self.height() / 2)
        scale = min(self.width(), self.height()) / 220.0
        painter.scale(scale, scale)

        # 绘制背景
        self.draw_background(painter)

        # 获取当前时间
        time = QTime.currentTime()

        # 绘制指针
        self.draw_hour_hand(painter, time)
        self.draw_minute_hand(painter, time)
        self.draw_second_hand(painter, time)

        # 绘制中心点
        self.draw_centre(painter)

    def draw_background(self, painter):
        # # 径向渐变背景
        radial = QRadialGradient(QPointF(0, 0), 110, QPointF(0, 0))
        radial.setColorAt(1, QColor(230, 230, 230, 255))
        radial.setColorAt(0.9, QColor(230, 230, 230, 255))

        painter.setPen(Qt.NoPen)
        painter.setBrush(radial)
        painter.drawEllipse(QPointF(0, 0), 110, 110)

    def draw_hour_hand(self, painter, time):
        painter.save()
        # 计算时针角度（包含分钟的影响）
        angle = 30.0 * (time.hour() + time.minute() / 60.0)
        painter.rotate(angle)

        painter.setPen(Qt.black)
        painter.setBrush(Qt.black)
        painter.drawConvexPolygon(QPolygonF(self.hourHand))
        painter.restore()

    def draw_minute_hand(self, painter, time):
        painter.save()
        # 计算分针角度（包含秒的影响）
        angle = 6.0 * (time.minute() + time.second() / 60.0)
        painter.rotate(angle)

        painter.setPen(Qt.black)
        painter.setBrush(Qt.black)
        painter.drawConvexPolygon(QPolygonF(self.minuteHand))
        painter.restore()

    def draw_second_hand(self, painter, time):
        painter.save()
        angle = 6.0 * time.second()
        painter.rotate(angle)

        painter.setPen(Qt.red)
        painter.setBrush(Qt.red)
        painter.drawConvexPolygon(QPolygonF(self.secondHand))
        painter.restore()

    def draw_centre(self, painter):
        # 中心点渐变效果
        conical = QConicalGradient(0, 0, -90.0)
        conical.setColorAt(0.0, Qt.darkGray)
        conical.setColorAt(0.2, QColor(150, 150, 200))
        conical.setColorAt(0.5, Qt.white)
        conical.setColorAt(1.0, Qt.darkGray)

        painter.setPen(Qt.NoPen)
        painter.setBrush(conical)
        painter.drawEllipse(-5, -5, 10, 10)


class SettingsWindow(QWidget):
    settings_saved = pyqtSignal(dict)  # 新增信号

    def __init__(self, initial_settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setWindowFlags(Qt.Window | Qt.WindowCloseButtonHint)
        self.settings = initial_settings.copy()

        # 界面初始化
        self.setup_ui()
        self.load_initial_settings()

    def setup_ui(self):
        self.setStyleSheet("""
                   QGroupBox {
                       font-weight: bold;
                       margin-top: 10px;
                   }
                   QCheckBox {
                       padding: 5px;
                   }
                   QSpinBox {
                       max-width: 80px;
                   }
               """)
        self.buttonBox.accepted.connect(self.save_settings)
        self.buttonBox.rejected.connect(self.hide)

    def load_initial_settings(self):
        # 加载当前设置到UI ↓↓↓
        self.BtnAutoStart.setChecked(self.settings.get('auto_start', False))
        self.checkBox.setChecked(self.settings.get('drawer_animation', True))
        self.mspeed.setValue(self.settings.get('animation_duration', 2000))
        self.ktime.setValue(self.settings.get('stay_duration', 1500))

    def setup_connections(self):
        self.buttonBox.accepted.connect(self.save_settings)
        self.buttonBox.rejected.connect(self.hide)

    def closeEvent(self, event):
        event.ignore()  # 拦截关闭事件
        self.hide()  # 改为隐藏

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.hide()  # ESC键隐藏窗口
    def save_settings(self):
        # 这里添加保存设置的逻辑
        settings = {
            'auto_start': self.BtnAutoStart.isChecked(),
            'animation_enabled': self.checkBox.isChecked(),
            'move_speed': self.mspeed.value(),
            'stay_time': self.ktime.value(),
            'time_second': self.findChild(QLineEdit, "Second").text(),
            'time_minute': self.findChild(QLineEdit, "Minute").text(),
            'time_hour': self.findChild(QLineEdit, "Hour").text(),
            'time_week': self.findChild(QLineEdit, "Week").text()
        }
        # 传递给主窗口或保存到配置文件
        self.settings_saved.emit(settings)  # 异步发送信号
        self.hide()  # 隐藏代替关闭

    def setup_ui(self):
        self.setObjectName("Sets")
        self.setWindowTitle("设置")
        self.resize(257, 395)

        self.verticalLayout = QVBoxLayout(self)

        # 第一组复选框
        self.groupBox_4 = QGroupBox()
        self.groupBox_4.setTitle("")
        self.verticalLayout_4 = QVBoxLayout(self.groupBox_4)

        self.BtnAutoStart = QCheckBox("开机自启动")
        self.checkBox = QCheckBox("抽屉动画效果")

        self.verticalLayout_4.addWidget(self.BtnAutoStart)
        self.verticalLayout_4.addWidget(self.checkBox)
        self.verticalLayout.addWidget(self.groupBox_4)

        # 分隔线
        from PyQt5.QtWidgets import QFrame
        self.line = QFrame()
        self.line.setFrameShape(QFrame.HLine)
        self.verticalLayout.addWidget(self.line)

        # 动画设置组
        self.groupBox = QGroupBox("动画效果设置")
        self.verticalLayout_5 = QVBoxLayout(self.groupBox)

        # 速度和时间设置
        self.horizontalLayout = QHBoxLayout()
        self.verticalLayout_3 = QVBoxLayout()
        self.label = QLabel("移动时间(毫秒)：")
        self.label_2 = QLabel("停留时间(秒)：")
        self.verticalLayout_3.addWidget(self.label)
        self.verticalLayout_3.addWidget(self.label_2)

        self.verticalLayout_2 = QVBoxLayout()
        self.mspeed = QSpinBox()
        self.mspeed.setMaximum(9999)
        self.ktime = QSpinBox()
        self.ktime.setMaximum(120)
        self.verticalLayout_2.addWidget(self.mspeed)
        self.verticalLayout_2.addWidget(self.ktime)

        self.horizontalLayout.addLayout(self.verticalLayout_3)
        self.horizontalLayout.addLayout(self.verticalLayout_2)
        self.verticalLayout_5.addLayout(self.horizontalLayout)

        # 时间设置组
        self.groupBox_2 = QGroupBox("时间设置：")
        self.verticalLayout_6 = QVBoxLayout(self.groupBox_2)

        self.create_time_field("秒：", "Second", self.verticalLayout_6)
        self.create_time_field("分：", "Minute", self.verticalLayout_6)
        self.create_time_field("时：", "Hour", self.verticalLayout_6)
        self.create_time_field("周：", "Week", self.verticalLayout_6)

        self.verticalLayout_5.addWidget(self.groupBox_2)
        self.verticalLayout.addWidget(self.groupBox)

        # 按钮组
        self.buttonBox = QDialogButtonBox()
        self.buttonBox.setStandardButtons(QDialogButtonBox.Cancel | QDialogButtonBox.Ok)
        self.verticalLayout.addWidget(self.buttonBox)

        # 连接复选框到动画设置组
        self.checkBox.clicked.connect(self.groupBox.setEnabled)

    def create_time_field(self, label_text, field_name, layout):
        h_layout = QHBoxLayout()
        label = QLabel(label_text)
        line_edit = QLineEdit()
        line_edit.setObjectName(field_name)
        h_layout.addWidget(label)
        h_layout.addWidget(line_edit)
        layout.addLayout(h_layout)

class PopupClockClass(QWidget):

    def __init__(self):
        super().__init__()
        # 添加CPU负载生成器
        self.cpu_load = CPULoadGenerator()

        self.registry_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        # 修改设置窗口实例化方式
        self.settings_window = None  # 延迟初始化设置窗口
        self.current_settings = {
            'animation_duration': 2000,
            'stay_duration': 1500,
            'drawer_animation': True
        }

        self.suppressed_period = None  # 抑制的时间段类型：'hour'或'half'
        self.dragged_pos = None  # 新增：存储拖动后的位置
        self.debug_mode = False # 默认关闭调试模式
        self.first_run = True  # 添加首次启动标志

        self.load_settings()

        # 背景透明度设置
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)

        # 初始化UI
        self.setup_ui()
        self.setup_timer()
        self.setup_animation()
        self.update_display()
        # 样式调整
        self.setStyleSheet("""
                   QFrame#frame1 {
                       background: qradialgradient(
                           cx:0.5, cy:0.5, radius: 2,
                           fx:0.5, fy:0.5,
                           stop:0 rgba(189, 189, 189, 255),
                           stop:1 rgba(150, 150, 150, 200)
                    
                       );
                       border-radius:22px;
                       border: 1px solid rgba(255,255,255,100);
                   }
                   QFrame#frame_3 {
                       background-color:rgba(230, 230, 230, 220);
                       border-radius:22px;
                       border: 1px solid rgba(0,0,0,30);
                   }
                   QLCDNumber {
                       background:transparent;
                       color: #111;
                       min-width: 120px;
                       qproperty-segmentStyle: Flat;
                       font: bold 18px 'Arial Black'; 
                   }
               """)
        # 窗口初始位置（左侧屏幕外）
        self.screen_geo = QApplication.primaryScreen().availableGeometry()
        self.window_width = 450  # 与resize保持一致
        self.init_pos = QPoint(-self.window_width, 0)  # 初始隐藏在左侧外
        self.show_pos = QPoint(0, 0)  # 显示在左上角
        self.move(self.init_pos)  # 初始位置
        self.setWindowOpacity(0)  # 初始完全显示

        # 添加上下文菜单
        self.setContextMenuPolicy(Qt.ActionsContextMenu)
        debug_action = QAction("调试模式（常显）", self, checkable=True)
        debug_action.toggled.connect(self.toggle_debug_mode)
        self.addAction(debug_action)

        self.setup_tray_icon()  # 添加系统托盘

        # 添加双击检测计时器
        self.last_click_time = QTime.currentTime()  # 记录上次点击时间
        self.click_count = 0  # 点击计数器

        self.double_click_timer = QTimer(self)
        self.double_click_timer.setSingleShot(True)
        self.double_click_timer.timeout.connect(self.check_double_click)


        # 设置窗口标志 - 关键修改
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool  # 最重要的标志，隐藏任务栏图标
        )

    def check_autostart(self):
        """检查是否已设置自启动"""
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.registry_path, 0, winreg.KEY_READ)
        try:
            value, _ = winreg.QueryValueEx(key, "PopupClock")
            return os.path.exists(value)
        except FileNotFoundError:
            return False
        finally:
            key.Close()

    def set_autostart(self, enable):
        """设置/取消自启动"""
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.registry_path, 0, winreg.KEY_SET_VALUE)
        app_path = os.path.abspath(sys.argv[0])

        with key:
            if enable:
                winreg.SetValueEx(key, "PopupClock", 0, winreg.REG_SZ, app_path)
            else:
                try:
                    winreg.DeleteValue(key, "PopupClock")
                except FileNotFoundError:
                    pass
    def load_settings(self):
        # 示例加载设置
        self.debug_mode = False
        self.animation_duration = 2000  # 默认值

    def update_animation_duration(self, duration):
        self.animation_duration = duration
        # 更新现有动画
        self.enter_pos_anim.setDuration(duration)
        self.enter_opacity_anim.setDuration(duration)
        self.exit_pos_anim.setDuration(duration)
        self.exit_opacity_anim.setDuration(duration)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # 双击检测
            self.click_count += 1
            if self.click_count == 1:
                self.double_click_timer.start(QApplication.doubleClickInterval())

            # 保持原有的拖动功能
            self.dragging = True
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def check_double_click(self):
        """检测是否为双击事件"""
        if self.click_count >= 2:
            self.handle_double_click()
        self.click_count = 0

    def handle_double_click(self):
        """处理双击事件 - 立即启动退出动画"""
        print("双击事件debug状态："+str(self.debug_mode) + "显示状态："+str(self.anim_state))

        if not self.debug_mode and self.anim_state == 1:  # 只在显示状态下且非调试模式时响应
            self.start_exit_animation()
            current_time = QTime.currentTime()
            current_min = current_time.minute()
            current_sec = current_time.second()
            # 判断当前时间段类型
            if (current_min ==59 and current_sec >= 30) or (current_min == 0 and current_sec < 30):
                self.suppressed_period = 'hour'
            elif (current_min == 29 and current_sec >= 30) or (current_min == 30 and current_sec < 30):
                self.suppressed_period = 'half'

    def showEvent(self, event):
        """重写showEvent处理首次显示逻辑"""
        super().showEvent(event)
        if self.first_run:
            self.first_run = False
            # 启动首次显示序列
            self.start_initial_sequence()
    def start_initial_sequence(self):
        """首次启动时的隐藏动画"""
        # 确保当前不是调试模式
        if not self.debug_mode:
            # 第一步：播放进入动画
            # 确保之前的连接被断开
            try:
                self.enter_anim_group.finished.disconnect()
            except:
                pass
            self.start_enter_animation()

            # 确保之前的连接被断开
            try:
                self.exit_anim_group.finished.disconnect()
            except:
                pass
            # 第二步：动画完成后启动1.5秒定时器
            self.enter_anim_group.finished.connect(
                lambda: QTimer.singleShot(1500, self.start_exit_animation)
            )

            # 第三步：退出动画完成后设置正常状态
            # self.exit_anim_group.finished.connect(
            #     lambda: setattr(self, 'anim_state', 0)
            # )
            self.exit_anim_group.finished.connect(
                lambda: self.set_anim_state(0)
            )

    def setup_tray_icon(self):
        # 创建系统托盘图标
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon(":/touxiang.ico"))  # 准备一个ico图标文件
        self.tray_icon.setToolTip("我的时钟")

        # 创建右键菜单
        tray_menu = QMenu()
        # 退出动作
        exit_action = QAction("退出", self)
        exit_action.triggered.connect(self.clean_exit)
        # 设置动作（占位）
        setting_action = QAction("设置(开发中)", self)
        setting_action.triggered.connect(lambda: print("开发中"))
        # setting_action.triggered.connect(self.show_settings)
        # 添加始终显示动作
        always_show_action = QAction("始终显示", self, checkable=True)
        always_show_action.toggled.connect(self.toggle_always_show)

        # 添加自启动菜单项
        self.auto_start_action = QAction("开机自启动", self, checkable=True)
        self.auto_start_action.setChecked(self.check_autostart())
        self.auto_start_action.toggled.connect(self.set_autostart)
        tray_menu.insertAction(setting_action, self.auto_start_action)

        # 添加CPU占用控制菜单
        cpu_menu = tray_menu.addMenu("CPU占用控制")

        # 添加滑块控制
        slider_action = QWidgetAction(cpu_menu)
        slider_widget = QWidget()
        slider_layout = QVBoxLayout()

        self.cpu_slider = QSlider(Qt.Horizontal)
        self.cpu_slider.setRange(0, 100)
        self.cpu_slider.setValue(0)
        self.cpu_slider.valueChanged.connect(self.set_cpu_load)

        self.cpu_label = QLabel("0%")
        self.cpu_label.setAlignment(Qt.AlignCenter)

        slider_layout.addWidget(self.cpu_slider)
        slider_layout.addWidget(self.cpu_label)
        slider_widget.setLayout(slider_layout)
        slider_action.setDefaultWidget(slider_widget)
        cpu_menu.addAction(slider_action)

        # 添加预设值
        for percent in [0, 25, 50, 75, 100]:
            action = QAction(f"{percent}%", self)
            action.triggered.connect(lambda checked, p=percent: self.set_cpu_load(p))
            cpu_menu.addAction(action)

        tray_menu.addAction(setting_action)
        tray_menu.addAction(always_show_action)  # 插入到退出按钮前
        tray_menu.addAction(exit_action)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()

        # 托盘图标点击事件
        self.tray_icon.activated.connect(self.on_tray_activated)

    def set_cpu_load(self, percent):
        """设置CPU占用百分比"""
        self.cpu_slider.setValue(percent)
        self.cpu_label.setText(f"{percent}%")
        self.cpu_load.set_load(percent)

    def show_settings(self):
        if not self.settings_window:
            self.settings_window = SettingsWindow(self.current_settings)
            self.settings_window.settings_saved.connect(self.apply_settings)
        self.settings_window.show()
        self.settings_window.raise_()

    def apply_settings(self, settings):
        # 动画期间不更新参数
        if self.anim_state == 2:
            QTimer.singleShot(300, lambda: self.apply_settings(settings))
            return
            # 安全更新动画参数
        self.current_settings.update(settings)
        self.animation_duration = settings.get('animation_duration', 2000)
        self.update_animation_duration()

    def on_tray_activated(self, reason):
        """处理托盘图标点击事件"""
        if reason == QSystemTrayIcon.Trigger:  # 左键单击
            if self.isVisible():
                self.hide()
            else:
                self.show()
                self.raise_()

    def show(self):
        """重写show方法确保正确显示"""
        super().show()
        # 确保窗口置顶
        self.setWindowState(self.windowState() & ~Qt.WindowMinimized)
        self.raise_()
        self.activateWindow()

    def toggle_always_show(self, checked):
        """切换始终显示模式"""
        self.debug_mode = checked

        # 如果当前正在动画中，延迟处理直到动画完成
        if self.anim_state == 2:
            # 先断开之前的连接
            try:
                self.enter_anim_group.finished.disconnect()
                self.exit_anim_group.finished.disconnect()
            except:
                pass

            # 根据当前动画类型设置回调
            if checked:
                # 如果是进入动画，完成后保持显示
                self.enter_anim_group.finished.connect(
                    lambda: [self.set_anim_state(1), self.ensure_visible_state()]
                )
            else:
                # 如果是退出动画，完成后保持隐藏
                self.exit_anim_group.finished.connect(
                    lambda: [self.set_anim_state(0), self.ensure_visible_state()]
                )
        else:
            # 不在动画中，立即处理
            self.ensure_visible_state()

    def ensure_visible_state(self):
        """确保窗口状态与debug_mode一致"""
        if self.debug_mode and self.anim_state != 1:
            self.start_enter_animation()
        elif not self.debug_mode and self.anim_state != 0:
            self.start_exit_animation()

    def clean_exit(self):
        """安全退出程序"""
        try:
            self.screen.screenLocked.disconnect()
            self.screen.screenUnlocked.disconnect()
        except:
            pass
        self.tray_icon.hide()  # 隐藏托盘图标
        self.exit_anim_group.start()  # 如果需要退出动画
        self.exit_anim_group.finished.connect(qApp.quit)  # 动画完成后退出

    def toggle_debug_mode(self, checked):
        """切换调试模式"""
        self.debug_mode = checked
        if checked:  # 如果开启调试模式，强制显示
            try:
                self.enter_anim_group.finished.disconnect()
            except:
                pass
            self.start_enter_animation()
    def setup_ui(self):

        # 尺寸调整
        self.resize(450, 150)

        # 主布局
        self.gridLayout = QGridLayout(self)
        self.gridLayout.setContentsMargins(20, 20, 20, 20)

        # 背景框架
        self.frame1 = QFrame()
        self.frame1.setObjectName("frame1")
        self.horizontalLayout = QHBoxLayout(self.frame1)
        self.horizontalLayout.setContentsMargins(20, 20, 20, 20)

        # 添加时钟部件
        self.clock_widget = DrawClock()
        self.horizontalLayout.addWidget(self.clock_widget)

        # 右侧数字面板
        self.frame_3 = QFrame()
        self.frame_3.setObjectName("frame_3")
        self.gridLayout_3 = QGridLayout(self.frame_3)
        self.lcdNumber = QLCDNumber()
        self.lcdNumber.setDigitCount(8)
        self.lcdNumber.setSegmentStyle(QLCDNumber.Flat)
        self.gridLayout_3.addWidget(self.lcdNumber)

        self.horizontalLayout.addWidget(self.frame_3)
        self.gridLayout.addWidget(self.frame1)

        self.lcdNumber.setAttribute(Qt.WA_AlwaysShowToolTips)  # 强制渲染优化
        self.lcdNumber.setStyle(QStyleFactory.create("Fusion"))  # 使用更现代的样式引擎

        # 无边框设置
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.setWindowTitle("PopupClock")

    def setup_timer(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_display)
        self.timer.start(200)  # 更快的检测频率

    def setup_animation(self):
        # 修改动画速度为500ms
        animation_duration = 2000  # 全局控制动画速度

        # 进入动画组
        self.enter_anim_group = QParallelAnimationGroup()
        # 位置动画
        self.enter_pos_anim = QPropertyAnimation(self, b"pos")
        self.enter_pos_anim.setDuration(animation_duration)
        self.enter_pos_anim.setEasingCurve(QEasingCurve.OutCubic)

        # 透明度动画
        self.enter_opacity_anim = QPropertyAnimation(self, b"windowOpacity")
        self.enter_opacity_anim.setDuration(animation_duration)
        self.enter_opacity_anim.setKeyValueAt(0.0, 0.0)
        self.enter_opacity_anim.setKeyValueAt(0.5, 1)
        self.enter_opacity_anim.setKeyValueAt(1.0, 1.0)
        self.enter_anim_group.addAnimation(self.enter_pos_anim)
        self.enter_anim_group.addAnimation(self.enter_opacity_anim)

        # 退出动画组
        self.exit_anim_group = QParallelAnimationGroup()
        # 位置动画
        self.exit_pos_anim = QPropertyAnimation(self, b"pos")
        self.exit_pos_anim.setDuration(animation_duration)
        self.exit_pos_anim.setEasingCurve(QEasingCurve.InCubic)
        # 透明度动画
        self.exit_opacity_anim = QPropertyAnimation(self, b"windowOpacity")
        self.exit_opacity_anim.setDuration(animation_duration)  # 修正此行
        self.exit_opacity_anim.setKeyValueAt(0.0, 1.0)
        self.exit_opacity_anim.setKeyValueAt(0.5, 1)
        self.exit_opacity_anim.setKeyValueAt(1.0, 0.0)
        self.exit_anim_group.addAnimation(self.exit_pos_anim)
        self.exit_anim_group.addAnimation(self.exit_opacity_anim)

        self.anim_state = 0  # 0:隐藏 1:显示 2:动画中
    def update_display(self):
        # 在时间条件判断前检查动画状态
        if self.anim_state == 2:
            return  # 动画中不处理新触发

        current_time = QTime.currentTime()
        self.lcdNumber.display(current_time.toString("HH:mm:ss"))
        self.clock_widget.set_time(current_time)

        # 如果是首次启动后的第一次更新，跳过时间判断
        if hasattr(self, 'first_run') and self.first_run:
            return

        # 调试/常显模式直接返回（保持显示）
        if self.debug_mode:
            if self.anim_state == 0:  # 如果当前是隐藏状态
                self.start_enter_animation()
            return  # 跳过原有时间判断

        # 计算当前分钟和秒
        current_min = current_time.minute()
        current_sec = current_time.second()


        in_window = False
        current_period = None
        # 检查整点窗口（如07:59:30-08:00:30）
        if (current_min == 59 and current_sec >= 30) or (current_min == 0 and current_sec < 30):  # 59:30-59:59
            current_period = 'hour'
            in_window = True
        # 检查半点窗口（如08:29:30-08:30:30）
        elif (current_min == 29 and current_sec >= 30) or (current_min == 30 and current_sec < 30):  # 29:30-29:59
            current_period = 'half'
            in_window = True

        # 检查是否被抑制
        if in_window and self.suppressed_period == current_period:
            in_window = False
        # 不在时间段时重置抑制
        elif not in_window and current_min not in [59, 0, 29, 30]:
            self.suppressed_period = None


        # print("当前状态：" + str(in_window) + "当前current_period：" + str(current_period) + ":" + str(self.suppressed_period))
        # print("当前状态：" + str(in_window) + "当前时间：" + str(current_min) + ":" + str(current_sec) + "状态" + str(self.anim_state))
        # print("当前状态："+str(self.anim_state))
        # 精确控制动画触发时机
        if in_window:
            # 进入动画触发点（59:30或29:30）
            if (current_min == 59 and current_sec == 30) or \
                    (current_min == 29 and current_sec == 30):
                if self.anim_state in [0, 2]:  # 隐藏或动画中
                    # 断开之前的信号连接（重要！）
                    try:
                        self.enter_anim_group.finished.disconnect()
                    except:
                        pass
                    # 启动进入动画
                    self.start_enter_animation()

        else:
            # 退出动画触发点（00:30或30:30）
            if (current_min == 0 and current_sec >= 30) or \
                    (current_min == 30 and current_sec >= 30):
                if self.anim_state in [1, 2]:  # 显示或动画中
                    # 断开之前的信号连接（重要！）
                    try:
                        self.exit_anim_group.finished.disconnect()
                    except:
                        pass
                    # 启动退出动画
                    self.start_exit_animation()


    def start_enter_animation(self):
        # 停止所有正在运行的动画
        if self.enter_anim_group.state() == QPropertyAnimation.Running:
            self.enter_anim_group.stop()
        if self.exit_anim_group.state() == QPropertyAnimation.Running:
            self.exit_anim_group.stop()

        if self.anim_state == 2:
            return
        self.anim_state = 2
        # 确保之前的连接被断开
        try:
            self.enter_anim_group.finished.disconnect()
        except:
            pass

        # 确定目标位置
        if self.dragged_pos is not None:
            target_pos = self.dragged_pos
        else:
            target_pos = self.show_pos  # 默认位置
        # 计算起始位置
        start_x = target_pos.x() - self.window_width
        start_pos = QPoint(start_x, target_pos.y())

        self.enter_pos_anim.setStartValue(start_pos)
        self.enter_pos_anim.setEndValue(target_pos)
        # 重置透明度（避免动画中断后状态异常）
        self.setWindowOpacity(0)
        self.enter_anim_group.start()
        # 使用安全的状态更新方法
        self.enter_anim_group.finished.connect(
            lambda: self.set_anim_state(1)
        )
        # self.enter_anim_group.finished.connect(
        #     # 添加回调并打印调试信息
        #         lambda: [setattr(self, 'anim_state', 1), print("Enter动画完成，状态设为1")]
        #     )

    def start_exit_animation(self):
        # 停止所有正在运行的动画
        if self.enter_anim_group.state() == QPropertyAnimation.Running:
            self.enter_anim_group.stop()
        if self.exit_anim_group.state() == QPropertyAnimation.Running:
            self.exit_anim_group.stop()

        if self.anim_state == 2:
            return
        self.anim_state = 2
        # 确保之前的连接被断开
        try:
            self.exit_anim_group.finished.disconnect()
        except:
            pass

        current_pos = self.pos()
        # 计算结束位置
        end_x = current_pos.x() - self.window_width
        end_pos = QPoint(end_x, current_pos.y())

        # 设置动画
        self.exit_pos_anim.setStartValue(current_pos)
        self.exit_pos_anim.setEndValue(end_pos)
        # 确保透明度初始状态
        self.setWindowOpacity(1)
        self.exit_anim_group.start()
        # 使用安全的状态更新方法
        self.exit_anim_group.finished.connect(
            lambda: self.set_anim_state(0)
        )
        # self.exit_anim_group.finished.connect(
        #     # 添加回调并打印调试信息
        #     lambda: [setattr(self, 'anim_state', 0) , print("Enter动画完成，状态设为0")]
        # )

    def set_anim_state(self, state):
        """线程安全的状态更新方法"""
        self.anim_state = state
        # 调试模式特殊处理
        if state == 0 and self.debug_mode:
            QTimer.singleShot(100, self.start_enter_animation)

    # 实现窗口拖动
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            current_time = QTime.currentTime()
            elapsed = self.last_click_time.msecsTo(current_time)

            # 双击检测（300ms内两次点击）
            if elapsed < QApplication.doubleClickInterval():
                self.click_count += 1
                if self.click_count == 2:
                    self.handle_double_click()
                    self.click_count = 0
                    return  # 双击事件优先处理
            else:
                self.click_count = 1

            self.last_click_time = current_time

            self.dragging = True
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self.dragging:
            new_pos = event.globalPos() - self.drag_position
            self.move(new_pos)
            # 更新显示位置
            self.show_pos = new_pos
            event.accept()

    def mouseReleaseEvent(self, event):
        self.dragging = False
        self.dragged_pos = self.pos()  # 新增：记录拖动后的位置
        event.accept()


if __name__ == "__main__":
    import sys

    QApplication.setAttribute(Qt.AA_UseDesktopOpenGL)  # 启用硬件加速
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(":/touxiang.ico"))  # 关键：设置应用全局图标
    window = PopupClockClass()
    window.show()
    sys.exit(app.exec_())