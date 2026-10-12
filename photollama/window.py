from __future__ import annotations

import os

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QAction, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QStyle,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from . import exif, fileops, jpeg
from .canvas import Canvas
from .dialogs.crop_dialog import CropDialog
from .dialogs.levels_dialog import LevelsDialog
from .dialogs.properties import PropertiesDialog
from .dialogs.rotate_dialog import RotateDialog
from .formats import load_image, list_images
from .model import Document
from .ops import Crop, Flip, Rotate90, RotateAngle
from .theme import Theme

IMAGE_FILTER = (
    "Images (*.jpg *.jpeg *.png *.gif *.webp *.tif *.tiff *.bmp *.ico *.svg "
    "*.jp2 *.ppm *.pgm *.pbm *.xbm *.xpm);;All files (*)"
)


class MainWindow(QMainWindow):
    def __init__(self, theme: Theme, parent=None):
        super().__init__(parent)
        self.theme = theme
        self.setWindowTitle("Photollama")
        self.resize(1100, 760)
        self.setAcceptDrops(True)

        self._paths: list[str] = []
        self._index = -1
        self._folder: str | None = None
        self._docs: dict[str, Document] = {}
        self._doc: Document | None = None

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.top_bar = QLabel()
        self.top_bar.setObjectName("TopBar")
        self.top_bar.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.top_bar)
        self.canvas = Canvas(theme)
        layout.addWidget(self.canvas, 1)
        self.setCentralWidget(central)

        self.info_label = QLabel()
        self.zoom_label = QLabel()
        self.statusBar().addWidget(self.info_label)
        self.statusBar().addPermanentWidget(self.zoom_label)

        self._build_actions()
        self._build_toolbar()
        self.canvas.zoom_changed.connect(self._update_status)
        self.theme.changed.connect(self._apply_theme)
        self._update_top()
        self._update_status()

    def _build_actions(self) -> None:
        self.act_open = QAction("Open File…", self)
        self.act_open.setShortcut(QKeySequence.Open)
        self.act_open.triggered.connect(self.open_file_dialog)

        self.act_open_folder = QAction("Open Folder…", self)
        self.act_open_folder.setShortcut("Ctrl+Shift+O")
        self.act_open_folder.triggered.connect(self.open_folder_dialog)

        self.act_save = QAction("Save", self)
        self.act_save.setShortcut(QKeySequence.Save)
        self.act_save.triggered.connect(self.save)

        self.act_save_as = QAction("Save As…", self)
        self.act_save_as.setShortcut("Ctrl+Shift+S")
        self.act_save_as.triggered.connect(self.save_as)

        self.act_rename = QAction("Rename…", self)
        self.act_rename.setShortcut("F2")
        self.act_rename.triggered.connect(self.rename_current)

        self.act_delete = QAction("Delete", self)
        self.act_delete.setShortcut(QKeySequence.Delete)
        self.act_delete.triggered.connect(self.delete_current)

        self.act_properties = QAction("Properties", self)
        self.act_properties.setShortcut("Ctrl+I")
        self.act_properties.triggered.connect(self.show_properties)

        self.act_undo = QAction("Undo", self)
        self.act_undo.setShortcut(QKeySequence.Undo)
        self.act_undo.triggered.connect(self.undo)

        self.act_redo = QAction("Redo", self)
        self.act_redo.setShortcut(QKeySequence.Redo)
        self.act_redo.triggered.connect(self.redo)

        self.act_rotate_left = QAction("Rotate Left", self)
        self.act_rotate_left.setShortcut("Ctrl+L")
        self.act_rotate_left.triggered.connect(lambda: self.rotate(clockwise=False))

        self.act_rotate_right = QAction("Rotate Right", self)
        self.act_rotate_right.setShortcut("Ctrl+R")
        self.act_rotate_right.triggered.connect(lambda: self.rotate(clockwise=True))

        self.act_rotate_angle = QAction("Rotate Angle…", self)
        self.act_rotate_angle.setShortcut("Ctrl+Shift+R")
        self.act_rotate_angle.triggered.connect(self.rotate_angle_dialog)

        self.act_flip_h = QAction("Flip Horizontal", self)
        self.act_flip_h.setShortcut("Ctrl+Shift+H")
        self.act_flip_h.triggered.connect(lambda: self.flip(horizontal=True))

        self.act_flip_v = QAction("Flip Vertical", self)
        self.act_flip_v.setShortcut("Ctrl+Shift+V")
        self.act_flip_v.triggered.connect(lambda: self.flip(horizontal=False))

        self.act_crop = QAction("Crop…", self)
        self.act_crop.setShortcut("Ctrl+Shift+C")
        self.act_crop.triggered.connect(self.crop_dialog)

        self.act_levels = QAction("Levels…", self)
        self.act_levels.setShortcut("Ctrl+Shift+L")
        self.act_levels.triggered.connect(self.levels_dialog)

        self.act_next = QAction("Next Image", self)
        self.act_next.setShortcuts([QKeySequence("Right"), QKeySequence("Space")])
        self.act_next.triggered.connect(self.next_image)

        self.act_prev = QAction("Previous Image", self)
        self.act_prev.setShortcuts([QKeySequence("Left"), QKeySequence("Backspace")])
        self.act_prev.triggered.connect(self.prev_image)

        self.act_zoom_in = QAction("Zoom In", self)
        self.act_zoom_in.setShortcuts([QKeySequence("Ctrl+="), QKeySequence("Ctrl++")])
        self.act_zoom_in.triggered.connect(self.canvas.zoom_in)

        self.act_zoom_out = QAction("Zoom Out", self)
        self.act_zoom_out.setShortcut(QKeySequence("Ctrl+-"))
        self.act_zoom_out.triggered.connect(self.canvas.zoom_out)

        self.act_fit = QAction("Fit to Window", self)
        self.act_fit.setShortcut("Ctrl+0")
        self.act_fit.triggered.connect(self.canvas.fit_to_window)

        self.act_actual = QAction("Actual Size", self)
        self.act_actual.setShortcut("Ctrl+1")
        self.act_actual.triggered.connect(self.canvas.zoom_actual)

        self.act_thirds = QAction("Grid of Thirds", self)
        self.act_thirds.setCheckable(True)
        self.act_thirds.setShortcut("G")
        self.act_thirds.toggled.connect(self._toggle_thirds)

        self.act_hist = QAction("Histogram", self)
        self.act_hist.setCheckable(True)
        self.act_hist.setShortcut("H")
        self.act_hist.toggled.connect(self._toggle_histogram)

        self.act_quit = QAction("Quit", self)
        self.act_quit.setShortcut(QKeySequence.Quit)
        self.act_quit.triggered.connect(self.close)

        for action in (
            self.act_open, self.act_open_folder, self.act_save, self.act_save_as,
            self.act_rename, self.act_delete, self.act_properties, self.act_undo,
            self.act_redo, self.act_rotate_left, self.act_rotate_right,
            self.act_rotate_angle, self.act_flip_h, self.act_flip_v, self.act_crop,
            self.act_levels, self.act_next, self.act_prev, self.act_zoom_in,
            self.act_zoom_out, self.act_fit, self.act_actual, self.act_thirds,
            self.act_hist, self.act_quit,
        ):
            self.addAction(action)

        file_menu = self.menuBar().addMenu("&File")
        file_menu.addAction(self.act_open)
        file_menu.addAction(self.act_open_folder)
        file_menu.addSeparator()
        file_menu.addAction(self.act_save)
        file_menu.addAction(self.act_save_as)
        self.open_with_menu = QMenu("Open With", self)
        self.open_with_menu.aboutToShow.connect(self._populate_open_with)
        file_menu.addMenu(self.open_with_menu)
        file_menu.addSeparator()
        file_menu.addAction(self.act_rename)
        file_menu.addAction(self.act_delete)
        file_menu.addAction(self.act_properties)
        file_menu.addSeparator()
        file_menu.addAction(self.act_quit)

        edit_menu = self.menuBar().addMenu("&Edit")
        edit_menu.addAction(self.act_undo)
        edit_menu.addAction(self.act_redo)
        edit_menu.addSeparator()
        edit_menu.addAction(self.act_rotate_left)
        edit_menu.addAction(self.act_rotate_right)
        edit_menu.addAction(self.act_rotate_angle)
        edit_menu.addSeparator()
        edit_menu.addAction(self.act_flip_h)
        edit_menu.addAction(self.act_flip_v)
        edit_menu.addSeparator()
        edit_menu.addAction(self.act_crop)
        edit_menu.addAction(self.act_levels)

        view_menu = self.menuBar().addMenu("&View")
        view_menu.addAction(self.act_next)
        view_menu.addAction(self.act_prev)
        view_menu.addSeparator()
        view_menu.addAction(self.act_zoom_in)
        view_menu.addAction(self.act_zoom_out)
        view_menu.addAction(self.act_fit)
        view_menu.addAction(self.act_actual)
        view_menu.addSeparator()
        view_menu.addAction(self.act_thirds)
        view_menu.addAction(self.act_hist)

        self._update_actions()

    def _build_toolbar(self) -> None:
        self.toolbar = QToolBar("Edit & View", self)
        self.toolbar.setObjectName("MainToolBar")
        self.toolbar.setOrientation(Qt.Vertical)
        self.toolbar.setMovable(False)
        self.toolbar.setFloatable(False)
        self.toolbar.setIconSize(QSize(20, 20))
        self.toolbar.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self.addToolBar(Qt.LeftToolBarArea, self.toolbar)

        edit_group = (
            (self.act_undo, ("edit-undo",), QStyle.SP_ArrowBack),
            (self.act_redo, ("edit-redo",), QStyle.SP_ArrowForward),
            None,
            (self.act_rotate_left, ("object-rotate-left",), QStyle.SP_ArrowLeft),
            (self.act_rotate_right, ("object-rotate-right",), QStyle.SP_ArrowRight),
            (self.act_rotate_angle, ("object-rotate-right", "view-refresh"), None),
            None,
            (self.act_flip_h, ("object-flip-horizontal",), None),
            (self.act_flip_v, ("object-flip-vertical",), None),
            None,
            (self.act_crop, ("crop-symbolic", "crop", "object-crop"), None),
            (self.act_levels, ("preferences-color-symbolic", "color-select-symbolic",
                               "preferences-color"), None),
        )
        view_group = (
            (self.act_next, ("go-next-symbolic", "go-next", "pan-end-symbolic"),
             QStyle.SP_ArrowRight),
            (self.act_prev, ("go-previous-symbolic", "go-previous", "pan-start-symbolic"),
             QStyle.SP_ArrowLeft),
            None,
            (self.act_zoom_in, ("zoom-in",), None),
            (self.act_zoom_out, ("zoom-out",), None),
            (self.act_fit, ("zoom-fit-best",), QStyle.SP_TitleBarNormalButton),
            (self.act_actual, ("zoom-original", "zoom-100"), None),
            None,
            (self.act_thirds, ("view-grid-symbolic", "view-app-grid-symbolic", "view-grid"),
             None),
            (self.act_hist, ("view-statistics-symbolic", "utilities-system-monitor-symbolic",
                             "view-statistics"), None),
        )

        for entry in edit_group:
            self._add_toolbar_entry(entry)
        self.toolbar.addSeparator()
        for entry in view_group:
            self._add_toolbar_entry(entry)

    def _add_toolbar_entry(self, entry) -> None:
        if entry is None:
            self.toolbar.addSeparator()
            return
        action, names, standard = entry
        self._assign_icon(action, names, standard)
        if not action.toolTip():
            action.setToolTip(action.text())
        shortcut = action.shortcut().toString()
        if shortcut:
            action.setToolTip(f"{action.text()}  ({shortcut})")
        self.toolbar.addAction(action)

    def _assign_icon(self, action: QAction, names, standard) -> None:
        icon = QIcon()
        for name in names:
            candidate = QIcon.fromTheme(name)
            if not candidate.isNull():
                icon = candidate
                break
        if icon.isNull() and standard is not None:
            icon = self.style().standardIcon(standard)
        if not icon.isNull():
            action.setIcon(icon)

    def _apply_theme(self) -> None:
        self.setPalette(self.theme.qpalette())
        self.setStyleSheet(self.theme.stylesheet())
        self.canvas.apply_theme()

    def closeEvent(self, event):
        if self._confirm_unsaved():
            event.accept()
        else:
            event.ignore()

    def _confirm_unsaved(self) -> bool:
        modified = [doc for doc in self._docs.values() if doc.is_modified]
        if not modified:
            return True
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle("Unsaved changes")
        if len(modified) == 1:
            box.setText(
                f"Save changes to \u201c{os.path.basename(modified[0].path)}\u201d?"
            )
        else:
            box.setText(f"Save changes to {len(modified)} images?")
        box.setInformativeText("Your changes will be lost if you don't save them.")
        save_button = box.addButton(
            "Save All" if len(modified) > 1 else "Save", QMessageBox.AcceptRole
        )
        discard_button = box.addButton("Discard", QMessageBox.DestructiveRole)
        cancel_button = box.addButton("Cancel", QMessageBox.RejectRole)
        box.setDefaultButton(save_button)
        box.exec()
        clicked = box.clickedButton()
        if clicked is cancel_button:
            return False
        if clicked is discard_button:
            return True
        return self._save_all(modified)

    def _save_all(self, docs) -> bool:
        for doc in docs:
            lossless = jpeg.is_lossless_for(doc.path, doc.ops) and jpeg.lossless_transform(
                doc.path, doc.ops, doc.path
            )
            if not lossless and not fileops.save_image(doc.render(), doc.path):
                QMessageBox.warning(self, "Save failed", f"Could not save {doc.path}")
                return False
            doc.commit()
        self._refresh_current()
        self._update_top()
        self._update_status()
        return True

    def open_file_dialog(self) -> None:
        start = self._folder or os.path.expanduser("~")
        path, _ = QFileDialog.getOpenFileName(self, "Open Image", start, IMAGE_FILTER)
        if path:
            self.open_path(path)

    def open_folder_dialog(self) -> None:
        start = self._folder or os.path.expanduser("~")
        folder = QFileDialog.getExistingDirectory(self, "Open Folder", start)
        if folder:
            self.open_folder(folder)

    def open_path(self, path: str) -> None:
        path = os.path.abspath(path)
        if os.path.isdir(path):
            self.open_folder(path)
        elif os.path.isfile(path):
            self.open_folder(os.path.dirname(path), select=path)

    def open_folder(self, folder: str, select: str | None = None) -> None:
        if not self._confirm_unsaved():
            return
        self._folder = folder
        self._paths = list_images(folder)
        if not self._paths:
            self._index = -1
            self._doc = None
            self.canvas.set_image(None)
            self._update_top()
            self._update_status()
            return
        index = 0
        if select:
            selected = os.path.abspath(select)
            for i, candidate in enumerate(self._paths):
                if os.path.abspath(candidate) == selected:
                    index = i
                    break
        self._show_index(index)

    def _show_index(self, index: int) -> None:
        if not self._paths:
            return
        self._index = max(0, min(index, len(self._paths) - 1))
        path = self._paths[self._index]
        doc = self._docs.get(path)
        if doc is None:
            image = load_image(path)
            if image.isNull():
                self.info_label.setText(f"Could not load {os.path.basename(path)}")
                return
            doc = Document(path, image)
            self._docs[path] = doc
        self._doc = doc
        self.canvas.set_image(doc.render())
        self._update_top()
        self._update_status()

    def next_image(self) -> None:
        if self._paths and self._index < len(self._paths) - 1:
            self._show_index(self._index + 1)

    def prev_image(self) -> None:
        if self._paths and self._index > 0:
            self._show_index(self._index - 1)

    def save(self) -> None:
        if self._doc is None or not self._doc.is_modified:
            return
        doc = self._doc
        if jpeg.is_lossless_for(doc.path, doc.ops) and jpeg.lossless_transform(
            doc.path, doc.ops, doc.path
        ):
            self._reload_current()
            return
        if fileops.save_image(doc.render(), doc.path):
            doc.commit()
            self._update_top()
            self._update_status()
        else:
            QMessageBox.warning(self, "Save failed", f"Could not save {doc.path}")

    def save_as(self) -> None:
        if self._doc is None:
            return
        start = self._doc.path
        path, _ = QFileDialog.getSaveFileName(self, "Save As", start, IMAGE_FILTER)
        if not path:
            return
        doc = self._doc
        saved = False
        jpeg_target = os.path.splitext(path)[1].lower() in jpeg.JPEG_EXTS
        if jpeg_target and jpeg.is_lossless_for(doc.path, doc.ops):
            saved = jpeg.lossless_transform(doc.path, doc.ops, path)
        if not saved:
            saved = fileops.save_image(doc.render(), path)
        if saved:
            doc.commit()
            self._docs.pop(doc.path, None)
            self._docs.pop(path, None)
            self.open_path(path)
        else:
            QMessageBox.warning(self, "Save failed", f"Could not save {path}")

    def _reload_current(self) -> None:
        if self._doc is None:
            return
        path = self._doc.path
        image = load_image(path)
        if image.isNull():
            return
        self._docs[path] = Document(path, image)
        self._show_index(self._index)

    def rename_current(self) -> None:
        if self._doc is None or self._doc.is_modified:
            if self._doc is not None and self._doc.is_modified:
                QMessageBox.information(
                    self, "Rename", "Save your changes before renaming this image."
                )
            return
        old_path = self._doc.path
        current = os.path.basename(old_path)
        new_name, ok = QInputDialog.getText(self, "Rename", "New name:", text=current)
        if not ok or new_name.strip() == current:
            return
        new_path = fileops.rename(old_path, new_name)
        if not new_path:
            QMessageBox.warning(self, "Rename failed", "That name is invalid or already exists.")
            return
        self._docs.pop(old_path, None)
        if self._index >= 0:
            self._paths[self._index] = new_path
        self._show_index(self._index)

    def delete_current(self) -> None:
        if self._doc is None:
            return
        path = self._doc.path
        if not fileops.trash(path):
            QMessageBox.warning(self, "Delete failed", f"Could not move {path} to trash.")
            return
        self._docs.pop(path, None)
        if path in self._paths:
            self._paths.remove(path)
        if not self._paths:
            self._index = -1
            self._doc = None
            self.canvas.set_image(None)
            self._update_top()
            self._update_status()
            return
        self._show_index(min(self._index, len(self._paths) - 1))

    def show_properties(self) -> None:
        if self._doc is None:
            return
        details = list(exif.read_exif(self._doc.path).items())
        dialog = PropertiesDialog(self._doc.path, self._doc.render(), details, parent=self)
        dialog.exec()

    def undo(self) -> None:
        if self._doc is None:
            return
        self._doc.undo()
        self._refresh_current()

    def redo(self) -> None:
        if self._doc is None:
            return
        self._doc.redo()
        self._refresh_current()

    def rotate(self, clockwise: bool) -> None:
        self._apply_op(Rotate90(clockwise=clockwise))

    def flip(self, horizontal: bool) -> None:
        self._apply_op(Flip(horizontal=horizontal))

    def rotate_angle_dialog(self) -> None:
        if self._doc is None:
            return
        preview = self._preview_image(self._doc.render())
        dialog = RotateDialog(preview, self)
        if dialog.exec():
            self._apply_op(RotateAngle(dialog.spin.value(), dialog.autocrop.isChecked()))

    def crop_dialog(self) -> None:
        if self._doc is None:
            return
        rendered = self._doc.render()
        preview = self._preview_image(rendered, max_dim=1400)
        dialog = CropDialog(preview, self)
        if not dialog.exec():
            return
        rect = dialog.crop_rect()
        if preview.width() != rendered.width():
            scale = rendered.width() / preview.width()
            rect = QRect(
                round(rect.x() * scale), round(rect.y() * scale),
                round(rect.width() * scale), round(rect.height() * scale),
            )
        self._apply_op(Crop(rect))

    def levels_dialog(self) -> None:
        if self._doc is None:
            return
        preview = self._preview_image(self._doc.render())
        dialog = LevelsDialog(preview, self)
        if dialog.exec():
            self._apply_op(dialog.op())

    def _apply_op(self, op) -> None:
        if self._doc is None:
            return
        self._doc.apply(op)
        self._refresh_current()

    @staticmethod
    def _preview_image(image, max_dim: int = 1000):
        if max(image.width(), image.height()) <= max_dim:
            return image
        return image.scaled(max_dim, max_dim, Qt.KeepAspectRatio, Qt.SmoothTransformation)

    def _refresh_current(self) -> None:
        if self._doc is not None:
            self.canvas.set_image(self._doc.render(), reset_view=False)
        self._update_top()
        self._update_status()

    def _populate_open_with(self) -> None:
        self.open_with_menu.clear()
        if self._doc is None:
            self.open_with_menu.setEnabled(False)
            return
        path = self._doc.path
        default = QAction("Default Application", self)
        default.triggered.connect(lambda: fileops.open_default(path))
        self.open_with_menu.addAction(default)
        apps = fileops.applications_for(path)
        if apps:
            self.open_with_menu.addSeparator()
            for label, desktop_id in apps:
                action = QAction(label, self)
                action.triggered.connect(
                    lambda _=False, did=desktop_id: fileops.open_with(path, did)
                )
                self.open_with_menu.addAction(action)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            if url.isLocalFile():
                self.open_path(url.toLocalFile())
                event.acceptProposedAction()
                return

    def _update_top(self) -> None:
        if self._doc is not None:
            name = os.path.basename(self._doc.path)
            marker = " *" if self._doc.is_modified else ""
            self.top_bar.setText(f"{name}{marker}")
            self.setWindowTitle(f"{name}{marker} — Photollama")
        else:
            self.top_bar.setText("No image loaded")
            self.setWindowTitle("Photollama")

    def _update_status(self) -> None:
        if self._paths and self._index >= 0:
            self.info_label.setText(f"{self._index + 1} of {len(self._paths)}")
        else:
            self.info_label.setText("")
        self.zoom_label.setText(f"{self.canvas.zoom * 100:.0f}%")
        self._update_actions()

    def _update_actions(self) -> None:
        has_doc = self._doc is not None
        modified = has_doc and self._doc.is_modified
        self.act_save.setEnabled(modified)
        self.act_save_as.setEnabled(has_doc)
        self.act_rename.setEnabled(has_doc and not modified)
        self.act_delete.setEnabled(has_doc)
        self.act_properties.setEnabled(has_doc)
        self.act_undo.setEnabled(has_doc and self._doc.can_undo)
        self.act_redo.setEnabled(has_doc and self._doc.can_redo)
        for action in (
            self.act_rotate_left, self.act_rotate_right, self.act_rotate_angle,
            self.act_flip_h, self.act_flip_v, self.act_crop, self.act_levels,
        ):
            action.setEnabled(has_doc)
        self.act_next.setEnabled(self._index < len(self._paths) - 1)
        self.act_prev.setEnabled(self._index > 0)
        self.open_with_menu.setEnabled(has_doc)

    def _toggle_thirds(self, checked: bool) -> None:
        self.canvas.show_thirds = checked
        self.canvas.viewport().update()

    def _toggle_histogram(self, checked: bool) -> None:
        self.canvas.show_histogram = checked
        self.canvas.viewport().update()
