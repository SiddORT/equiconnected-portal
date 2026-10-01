"""Settings-only checks; run with unittest, never the database pytest bootstrap.

    python -m unittest discover -s backend/isolated_tests -v

Only synthetic dotenv files in a temporary repository are read or written.
"""
import importlib.util
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

from pydantic import ValidationError


SOURCE = Path(__file__).resolve().parents[1] / "app/core/config.py"
ROOT = SOURCE.parents[3]


def load_settings(path):
    name = f"_isolated_settings_{uuid4().hex}"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    # Pydantic resolves forward references using the module registry.
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module.Settings


class SettingsEnvTests(unittest.TestCase):
    def tearDown(self):
        for name in list(sys.modules):
            if name.startswith("_isolated_settings_"):
                del sys.modules[name]

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "project"
        self.module = self.root / "backend/app/core/config.py"
        self.module.parent.mkdir(parents=True)
        shutil.copyfile(SOURCE, self.module)
        self.other = Path(self.temp.name) / "unrelated"
        self.other.mkdir()
        self.addCleanup(os.chdir, Path.cwd())
        self.env = patch.dict(os.environ, {}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.dotenv = self.root / ".env"
        self.dotenv.write_text(
            "DATABASE_URL=sqlite:///synthetic-only.db\n"
            "SECRET_KEY=synthetic-dotenv-key\n"
            "APP_NAME=Équi 馬\n"
            "DEBUG=true\n"
            "ALLOWED_ORIGINS=[\"https://example.test\"]\n"
            "PUBLIC_APP_URL=https://example.test\n"
            "IGNORED_SYNTHETIC_SETTING=yes\n",
            encoding="utf-8",
        )

    def directories(self):
        return self.root, self.root / "backend", self.other

    def test_real_module_path_is_absolute_and_cwd_independent(self):
        # Inspect configuration only: do not instantiate against the real .env.
        for cwd in (ROOT, ROOT / "backend", self.other):
            with self.subTest(cwd=cwd):
                os.chdir(cwd)
                settings_class = load_settings(SOURCE)
                path = settings_class.model_config["env_file"]
                self.assertTrue(path.is_absolute())
                self.assertEqual(path, ROOT / ".env")
                self.assertEqual(settings_class.model_config["env_file_encoding"], "utf-8")

    def test_root_dotenv_loads_from_each_working_directory(self):
        for cwd in self.directories():
            with self.subTest(cwd=cwd):
                os.chdir(cwd)
                settings = load_settings(self.module)()
                self.assertEqual(settings.DATABASE_URL, "sqlite:///synthetic-only.db")
                self.assertEqual(settings.SECRET_KEY, "synthetic-dotenv-key")
                self.assertEqual(settings.APP_NAME, "Équi 馬")
                self.assertTrue(settings.DEBUG)
                self.assertEqual(settings.ALLOWED_ORIGINS, ["https://example.test"])
                self.assertEqual(settings.public_link("/test"), "https://example.test/test")

    def test_environment_takes_precedence_over_dotenv(self):
        with patch.dict(os.environ, {
            "DATABASE_URL": "sqlite:///environment-only.db",
            "SECRET_KEY": "synthetic-environment-key",
            "app_name": "Environment name",
        }):
            for cwd in self.directories():
                with self.subTest(cwd=cwd):
                    os.chdir(cwd)
                    settings = load_settings(self.module)()
                    self.assertEqual(settings.DATABASE_URL, "sqlite:///environment-only.db")
                    self.assertEqual(settings.SECRET_KEY, "synthetic-environment-key")
                    self.assertEqual(settings.APP_NAME, "Environment name")

    def test_explicit_env_file_override_remains_relative_to_cwd(self):
        for cwd in self.directories():
            with self.subTest(cwd=cwd):
                os.chdir(cwd)
                override = cwd / "override.env"
                override.write_text(
                    "DATABASE_URL=sqlite:///override-only.db\n"
                    "SECRET_KEY=synthetic-override-key\n",
                    encoding="utf-8",
                )
                settings = load_settings(self.module)(_env_file="override.env")
                self.assertEqual(settings.DATABASE_URL, "sqlite:///override-only.db")
                self.assertEqual(settings.SECRET_KEY, "synthetic-override-key")
                self.assertEqual(settings.APP_NAME, "EquiConnected Portal")

    def test_absolute_override_and_environment_precedence(self):
        os.chdir(self.other)
        with patch.dict(os.environ, {"SECRET_KEY": "synthetic-environment-key"}):
            settings = load_settings(self.module)(_env_file=self.dotenv)
        self.assertEqual(settings.SECRET_KEY, "synthetic-environment-key")
        self.assertEqual(settings.APP_NAME, "Équi 馬")

    def test_env_file_can_be_disabled_without_relaxing_requirements(self):
        settings_class = load_settings(self.module)
        with self.assertRaises(ValidationError) as raised:
            settings_class(_env_file=None)
        self.assertEqual(
            {error["loc"] for error in raised.exception.errors()},
            {("DATABASE_URL",), ("SECRET_KEY",)},
        )
        settings = settings_class(
            _env_file=None,
            DATABASE_URL="sqlite:///arguments-only.db",
            SECRET_KEY="synthetic-argument-key",
        )
        self.assertEqual(settings.APP_NAME, "EquiConnected Portal")

    def test_existing_public_url_validator_is_retained(self):
        settings_class = load_settings(self.module)
        with self.assertRaises(ValidationError):
            settings_class(PUBLIC_APP_URL="https://example.test/not-an-origin")
        with self.assertRaises(ValidationError):
            settings_class(ENVIRONMENT="production", PUBLIC_APP_URL="http://localhost:5000")
        self.assertTrue(settings_class(ENVIRONMENT="production").is_production)


if __name__ == "__main__":
    unittest.main()