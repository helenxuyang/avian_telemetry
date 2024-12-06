from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QGridLayout, QPushButton, QComboBox, QProgressBar, QSizePolicy
from PyQt5.QtGui import QFont, QPainter, QPixmap
from PyQt5.QtCore import QTimer, QThread, pyqtSignal, Qt
import pyqtgraph as pg
import csv
import serial
import sys
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
                now = datetime.now()
                self.timestamps.append(now)
                self.raw_data.append(line)
                now_str = f"{now.strftime('%H_%M_%S.')}{round(now.microsecond / 10000):02d}"
                print(f"{now_str} {line}")

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
    CONSUMPTION: "mAh",
    VOLTAGE: "V",
    INPUT_SIGNAL: "%",
    BATTERY_VOLTAGE: "V",
    TOTAL_CURRENT: "A",
    TOTAL_CONSUMPTION: "mAh",
    SIGNAL_STRENGTH: "dBm"
}


class CustomProgressBar(QProgressBar):
    def __init__(self, unit, parent=None):
        super().__init__(parent)
        self.setTextVisible(False)
        self.unclamped_value = 0
        self.unit = unit

    def set_value(self, value):
        super().setValue(self.clamp_value(value))
        self.unclamped_value = value
        self.update()

    def clamp_value(self, unclamped_value):
        max_value = self.maximum()
        min_value = self.minimum()
        return max(min(unclamped_value, max_value), min_value)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        max_value = self.maximum()
        min_value = self.minimum()

        proportion = (self.unclamped_value - min_value) / \
            (max_value - min_value)
        fill_width = int(self.width() * proportion)

        bar_color = self.palette().highlight(
        ) if self.unclamped_value <= max_value else Qt.red
        painter.fillRect(0, 0, fill_width, self.height(), bar_color)

        painter.setPen(self.palette().color(self.palette().WindowText))
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))

        # Draw the text in the center
        text = f"{str(self.unclamped_value)} {self.unit}"
        text_color = Qt.black if self.unclamped_value >= min_value else Qt.red
        painter.setPen(text_color)
        painter.drawText(self.rect(), Qt.AlignCenter, text)

        painter.end()


class Measurement():
    def __init__(self, name, minimum=0, maximum=100, is_shown=True, should_plot=True):
        self.name = name
        self.unit = UNITS[name]

        self.values = []
        self.minimum = minimum
        self.maximum = maximum

        self.is_shown = is_shown
        self.should_plot = should_plot

        self.init_name_label(name)
        self.init_value_label(self.unit)
        self.init_value_bar(minimum, maximum, self.unit)
        self.init_min_max_labels(minimum, maximum)

        self.init_plot()

    def get_current_value(self):
        return self.values[-1] if len(self.values) > 0 else self.minimum

    def add_value(self, value):
        self.values.append(value)

    def init_name_label(self, name):
        self.name_label = QLabel(name + "  ")
        self.name_label.setFont(
            QFont(FONT_FAMILY, 24, QFont.Bold))
        self.name_label.setSizePolicy(
            QSizePolicy.Preferred, QSizePolicy.Minimum)

    def init_value_label(self, unit):
        self.value_label = QLabel(f"{self.get_current_value()} {unit}")
        self.value_label.setFont(QFont(FONT_FAMILY, 18, QFont.Bold))
        self.value_label.setFont(
            QFont(FONT_FAMILY, 24, QFont.Normal))
        self.value_label.setSizePolicy(
            QSizePolicy.Preferred, QSizePolicy.Minimum)

    def init_value_bar(self, minimum, maximum, unit):
        self.value_bar = CustomProgressBar(unit)
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
            font-size: 48px;
            font-weight: bold;
            padding: 0;
            font-family: Bahnschrift;
        }
        QProgressBar::chunk {
            background-color: #3add36;
            width: 1px;
        }
        """
        self.value_bar.setStyleSheet(bar_style)
        self.update_value_bar()

    def init_min_max_labels(self, min, max):
        measurement_min_max_font = QFont(FONT_FAMILY, 14, QFont.Bold)

        self.min_label = QLabel(str(min))
        self.min_label.setFont(measurement_min_max_font)

        self.max_label = QLabel(str(max))
        self.max_label.setFont(measurement_min_max_font)

    def init_plot(self):
        pg.setConfigOption('background', 'w')
        self.graph = pg.PlotWidget()
        self.pen_options = pg.mkPen('k', width=1)

    def update_value_bar(self):
        self.value_bar.set_value(self.get_current_value())

    def update_value_label(self):
        self.value_label.setText(f"{self.get_current_value()} {self.unit}")

    def update_plot(self):
        self.graph.clear()
        self.graph.plot(self.values, pen=self.pen_options)
        num_values = len(self.values)
        n = 50
        min_x = max(num_values-1-n, 0)
        max_x = num_values-1
        min_y = self.minimum
        max_y = self.maximum

        self.graph.getPlotItem().getViewBox().setRange(
            xRange=(min_x, max_x), yRange=(min_y, max_y))

    def add_random_value(self):
        random_value = random.randint(
            self.minimum,
            round(self.maximum * 1.2)
        )
        self.add_value(random_value)

    def clear_values(self):
        self.values = []


class SignalStrengthMeasurement(Measurement):
    def __init__(self, name, minimum=0, maximum=100, is_shown=True):
        super().__init__(name, minimum, maximum, is_shown)

    def update_value_label(self):
        value = self.get_current_value()
        if value < -90:
            self.value_label.setStyleSheet('background-color: red;')
        elif value < -80:
            self.value_label.setStyleSheet('background-color: orange;')
        elif value < -70:
            self.value_label.setStyleSheet('background-color: yellow;')
        super().update_value_label()


class TemperatureMeasurement(Measurement):
    def __init__(self, name, minimum=0, maximum=100, is_shown=True):
        super().__init__(name, minimum, maximum, is_shown)

    def update_value_label(self):
        value = self.get_current_value()
        if value >= 85:
            self.value_label.setStyleSheet('background-color: red;')
        elif value >= 75:
            self.value_label.setStyleSheet('background-color: orange;')
        elif value >= 68:
            self.value_label.setStyleSheet('background-color: yellow;')
        super().update_value_label()


class ESC():
    def __init__(self, name, measurements: list[Measurement], active=True):
        self.name = name
        self.measurements: dict[str, Measurement] = {}
        for measurement in measurements:
            self.measurements[measurement.name] = measurement
        self.active = active
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
            if measurement.is_shown:
                measurement_grid.addWidget(
                    measurement.name_label, m_index, 0, alignment=Qt.AlignRight)
                measurement_grid.addWidget(measurement.min_label, m_index, 1)
                measurement_grid.addWidget(measurement.value_bar, m_index, 2)
                measurement_grid.addWidget(measurement.max_label, m_index, 3)
                measurement_grid.addWidget(measurement.graph, m_index, 4)
        card_layout.addLayout(measurement_grid)
        self.card.setLayout(card_layout)


class Robot():
    def __init__(self, name, escs: list[ESC], serial_port):

        self.name = name
        self.escs: dict[str, ESC] = {}
        for esc in escs:
            self.escs[esc.name] = esc

        self.timestamps = []
        self.start_time = datetime.now()

        self.measurements: dict[str, Measurement] = {
            BATTERY_VOLTAGE: Measurement(BATTERY_VOLTAGE, 5, 28, True),
            TOTAL_CURRENT: Measurement(TOTAL_CURRENT, 0, 400, True),
            TOTAL_CONSUMPTION: Measurement(TOTAL_CONSUMPTION, 0, 12000, True),
            SIGNAL_STRENGTH: SignalStrengthMeasurement(SIGNAL_STRENGTH, -100, 0, True),
        }

        if serial_port != None:
            self.serial_reader = SerialReaderThread(serial_port)
            self.serial_reader.new_data.connect(self.handle_data)
            self.serial_reader.start()
        else:
            print("NO PORT")

    def __iter__(self):
        return iter(self.escs.values())

    def add_parsed_data(self, parsed_esc_data, signal_strength):
        total_current = 0
        total_consumption = 0
        for esc, data in parsed_esc_data.items():
            if (self.escs[esc].active):
                total_current += data[CURRENT]
                total_consumption += data[CONSUMPTION]
                for measurement in data:
                    value = data[measurement]
                    rounded_value = round(value)
                    self.add_value(esc, measurement, rounded_value)
                    # print(esc, data)

        self.measurements[BATTERY_VOLTAGE].add_value(
            round(parsed_esc_data[WEAPON_ESC][VOLTAGE]))
        self.measurements[TOTAL_CURRENT].add_value(round(total_current))
        self.measurements[TOTAL_CONSUMPTION].add_value(
            round(total_consumption))
        self.measurements[SIGNAL_STRENGTH].add_value(signal_strength)

    def handle_data(self, received_data):
        if (not "Data:" in received_data):
            return

        now = datetime.now()
        self.timestamps.append(now)

        raw_data = list(map(lambda str: int(str), received_data.split()[1:]))
        split_data = {
            DRIVE_ESC_1: raw_data[0:9],  # first 9
            DRIVE_ESC_2: raw_data[9:18],  # next 9
            ARM_ESC: raw_data[18:26],  # next 8
            WEAPON_ESC: raw_data[26:34],  # last 8
            SIGNAL_STRENGTH: raw_data[34]
        }

        def merge_bytes(byte1, byte2):
            return (byte1 << 8) + byte2

        parsed_esc_data = {}
        for esc_name in [DRIVE_ESC_1, DRIVE_ESC_2]:
            if (self.escs[esc_name].active):
                esc_data = split_data[esc_name]
                parsed_esc_data[esc_name] = {
                    TEMP: esc_data[0],
                    VOLTAGE: merge_bytes(esc_data[1], esc_data[2]) / 100,
                    CURRENT: merge_bytes(esc_data[3], esc_data[4]) / 100,
                    CONSUMPTION: merge_bytes(esc_data[5], esc_data[6]),
                    RPM: int(merge_bytes(esc_data[7], esc_data[8]) * 100 / 6)
                }

        for esc_name in [WEAPON_ESC, ARM_ESC]:
            if (self.escs[esc_name].active):
                esc_data = split_data[esc_name]
                scale_val = 2042
                current = merge_bytes(
                    esc_data[4], esc_data[5]) / scale_val * 50

                delta_time_hours = (
                    now - self.timestamps[-2]).total_seconds() / 3600 if len(self.timestamps) > 2 else 0
                curr_consumption = current * 1000 * delta_time_hours
                prev_consumption = self.escs[esc_name].measurements[CONSUMPTION].get_current_value(
                )
                parsed_esc_data[esc_name] = {
                    TEMP: merge_bytes(esc_data[0], esc_data[1]) / scale_val * 30,
                    VOLTAGE: merge_bytes(esc_data[2], esc_data[3]) / scale_val * 20,
                    CURRENT: current,
                    CONSUMPTION: prev_consumption + curr_consumption,
                    RPM: int(merge_bytes(
                        esc_data[6], esc_data[7]) / scale_val * 20416.66 / 7)
                }

        self.add_parsed_data(parsed_esc_data, split_data[SIGNAL_STRENGTH])

    def add_random_values(self):
        for esc in self:
            for measurement in esc:
                measurement.add_random_value()

        for measurement in self.measurements.values():
            measurement.add_random_value()

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
                measurement.update_plot()
        for measurement in self.measurements.values():
            measurement.update_value_label()
            measurement.update_plot()

    def clear_data(self):
        for esc in self:
            for measurement in esc:
                measurement.clear_values()
        self.repaint()

    def export_to_csv(self, is_auto_saved=False):
        csv_data = []

        headers = ['Timestamp', 'Seconds from start']
        for esc in self:
            for measurement in esc:
                headers.append(f"{esc.name} {measurement.name}")
        csv_data.append(headers)

        for i, timestamp in enumerate(self.timestamps):
            formatted_timestamp = timestamp.strftime('%H_%M_%S_%f')
            seconds_since_start = round(
                (timestamp - self.start_time).total_seconds(), 3)
            data_row = [formatted_timestamp, seconds_since_start]

            for esc in self:
                for measurement in esc:
                    data_row.append(measurement.values[i] if len(
                        measurement.values) > i else -1)
            csv_data.append(data_row)

        now = datetime.now().strftime('%Y_%m_%d_%H_%M_%S')
        file_name = f"telemetry_{now}_auto_saved.csv" if is_auto_saved else f"telemetry_{now}.csv"
        with open(file_name, "w", newline="") as csv_file:
            writer = csv.writer(csv_file)
            writer.writerows(csv_data)

        if hasattr(self, 'serial_reader'):
            self.serial_reader.export_raw_data()


class TelemetryGUI(QWidget):
    def __init__(self, robot: Robot):
        super().__init__()
        self.setWindowTitle(robot.name + ' Telemetry')

        self.setStyleSheet("background-color: white;")
        self.robot = robot

        self.should_auto_save = True

        self.com_port_dropdown = QComboBox()
        ports = list_ports.comports()
        self.port_names = list(map(lambda port: port.name, ports))
        self.com_port_dropdown.addItems(self.port_names)

        self.use_fake_data = sys.argv[1] if len(sys.argv) >= 2 else False

        self.initialize_gui()

    def initialize_gui(self):
        self.main_layout = QHBoxLayout()
        self.setLayout(self.main_layout)

        esc_grid = QGridLayout()
        esc_grid.setSpacing(16)
        self.main_layout.addLayout(esc_grid)

        for e_idx, esc in enumerate(self.robot):
            if (esc.active):
                esc_grid.addWidget(esc.card, e_idx // 2, e_idx % 2)

        self.main_layout.addLayout(self.get_robot_column())

        self.timer = QTimer()
        self.timer.start(100 if self.use_fake_data else 100)

        self.start_recording()

    def get_robot_column(self):
        robot_column = QVBoxLayout()
        margin = 16
        robot_column.setContentsMargins(margin, margin, margin, margin)
        robot_column.setSpacing(8)

        robot_name_label = QLabel("Colossal Avian")
        robot_name_label.setFont(QFont(FONT_FAMILY, 32, QFont.Bold))
        robot_column.addWidget(robot_name_label)

        robot_img = QLabel(self)
        pixmap = QPixmap('avian.png')
        robot_img.setPixmap(pixmap)
        robot_img.setFixedHeight(200)
        robot_img.setFixedWidth(250)
        robot_img.setScaledContents(True)
        robot_column.addWidget(robot_img)

        for m_index, measurement in enumerate(self.robot.measurements.values()):
            if (measurement.is_shown):
                robot_column.addWidget(measurement.name_label)
                robot_column.addWidget(measurement.value_label)

        # self.com_port_dropdown = QComboBox()
        # ports = list_ports.comports()
        # self.port_names = list(map(lambda port: port.name, ports))
        # self.com_port_dropdown.addItems(self.port_names)

        export_button = QPushButton("Export to CSV")
        export_button.clicked.connect(self.robot.export_to_csv)
        robot_column.addWidget(export_button)

        self.stop_button = QPushButton("Pause recording")
        robot_column.addWidget(self.stop_button)

        clear_button = QPushButton("Clear data")
        clear_button.clicked.connect(self.clear_recording)
        robot_column.addWidget(clear_button)

        return robot_column

    def update_gui(self):
        if (self.use_fake_data):
            # self.robot.mock_handle_data()
            self.robot.add_random_values()
        self.robot.repaint()

    def start_recording(self):
        self.timer.timeout.connect(self.update_gui)
        self.stop_button.clicked.connect(self.pause_recording)
        self.recording = True
        self.stop_button.setText("Pause recording")

    def resume_recording(self):
        self.stop_button.clicked.disconnect()
        self.start_recording()

    def pause_recording(self):
        self.timer.timeout.disconnect()
        self.stop_button.clicked.disconnect()
        self.stop_button.clicked.connect(self.resume_recording)
        self.recording = False
        self.stop_button.setText("Resume recording")

    def clear_recording(self):
        if self.should_auto_save:
            self.robot.export_to_csv(True)
        self.robot.clear_data()

    def closeEvent(self, event):
        if self.should_auto_save:
            self.robot.export_to_csv(True)


if __name__ == '__main__':
    app = QApplication(sys.argv)

    escs = [
        ESC(DRIVE_ESC_1, [
            TemperatureMeasurement(TEMP, 25, 100),
            Measurement(RPM, 0, 10000),
            Measurement(CURRENT, 0, 30),
            Measurement(CONSUMPTION, 0, 3000),
            Measurement(VOLTAGE, 5, 28, False),
            Measurement(INPUT_SIGNAL, 0, 100, False)
        ], active=False),
        ESC(DRIVE_ESC_2, [
            TemperatureMeasurement(TEMP, 25, 100),
            Measurement(RPM, 0, 10000),
            Measurement(CURRENT, 0, 30),
            Measurement(CONSUMPTION, 0, 3000),
            Measurement(VOLTAGE, 5, 28, False),
            Measurement(INPUT_SIGNAL, 0, 100, False)
        ], active=False),
        ESC(WEAPON_ESC, [
            TemperatureMeasurement(TEMP, 25, 100),
            Measurement(RPM, 0, 20000),
            Measurement(CURRENT, 0, 100),
            Measurement(CONSUMPTION, 0, 3000),
            Measurement(VOLTAGE, 5, 28, False),
            Measurement(INPUT_SIGNAL, 0, 100, False)
        ], active=True),
        ESC(ARM_ESC, [
            TemperatureMeasurement(TEMP, 25, 100),
            Measurement(RPM, 0, 20000),
            Measurement(CURRENT, 0, 100),
            Measurement(CONSUMPTION, 0, 3000),
            Measurement(VOLTAGE, 5, 28, False),
            Measurement(INPUT_SIGNAL, 0, 100, False)
        ], active=False)
    ]

    ports = list_ports.comports()
    avian = Robot('Colossal Avian', escs,
                  ports[0].name if len(ports) > 0 else None)

    window = TelemetryGUI(avian)
    window.showMaximized()
    sys.exit(app.exec_())
