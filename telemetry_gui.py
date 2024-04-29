import sys
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QGridLayout, QPushButton, QComboBox, QCheckBox
from PyQt5.QtGui import QFont
from PyQt5.QtCore import QTimer, QThread, pyqtSignal

from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt
import csv
import serial
from serial.tools import list_ports
from datetime import datetime
import random

# font styles
font_family = 'Bahnschrift'
avian_font = QFont(font_family, 20, QFont.Bold)
esc_label_font = QFont(font_family, 12, QFont.Bold)
measurement_font = QFont(font_family, 10)
value_font = QFont(font_family, 28, QFont.Bold)
min_max_font = QFont(font_family, 10)

# consts
DRIVE_ESC_1 = 'Drive ESC 1'
DRIVE_ESC_2 = 'Drive ESC 2'
WEAPON_ESC = 'Weapon ESC'
ARM_ESC = 'Arm ESC'

TEMP = 'Temp'
RPM = 'RPM'
CURRENT = 'Current'
CONSUMPTION = 'Consumption'
VOLTAGE = 'Voltage'

BATTERY_VOLTAGE = 'Battery Voltage'
TOTAL_CURRENT = 'Total Current'
TOTAL_CONSUMPTION = 'Total Consumption'
SIGNAL_STRENGTH = 'Signal Strength'


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
        file_name = f"avian_data_{now}_raw.csv"
        with open(file_name, "w", newline="") as csv_file:
            writer = csv.writer(csv_file)
            writer.writerows(self.raw_data)


class Avian():
    def __init__(self, serial_port, use_fake_data=False):
        self.data = {}
        if not serial_port == None:
            self.serial_reader = SerialReaderThread(serial_port)
            self.serial_reader.new_data.connect(self.handle_data)
            self.serial_reader.start()

        self.use_fake_data = use_fake_data

        self.data_timestamps = []

        self.esc_names = [DRIVE_ESC_1, DRIVE_ESC_2, WEAPON_ESC, ARM_ESC]
        self.esc_measurement_names = [TEMP, RPM, CURRENT, CONSUMPTION, VOLTAGE]
        self.esc_measurement_units = ["°C", "", "A", "mAh", "V"]

        for esc_name in self.esc_names:
            esc_data = {}
            for measurement_name in self.esc_measurement_names:
                esc_data[measurement_name] = {
                    'values': [],
                    'min': None,
                    'max': None,
                }
            self.data[esc_name] = esc_data

        self.robot_measurement_names = [
            BATTERY_VOLTAGE, TOTAL_CURRENT, TOTAL_CONSUMPTION, SIGNAL_STRENGTH
        ]

        for measurement_name in self.robot_measurement_names:
            self.data[measurement_name] = {
                'values': [],
                'min': None,
                'max': None,
            }

    def get_esc_names(self):
        return self.esc_names

    def get_esc_measurement_names(self):
        return self.esc_measurement_names

    def get_esc_measurement_units(self):
        return self.esc_measurement_units

    def get_displayed_esc_measurement_names(self):
        return self.esc_measurement_names[:4]

    def get_displayed_esc_measurement_units(self):
        return self.esc_measurement_units[:4]

    def get_robot_measurement_names(self):
        return self.robot_measurement_names

    def get_all_values(self, measurement, esc=None):
        obj = (self.data if esc == None else self.data[esc])
        return obj[measurement]['values']

    def get_last_n_values(self, measurement, n, esc=None):
        obj = (self.data if esc == None else self.data[esc])
        return obj[measurement]['values'][-n:]

    def get_current_value(self, measurement, esc=None):
        obj = (self.data if esc == None else self.data[esc])
        values = obj[measurement]['values']
        return values[-1] if len(values) > 0 else None

    def get_min_value(self, measurement, esc=None):
        obj = (self.data if esc == None else self.data[esc])
        return obj[measurement]['min']

    def get_max_value(self, measurement, esc=None):
        obj = (self.data if esc == None else self.data[esc])
        return obj[measurement]['max']

    def add_value(self, measurement, value, esc=None):
        obj = (self.data if esc == None else self.data[esc])
        obj[measurement]['values'].append(value)
        min_value = self.get_min_value(measurement, esc)
        if min_value == None or value < min_value:
            obj[measurement]['min'] = value
        max_value = self.get_max_value(measurement, esc)
        if max_value == None or value > max_value:
            obj[measurement]['max'] = value

    def export_to_csv(self):
        timestamp = datetime.now().strftime('%Y_%m_%d_%H_%M_%S')
        csv_data = []

        headers = ['Timestamp']
        for esc in self.get_esc_names():
            for measurement in self.get_esc_measurement_names():
                headers.append(f"{esc} {measurement}")
        for measurement in self.robot_measurement_names:
            headers.append(measurement)
        csv_data.append(headers)

        # one row per timestamp
        for i in range(len(self.data_timestamps)):
            data_row = [self.data_timestamps[i].strftime('%H_%M_%S_%f')]
            for esc in self.get_esc_names():
                for measurement in self.get_esc_measurement_names():
                    all_values = self.get_all_values(measurement, esc)
                    data_row.append(all_values[i] if len(
                        all_values) > i else None)

            for measurement in self.robot_measurement_names:
                all_values = self.get_all_values(measurement)
                data_row.append(all_values[i] if len(
                    all_values) > i else None)
            csv_data.append(data_row)

        file_name = f"avian_data_{timestamp}.csv"
        with open(file_name, "w", newline="") as csv_file:
            writer = csv.writer(csv_file)
            writer.writerows(csv_data)

        self.serial_reader.export_raw_data()

    def print_data(self):
        print(self.data)

    def handle_data(self, data):
        if (not "Data:" in data):
            return

        now_timestamp = datetime.now()
        self.data_timestamps.append(now_timestamp)
        data_array = list(map(lambda str: int(str), data.split()[1:]))
        split_data = {
            DRIVE_ESC_1: data_array[0:9],  # first 9
            DRIVE_ESC_2: data_array[9:18],  # next 9
            WEAPON_ESC: data_array[18:26],  # next 8
            ARM_ESC: data_array[26:34],  # last 8
            SIGNAL_STRENGTH: data_array[34]
        }

        def merge_bytes(byte1, byte2):
            return (byte1 << 8) + byte2

        parsed_esc_data = {}
        for esc in [DRIVE_ESC_1, DRIVE_ESC_2]:
            esc_data = split_data[esc]
            parsed_esc_data[esc] = {
                TEMP: esc_data[0],
                VOLTAGE: merge_bytes(esc_data[1], esc_data[2]) / 100,
                CURRENT: merge_bytes(esc_data[3], esc_data[4]) / 100,
                CONSUMPTION: merge_bytes(esc_data[5], esc_data[6]),
                RPM: merge_bytes(esc_data[7], esc_data[8]) * 100 / 6
            }

        for esc in [WEAPON_ESC, ARM_ESC]:
            esc_data = split_data[esc]
            scale_val = 2042
            current = merge_bytes(esc_data[4], esc_data[5]) / scale_val * 50
            delta_time_hours = (
                now_timestamp - self.data_timestamps[-1]).total_seconds() / 3600
            consumption = current * delta_time_hours
            parsed_esc_data[esc] = {
                TEMP: merge_bytes(esc_data[0], esc_data[1]) / scale_val * 30,
                VOLTAGE: merge_bytes(esc_data[2], esc_data[3]) / scale_val * 20,
                CURRENT: current,
                CONSUMPTION: consumption,
                RPM: merge_bytes(
                    esc_data[6], esc_data[7]) / scale_val * 20416.66
            }

        for esc in parsed_esc_data:
            for measurement in parsed_esc_data[esc]:
                parsed_esc_data[esc][measurement] = round(
                    parsed_esc_data[esc][measurement], 2)
                self.add_value(
                    measurement, parsed_esc_data[esc][measurement], esc)

        parsed_robot_data = {}
        parsed_robot_data[BATTERY_VOLTAGE] = parsed_esc_data[DRIVE_ESC_1][VOLTAGE]
        parsed_robot_data[TOTAL_CURRENT] = sum(
            list(map(lambda esc: parsed_esc_data[esc][CURRENT], self.esc_names)))
        parsed_robot_data[TOTAL_CONSUMPTION] = sum(
            list(map(lambda esc: parsed_esc_data[esc][CONSUMPTION], self.esc_names)))
        parsed_robot_data[SIGNAL_STRENGTH] = split_data[SIGNAL_STRENGTH]

        for measurement in parsed_robot_data:
            self.add_value(
                measurement, round(parsed_robot_data[measurement], 2)
            )


class TelemetryGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.com_port_dropdown = QComboBox()
        ports = list_ports.comports()
        self.port_names = list(map(lambda port: port.name, ports))
        self.com_port_dropdown.addItems(self.port_names)

        if len(self.port_names) > 0:
            self.avian = Avian(self.port_names[0])
        else:
            self.avian = Avian(None)

        self.displayed_data = {}
        self.plots_checkbox = QCheckBox("Show plots")
        self.plots_checkbox.stateChanged.connect(self.on_checkbox_toggle)
        self.should_show_plots = False

        self.initialize_gui()

    # TODO: hook up properly
    def on_select_port(self, index):
        selected_port = self.port_names[index]
        self.avian = Avian(selected_port)

    def on_checkbox_toggle(self):
        self.should_show_plots = self.plots_checkbox.isChecked()
        self.reinitialize_gui()

    def initialize_gui(self):
        self.main_layout = QHBoxLayout()
        self.setLayout(self.main_layout)

        esc_layout = QGridLayout()
        self.main_layout.addLayout(esc_layout)

        for esc_index, esc_name in enumerate(self.avian.get_esc_names()):
            esc_square = QVBoxLayout()

            esc_label = QLabel(esc_name)
            esc_label.setFont(esc_label_font)
            esc_square.addWidget(esc_label)

            measurement_grid = QGridLayout()
            measurement_grid.setSpacing(8)

            displayed_measurements = self.avian.get_displayed_esc_measurement_names()
            displayed_measurement_units = self.avian.get_displayed_esc_measurement_units()

            for measurement_index, measurement_name in enumerate(displayed_measurements):
                units = displayed_measurement_units[
                    measurement_index
                ]
                measurement_square = QWidget()
                measurement_square_style = "background-color: #cccccc;"
                measurement_square.setStyleSheet(measurement_square_style)
                esc_layout.addWidget(measurement_square)

                value_column = QVBoxLayout(measurement_square)
                self.create_measurement_display(
                    value_column, measurement_name, units, esc_name
                )
                measurement_grid.addWidget(
                    measurement_square, measurement_index // 2, measurement_index % 2
                )

            esc_square.addLayout(measurement_grid)
            esc_layout.addLayout(esc_square, esc_index // 2, esc_index % 2)

        # right side
        robot_column = QVBoxLayout()
        self.main_layout.addLayout(robot_column)

        avian_label = QLabel("Colossal Avian")
        avian_label.setFont(avian_font)
        robot_column.addWidget(avian_label)

        self.create_measurement_display(
            robot_column, BATTERY_VOLTAGE, 'V'
        )
        self.total_current_label = self.create_measurement_display(
            robot_column, TOTAL_CURRENT, 'A'
        )
        self.total_consumption_label = self.create_measurement_display(
            robot_column, TOTAL_CONSUMPTION, 'mAh'
        )
        self.total_consumption_label = self.create_measurement_display(
            robot_column, SIGNAL_STRENGTH, 'dBm'
        )

        dropdown_title = QLabel("COM Port")
        dropdown_title.setFont(measurement_font)
        robot_column.addWidget(dropdown_title)
        robot_column.addWidget(self.com_port_dropdown)

        robot_column.addWidget(self.plots_checkbox)

        export_button = QPushButton("Export to CSV")
        export_button.clicked.connect(self.avian.export_to_csv)
        robot_column.addWidget(export_button)

        # flex
        self.main_layout.setStretch(0, 8)
        self.main_layout.setStretch(1, 2)

        self.setWindowTitle('Colossal Avian')
        self.setGeometry(100, 100, 500, 300)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_gui)
        self.timer.start(100)

    def reinitialize_gui(self):
        if self.main_layout is not None:
            while self.main_layout.count():
                item = self.main_layout.takeAt(0)
                self.main_layout.removeItem(item)
        self.timer.stop()

        self.initialize_gui()

    def update_gui(self):
        if (self.avian.use_fake_data):
            print('using fake data')
            for measurement in self.avian.get_robot_measurement_names():
                self.avian.add_value(measurement, random.randint(-100, 0)
                                     if measurement == SIGNAL_STRENGTH else random.randint(0, 100))
            for esc in self.avian.get_esc_names():
                for measurement in self.avian.get_displayed_esc_measurement_names():
                    self.avian.add_value(
                        measurement, random.randint(0, 100), esc)

        # update labels and plots
        for measurement in self.avian.get_robot_measurement_names():
            self.update_label_and_plot(measurement)
        for esc in self.avian.get_esc_names():
            for measurement in self.avian.get_displayed_esc_measurement_names():
                self.update_label_and_plot(measurement, esc)

    def create_measurement_display(self, layout, measurement, units, esc=None):
        name_label = QLabel(measurement)
        name_label.setFont(measurement_font)
        layout.addWidget(name_label)

        current_value = self.avian.get_current_value(measurement, esc)
        value_label = QLabel(str(current_value))
        value_label.setFont(value_font)
        layout.addWidget(value_label)

        data = self.avian.get_all_values(
            measurement, esc
        )

        min_value = self.avian.get_min_value(measurement, esc)
        max_value = self.avian.get_max_value(measurement, esc)
        min_max_label = QLabel(
            f"{min_value} | {max_value}"
        )
        min_max_label.setFont(min_max_font)
        layout.addWidget(min_max_label)

        fig, ax = plt.subplots()
        canvas = FigureCanvas(fig)
        # if self.should_show_plots:
        layout.addWidget(canvas)

        display_data = {'value_label': value_label, 'units': units, 'min_max_label': min_max_label,
                        'fig': fig, 'ax': ax, 'canvas': canvas, 'data': data}
        if esc == None:
            self.displayed_data[measurement] = display_data
        else:
            if not esc in self.displayed_data:
                self.displayed_data[esc] = {}
            self.displayed_data[esc][measurement] = display_data

    def update_label_and_plot(self, measurement, esc=None):
        obj = self.displayed_data[measurement] if esc == None else self.displayed_data[esc][measurement]
        value = self.avian.get_current_value(measurement, esc)
        value_text = f"{str(value)} {obj['units']}"
        min_max_text = f"{str(self.avian.get_min_value(measurement, esc))} | {str(self.avian.get_max_value(measurement, esc))}"

        if esc == None:
            self.displayed_data[measurement]['value_label'].setText(value_text)
            if measurement == TOTAL_CONSUMPTION and value != None:
                percent = round(100 * value / 3000, 2)
                self.displayed_data[measurement]['value_label'].setText(
                    f"{value_text} ({percent}%)"
                )
            elif measurement == SIGNAL_STRENGTH and value != None:
                if value < -90:
                    style_sheet = 'background-color: red;'
                elif value < -80:
                    style_sheet = 'background-color: orange;'
                elif value < -70:
                    style_sheet = 'background-color: yellow;'
                else:
                    style_sheet = 'color: black;'
                self.displayed_data[measurement]['value_label'].setStyleSheet(
                    style_sheet
                )

            self.displayed_data[measurement]['min_max_label'].setText(
                min_max_text
            )
        else:
            self.displayed_data[esc][measurement]['value_label'].setText(
                value_text
            )
            if measurement == TEMP and value != None:
                if value >= 80:
                    style_sheet = 'background-color: red;'
                elif value >= 70:
                    style_sheet = 'background-color: orange;'
                elif value >= 60:
                    style_sheet = 'background-color: yellow;'
                else:
                    style_sheet = 'color: black;'
                self.displayed_data[esc][measurement]['value_label'].setStyleSheet(
                    style_sheet
                )

            self.displayed_data[esc][measurement]['min_max_label'].setText(
                min_max_text
            )

        update_plot = self.displayed_data[measurement][
            'ax'] != None if esc == None else self.displayed_data[esc][measurement]['ax'] != None

        if update_plot:
            data = self.avian.get_last_n_values(
                measurement, 100, esc
            )
            if esc == None:
                self.displayed_data[measurement]['data'] = data
                self.displayed_data[measurement]['ax'].clear()
                self.displayed_data[measurement]['ax'].plot(
                    self.displayed_data[measurement]['data']
                )
                self.displayed_data[measurement]['canvas'].draw()
            else:
                self.displayed_data[esc][measurement]['data'] = data
                self.displayed_data[esc][measurement]['ax'].clear()
                self.displayed_data[esc][measurement]['ax'].plot(
                    self.displayed_data[esc][measurement]['data']
                )
                self.displayed_data[esc][measurement]['canvas'].draw()

    # def closeEvent(self, event):
        # self.avian.export_to_csv()f


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = TelemetryGUI()
    window.show()
    sys.exit(app.exec_())
