"""Tests for per-estante label configuration (pure functions + QR generation).

Covers the pure label helpers and ``generate_qr_valor``:
- Excel-style bijective base-26 alpha formatting.
- Axis direction mapping (bottom_up / right_left).
- Adaptive QR shapes with and without label config.
- Full-grid uniqueness of generated QR values.
"""

from app.repositories.ubicacion_repository import (
    _to_alpha,
    compute_labels,
    effective_label_index,
    format_axis_label,
    generate_qr_valor,
)


class TestToAlpha:
    def test_single_letters(self):
        assert _to_alpha(1) == "A"
        assert _to_alpha(26) == "Z"

    def test_double_letters(self):
        assert _to_alpha(27) == "AA"
        assert _to_alpha(28) == "AB"
        assert _to_alpha(52) == "AZ"
        assert _to_alpha(53) == "BA"
        assert _to_alpha(702) == "ZZ"


class TestFormatAxisLabel:
    def test_numeric(self):
        assert format_axis_label(3, "numeric") == "3"

    def test_alpha(self):
        assert format_axis_label(3, "alpha") == "C"
        assert format_axis_label(27, "alpha") == "AA"

    def test_unknown_format_falls_back_to_numeric(self):
        assert format_axis_label(5, "anything") == "5"


class TestEffectiveLabelIndex:
    def test_top_down_is_identity(self):
        assert effective_label_index(2, 4, "top_down") == 2

    def test_left_right_is_identity(self):
        assert effective_label_index(2, 5, "left_right") == 2

    def test_bottom_up_reverses(self):
        # 4-row shelf: stored bottom row (4) labels as 1, stored top row (1) as 4.
        assert effective_label_index(4, 4, "bottom_up") == 1
        assert effective_label_index(1, 4, "bottom_up") == 4

    def test_right_left_reverses(self):
        # 5-column shelf: stored leftmost column (1) labels as 5.
        assert effective_label_index(1, 5, "right_left") == 5
        assert effective_label_index(5, 5, "right_left") == 1


class TestGenerateQrValorDefaults:
    def test_2d_grid_default_matches_legacy(self):
        assert generate_qr_valor("A", 1, 2, 4, 3) == "A-F1-C2"

    def test_1x1_is_just_the_name(self):
        assert generate_qr_valor("Suelto", 1, 1, 1, 1) == "Suelto"

    def test_single_row_uses_only_column(self):
        assert generate_qr_valor("A", 1, 5, 1, 5) == "A-C5"

    def test_single_column_uses_only_row(self):
        assert generate_qr_valor("A", 3, 1, 4, 1) == "A-F3"


class TestGenerateQrValorConfigured:
    def test_bottom_up_right_left_alpha_numeric(self):
        # Stored top-left cell (1,1) of a 4x3 shelf is physically bottom-right:
        # fila 4 -> D, columna 3 -> 3.
        assert (
            generate_qr_valor(
                "A", 1, 1, 4, 3,
                fila_order="bottom_up",
                columna_order="right_left",
                fila_format="alpha",
                columna_format="numeric",
            )
            == "A-FD-C3"
        )
        # Opposite corner: stored (4,3) -> fila 1 -> A, columna 1 -> 1.
        assert (
            generate_qr_valor(
                "A", 4, 3, 4, 3,
                fila_order="bottom_up",
                columna_order="right_left",
                fila_format="alpha",
                columna_format="numeric",
            )
            == "A-FA-C1"
        )

    def test_direction_only_keeps_numeric_format(self):
        assert (
            generate_qr_valor("A", 1, 1, 4, 3, fila_order="bottom_up", columna_order="right_left")
            == "A-F4-C3"
        )

    def test_format_only_keeps_direction(self):
        assert (
            generate_qr_valor("A", 1, 2, 4, 3, fila_format="alpha", columna_format="alpha")
            == "A-FA-CB"
        )

    def test_single_row_with_config_uses_only_column_label(self):
        # 1x5 shelf, right_left + alpha: stored col 1 -> label index 5 -> E.
        assert (
            generate_qr_valor("A", 1, 1, 1, 5, columna_order="right_left", columna_format="alpha")
            == "A-CE"
        )

    def test_single_column_with_config_uses_only_row_label(self):
        # 4x1 shelf, bottom_up + alpha: stored row 1 -> label index 4 -> D.
        assert (
            generate_qr_valor("A", 1, 1, 4, 1, fila_order="bottom_up", fila_format="alpha")
            == "A-FD"
        )

    def test_1x1_ignores_config(self):
        assert (
            generate_qr_valor(
                "Suelto", 1, 1, 1, 1,
                fila_order="bottom_up",
                columna_order="right_left",
                fila_format="alpha",
                columna_format="alpha",
            )
            == "Suelto"
        )


class TestComputeLabels:
    def test_defaults_are_identity_numeric(self):
        row = {"fila": 2, "columna": 3}
        assert compute_labels(row) == ("2", "3")

    def test_reversed_axis_uses_estante_dimensions(self):
        row = {
            "fila": 1,
            "columna": 1,
            "estante_filas": 4,
            "estante_columnas": 3,
            "fila_order": "bottom_up",
            "columna_order": "right_left",
            "fila_format": "alpha",
            "columna_format": "numeric",
        }
        assert compute_labels(row) == ("D", "3")


class TestFullGridUniqueness:
    CONFIGS = [
        {},
        {"fila_order": "bottom_up"},
        {"columna_order": "right_left"},
        {"fila_format": "alpha", "columna_format": "alpha"},
        {
            "fila_order": "bottom_up",
            "columna_order": "right_left",
            "fila_format": "alpha",
            "columna_format": "numeric",
        },
    ]

    def test_all_12_qr_valores_unique_for_any_config(self):
        for config in self.CONFIGS:
            valores = {
                generate_qr_valor("A", fila, columna, 4, 3, **config)
                for fila in range(1, 5)
                for columna in range(1, 4)
            }
            assert len(valores) == 12, f"collision with config {config}"
