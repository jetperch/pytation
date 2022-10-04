# Copyright 2019-2021 Jetperch LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import sys
from pytation import __version__, Context
from PySide6 import QtCore, QtWidgets, QtGui
from time import sleep
import pkgutil
import queue
import threading
import logging


LOG_COLOR = {
    logging.CRITICAL: QtGui.QColor(255, 0, 0),
    logging.ERROR: QtGui.QColor(128, 0, 0),
    logging.WARNING: QtGui.QColor(255, 165, 0),
    logging.INFO: QtGui.QColor(0, 0, 0),
    logging.DEBUG: QtGui.QColor(128, 128, 128),
}


class Handler(logging.Handler):

    def __init__(self, cbk):
        logging.Handler.__init__(self)
        self._cbk = cbk

    def emit(self, record):
        self._cbk(record)


class Formatter(logging.Formatter):
    def formatException(self, ei):
        result = super(Formatter, self).formatException(ei)
        return result

    def format(self, record):
        s = super(Formatter, self).format(record)
        if record.exc_text:
            s = s.replace('\n', '')
        return s


class QResyncEvent(QtCore.QEvent):
    """An event containing a request for python message processing."""
    EVENT_TYPE = QtCore.QEvent.Type(QtCore.QEvent.registerEventType())

    def __init__(self):
        QtCore.QEvent.__init__(self, self.EVENT_TYPE)

    def __str__(self):
        return 'QResyncEvent()'

    def __len__(self):
        return 0


class StationObject:

    def __init__(self, parent, station):
        self._context = Context(station)
        self._parent = parent
        self._log = logging.getLogger('station')
        self._context.callback_register('progress', self._on_progress_cbk)
        self._context.callback_register('state', self._on_state_cbk)
        self._context.callback_register('wait_for_user', self._on_wait_for_user_cbk)
        self._context.callback_register('prompt', self._on_prompt_cbk)
        self.wait_for_user = False
        self.prompt_result_str = None

    def _on_progress_cbk(self, progress):
        self._parent.on_message({'type': 'progress', 'data': progress})

    def _on_state_cbk(self, state):
        self._parent.on_message({'type': 'state', 'data': state})

    def _on_wait_for_user_cbk(self):
        self.wait_for_user = False
        while True:
            if self._context.do_quit:
                raise KeyboardInterrupt('do_quit while wait_for_user')
            elif self.wait_for_user:
                return
            sleep(0.05)

    def _on_prompt_cbk(self, prompt_str):
        self.prompt_result_str = None
        self._parent.on_message({'type': 'prompt', 'data': prompt_str})
        while True:
            if self._context.do_quit:
                raise KeyboardInterrupt('do_quit while prompt')
            elif self.prompt_result_str is False:
                return None
            elif self.prompt_result_str is not None:
                return self.prompt_result_str
            sleep(0.05)

    def keyPressEvent(self, event: QtGui.QKeyEvent):
        handler = self._context.handler('qt_keypress')
        if handler is not None:
            return handler(self._context, event)
        return False

    def run(self):
        self._log.info('Station thread starting')
        self._context.station_run()
        self._log.info('Station thread stopping')

    @QtCore.Slot()
    def quit_request(self):
        self._context.do_quit = True


class MainWindow(QtWidgets.QMainWindow):

    def __init__(self, app, station):
        super(MainWindow, self).__init__()
        self.setObjectName('MainWindow')
        self._app = app
        self._handler = Handler(self._on_log_cbk)
        self._formatter = Formatter('%(asctime)s %(levelname)s %(message)s', '%Y%m%d %H:%M:%S')
        self._log = logging.getLogger()
        self._station_thread = None
        self._station = None
        self._queue = queue.Queue()
        self._pixmap_bin = None

        self.resize(800, 600)

        #window_icon = station.get('window_icon')
        #if window_icon is not None:
        #    self._icon = QIcon()
        #    self._icon.addFile(window_icon, QSize(), QIcon.Normal, QIcon.Off)
        #    self.setWindowIcon(self._icon)

        self._central_widget = QtWidgets.QWidget(self)
        self._central_widget.setObjectName('_central_widget')
        self.setCentralWidget(self._central_widget)
        self._vertical_layout = QtWidgets.QVBoxLayout(self._central_widget)
        self._vertical_layout.setObjectName('_vertical_layout')

        self._frame = QtWidgets.QFrame(self._central_widget)
        self._frame.setObjectName('_frame')
        self._frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self._frame.setFrameShadow(QtWidgets.QFrame.Raised)
        self._vertical_layout.addWidget(self._frame)
        self._horizontal_layout = QtWidgets.QHBoxLayout(self._frame)
        self._horizontal_layout.setObjectName('_horizontal_layout')

        self._image_label = QtWidgets.QLabel(self._frame)
        self._image_label.setObjectName('_image_label')
        size_policy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)
        size_policy.setHorizontalStretch(1)
        size_policy.setVerticalStretch(0)
        size_policy.setHeightForWidth(self._image_label.sizePolicy().hasHeightForWidth())
        self._image_label.setSizePolicy(size_policy)
        self._image_label.setAlignment(QtGui.Qt.AlignCenter)
        self._horizontal_layout.addWidget(self._image_label)

        self._stage_text = QtWidgets.QLabel(self._frame)
        self._stage_text.setObjectName('_stage_text')
        size_policy.setHeightForWidth(self._stage_text.sizePolicy().hasHeightForWidth())
        self._stage_text.setSizePolicy(size_policy)
        self._stage_text.setAlignment(QtGui.Qt.AlignCenter)
        self._horizontal_layout.addWidget(self._stage_text)

        self._logging_textEdit = QtWidgets.QTextEdit(self._central_widget)
        self._logging_textEdit.setObjectName('_logging_textEdit')
        self._logging_textEdit.setUndoRedoEnabled(False)
        self._logging_textEdit.setReadOnly(True)
        self._logging_textEdit.setTextInteractionFlags(QtGui.Qt.NoTextInteraction)
        self._vertical_layout.addWidget(self._logging_textEdit)

        self._progress_bar = QtWidgets.QProgressBar(self._central_widget)
        self._progress_bar.setObjectName('_progress_bar')
        self._progress_bar.setRange(0, 1000)
        self._vertical_layout.addWidget(self._progress_bar)

        self._logging_configure()
        self._log.info('\n**************************************' +
                       '\n* STATION=%s' +
                       '\n* VERSION=%s' +
                       '\n**************************************',
                       station['name'], __version__)
        self._log_demo()

        self._shortcut_spacebar = QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Space), self)
        self._shortcut_spacebar.activated.connect(self._on_spacebar)

        # self.showFullScreen()
        self.showMaximized()
        self._station_start(station)

    def _station_start(self, station):
        self._station = StationObject(self, station)

        self._station_thread = threading.Thread(target=self._station.run)
        self._station_thread.start()

    def _station_stop(self):
        if self._station_thread is not None:
            self._station.quit_request()
            self._station_thread.join()
            self._station = None
            self._station_thread = None

    @QtCore.Slot(float)
    def _on_progress(self, progress):
        if progress <= 0:
            self._logging_textEdit.clear()
        self._progress_bar.setValue(round(progress * 1000))

    @QtCore.Slot(float)
    def _on_state(self, state):
        pixmap = state.get('pixmap')
        style = state.get('style', 'QLabel { background-color : white; color : black; font-size : 12pt; }')
        html = state.get('html', '')
        if pixmap is None:
            self._image_label.clear()
            self._pixmap_bin = None
        else:
            try:
                pixmap_bin = QtGui.QPixmap(pixmap)
                self._log.info('image_label pixmap: %s => %s', pixmap, pixmap_bin.size())
                if pixmap_bin is None:
                    self._log.warning('QPixmap failed for resource %s', state.get('pixmap'))
                self._image_label.setPixmap(pixmap_bin)
                self._pixmap_bin = pixmap_bin
            except Exception:
                self._log.warning('Could not load image')
        if style is not None:
            self._stage_text.setStyleSheet(style)
        if html is not None:
            self._stage_text.setText(html)

    @QtCore.Slot(str)
    def _on_prompt(self, prompt_str):
        s, status = QtWidgets.QInputDialog.getText(self, "Input data", prompt_str)
        if s is None or not status:
            self._station.prompt_result_str = False
        else:
            self._station.prompt_result_str = s

    def _logging_configure(self):
        self._handler.setLevel(logging.INFO)
        self._log.addHandler(self._handler)
        self._log.setLevel(logging.DEBUG)

    def _log_demo(self):
        self._log.critical('critical')
        self._log.error('error')
        self._log.warning('warning')
        self._log.info('info')
        self._log.debug('debug')

    def keyPressEvent(self, event: QtGui.QKeyEvent):
        key = event.key()
        if key in [QtCore.Qt.Key_Escape]:
            self.close()
        elif self._station.keyPressEvent(event):
            pass
        else:
            self._station.wait_for_user = True
        event.accept()

    def _on_spacebar(self):
        self._station.wait_for_user = True

    def event(self, event: QtCore.QEvent):
        if event.type() == QResyncEvent.EVENT_TYPE:
            # process resync_handler resync calls.
            event.accept()
            self._message_process()
            return True
        else:
            return super(MainWindow, self).event(event)

    def _message_process(self):
        while True:
            try:
                msg = self._queue.get(block=False)
                msg_type = msg['type']
                if msg_type == 'log':
                    self.on_logRecord(msg['data'])
                elif msg_type == 'progress':
                    self._on_progress(msg['data'])
                elif msg_type == 'state':
                    self._on_state(msg['data'])
                elif msg_type == 'prompt':
                    self._on_prompt(msg['data'])
            except queue.Empty:
                break

    def on_message(self, msg):
        self._queue.put(msg)
        event = QResyncEvent()
        QtCore.QCoreApplication.postEvent(self, event)

    def _on_log_cbk(self, record):
        msg = {
            'type': 'log',
            'data': record
        }
        self.on_message(msg)

    @QtCore.Slot(object)
    def on_logRecord(self, record: logging.LogRecord):
        txt = self._formatter.format(record)
        color = LOG_COLOR[record.levelno]
        self._logging_textEdit.setTextColor(color)
        self._logging_textEdit.append(txt)

    def closeEvent(self, event: QtGui.QCloseEvent):
        self._log.info('MainWindow.closeEvent')
        self._station_stop()
        event.accept()


def run(station):
    #if sys.platform.startswith('win'):
    #    ctypes.windll.user32.SetProcessDPIAware()
    #QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling)
    app = QtWidgets.QApplication(sys.argv)

    resources = []
    log = logging.getLogger()
    for package, data in station['gui_resources']:
        b = pkgutil.get_data(package, data)
        log.info(f'resource {package} {data} => {len(b)} bytes')
        if b is None or not len(b):
            log.warning('Could not find resource: %s %s', package, data)
        if not QtCore.QResource.registerResourceData(b):
            log.warning('Could not register resource: %s %s', package, data)
        resources.append(b)

    try:
        ui = MainWindow(app, station)
        rc = app.exec_()
    except Exception:
        log.exception('while running MainWindow')
        raise
    return rc
