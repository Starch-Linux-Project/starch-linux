import pathlib
import shutil
import subprocess
import tempfile
import unittest

SOURCE = pathlib.Path(__file__).resolve().parents[2]

class ScaffoldSafety(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name) / "checkout with spaces"
        (self.root / "scripts/build").mkdir(parents=True)
        for name in ("clean.sh", "build.sh", "scripts/build/paths.sh"):
            shutil.copy2(SOURCE / name, self.root / name)
        (self.root / "source.txt").write_text("preserve")

    def run_clean(self, *args):
        return subprocess.run([str(self.root / "clean.sh"), *args], cwd="/tmp", capture_output=True)

    def test_invalid_paths_rejected(self):
        for name in ("/", "..", "../source.txt", "", "build", str(self.root)):
            self.assertNotEqual(self.run_clean(name).returncode, 0)
        self.assertEqual((self.root / "source.txt").read_text(), "preserve")

    def test_symlink_roots_and_targets_rejected(self):
        outside = pathlib.Path(self.temp.name) / "outside"
        outside.mkdir()
        (outside / "keep").touch()
        (self.root / "build").symlink_to(outside, target_is_directory=True)
        self.assertNotEqual(self.run_clean("logs").returncode, 0)
        (self.root / "build").unlink()
        (self.root / "build").mkdir()
        (self.root / "build/logs").symlink_to(outside, target_is_directory=True)
        self.assertNotEqual(self.run_clean("logs").returncode, 0)
        self.assertTrue((outside / "keep").exists())

    def test_dry_run_and_complete_request_validation(self):
        logs = self.root / "build/logs"
        logs.mkdir(parents=True)
        (logs / "log").touch()
        self.assertEqual(self.run_clean("--dry-run", "logs").returncode, 0)
        self.assertTrue(logs.exists())
        self.assertNotEqual(self.run_clean("logs", "..").returncode, 0)
        self.assertTrue(logs.exists())
        self.assertEqual(self.run_clean("logs").returncode, 0)
        self.assertFalse(logs.exists())
        self.assertTrue((self.root / "source.txt").exists())

    def test_build_requires_explicit_action(self):
        result = subprocess.run([str(self.root / "build.sh")], capture_output=True)
        self.assertEqual(result.returncode, 2)

    def test_build_checks_generated_directory_before_installer_build(self):
        script = (SOURCE / "build.sh").read_text()
        writable_check = script.index("Generated directory is not writable")
        installer_build = script.index('scripts/build/calamares.sh\" --ensure')
        self.assertLess(writable_check, installer_build)

    def test_private_checkout_is_ignored_and_no_gitlinks_are_tracked(self):
        ignored = subprocess.run(
            ["git", "check-ignore", "-q", "dev-private-starch/"], cwd=SOURCE
        )
        self.assertEqual(ignored.returncode, 0)
        index = subprocess.check_output(
            ["git", "ls-files", "--stage"], cwd=SOURCE, text=True
        )
        gitlinks = [line for line in index.splitlines() if line.startswith("160000 ")]
        self.assertEqual(gitlinks, [], f"unexpected tracked gitlinks: {gitlinks}")

if __name__ == "__main__":
    unittest.main()
