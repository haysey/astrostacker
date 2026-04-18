"""First-run setup wizard for new users.

Shows once on first launch. Walks through camera type, optional plate
solving setup, and a quick-start guide. Can be re-launched from Help menu.
"""

from __future__ import annotations

from PyQt6.QtCore import QSettings, Qt
from PyQt6.QtGui import QDoubleValidator, QFont, QIntValidator
from PyQt6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from astrostacker.config import APP_NAME

SETTINGS_ORG = "HayseysAstrostacker"
SETTINGS_APP = "HayseysAstrostacker"
_WIZARD_DONE_KEY = "wizard/completed"

# ── Bronze / dark palette ────────────────────────────────────────────────────
_STYLESHEET = """
QDialog {
    background-color: #0f0f19;
    color: #e5e5e5;
}
QWidget {
    background-color: transparent;
    color: #e5e5e5;
}
QLabel {
    background: transparent;
}
QRadioButton {
    color: #e5e5e5;
    spacing: 10px;
    font-size: 14px;
    padding: 2px 0;
}
QRadioButton::indicator {
    width: 18px;
    height: 18px;
}
QPushButton {
    background-color: rgba(255,255,255,0.06);
    color: #e5e5e5;
    border: 1px solid rgba(255,255,255,0.15);
    border-radius: 6px;
    padding: 8px 22px;
    font-size: 13px;
    font-weight: 600;
    min-width: 90px;
}
QPushButton:hover {
    background-color: rgba(255,149,0,0.12);
    border-color: rgba(255,149,0,0.5);
    color: #ffb340;
}
QPushButton#primaryBtn {
    background-color: #cc6600;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 8px 28px;
}
QPushButton#primaryBtn:hover {
    background-color: #e87a00;
}
QPushButton#primaryBtn:pressed {
    background-color: #a85500;
}
QPushButton#skipBtn {
    background-color: transparent;
    color: rgba(255,255,255,0.35);
    border: none;
    padding: 8px 12px;
    font-size: 12px;
}
QPushButton#skipBtn:hover {
    color: rgba(255,255,255,0.6);
}
QLineEdit, QSpinBox, QDoubleSpinBox {
    background-color: rgba(255,255,255,0.08);
    color: #e5e5e5;
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: 8px;
    padding: 5px 10px;
    font-size: 13px;
    min-height: 28px;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #ff9500;
    background-color: rgba(255,149,0,0.06);
}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
    border: none;
    width: 16px;
}
QFormLayout QLabel {
    color: rgba(255,255,255,0.7);
    font-size: 13px;
}
"""


def should_show_wizard() -> bool:
    """Return True if the first-run wizard has not been completed."""
    s = QSettings(SETTINGS_ORG, SETTINGS_APP)
    return not s.value(_WIZARD_DONE_KEY, False, type=bool)


def mark_wizard_done() -> None:
    """Mark the wizard as complete so it won't appear again."""
    s = QSettings(SETTINGS_ORG, SETTINGS_APP)
    s.setValue(_WIZARD_DONE_KEY, True)


class SetupWizard(QDialog):
    """Four-page first-run setup wizard."""

    # Results read by MainWindow after exec()
    camera_type: str = "colour"     # "mono" | "colour"

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Welcome to {APP_NAME}")
        self.setMinimumSize(580, 520)
        self.setModal(True)
        self.setStyleSheet(_STYLESHEET)

        self._page_index = 0
        self._setup_ui()
        self._show_page(0)

    # ── UI construction ──────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header strip with title + step counter
        header = QWidget()
        header.setFixedHeight(78)
        header.setStyleSheet(
            "background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #1a1430,stop:1 #0f0f19);"
            "border-bottom: 1px solid rgba(232,160,68,0.35);"
        )
        hl = QHBoxLayout(header)
        hl.setContentsMargins(28, 0, 28, 0)

        self._title_lbl = QLabel()
        tf = QFont()
        tf.setFamilies(["SF Pro Display", "Helvetica Neue", "Segoe UI", "Arial"])
        tf.setPointSize(18)
        tf.setBold(True)
        self._title_lbl.setFont(tf)
        self._title_lbl.setStyleSheet("color: #E8A044;")
        hl.addWidget(self._title_lbl, stretch=1)

        self._step_lbl = QLabel()
        self._step_lbl.setStyleSheet("color: rgba(255,255,255,0.30); font-size: 12px;")
        self._step_lbl.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        hl.addWidget(self._step_lbl)

        root.addWidget(header)

        # Page container
        self._page_area = QWidget()
        self._page_area.setStyleSheet("background: transparent;")
        self._page_layout = QVBoxLayout(self._page_area)
        self._page_layout.setContentsMargins(32, 24, 32, 20)

        self._pages = [
            self._build_welcome(),
            self._build_camera(),
            self._build_platesolve(),
            self._build_done(),
        ]
        for pg in self._pages:
            self._page_layout.addWidget(pg)
            pg.hide()

        root.addWidget(self._page_area, stretch=1)

        # Navigation bar
        nav = QWidget()
        nav.setFixedHeight(62)
        nav.setStyleSheet(
            "background: rgba(0,0,0,0.25);"
            "border-top: 1px solid rgba(255,255,255,0.07);"
        )
        nl = QHBoxLayout(nav)
        nl.setContentsMargins(24, 0, 24, 0)

        self._back_btn = QPushButton("← Back")
        self._back_btn.clicked.connect(self._on_back)
        nl.addWidget(self._back_btn)

        nl.addStretch()

        self._skip_btn = QPushButton("Skip plate solving →")
        self._skip_btn.setObjectName("skipBtn")
        self._skip_btn.clicked.connect(self._on_skip)
        nl.addWidget(self._skip_btn)

        self._next_btn = QPushButton("Next →")
        self._next_btn.setObjectName("primaryBtn")
        self._next_btn.clicked.connect(self._on_next)
        nl.addWidget(self._next_btn)

        root.addWidget(nav)

    # ── Pages ────────────────────────────────────────────────────────────────

    def _build_welcome(self) -> QWidget:
        pg = QWidget()
        ly = QVBoxLayout(pg)
        ly.setSpacing(14)
        ly.setContentsMargins(0, 0, 0, 0)

        intro = QLabel(
            "This app combines many individual exposures into one clean, "
            "detailed image — a process called <b>image stacking</b>. "
            "The more frames you stack, the less noise, the more detail."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("font-size: 14px; color: rgba(255,255,255,0.85); line-height: 1.5;")
        ly.addWidget(intro)

        ly.addSpacing(4)

        guide_lbl = QLabel("This wizard covers three quick things:")
        guide_lbl.setStyleSheet("font-size: 13px; color: rgba(255,255,255,0.50);")
        ly.addWidget(guide_lbl)

        for icon, text in [
            ("📷", "Your camera type (colour or monochrome)"),
            ("🔭", "Your telescope details — optional, speeds up plate solving"),
            ("✅", "How to load images and run your first stack"),
        ]:
            row = QLabel(f"    {icon}   {text}")
            row.setStyleSheet("font-size: 14px; padding: 5px 0; color: #e5e5e5;")
            ly.addWidget(row)

        ly.addStretch()

        note = QLabel(
            "Everything you enter here is saved automatically. "
            "You can change any setting in the app later."
        )
        note.setWordWrap(True)
        note.setStyleSheet(
            "font-size: 12px; color: rgba(255,255,255,0.35); font-style: italic;"
        )
        ly.addWidget(note)
        return pg

    def _build_camera(self) -> QWidget:
        pg = QWidget()
        ly = QVBoxLayout(pg)
        ly.setSpacing(10)
        ly.setContentsMargins(0, 0, 0, 0)

        desc = QLabel(
            "The app needs to know your camera type so it can process your images correctly."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("font-size: 14px; color: rgba(255,255,255,0.75);")
        ly.addWidget(desc)
        ly.addSpacing(6)

        self._colour_radio = QRadioButton("Colour camera")
        self._colour_radio.setChecked(True)
        colour_note = QLabel(
            "        Canon, Nikon, Sony DSLR or mirrorless  —  or any ZWO, Altair, Player One\n"
            "        'one-shot colour' astronomy camera. Most beginners use one of these."
        )
        colour_note.setStyleSheet("color: rgba(255,255,255,0.40); font-size: 12px;")

        self._mono_radio = QRadioButton("Monochrome camera")
        mono_note = QLabel(
            "        A dedicated black-and-white astronomy camera, typically used\n"
            "        with separate LRGB or narrowband filters."
        )
        mono_note.setStyleSheet("color: rgba(255,255,255,0.40); font-size: 12px;")

        grp = QButtonGroup(self)
        grp.addButton(self._colour_radio)
        grp.addButton(self._mono_radio)

        ly.addWidget(self._colour_radio)
        ly.addWidget(colour_note)
        ly.addSpacing(8)
        ly.addWidget(self._mono_radio)
        ly.addWidget(mono_note)
        ly.addStretch()

        tip = QLabel(
            "💡  Not sure?  If your images come out in colour straight from the camera, "
            "choose Colour. You can change this at any time in the Settings panel."
        )
        tip.setWordWrap(True)
        tip.setStyleSheet(
            "font-size: 12px; color: rgba(255,255,255,0.45);"
            "background: rgba(255,149,0,0.07); border-radius: 8px; padding: 12px;"
        )
        ly.addWidget(tip)
        return pg

    def _build_platesolve(self) -> QWidget:
        pg = QWidget()
        ly = QVBoxLayout(pg)
        ly.setSpacing(10)
        ly.setContentsMargins(0, 0, 0, 0)

        desc = QLabel(
            "Plate solving identifies exactly where your image points in the sky "
            "and labels the objects in it. It uses the free Astrometry.net service. "
            "This is <i>optional</i> — you can skip it now and set it up later in the "
            "Plate Solve tab."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("font-size: 13px; color: rgba(255,255,255,0.75);")
        ly.addWidget(desc)

        form = QFormLayout()
        form.setSpacing(10)
        form.setContentsMargins(0, 8, 0, 0)

        self._api_input = QLineEdit()
        self._api_input.setPlaceholderText(
            "Paste your free API key here  (nova.astrometry.net)"
        )
        self._api_input.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("API Key", self._api_input)

        self._focal_input = QLineEdit()
        self._focal_input.setPlaceholderText("e.g. 335")
        self._focal_input.setValidator(QIntValidator(1, 20000, self))
        self._focal_input.setToolTip(
            "Your telescope focal length in millimetres.\n"
            "Printed on the tube or in the manual (e.g. f=335mm → enter 335)."
        )
        form.addRow("Focal length (mm)", self._focal_input)

        self._pixel_input = QLineEdit()
        self._pixel_input.setPlaceholderText("e.g. 4.63")
        validator = QDoubleValidator(0.01, 50.0, 2, self)
        validator.setNotation(QDoubleValidator.Notation.StandardNotation)
        self._pixel_input.setValidator(validator)
        self._pixel_input.setToolTip(
            "Your camera's pixel size in micrometres (µm).\n"
            "Find this in your camera's spec sheet or product page.\n"
            "Every camera model has a different value."
        )
        form.addRow("Pixel size (µm)", self._pixel_input)

        ly.addLayout(form)
        ly.addStretch()

        hint = QLabel(
            "📖  See the README or GETTING_STARTED.txt for a step-by-step guide "
            "on where to find your focal length and pixel size."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(
            "font-size: 12px; color: rgba(255,255,255,0.40);"
            "background: rgba(255,149,0,0.07); border-radius: 8px; padding: 12px;"
        )
        ly.addWidget(hint)
        return pg

    def _build_done(self) -> QWidget:
        pg = QWidget()
        ly = QVBoxLayout(pg)
        ly.setSpacing(12)
        ly.setContentsMargins(0, 0, 0, 0)

        ready_lbl = QLabel("Here's how to stack your first image:")
        rf = QFont()
        rf.setPointSize(14)
        rf.setBold(True)
        ready_lbl.setFont(rf)
        ready_lbl.setStyleSheet("color: #E8A044;")
        ly.addWidget(ready_lbl)

        steps = [
            ("1", "In the Stacking tab (left sidebar), click Add under Light Frames and select your images."),
            ("2", "Optionally add Dark Frames and Flat Frames for better results — but it's fine to skip these for your first attempt."),
            ("3", "Under Processing, the Median stacking method is already selected — it's the safe default for any number of frames."),
            ("4", "Click Start Processing and wait for the completion chime."),
            ("5", "Your stack appears in the Preview panel. Use File > Export as TIFF to save a shareable image."),
        ]

        for num, text in steps:
            row_w = QWidget()
            row_l = QHBoxLayout(row_w)
            row_l.setContentsMargins(0, 0, 0, 0)
            row_l.setSpacing(12)

            badge = QLabel(num)
            badge.setFixedSize(26, 26)
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setStyleSheet(
                "background: #cc6600; color: white; border-radius: 13px;"
                "font-weight: 700; font-size: 12px;"
            )
            row_l.addWidget(badge, alignment=Qt.AlignmentFlag.AlignTop)

            step_lbl = QLabel(text)
            step_lbl.setWordWrap(True)
            step_lbl.setStyleSheet("font-size: 13px; color: #e5e5e5;")
            row_l.addWidget(step_lbl, stretch=1)

            ly.addWidget(row_w)

        ly.addStretch()

        guide_tip = QLabel(
            "📄  GETTING_STARTED.txt (in the same folder as the app) has a full "
            "beginner walkthrough. The README covers all features in detail."
        )
        guide_tip.setWordWrap(True)
        guide_tip.setStyleSheet(
            "font-size: 12px; color: rgba(255,255,255,0.40);"
            "background: rgba(255,149,0,0.07); border-radius: 8px; padding: 12px;"
        )
        ly.addWidget(guide_tip)
        return pg

    # ── Navigation ───────────────────────────────────────────────────────────

    def _show_page(self, index: int) -> None:
        for i, pg in enumerate(self._pages):
            pg.setVisible(i == index)

        titles = [
            f"Welcome to {APP_NAME}!",
            "Your Camera",
            "Plate Solving  —  Optional",
            "You're Ready!",
        ]
        self._title_lbl.setText(titles[index])
        self._step_lbl.setText(f"Step {index + 1} of {len(self._pages)}")

        is_last = index == len(self._pages) - 1
        is_first = index == 0

        self._back_btn.setVisible(not is_first)
        self._skip_btn.setVisible(index == 2)
        self._next_btn.setText("Let's go!  ✓" if is_last else "Next  →")

        self._page_index = index

    def _on_next(self) -> None:
        if self._page_index == len(self._pages) - 1:
            self._finish()
        else:
            self._show_page(self._page_index + 1)

    def _on_back(self) -> None:
        if self._page_index > 0:
            self._show_page(self._page_index - 1)

    def _on_skip(self) -> None:
        """Skip the plate-solving page and go straight to the done page."""
        self._show_page(3)

    # ── Save & close ─────────────────────────────────────────────────────────

    def _finish(self) -> None:
        """Persist wizard results to QSettings and close."""
        self.camera_type = "colour" if self._colour_radio.isChecked() else "mono"

        s = QSettings(SETTINGS_ORG, SETTINGS_APP)

        api_key = self._api_input.text().strip()
        if api_key:
            s.setValue("astrometry/api_key", api_key)

        try:
            focal = int(self._focal_input.text())
            if focal > 0:
                s.setValue("astrometry/focal_length", focal)
        except (ValueError, AttributeError):
            pass

        try:
            pixel = float(self._pixel_input.text())
            if pixel > 0:
                s.setValue("astrometry/pixel_size", pixel)
        except (ValueError, AttributeError):
            pass

        mark_wizard_done()
        self.accept()
