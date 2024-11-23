from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPainter, QFont
from PyQt5.QtWidgets import QApplication, QWidget
import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QGridLayout, QPushButton, QComboBox, QProgressBar, QScrollArea
from PyQt5.QtGui import QFont, QPainter, QColor
from PyQt5.QtCore import QTimer, QThread, pyqtSignal, Qt
import pyqtgraph as pg
import csv
import serial
from serial.tools import list_ports
from datetime import datetime
import random


class SerialReaderThread(QThread):
    new_data = pyqtSignal(str)
    timestamps = []
    raw_data = []

    def __init__(self, port, parent=None):
        super().__init__(parent)
        self.baudrate = 115200
        self.serial_port = serial.Serial(port, self.baudrate)
        self.serial_port.flushInput()

    def set_port(self, port):
        self.serial_port = serial.Serial(port, self.baudrate)
        self.serial_port.flushInput()

    def run(self):
        while True:
            if self.serial_port.in_waiting:
                line = self.serial_port.readline().decode().strip()
                self.new_data.emit(line)
                self.timestamps.append(datetime.now())
                self.raw_data.append(line)
                print(line)

    def export_raw_data(self):
        now = datetime.now().strftime('%Y_%m_%d_%H_%M_%S')
        file_name = f"data/telemetry_{now}_raw.csv"
        with open(file_name, "w", newline="") as csv_file:
            writer = csv.writer(csv_file)
            writer.writerows(self.raw_data)


TEMP = 'Temp'
RPM = 'RPM'
CURRENT = 'Current'
CONSUMPTION = 'Consumption'
VOLTAGE = 'Voltage'
INPUT_SIGNAL = 'Input Signal'

BATTERY_VOLTAGE = 'Battery Voltage'
TOTAL_CURRENT = 'Total Current'
TOTAL_CONSUMPTION = 'Total Consumption'
SIGNAL_STRENGTH = 'Signal Strength'

FONT_FAMILY = 'Bahnschrift'

UNITS = {
    TEMP: "°C",
    RPM: "",
    CURRENT: "A",
    CONSUMPTION: "V",
    VOLTAGE: "V",
    INPUT_SIGNAL: "%"
}


class CustomProgressBar(QProgressBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTextVisible(False)
        self.unclamped_value = 0

    def set_value(self, value):
        self.unclamped_value = value
        super().setValue(self.clamp_value(value))

    def clamp_value(self, unclamped_value):
        max_value = self.maximum()
        min_value = self.minimum()
        return max(min(unclamped_value, max_value), min_value)

    def paintEvent(self, event):
        # Custom painting for the progress bar
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Calculate the filled portion (limited to 100%)
        clamped_value = self.clamp_value(self.unclamped_value)
        max_value = self.maximum()
        min_value = self.minimum()

        proportion = (self.unclamped_value - min_value) / \
            (max_value - min_value)
        fill_width = int(self.width() * proportion)

        bar_color = self.palette().highlight(
        ) if self.unclamped_value <= max_value else Qt.red
        # Paint the filled portion
        painter.fillRect(0, 0, fill_width, self.height(), bar_color)

        # Draw the border and background
        painter.setPen(self.palette().color(self.palette().WindowText))
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))

        # Draw the text in the center
        text = str(self.unclamped_value)
        text_color = Qt.black if self.unclamped_value >= min_value else Qt.red
        painter.setPen(text_color)
        painter.drawText(self.rect(), Qt.AlignCenter, text)

        painter.end()


class Measurement():
    def __init__(self, name, minimum=0, maximum=100, is_shown=True):
        self.name = name
        self.unit = UNITS[name]

        self.values = []
        self.minimum = minimum
        self.maximum = maximum

        self.is_shown = is_shown

        self.init_name_label(name)
        self.init_value_bar(minimum, maximum, self.unit)
        self.init_min_max_labels(minimum, maximum)

    def get_current_value(self):
        return self.values[-1] if len(self.values) > 0 else self.minimum

    def add_value(self, value):
        self.values.append(value)

    def init_name_label(self, name):
        self.name_label = QLabel(name + "  ")
        self.name_label.setFont(QFont(FONT_FAMILY, 18, QFont.Bold))

    def init_value_bar(self, minimum, maximum, unit):
        self.value_bar = CustomProgressBar()
        self.value_bar.setMinimum(minimum)
        self.value_bar.setMaximum(maximum)
        self.value_bar.setFormat(
            f" %v {unit}")
        bar_style = """
        QProgressBar { 
            border: 2px solid grey; 
            border-radius: 0px; 
            text-align: left; 
            height: 80px;
            font-size: 40px;
            padding: 0;
        } 
        QProgressBar::chunk {
            background-color: #3add36; 
            width: 1px;
        }
        """
        self.value_bar.setStyleSheet(bar_style)
        self.update_value_bar()

    def init_min_max_labels(self, min, max):
        measurement_min_max_font = QFont(FONT_FAMILY, 10, QFont.Bold)

        self.min_label = QLabel(str(min))
        self.min_label.setFont(measurement_min_max_font)

        self.max_label = QLabel(str(max))
        self.max_label.setFont(measurement_min_max_font)

    def update_value_bar(self):
        self.value_bar.set_value(self.get_current_value())


class ESC():
    def __init__(self, name, measurements):
        self.name = name
        self.measurements = measurements
        self.init_card()

    def init_card(self):
        self.card = QWidget()
        self.card.setStyleSheet(
            "background-color: #eeeeee; padding: 16px; border-radius: 16px;")

        card_layout = QVBoxLayout()
        self.card.setLayout(card_layout)

        self.name_label = QLabel(self.name)
        name_font = QFont(FONT_FAMILY, 20, QFont.Bold)
        self.name_label.setFont(name_font)
        card_layout.addWidget(self.name_label)

        measurement_grid = QGridLayout()
        measurement_grid.setHorizontalSpacing(8)

        for m_index, measurement in enumerate(self.measurements):
            measurement_grid.addWidget(
                measurement.name_label, m_index, 0, alignment=Qt.AlignRight)
            measurement_grid.addWidget(measurement.min_label, m_index, 1)
            measurement_grid.addWidget(measurement.value_bar, m_index, 2)
            measurement_grid.addWidget(measurement.max_label, m_index, 3)
        card_layout.addLayout(measurement_grid)
        self.card.setLayout(card_layout)


class Robot():
    def __init__(self, name, escs, serial_port):
        self.name = name
        self.escs = escs

        if serial_port != None:
            self.serial_reader = SerialReaderThread(serial_port)
            self.serial_reader.new_data.connect(self.handle_data)
            self.serial_reader.start()

    def add_random_values(self):
        for esc in self.escs:
            for measurement in esc.measurements:
                random_value = random.randint(
                    measurement.minimum,
                    measurement.maximum * 2
                )
                measurement.add_value(random_value)
                measurement.update_value_bar()


class TelemetryGUI(QWidget):
    def __init__(self, robot: Robot):
        super().__init__()
        self.setWindowTitle(robot.name + ' Telemetry')
        self.setStyleSheet("background-color: white;")
        self.robot = robot

        self.com_port_dropdown = QComboBox()
        ports = list_ports.comports()
        self.port_names = list(map(lambda port: port.name, ports))
        self.com_port_dropdown.addItems(self.port_names)

        self.displayed_data = {}
        self.use_fake_data = sys.argv[1] if len(sys.argv) >= 2 else False

        self.robot_name_font = QFont(FONT_FAMILY, 20, QFont.Bold)

        self.initialize_gui()

    def initialize_gui(self):
        self.main_layout = QHBoxLayout()
        self.setLayout(self.main_layout)

        esc_grid = QGridLayout()
        esc_grid.setSpacing(16)
        self.main_layout.addLayout(esc_grid)

        for e_idx, esc in enumerate(self.robot.escs):
            esc_grid.addWidget(esc.card, e_idx // 2, e_idx % 2)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_gui)
        # self.timer.start(1000)

    def update_gui(self):
        if (self.use_fake_data):
            self.robot.add_random_values()


if __name__ == '__main__':
    app = QApplication(sys.argv)

    esc_drive_1 = ESC('Drive ESC 1', [
        Measurement(TEMP, 25, 100),
        Measurement(RPM, 0, 10000),
        Measurement(CURRENT, 0, 30),
        Measurement(CONSUMPTION, 0, 3000),
        Measurement(INPUT_SIGNAL, 0, 100)
    ])

    esc_drive_2 = ESC('Drive ESC 2', [
        Measurement(TEMP, 25, 100),
        Measurement(RPM, 0, 10000),
        Measurement(CURRENT, 0, 30),
        Measurement(CONSUMPTION, 0, 3000),
        Measurement(INPUT_SIGNAL, 0, 100)
    ])

    esc_weapon = ESC('Weapon ESC', [
        Measurement(TEMP, 25, 100),
        Measurement(RPM, 0, 20000),
        Measurement(CURRENT, 0, 100),
        Measurement(CONSUMPTION, 0, 3000),
        Measurement(INPUT_SIGNAL, 0, 100)
    ])

    esc_arm = ESC('Arm ESC', [
        Measurement(TEMP, 25, 100),
        Measurement(RPM, 0, 20000),
        Measurement(CURRENT, 0, 100),
        Measurement(CONSUMPTION, 0, 3000),
        Measurement(INPUT_SIGNAL, 0, 100)
    ])

    avian = Robot('Colossal Avian', [
        esc_drive_1, esc_drive_2, esc_weapon, esc_arm
    ], None)

    window = TelemetryGUI(avian)
    window.showMaximized()
    sys.exit(app.exec_())
