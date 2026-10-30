"""
Exercise real OpenSSL generation and failure-safe replacement.
"""

import os
from pathlib import Path
from subprocess import CalledProcessError, run
from tempfile import TemporaryDirectory
from typing import Dict, List
from unittest import TestCase, main
from unittest.mock import patch

from click.testing import CliRunner

import create_certificate
import create_certificate_authority
from output_transaction import output_transaction


class CertificateOutputsTest(TestCase):
    """
    Check successful generation and preservation after failed replacement.
    """

    def setUp(self) -> None:
        """
        Create an isolated working directory and an encrypted test CA.
        """
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        previous = Path.cwd()
        os.chdir(self.temporary.name)
        self.addCleanup(os.chdir, previous)
        self.runner = CliRunner()
        self.ca_args = ["test", "--subject", "/CN=Test CA"]
        self.leaf_args = ["test", "host.example", "--subject", "/CN=host.example"]
        with patch.object(create_certificate_authority, "run", self.openssl):
            result = self.runner.invoke(create_certificate_authority.main, self.ca_args)
        self.assertEqual(result.exit_code, 0, result.output)
        with patch.object(create_certificate, "run", self.openssl):
            result = self.runner.invoke(create_certificate.main, self.leaf_args)
        self.assertEqual(result.exit_code, 0, result.output)

    @staticmethod
    def openssl(*, args: List[str], check: bool) -> object:
        """
        Run OpenSSL with a test-only password instead of interactive prompts.

        Args:
            args: OpenSSL command and arguments.
            check: Whether command failure raises an exception.

        Returns:
            The completed subprocess result.
        """
        command = list(args)
        if command[1] == "genrsa" and "-des3" in command:
            command[2:2] = ["-passout", "pass:test-password"]
        elif command[1] == "req" and "-x509" in command:
            command += ["-passin", "pass:test-password"]
        elif command[1] == "x509" and "-req" in command:
            command += ["-passin", "pass:test-password"]
        return run(args=command, check=check, capture_output=True)

    @staticmethod
    def snapshot(*, directory: Path) -> Dict[str, bytes]:
        """
        Read the working files for comparison after a command.

        Args:
            directory: Directory to inspect recursively.

        Returns:
            File contents indexed by relative path.
        """
        return {
            str(path.relative_to(directory)): path.read_bytes()
            for path in directory.rglob("*")
            if path.is_file()
        }

    def test_generated_chain_passes_strict_validation(self) -> None:
        """
        Accept the generated chain under strict X.509 checks used by TLS clients.
        """
        run(
            args=[
                "openssl",
                "verify",
                "-x509_strict",
                "-CAfile",
                "out/test/root.pem",
                "out/test/host.example/certificate.crt",
            ],
            check=True,
            capture_output=True,
        )

    def test_generation_and_validation_failures_preserve_outputs(self) -> None:
        """
        Keep both old pairs intact after signing, validation, or cancellation fails.
        """
        for module, arguments in (
            (create_certificate_authority, self.ca_args),
            (create_certificate, self.leaf_args),
        ):
            for failure in ("sign", "verify", "cancel"):
                with self.subTest(script=module.__name__, failure=failure):
                    before = self.snapshot(directory=Path("out"))

                    def fail(*, args: List[str], check: bool) -> object:
                        """
                        Inject a failure after key generation.

                        Args:
                            args: OpenSSL command and arguments.
                            check: Whether to raise on command failure.

                        Returns:
                            The completed result for commands that do not fail.

                        Raises:
                            KeyboardInterrupt: Simulates cancellation during signing.
                            CalledProcessError: Simulates signing or validation failure.
                        """
                        signing = (
                            args[1] == "req"
                            if module is create_certificate_authority
                            else args[1] == "x509"
                        )
                        if failure == "verify" and args[1] == "verify":
                            raise CalledProcessError(1, args)
                        if signing and failure != "verify":
                            if failure == "cancel":
                                raise KeyboardInterrupt()
                            raise CalledProcessError(1, args)
                        return self.openssl(args=args, check=check)

                    with patch.object(module, "run", fail):
                        result = self.runner.invoke(
                            module.main, arguments + ["--existing", "replace"]
                        )
                    self.assertNotEqual(result.exit_code, 0)
                    self.assertEqual(before, self.snapshot(directory=Path("out")))
                    self.assertFalse(list(Path("out").rglob(".certificate-*")))

    def test_renew_reuses_keys_and_replace_changes_keys(self) -> None:
        """
        Preserve renew semantics and publish matching new replacement pairs.
        """
        for mode in ("renew", "replace"):
            for module, arguments, key in (
                (
                    create_certificate_authority,
                    self.ca_args,
                    Path("out/test/private.key"),
                ),
                (
                    create_certificate,
                    self.leaf_args,
                    Path("out/test/host.example/private.key"),
                ),
            ):
                with self.subTest(mode=mode, script=module.__name__):
                    old_key = key.read_bytes()
                    with patch.object(module, "run", self.openssl):
                        result = self.runner.invoke(
                            module.main, arguments + ["--existing", mode]
                        )
                    self.assertEqual(result.exit_code, 0, result.output)
                    self.assertEqual(old_key == key.read_bytes(), mode == "renew")
                    certificate = key.parent / (
                        "root.pem"
                        if module is create_certificate_authority
                        else "certificate.crt"
                    )
                    public_key = run(
                        args=[
                            "openssl",
                            "pkey",
                            "-in",
                            str(key),
                            "-passin",
                            "pass:test-password",
                            "-pubout",
                        ],
                        check=True,
                        capture_output=True,
                    ).stdout
                    certificate_key = run(
                        args=[
                            "openssl",
                            "x509",
                            "-in",
                            str(certificate),
                            "-pubkey",
                            "-noout",
                        ],
                        check=True,
                        capture_output=True,
                    ).stdout
                    self.assertEqual(public_key, certificate_key)

    def test_publish_failure_rolls_back(self) -> None:
        """
        Restore files already published when a later replacement fails.
        """
        for directory in (Path("out/test"), Path("out/new")):
            directory.mkdir(exist_ok=True)
            before = self.snapshot(directory=directory)
            replace = Path.replace
            failed = False

            def fail_once(source: Path, target: Path) -> Path:
                """
                Fail publication of the root certificate once, allowing rollback.

                Args:
                    source: File being moved.
                    target: Destination file.

                Returns:
                    The destination after successful replacement.

                Raises:
                    OSError: Simulates a failed filesystem operation.
                """
                nonlocal failed
                if (
                    source.name == "root.pem"
                    and source.parent.name.startswith(".certificate-")
                    and not failed
                ):
                    failed = True
                    raise OSError("simulated publication failure")
                return replace(source, target)

            with self.assertRaises(OSError), patch.object(Path, "replace", fail_once):
                with output_transaction(
                    out_dir=directory, filenames=("private.key", "root.pem")
                ) as staging:
                    (staging / "private.key").write_bytes(b"replacement key")
                    (staging / "root.pem").write_bytes(b"replacement certificate")
            self.assertEqual(before, self.snapshot(directory=directory))


if __name__ == "__main__":
    main()
