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
        file_name = f"telemetry_{now}_raw.csv"
        with open(file_name, "w", newline="") as csv_file:
            writer = csv.writer(csv_file)
            writer.writerows(self.raw_data)


DRIVE_ESC_1 = 'Drive ESC 1'
DRIVE_ESC_2 = 'Drive ESC 2'
WEAPON_ESC = 'Weapon ESC'
ARM_ESC = 'Arm ESC'

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
    def __init__(self, name, measurements: list[Measurement]):
        self.name = name
        self.measurements: dict[str, Measurement] = {}
        for measurement in measurements:
            self.measurements[measurement.name] = measurement
        self.init_card()

    def __iter__(self):
        return iter(self.measurements.values())

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

        for m_index, measurement in enumerate(self):
            measurement_grid.addWidget(
                measurement.name_label, m_index, 0, alignment=Qt.AlignRight)
            measurement_grid.addWidget(measurement.min_label, m_index, 1)
            measurement_grid.addWidget(measurement.value_bar, m_index, 2)
            measurement_grid.addWidget(measurement.max_label, m_index, 3)
        card_layout.addLayout(measurement_grid)
        self.card.setLayout(card_layout)


class Robot():
    def __init__(self, name, escs: list[ESC], serial_port):
        self.name = name
        self.escs: dict[str, ESC] = {}
        for esc in escs:
            self.escs[esc.name] = esc

        self.timestamps = []
        self.seconds_since_start = []
        self.start_time = datetime.now()

        if serial_port != None:
            self.serial_reader = SerialReaderThread(serial_port)
            self.serial_reader.new_data.connect(self.handle_data)
            self.serial_reader.start()

    def __iter__(self):
        return iter(self.escs.values())

    def add_timestamps(self, now):
        self.timestamps.append(now)
        seconds_since_start = round(
            (now - self.start_time).total_seconds(), 3)
        self.seconds_since_start.append(seconds_since_start)

    def handle_data(self, received_data):
        if (not "Data:" in received_data):
            return

        now = datetime.now()
        self.add_timestamps(now)

        raw_data = list(map(lambda str: int(str), received_data.split()[1:]))
        raw_data_by_esc = {
            DRIVE_ESC_1: raw_data[0:9],  # first 9
            DRIVE_ESC_2: raw_data[9:18],  # next 9
            WEAPON_ESC: raw_data[18:26],  # next 8
            ARM_ESC: raw_data[26:34],  # last 8
            SIGNAL_STRENGTH: raw_data[34]
        }

        def merge_bytes(byte1, byte2):
            return (byte1 << 8) + byte2

        parsed_esc_data = {}
        for esc in [DRIVE_ESC_1, DRIVE_ESC_2]:
            esc_data = raw_data_by_esc[esc]
            parsed_esc_data[esc] = {
                TEMP: esc_data[0],
                VOLTAGE: merge_bytes(esc_data[1], esc_data[2]) / 100,
                CURRENT: merge_bytes(esc_data[3], esc_data[4]) / 100,
                CONSUMPTION: merge_bytes(esc_data[5], esc_data[6]),
                RPM: int(merge_bytes(esc_data[7], esc_data[8]) * 100 / 6)
            }

        for esc in [WEAPON_ESC, ARM_ESC]:
            esc_data = raw_data_by_esc[esc]
            scale_val = 2042
            current = merge_bytes(esc_data[4], esc_data[5]) / scale_val * 50
            delta_time_hours = (
                now - self.timestamps[-1]).total_seconds() / 3600
            consumption = current * 1000 * delta_time_hours
            parsed_esc_data[esc] = {
                TEMP: merge_bytes(esc_data[0], esc_data[1]) / scale_val * 30,
                VOLTAGE: merge_bytes(esc_data[2], esc_data[3]) / scale_val * 20,
                CURRENT: current,
                CONSUMPTION: consumption,
                RPM: int(merge_bytes(
                    esc_data[6], esc_data[7]) / scale_val * 20416.66 / 7)
            }

        for esc in parsed_esc_data:
            for measurement in parsed_esc_data[esc]:
                value = parsed_esc_data[esc][measurement]
                rounded_value = round(value)
                self.add_value(esc, measurement, rounded_value)

    def add_random_values(self):
        for esc in self:
            for measurement in esc:
                random_value = random.randint(
                    measurement.minimum,
                    measurement.maximum * 2
                )
                measurement.add_value(random_value)

    def add_value(self, esc, measurement, value):
        self.escs[esc].measurements[measurement].add_value(value)

    def mock_handle_data(self):
        mock_data = 'Data:'
        for _ in range(35):
            random_num = random.randint(0, 100)
            mock_data += ' '
            mock_data += str(random_num)
        print('MOCK ' + mock_data)
        self.handle_data(mock_data)

    def repaint(self):
        for esc in self:
            for measurement in esc:
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

        for e_idx, esc in enumerate(self.robot):
            esc_grid.addWidget(esc.card, e_idx // 2, e_idx % 2)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_gui)
        self.timer.start(1000 if self.use_fake_data else 100)

    def update_gui(self):
        if (self.use_fake_data):
            self.robot.mock_handle_data()
            # self.robot.add_random_values()
        self.robot.repaint()


if __name__ == '__main__':
    app = QApplication(sys.argv)

    escs = [
        ESC(DRIVE_ESC_1, [
            Measurement(TEMP, 25, 100),
            Measurement(RPM, 0, 10000),
            Measurement(CURRENT, 0, 30),
            Measurement(CONSUMPTION, 0, 3000),
            Measurement(VOLTAGE, 5, 28, False),
            Measurement(INPUT_SIGNAL, 0, 100)
        ]),
        ESC(DRIVE_ESC_2, [
            Measurement(TEMP, 25, 100),
            Measurement(RPM, 0, 10000),
            Measurement(CURRENT, 0, 30),
            Measurement(CONSUMPTION, 0, 3000),
            Measurement(VOLTAGE, 5, 28, False),
            Measurement(INPUT_SIGNAL, 0, 100)
        ]),
        ESC(WEAPON_ESC, [
            Measurement(TEMP, 25, 100),
            Measurement(RPM, 0, 20000),
            Measurement(CURRENT, 0, 100),
            Measurement(CONSUMPTION, 0, 3000),
            Measurement(VOLTAGE, 5, 28, False),
            Measurement(INPUT_SIGNAL, 0, 100)
        ]),
        ESC(ARM_ESC, [
            Measurement(TEMP, 25, 100),
            Measurement(RPM, 0, 20000),
            Measurement(CURRENT, 0, 100),
            Measurement(CONSUMPTION, 0, 3000),
            Measurement(VOLTAGE, 5, 28, False),
            Measurement(INPUT_SIGNAL, 0, 100)
        ])
    ]

    avian = Robot('Colossal Avian', escs, None)

    window = TelemetryGUI(avian)
    window.showMaximized()
    sys.exit(app.exec_())
