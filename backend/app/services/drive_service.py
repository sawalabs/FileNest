import ctypes
import os
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Optional
from sqlalchemy.orm import Session

from backend.app.schemas.managed_folder import DriveInfo


DRIVE_TYPES = {
    0: "unknown",
    1: "no_root_dir",
    2: "removable",
    3: "fixed",
    4: "remote",
    5: "cdrom",
    6: "ramdisk",
}


def get_volume_identity(root_path: str) -> Dict[str, Optional[str]]:
    """Retrieves Windows volume label, filesystem name, and volume serial number.
    Returns normalized metadata dict.
    """
    clean_path = normalize_drive_root(root_path)
    volume_name = ""
    fs_name = ""
    serial_str: Optional[str] = None
    is_available = False

    if sys.platform == "win32":
        try:
            vol_buf = ctypes.create_unicode_buffer(1024)
            fs_buf = ctypes.create_unicode_buffer(1024)
            serial_num = ctypes.c_ulong(0)
            max_comp_len = ctypes.c_ulong(0)
            fs_flags = ctypes.c_ulong(0)

            ret = ctypes.windll.kernel32.GetVolumeInformationW(
                ctypes.c_wchar_p(clean_path),
                vol_buf,
                ctypes.sizeof(vol_buf),
                ctypes.byref(serial_num),
                ctypes.byref(max_comp_len),
                ctypes.byref(fs_flags),
                fs_buf,
                ctypes.sizeof(fs_buf),
            )
            if ret != 0:
                is_available = True
                volume_name = vol_buf.value
                fs_name = fs_buf.value
                # Format serial as XXXX-XXXX
                val = serial_num.value
                serial_str = f"{(val >> 16) & 0xFFFF:04X}-{val & 0xFFFF:04X}"
        except Exception:
            pass

    if not is_available:
        try:
            if os.path.exists(clean_path):
                is_available = True
        except Exception:
            pass

    return {
        "volume_label": volume_name,
        "filesystem": fs_name,
        "volume_serial": serial_str,
        "is_available": is_available,
    }


def is_drive_root_path(raw: str) -> bool:
    """Checks whether the given path represents an entire drive root (e.g. 'C:\\' or 'D:\\')."""
    if not raw or not isinstance(raw, str):
        return False
    s = raw.strip()
    if len(s) == 1 and s.isalpha():
        return True
    try:
        drive = Path(s).drive.upper()
        if drive and len(drive) == 2 and drive[1] == ":":
            stripped = s.replace("/", "\\").rstrip("\\").upper()
            return stripped == drive
    except Exception:
        pass
    return False


def normalize_drive_root(raw: str) -> str:
    """Normalizes a drive string (e.g., 'c', 'C:', 'C:\\', 'c:/') to 'C:\\'."""
    s = raw.strip()
    if not s:
        return s
    if len(s) == 1 and s.isalpha():
        return f"{s.upper()}:\\"
    try:
        drive = Path(s).drive.upper()
        if drive and len(drive) == 2 and drive[1] == ":":
            stripped = s.replace("/", "\\").rstrip("\\").upper()
            if stripped == drive:
                return f"{drive}\\"
    except Exception:
        pass
    return s.replace("/", "\\").rstrip("\\") + "\\"



def get_drive_type_name(root_path: str) -> str:
    if sys.platform == "win32":
        try:
            dt = ctypes.windll.kernel32.GetDriveTypeW(ctypes.c_wchar_p(normalize_drive_root(root_path)))
            return DRIVE_TYPES.get(dt, "unknown")
        except Exception:
            return "unknown"
    return "fixed"


def list_available_drives(db: Optional[Session] = None) -> List[DriveInfo]:
    """Discovers all available logical drives on the host Windows machine."""
    drives: List[DriveInfo] = []

    # Map registered folders if db session provided
    registered_map: Dict[str, str] = {}
    if db is not None:
        try:
            from backend.app.db.models.managed_folder import ManagedFolder
            existing = db.query(ManagedFolder).all()
            for f in existing:
                norm = normalize_drive_root(f.root_path).upper()
                registered_map[norm] = f.id
        except Exception:
            pass

    drive_roots: List[str] = []

    if sys.platform == "win32":
        try:
            bitmask = ctypes.windll.kernel32.GetLogicalDrives()
            for letter_idx in range(26):
                if bitmask & (1 << letter_idx):
                    letter = chr(ord('A') + letter_idx)
                    drive_roots.append(f"{letter}:\\")
        except Exception:
            pass

    if not drive_roots:
        # Fallback check common drives
        for letter in "CDEFGHIJKLMNOPQRSTUVWXYZ":
            root = f"{letter}:\\"
            try:
                if os.path.exists(root):
                    drive_roots.append(root)
            except Exception:
                pass

    for root in drive_roots:
        norm_root = normalize_drive_root(root)
        drive_letter = norm_root[:2].upper()
        dtype = get_drive_type_name(norm_root)

        # Skip CD-ROM or no root
        if dtype in ("cdrom", "no_root_dir"):
            continue

        ident = get_volume_identity(norm_root)
        total_b, free_b, used_b = 0, 0, 0
        if ident["is_available"]:
            try:
                usage = shutil.disk_usage(norm_root)
                total_b = usage.total
                free_b = usage.free
                used_b = usage.used
            except Exception:
                pass

        reg_id = registered_map.get(norm_root.upper())
        drives.append(
            DriveInfo(
                drive_letter=drive_letter,
                root_path=norm_root,
                volume_label=ident["volume_label"] or (f"Local Disk ({drive_letter})" if dtype == "fixed" else f"Drive ({drive_letter})"),
                volume_serial=ident["volume_serial"],
                filesystem=ident["filesystem"] or "Unknown",
                drive_type=dtype,
                total_bytes=total_b,
                free_bytes=free_b,
                used_bytes=used_b,
                is_available=bool(ident["is_available"]),
                is_registered=bool(reg_id),
                registered_folder_id=reg_id,
            )
        )

    return drives


class DriveService:
    list_available_drives = staticmethod(list_available_drives)
    get_volume_identity = staticmethod(get_volume_identity)
    normalize_drive_root = staticmethod(normalize_drive_root)
    is_drive_root_path = staticmethod(is_drive_root_path)
    get_drive_type_name = staticmethod(get_drive_type_name)

