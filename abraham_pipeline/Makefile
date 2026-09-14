.PHONY: test proof verify

test:
	pytest -v

proof:
	bash scripts/build_proof.sh

verify: test proof
	python -c "from pathlib import Path; p=Path('assets/build/mobile/abraham_upgrade_bundle.glb'); assert p.exists(), p; assert p.stat().st_size <= 18*1024*1024, p.stat().st_size; print(f'bundle: {p.stat().st_size/1024/1024:.2f} MB')"
