from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


IMAGE_EXTENSIONS = frozenset(
    {
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
        ".heic",
        ".heif",
        ".gif",
        ".bmp",
        ".tif",
        ".tiff",
        ".dng",
    }
)


class CollectionError(RuntimeError):
    """Raised when a device or collection operation cannot continue safely."""


@dataclass(frozen=True)
class Device:
    serial: str
    state: str
    description: str = ""


class MediaClient(Protocol):
    source_name: str

    def list_images(self, source_root: str) -> list[str]: ...

    def copy_file(self, source_path: str, destination: Path) -> None: ...

    def source_exists(self, source_path: str) -> bool: ...


def is_image_path(path: str) -> bool:
    return Path(path).suffix.lower() in IMAGE_EXTENSIONS


def parse_adb_devices(output: str) -> list[Device]:
    devices: list[Device] = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("List of devices attached"):
            continue
        parts = line.split(maxsplit=2)
        if len(parts) < 2:
            continue
        devices.append(
            Device(
                serial=parts[0],
                state=parts[1],
                description=parts[2] if len(parts) > 2 else "",
            )
        )
    return devices


class AdbClient:
    def __init__(self, adb_path: str | None = None, serial: str | None = None):
        configured_path = self._resolve_adb_path(adb_path)
        if not configured_path:
            raise CollectionError(
                "ADB was not found. Install Android Platform Tools or pass --adb-path."
            )
        self.adb_path = configured_path
        self.serial = serial
        self.source_name = "android"
        self.scan_warnings: list[str] = []

    @staticmethod
    def _resolve_adb_path(adb_path: str | None) -> str | None:
        direct = adb_path or os.environ.get("ADB_PATH") or shutil.which("adb")
        if direct:
            return direct
        if os.name != "nt":
            return None
        local_app_data = os.environ.get("LOCALAPPDATA")
        if not local_app_data:
            return None
        packages = Path(local_app_data) / "Microsoft" / "WinGet" / "Packages"
        if not packages.is_dir():
            return None
        for package in sorted(packages.glob("Google.PlatformTools_*"), reverse=True):
            candidate = package / "platform-tools" / "adb.exe"
            if candidate.is_file():
                return str(candidate)
        return None

    def _run(
        self,
        arguments: list[str],
        *,
        use_serial: bool = True,
        check: bool = True,
        timeout: int = 120,
    ) -> subprocess.CompletedProcess[str]:
        command = [self.adb_path]
        if use_serial and self.serial:
            command.extend(["-s", self.serial])
        command.extend(arguments)
        try:
            return subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=check,
                timeout=timeout,
            )
        except FileNotFoundError as exc:
            raise CollectionError(f"ADB executable not found: {self.adb_path}") from exc
        except subprocess.TimeoutExpired as exc:
            raise CollectionError(f"ADB command timed out: {' '.join(command)}") from exc
        except subprocess.CalledProcessError as exc:
            message = (exc.stderr or exc.stdout or "ADB command failed").strip()
            raise CollectionError(message) from exc

    def list_devices(self) -> list[Device]:
        result = self._run(["devices", "-l"], use_serial=False)
        return parse_adb_devices(result.stdout)

    def select_device(self) -> Device:
        devices = self.list_devices()
        if self.serial:
            selected = next((device for device in devices if device.serial == self.serial), None)
            if selected is None:
                raise CollectionError(f"Android device {self.serial!r} was not detected.")
            if selected.state != "device":
                raise CollectionError(
                    f"Android device {self.serial!r} is {selected.state}. "
                    "Unlock it and accept the USB debugging prompt."
                )
            return selected

        authorized = [device for device in devices if device.state == "device"]
        if len(authorized) == 1:
            self.serial = authorized[0].serial
            return authorized[0]
        if len(authorized) > 1:
            serials = ", ".join(device.serial for device in authorized)
            raise CollectionError(
                f"Multiple Android devices are connected ({serials}). Use --serial."
            )
        if any(device.state == "unauthorized" for device in devices):
            raise CollectionError(
                "The phone is connected but unauthorized. Unlock it and accept the "
                "USB debugging prompt."
            )
        raise CollectionError(
            "No authorized Android phone was detected. Check the cable and USB debugging."
        )

    def list_images(self, source_root: str = "/sdcard") -> list[str]:
        result = self._run(
            ["shell", "find", source_root, "-type", "f"],
            check=False,
            timeout=600,
        )
        self.scan_warnings = [
            line.strip()
            for line in result.stderr.splitlines()
            if line.strip()
        ]
        if result.returncode != 0 and not result.stdout.strip():
            message = "\n".join(self.scan_warnings) or "Android storage scan failed."
            raise CollectionError(message)
        paths = {
            line.strip().rstrip("\r")
            for line in result.stdout.splitlines()
            if line.strip() and is_image_path(line.strip())
        }
        return sorted(paths, key=str.casefold)

    def copy_file(self, source_path: str, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        self._run(["pull", "-a", source_path, str(destination)], timeout=1800)

    def source_exists(self, source_path: str) -> bool:
        result = self._run(
            ["shell", "test", "-f", source_path], check=False, timeout=30
        )
        return result.returncode == 0


class LocalFolderClient:
    """Local development substitute for Android storage."""

    def __init__(self, root: Path):
        self.root = root.resolve()
        if not self.root.is_dir():
            raise CollectionError(f"Local source folder does not exist: {self.root}")
        self.source_name = "local-demo"
        self.scan_warnings: list[str] = []

    def list_images(self, source_root: str = "") -> list[str]:
        del source_root
        return sorted(
            (str(path) for path in self.root.rglob("*") if path.is_file() and is_image_path(str(path))),
            key=str.casefold,
        )

    def copy_file(self, source_path: str, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination)

    def source_exists(self, source_path: str) -> bool:
        return Path(source_path).is_file()
