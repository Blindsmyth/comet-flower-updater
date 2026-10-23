"""Configuration profiles management for Comet Flower Installer."""

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from typing import Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_PROFILES_PATH = REPO_ROOT / "build" / "loader" / "profiles.json"


@dataclass
class Profile:
    name: str
    is_default: bool = False
    checked_effects: List[str] = field(default_factory=list)
    default_patch_names: Dict[str, str] = field(default_factory=dict)
    firmware_path: str = ""
    version: str = ""
    backup_before_build: bool = True

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Profile":
        return cls(
            name=data.get("name", "Default"),
            is_default=bool(data.get("is_default", False)),
            checked_effects=list(data.get("checked_effects", [])),
            default_patch_names=dict(data.get("default_patch_names", {})),
            firmware_path=str(data.get("firmware_path", "")),
            version=str(data.get("version", "")),
            backup_before_build=bool(data.get("backup_before_build", True)),
        )


def get_default_fallback_profile() -> Profile:
    """Return factory default initial profile."""
    return Profile(
        name="Comet Flower Default",
        is_default=True,
        checked_effects=[],
        default_patch_names={},
        firmware_path="",
        version="",
        backup_before_build=True,
    )


def load_profiles(profiles_file: Optional[Path] = None) -> Dict[str, Profile]:
    """Load profiles from JSON file."""
    p_path = profiles_file or DEFAULT_PROFILES_PATH
    if not p_path.exists():
        default_prof = get_default_fallback_profile()
        return {default_prof.name: default_prof}

    try:
        data = json.loads(p_path.read_text(encoding="utf-8"))
        profiles: Dict[str, Profile] = {}
        has_default = False
        for k, v in data.items():
            prof = Profile.from_dict(v)
            profiles[prof.name] = prof
            if prof.is_default:
                has_default = True

        if not profiles:
            default_prof = get_default_fallback_profile()
            return {default_prof.name: default_prof}

        if not has_default and profiles:
            first_name = next(iter(profiles))
            profiles[first_name].is_default = True

        return profiles
    except Exception:
        default_prof = get_default_fallback_profile()
        return {default_prof.name: default_prof}


def save_profiles(profiles: Dict[str, Profile], profiles_file: Optional[Path] = None) -> None:
    """Save all profiles to JSON file."""
    p_path = profiles_file or DEFAULT_PROFILES_PATH
    p_path.parent.mkdir(parents=True, exist_ok=True)
    out_dict = {name: p.to_dict() for name, p in profiles.items()}
    p_path.write_text(json.dumps(out_dict, indent=2), encoding="utf-8")


def save_profile(profile: Profile, profiles_file: Optional[Path] = None) -> None:
    """Save or update a single profile."""
    p_path = profiles_file or DEFAULT_PROFILES_PATH
    profiles = load_profiles(p_path)
    if not p_path.exists() and len(profiles) == 1 and "Comet Flower Default" in profiles and profile.name != "Comet Flower Default":
        profiles = {}
    if profile.is_default:
        for p in profiles.values():
            p.is_default = False
    profiles[profile.name] = profile
    save_profiles(profiles, p_path)


def delete_profile(name: str, profiles_file: Optional[Path] = None) -> bool:
    """Delete a profile by name. Refuses if only one profile left."""
    profiles = load_profiles(profiles_file)
    if name not in profiles:
        return False
    if len(profiles) <= 1:
        return False

    was_default = profiles[name].is_default
    del profiles[name]
    if was_default and profiles:
        next(iter(profiles.values())).is_default = True

    save_profiles(profiles, profiles_file)
    return True


def rename_profile(old_name: str, new_name: str, profiles_file: Optional[Path] = None) -> bool:
    """Rename an existing profile."""
    profiles = load_profiles(profiles_file)
    if old_name not in profiles or not new_name.strip():
        return False
    if new_name in profiles and new_name != old_name:
        return False

    prof = profiles.pop(old_name)
    prof.name = new_name.strip()
    profiles[prof.name] = prof
    save_profiles(profiles, profiles_file)
    return True


def set_default_profile(name: str, profiles_file: Optional[Path] = None) -> bool:
    """Set the specified profile as the default."""
    profiles = load_profiles(profiles_file)
    if name not in profiles:
        return False
    for p in profiles.values():
        p.is_default = (p.name == name)
    save_profiles(profiles, profiles_file)
    return True


def get_default_profile(profiles_file: Optional[Path] = None) -> Profile:
    """Return the current default profile, or fallback if none."""
    profiles = load_profiles(profiles_file)
    for p in profiles.values():
        if p.is_default:
            return p
    if profiles:
        return next(iter(profiles.values()))
    return get_default_fallback_profile()
