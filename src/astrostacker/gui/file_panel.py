"""Sidebar file panel with macOS-native styling.

Supports drag-and-drop from the OS file manager and folder import.
"""

from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from astrostacker.config import FILE_FILTER, SUPPORTED_EXTENSIONS


def _collect_supported_files(paths: list[str]) -> list[str]:
    """Given a mix of file and directory paths, return supported image files.

    Directories are scanned one level deep (not recursive).
    Individual files are kept if they have a supported extension.
    Results are sorted alphabetically by filename.
    """
    result: list[str] = []
    for p in paths:
        path = Path(p)
        if path.is_dir():
            for child in sorted(path.iterdir()):
                if child.is_file() and child.suffix.lower() in SUPPORTED_EXTENSIONS:
                    result.append(str(child))
        elif path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
            result.append(str(path))
    return result


class DropListWidget(QListWidget):
    """QListWidget that accepts file and folder drops from the OS.

    Emits ``files_dropped`` with a list of resolved file paths
    (folders are scanned for supported image extensions).
    """

    files_dropped = pyqtSignal(list)

    _NORMAL_BORDER = ""
    _HOVER_BORDER = (
        "DropListWidget {"
        "  border: 2px solid rgba(255, 149, 0, 0.6);"
        "  border-radius: 6px;"
        "}"
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragDropMode(QListWidget.DragDropMode.DropOnly)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet(self._HOVER_BORDER)
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dragLeaveEvent(self, event):
        self.setStyleSheet(self._NORMAL_BORDER)
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        self.setStyleSheet(self._NORMAL_BORDER)
        if event.mimeData().hasUrls():
            raw_paths = []
            for url in event.mimeData().urls():
                local = url.toLocalFile()
                if local:
                    raw_paths.append(local)
            if raw_paths:
                resolved = _collect_supported_files(raw_paths)
                if resolved:
                    self.files_dropped.emit(resolved)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)


class FrameListGroup(QWidget):
    """A collapsible section with header label, file list, and action buttons."""

    files_changed = pyqtSignal()
    file_selected = pyqtSignal(str)

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self._base_title = title
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 8)
        layout.setSpacing(4)

        # Section header
        self._header = QLabel(self._base_title.upper())
        self._header.setObjectName("sectionHeader")
        layout.addWidget(self._header)

        # File list (with drag-and-drop support)
        self.list_widget = DropListWidget()
        self.list_widget.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.list_widget.setMinimumHeight(60)
        self.list_widget.setMaximumHeight(140)
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        self.list_widget.files_dropped.connect(self._add_paths)
        layout.addWidget(self.list_widget)

        # Action buttons row
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(6)

        style = self.style()

        # Add button with dropdown menu (Files / Folder)
        self.add_btn = QPushButton("Add")
        self.add_btn.setObjectName("secondaryButton")
        self.add_btn.setFixedHeight(28)
        self.add_btn.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_FileDialogNewFolder))
        self.add_btn.setToolTip(
            "Add image files or an entire folder.\n"
            "You can also drag and drop files/folders onto the list."
        )

        add_menu = QMenu(self)
        add_menu.addAction(
            style.standardIcon(QStyle.StandardPixmap.SP_FileIcon),
            "Add Files...",
            self._add_files,
        )
        add_menu.addAction(
            style.standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon),
            "Add Folder...",
            self._add_folder,
        )
        self.add_btn.setMenu(add_menu)
        btn_layout.addWidget(self.add_btn)

        self.remove_btn = QPushButton("Remove")
        self.remove_btn.setObjectName("secondaryButton")
        self.remove_btn.setFixedHeight(28)
        self.remove_btn.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_DialogDiscardButton))
        self.remove_btn.clicked.connect(self._remove_selected)
        btn_layout.addWidget(self.remove_btn)

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setObjectName("secondaryButton")
        self.clear_btn.setFixedHeight(28)
        self.clear_btn.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_DialogResetButton))
        self.clear_btn.clicked.connect(self._clear_all)
        btn_layout.addWidget(self.clear_btn)

        layout.addLayout(btn_layout)

    def _on_item_clicked(self, item: QListWidgetItem):
        path = item.data(Qt.ItemDataRole.UserRole)
        if path:
            self.file_selected.emit(path)

    def _add_paths(self, paths: list[str]):
        """Add a list of file paths to the list widget.

        Shared by file dialog, folder dialog, and drag-and-drop.
        Skips duplicates already in the list.
        """
        existing = set(self.get_paths())
        added = 0
        for path in paths:
            if path not in existing:
                item = QListWidgetItem(Path(path).name)
                item.setData(Qt.ItemDataRole.UserRole, path)
                item.setToolTip(path)
                self.list_widget.addItem(item)
                existing.add(path)
                added += 1
        if added:
            self._update_header()
            self.files_changed.emit()

    def _add_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, f"Add {self._base_title}", "", FILE_FILTER
        )
        if paths:
            self._add_paths(paths)

    def _add_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, f"Add {self._base_title} from Folder"
        )
        if folder:
            paths = _collect_supported_files([folder])
            if paths:
                self._add_paths(paths)

    def _remove_selected(self):
        for item in self.list_widget.selectedItems():
            self.list_widget.takeItem(self.list_widget.row(item))
        self._update_header()
        self.files_changed.emit()

    def _clear_all(self):
        self.list_widget.clear()
        self._update_header()
        self.files_changed.emit()

    def _update_header(self):
        count = self.list_widget.count()
        if count > 0:
            self._header.setText(f"{self._base_title.upper()}  ({count})")
        else:
            self._header.setText(self._base_title.upper())

    def title(self):
        return self._base_title

    def get_paths(self) -> list[str]:
        paths = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            path = item.data(Qt.ItemDataRole.UserRole)
            if path:
                paths.append(path)
        return paths

    def count(self) -> int:
        return self.list_widget.count()


class FilePanel(QWidget):
    """Sidebar panel containing frame lists for all frame types."""

    file_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._master_dark_path = ""
        self._master_flat_path = ""
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(2)

        # App title in sidebar
        title_label = QLabel("Frames")
        title_label.setStyleSheet(
            "font-size: 18px; font-weight: 700; color: #ffffff;"
            "padding-bottom: 8px;"
        )
        layout.addWidget(title_label)

        self.lights = FrameListGroup("Light Frames")
        self.darks = FrameListGroup("Dark Frames")
        self.flats = FrameListGroup("Flat Frames")
        self.dark_flats = FrameListGroup("Dark Flat Frames")

        for group in (self.lights, self.darks, self.flats, self.dark_flats):
            layout.addWidget(group)
            group.file_selected.connect(self.file_selected.emit)

        # Master frame loaders
        master_header = QLabel("OR LOAD EXISTING MASTERS")
        master_header.setObjectName("sectionHeader")
        layout.addWidget(master_header)

        master_layout = QHBoxLayout()
        master_layout.setSpacing(6)

        style = self.style()
        folder_icon = style.standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon)

        self._master_dark_btn = QPushButton("Master Dark...")
        self._master_dark_btn.setObjectName("secondaryButton")
        self._master_dark_btn.setFixedHeight(28)
        self._master_dark_btn.setIcon(folder_icon)
        self._master_dark_btn.setToolTip(
            "Load a pre-built master dark FITS file.\n"
            "Overrides individual dark frames above."
        )
        self._master_dark_btn.clicked.connect(self._load_master_dark)
        master_layout.addWidget(self._master_dark_btn)

        self._master_flat_btn = QPushButton("Master Flat...")
        self._master_flat_btn.setObjectName("secondaryButton")
        self._master_flat_btn.setFixedHeight(28)
        self._master_flat_btn.setIcon(folder_icon)
        self._master_flat_btn.setToolTip(
            "Load a pre-built master flat FITS file.\n"
            "Overrides individual flat frames above."
        )
        self._master_flat_btn.clicked.connect(self._load_master_flat)
        master_layout.addWidget(self._master_flat_btn)

        layout.addLayout(master_layout)

        self._master_dark_label = QLabel("")
        self._master_dark_label.setStyleSheet(
            "font-size: 10px; color: rgba(255,255,255,0.4);"
        )
        layout.addWidget(self._master_dark_label)

        self._master_flat_label = QLabel("")
        self._master_flat_label.setStyleSheet(
            "font-size: 10px; color: rgba(255,255,255,0.4);"
        )
        layout.addWidget(self._master_flat_label)

        layout.addStretch()

    def _load_master_dark(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Master Dark", "", FILE_FILTER
        )
        if path:
            self._master_dark_path = path
            self._master_dark_label.setText(f"Dark: {Path(path).name}")
            self._master_dark_btn.setText("Master Dark \u2713")

    def _load_master_flat(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Master Flat", "", FILE_FILTER
        )
        if path:
            self._master_flat_path = path
            self._master_flat_label.setText(f"Flat: {Path(path).name}")
            self._master_flat_btn.setText("Master Flat \u2713")

    def get_light_paths(self) -> list[str]:
        return self.lights.get_paths()

    def get_dark_paths(self) -> list[str]:
        return self.darks.get_paths()

    def get_flat_paths(self) -> list[str]:
        return self.flats.get_paths()

    def get_dark_flat_paths(self) -> list[str]:
        return self.dark_flats.get_paths()

    def get_master_dark_path(self) -> str:
        return self._master_dark_path

    def get_master_flat_path(self) -> str:
        return self._master_flat_path
