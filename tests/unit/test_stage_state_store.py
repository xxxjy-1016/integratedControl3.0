import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from integrated_control.infrastructure.persistence import StageStateStore


class StageStateStoreTests(unittest.TestCase):
    """Group checks for stage state store tests."""
    def test_missing_file_is_not_treated_as_known_origin(self) -> None:
        """Check missing file is not treated as known origin."""
        with TemporaryDirectory() as directory:
            store = StageStateStore(
                Path(directory) / "stage.json",
                default_offset_x=1.25,
                default_offset_y=-2.5,
            )

            state = store.load()

            self.assertFalse(state.stage_at_origin)
            self.assertEqual(1.25, state.offset_x)
            self.assertEqual(-2.5, state.offset_y)

    def test_origin_and_offsets_survive_reload(self) -> None:
        """Check origin and offsets survive reload."""
        with TemporaryDirectory() as directory:
            path = Path(directory) / "stage.json"
            store = StageStateStore(path)

            store.save_offsets(3.0, 4.0)
            store.save_origin(True)
            state = StageStateStore(path).load()

            self.assertTrue(state.stage_at_origin)
            self.assertEqual(3.0, state.offset_x)
            self.assertEqual(4.0, state.offset_y)

    def test_non_boolean_origin_flag_falls_back_to_unsafe_default(self) -> None:
        """Check non boolean origin flag falls back to unsafe default."""
        with TemporaryDirectory() as directory:
            path = Path(directory) / "stage.json"
            path.write_text(
                json.dumps(
                    {"stage_at_origin": "false", "offset_x": 9, "offset_y": 8}
                ),
                encoding="utf-8",
            )

            state = StageStateStore(path, default_offset_x=1, default_offset_y=2).load()

            self.assertFalse(state.stage_at_origin)
            self.assertEqual(1.0, state.offset_x)
            self.assertEqual(2.0, state.offset_y)


if __name__ == "__main__":
    unittest.main()
