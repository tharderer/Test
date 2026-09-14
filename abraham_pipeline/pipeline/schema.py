from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json


@dataclass(frozen=True)
class EquipmentProfile:
    name: str
    equipment_class: str
    target_bone_role: str
    clearance_m: float = 0.008
    max_influences: int = 4
    fit: dict[str, object] | None = None


@dataclass(frozen=True)
class ValidationThresholds:
    max_unweighted_vertices: int
    max_influences_per_vertex: int
    max_floating_distance_m: float
    max_penetration_ratio: float
    max_bundle_mb: float
    max_floating_vertex_ratio: float = 0.08


@dataclass(frozen=True)
class BuildConfig:
    canonical_height_m: float
    equipment: dict[str, EquipmentProfile]
    validation: ValidationThresholds


@dataclass(frozen=True)
class SourceAsset:
    role: str
    url: str
    filename: str


@dataclass(frozen=True)
class SourceManifest:
    assets: tuple[SourceAsset, ...]

    def by_role(self, role: str) -> SourceAsset:
        for asset in self.assets:
            if asset.role == role:
                return asset
        raise KeyError(role)


REQUIRED_SOURCE_ROLES = {
    'base_rigged', 'staff', 'belt', 'mantle', 'idle', 'walk', 'run'
}


def load_build_config(path: Path) -> BuildConfig:
    raw = json.loads(path.read_text())
    equipment = {
        name: EquipmentProfile(
            name=name,
            equipment_class=item['class'],
            target_bone_role=item['target_bone_role'],
            clearance_m=float(item.get('clearance_m', 0.008)),
            max_influences=int(item.get('max_influences', 4)),
            fit=item.get('fit'),
        )
        for name, item in raw['equipment'].items()
    }
    if set(equipment) != {'staff', 'belt', 'mantle'}:
        raise ValueError('equipment must contain exactly staff, belt, mantle')
    validation = ValidationThresholds(**raw['validation'])
    return BuildConfig(float(raw['canonical_height_m']), equipment, validation)


def load_source_manifest(path: Path) -> SourceManifest:
    raw = json.loads(path.read_text())
    assets = tuple(SourceAsset(**item) for item in raw['assets'])
    roles = {asset.role for asset in assets}
    missing = REQUIRED_SOURCE_ROLES - roles
    if missing:
        raise ValueError(f'missing required source roles: {sorted(missing)}')
    duplicates = sorted(role for role in roles if sum(a.role == role for a in assets) > 1)
    if duplicates:
        raise ValueError(f'duplicate source roles: {duplicates}')
    return SourceManifest(assets)
