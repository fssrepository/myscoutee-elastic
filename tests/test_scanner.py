import tempfile
import unittest
from pathlib import Path

from app.scanner import analyze_file, module_for, scan


class ScannerTest(unittest.TestCase):
    def test_signals_and_stable_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "src" / "domain" / "events" / "Review.java"
            path.parent.mkdir(parents=True)
            path.write_text("// TODO: review\ntry { work(); } catch (Exception ex) {}\n" + "x" * 161 + "\n")
            first_file, first_findings = analyze_file(root, path, "sample")
            second_file, second_findings = analyze_file(root, path, "sample")
            self.assertEqual(first_file[0], second_file[0])
            self.assertEqual([item[0] for item in first_findings], [item[0] for item in second_findings])
            self.assertEqual({item[1]["rule"] for item in first_findings},
                             {"work_marker", "broad_catch", "long_line"})
            self.assertEqual(first_file[1]["module"], "events")

    def test_ignores_generated_directories(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "node_modules").mkdir()
            (root / "node_modules" / "ignored.ts").write_text("TODO")
            (root / "sample.ts").write_text("export const ok = true;\n")
            files, findings = scan(root, "sample")
            self.assertEqual(len(files), 1)
            self.assertEqual(findings, [])

    def test_root_level_app_file_has_module_name(self):
        self.assertEqual(module_for(Path("frontend/src/app/app.ts")), "app-root")


if __name__ == "__main__":
    unittest.main()
