import json
import os
import subprocess
import sys
from dataclasses import dataclass

from PyQt5 import QtCore

from logger import get_logger


@dataclass
class TreeDex:
    TITLE: int = 0
    FORMAT: int = 1
    SIZE: int = 2
    PROGRESS: int = 3
    STATUS: int = 4
    SPEED: int = 5
    ETA: int = 6


class WorkerThread(QtCore.QObject):
    update_progress = QtCore.pyqtSignal(object, int, str)

    def __init__(self, tree_item, link, folder, video_fmt, metadata, thumbnail, subtitles):
        super().__init__()
        self.tree_item = tree_item
        self.link = link
        self.folder = folder
        self.video_fmt = video_fmt
        self.metadata = metadata
        self.thumbnail = thumbnail
        self.subtitles = subtitles
        self.log = get_logger("worker_log")

    def get_args(self):
        if self.video_fmt == "best":
            _args = ['yt-dlp', '--newline', '-i', '-o', f'{self.folder}/%(title)s.%(ext)s', '--ignore-config',
                     '--hls-prefer-native', self.link]
        elif self.video_fmt == "mp4":
            _args = ['yt-dlp', '--newline', '-i', '-o', f'{self.folder}/%(title)s.%(ext)s', '-S', 'ext:mp4:m4a',
                     '--ignore-config', '--hls-prefer-native', self.link]
        elif self.video_fmt == "mp3":
            _args = ['yt-dlp', '--newline', '-i', '-o', f'{self.folder}/%(title)s.%(ext)s', '-x',
                     '--audio-format', 'mp3', '--audio-quality', '0', '--ignore-config', '--hls-prefer-native',
                     self.link]
        if self.metadata > 0:
            _args.insert(len(_args) - 1, '--embed-metadata')
        if self.thumbnail > 0:
            _args.insert(len(_args) - 1, '--embed-thumbnail')
        if self.subtitles > 0:
            _args.insert(len(_args) - 1, '--write-auto-subs')
        return _args

    @QtCore.pyqtSlot()
    def run(self):
        create_window = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        result = subprocess.run(['yt-dlp', '--dump-json', self.link], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, creationflags=create_window)
        info_dict = json.loads(result.stdout)
        self.update_progress.emit(self.tree_item, TreeDex.TITLE, info_dict['title'])
        with subprocess.Popen(self.get_args(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              universal_newlines=True, creationflags=create_window) as p:
            err = False

            for line in p.stdout:
                if "[youtube]" in line:
                    self.update_progress.emit(self.tree_item, TreeDex.STATUS, "Processing")

                elif "[download]" in line and "100%" not in line and "ETA" in line:
                    self.update_progress.emit(self.tree_item, TreeDex.STATUS, "Downloading")
                    data = line.split()
                    self.update_progress.emit(self.tree_item, TreeDex.SIZE, data[3])
                    self.update_progress.emit(self.tree_item, TreeDex.PROGRESS, data[1])
                    self.update_progress.emit(self.tree_item, TreeDex.ETA, data[7])
                    self.update_progress.emit(self.tree_item, TreeDex.SPEED, data[5])

                elif "[Merger]" in line or "[ExtractAudio]" in line:
                    self.update_progress.emit(self.tree_item, TreeDex.STATUS, "Converting")

                if "error" in line.lower() and "warning" not in line.lower():
                    err = True
                    self.log.error(line)
                    self.update_progress.emit(self.tree_item, TreeDex.SIZE, "ERROR")
                    self.update_progress.emit(self.tree_item, TreeDex.PROGRESS, "ERROR")
                    self.update_progress.emit(self.tree_item, TreeDex.STATUS, "ERROR")
                    self.update_progress.emit(self.tree_item, TreeDex.SPEED, "ERROR")

            if not err:
                self.update_progress.emit(self.tree_item, TreeDex.PROGRESS, "100%")
                self.update_progress.emit(self.tree_item, TreeDex.STATUS, "Finished")
