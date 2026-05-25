from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .artiq_description import CARD_DEFINITIONS, validate_peripherals, write_artiq_description
from .build_gateware import dry_run_lines
from .config import ExperimentConfig, load_config
from .paths import DEFAULT_CONFIG, display_path


def launch_gui(config_path: str | Path = DEFAULT_CONFIG) -> None:
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import (
            QApplication,
            QComboBox,
            QFileDialog,
            QFormLayout,
            QHBoxLayout,
            QHeaderView,
            QLabel,
            QLineEdit,
            QMainWindow,
            QMessageBox,
            QPushButton,
            QPlainTextEdit,
            QSpinBox,
            QTableWidget,
            QTableWidgetItem,
            QVBoxLayout,
            QWidget,
        )
    except ImportError as exc:
        raise RuntimeError("Qt GUI support requires: uv sync --extra gui") from exc

    class MainWindow(QMainWindow):
        def __init__(self, cfg: ExperimentConfig):
            super().__init__()
            self.cfg = cfg
            self.setWindowTitle("MADMAX Kasli-SoC Gateware Builder")
            self.resize(1100, 720)

            central = QWidget()
            self.setCentralWidget(central)
            root = QVBoxLayout(central)

            form = QFormLayout()
            self.variant = QLineEdit(cfg.target.variant)
            self.hw_rev = QLineEdit(cfg.target.hw_rev)
            self.role = QComboBox()
            self.role.addItems(["standalone", "master", "satellite"])
            self.role.setCurrentText(cfg.target.drtio_role)
            self.rtio_frequency = QLineEdit(str(cfg.target.rtio_frequency))
            form.addRow("Variant", self.variant)
            form.addRow("Kasli-SoC hardware revision", self.hw_rev)
            form.addRow("DRTIO role", self.role)
            form.addRow("RTIO frequency", self.rtio_frequency)
            root.addLayout(form)

            root.addWidget(QLabel("ARTIQ cards / EEM connections"))
            self.table = QTableWidget(0, 4)
            self.table.setHorizontalHeaderLabels(["Card", "Start EEM", "Ports", "Options JSON"])
            self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
            self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
            root.addWidget(self.table)

            buttons = QHBoxLayout()
            for label, callback in [
                ("Add card", self.add_blank_row),
                ("Add 2in/2out Entangler", self.load_entangler_example),
                ("Remove selected", self.remove_selected),
                ("Generate JSON", self.generate_json),
                ("Show build commands", self.show_build_commands),
            ]:
                button = QPushButton(label)
                button.clicked.connect(callback)
                buttons.addWidget(button)
            root.addLayout(buttons)

            self.preview = QPlainTextEdit()
            self.preview.setReadOnly(True)
            root.addWidget(self.preview)

            self.load_entangler_example()

        def add_blank_row(self) -> None:
            self._add_row("dio", 0)

        def load_entangler_example(self) -> None:
            self.table.setRowCount(0)
            self._add_row("entangler", self.cfg.hardware.dio_eem)
            self.update_preview()

        def remove_selected(self) -> None:
            rows = sorted({idx.row() for idx in self.table.selectedIndexes()}, reverse=True)
            for row in rows:
                self.table.removeRow(row)
            self.update_preview()

        def _add_row(self, card_type: str, start_port: int) -> None:
            row = self.table.rowCount()
            self.table.insertRow(row)

            card = QComboBox()
            for definition in CARD_DEFINITIONS.values():
                card.addItem(definition.label, definition.type)
            card.setCurrentIndex(max(0, card.findData(card_type)))
            card.currentIndexChanged.connect(lambda _idx, current_row=row: self._card_changed(current_row))
            self.table.setCellWidget(row, 0, card)

            start = QSpinBox()
            start.setRange(0, 11)
            start.setValue(start_port)
            start.valueChanged.connect(lambda _value: self.update_preview())
            self.table.setCellWidget(row, 1, start)

            ports = QLineEdit()
            ports.textChanged.connect(lambda _value: self.update_preview())
            self.table.setCellWidget(row, 2, ports)

            options = QPlainTextEdit()
            options.setMaximumHeight(78)
            options.textChanged.connect(self.update_preview)
            self.table.setCellWidget(row, 3, options)
            self._card_changed(row)

        def _card_changed(self, row: int) -> None:
            card_type = self._row_card_type(row)
            definition = CARD_DEFINITIONS[card_type]
            start = self.table.cellWidget(row, 1).value()
            ports = [] if definition.port_count == 0 else list(range(start, start + definition.port_count))
            self.table.cellWidget(row, 2).setText(",".join(str(port) for port in ports))
            self.table.cellWidget(row, 3).setPlainText(json.dumps(definition.default_options, indent=2))
            self.update_preview()

        def _row_card_type(self, row: int) -> str:
            widget = self.table.cellWidget(row, 0)
            return widget.currentData()

        def _peripherals(self) -> list[dict[str, Any]]:
            peripherals = []
            for row in range(self.table.rowCount()):
                card_type = self._row_card_type(row)
                ports_text = self.table.cellWidget(row, 2).text().strip()
                ports = [] if not ports_text else [int(part.strip()) for part in ports_text.split(",") if part.strip()]
                options_text = self.table.cellWidget(row, 3).toPlainText().strip()
                options = json.loads(options_text) if options_text else {}
                peripheral = {"type": card_type, **options}
                if CARD_DEFINITIONS[card_type].port_count != 0:
                    peripheral["ports"] = ports
                peripherals.append(peripheral)
            return peripherals

        def _current_config(self) -> ExperimentConfig:
            data = self.cfg.model_dump(exclude={"source_path"})
            data["target"]["variant"] = self.variant.text().strip()
            data["target"]["hw_rev"] = self.hw_rev.text().strip()
            data["target"]["drtio_role"] = self.role.currentText()
            data["target"]["rtio_frequency"] = float(self.rtio_frequency.text())
            cfg = ExperimentConfig.model_validate(data)
            cfg.source_path = self.cfg.source_path
            return cfg

        def update_preview(self) -> None:
            try:
                cfg = self._current_config()
                peripherals = self._peripherals()
                errors = validate_peripherals(peripherals, drtio_role=cfg.target.drtio_role)
                description = {
                    "target": cfg.target.board,
                    "variant": cfg.target.variant,
                    "hw_rev": cfg.target.hw_rev,
                    "drtio_role": cfg.target.drtio_role,
                    "rtio_frequency": cfg.target.rtio_frequency,
                    "peripherals": peripherals,
                }
                text = json.dumps(description, indent=4)
                if errors:
                    text += "\n\nValidation issues:\n" + "\n".join(f"- {error}" for error in errors)
                self.preview.setPlainText(text)
            except Exception as exc:
                self.preview.setPlainText(f"Invalid GUI state: {exc}")

        def generate_json(self) -> None:
            try:
                cfg = self._current_config()
                peripherals = self._peripherals()
                errors = validate_peripherals(peripherals, drtio_role=cfg.target.drtio_role)
                if errors:
                    QMessageBox.warning(self, "Validation issues", "\n".join(errors))
                    return
                default_name = f"{cfg.target.variant}.json"
                path, _ = QFileDialog.getSaveFileName(self, "Write ARTIQ JSON", default_name, "JSON (*.json)")
                if not path:
                    return
                written = write_artiq_description(cfg, path, peripherals=peripherals)
                QMessageBox.information(self, "Generated", f"Wrote {display_path(written)}")
            except Exception as exc:
                QMessageBox.critical(self, "Generation failed", str(exc))

        def show_build_commands(self) -> None:
            try:
                cfg = self._current_config()
                self.preview.setPlainText("\n".join(dry_run_lines(cfg)))
            except Exception as exc:
                QMessageBox.critical(self, "Build plan failed", str(exc))

    app = QApplication.instance() or QApplication([])
    window = MainWindow(load_config(config_path))
    window.show()
    app.exec()

