from io import BytesIO
from pathlib import Path

from pipeline.fetch import fetch_sources
from pipeline.schema import SourceAsset, SourceManifest


class FakeResponse(BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def test_fetch_sources_writes_each_role(tmp_path: Path):
    manifest = SourceManifest((SourceAsset('base_rigged', 'https://x/base', 'base.glb'),))
    paths = fetch_sources(manifest, tmp_path, opener=lambda _: FakeResponse(b'glb-bytes'))
    assert paths['base_rigged'].read_bytes() == b'glb-bytes'
