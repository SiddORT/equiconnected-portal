"""Failure-injection checks for the real-browser layout gate (synthetic only)."""
import argparse
import asyncio
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "messages_check", Path(__file__).with_name("check-messages-theme-browser.py"))
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class FailureChecks(unittest.TestCase):
    def exercise(self, source, path, expected):
        async def injected(check, command, wait, click, evaluate, fixtures, origin, conversation_id):
            await command("Page.addScriptToEvaluateOnNewDocument", {"source": source})
            await check("member", 360, path)
            # The outer gate must also reject unknown intercepted requests.

        with tempfile.TemporaryDirectory(prefix="synthetic-gate-test-") as directory:
            args = argparse.Namespace(app_url=None, output_dir=Path(directory),
                                      chromium=gate.find_chromium())
            processes = []
            original = gate.subprocess.Popen

            def tracked(*args, **kwargs):
                process = original(*args, **kwargs)
                processes.append(process)
                return process

            with patch.object(gate, "run_checks", injected), patch.object(gate.subprocess, "Popen", tracked):
                with self.assertRaises(AssertionError):
                    asyncio.run(gate.run(args))
            report = json.loads((Path(directory) / "failure.json").read_text())
            self.assertIn("SYNTHETIC", report["provenance"])
            self.assertIn(expected, report["error"])
            self.assertTrue(list(Path(directory).glob("failure-*.png")))
            self.assertEqual(len(processes), 2)
            self.assertTrue(all(process.poll() is not None for process in processes))

    def test_overflow_fails_with_evidence_and_cleanup(self):
        self.exercise("""
          addEventListener('DOMContentLoaded', () => {
            const el=document.createElement('div');
            el.style.cssText='width:3000px;height:1px';
            document.body.append(el);
          });
        """, "/member/messages", "'overflow': True")

    def test_covered_composer_fails(self):
        self.exercise("""
          addEventListener('DOMContentLoaded', () => {
            new MutationObserver(() => {
              const reply=document.querySelector('#private-message-reply');
              if(reply && !document.getElementById('synthetic-test-cover')){
                reply.parentElement.style.position='relative';
                const cover=document.createElement('div');
                cover.id='synthetic-test-cover';
                cover.style.cssText='position:absolute;inset:0;z-index:500;background:red';
                reply.parentElement.append(cover);
              }
            }).observe(document.body,{subtree:true,childList:true});
          });
        """, "/member/messages/sample-private-conversation", "Obscured composer")

    def test_covered_navigation_fails(self):
        self.exercise("""
          addEventListener('DOMContentLoaded', () => {
            const cover=document.createElement('div');
            cover.style.cssText='position:fixed;top:0;left:0;width:100%;height:100px;z-index:9999;background:red';
            document.body.append(cover);
          });
        """, "/member/messages", "Obscured member menu toggle")

    def test_absolute_unknown_api_is_blocked(self):
        self.exercise("""
          addEventListener('DOMContentLoaded', () => {
            fetch('http://127.0.0.1:1/api/v1/synthetic-unmatched').catch(()=>{});
          });
        """, "/member/messages", "synthetic-unmatched")


if __name__ == "__main__":
    unittest.main()