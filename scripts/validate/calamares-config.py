#!/usr/bin/env python3
"""Validate Starch configuration against the pinned upstream module schemas."""
from pathlib import Path
import sys
import jsonschema
import yaml

source = Path(sys.argv[1])
project = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).resolve().parents[2]
for config in sorted((project / 'calamares/modules').glob('*.conf')):
    schema_path = source / 'src/modules' / config.stem / (config.stem + '.schema.yaml')
    if not schema_path.is_file():
        raise SystemExit(f'Missing upstream schema: {schema_path}')
    schema = yaml.safe_load(schema_path.read_text())
    if config.stem == 'partition':
        # v3.3.14 documents and consumes this setting in PartitionViewStep.cpp,
        # but omits it from the schema. Validate that one key explicitly.
        assert '"defaultPartitionTableType"' in (source / 'src/modules/partition/PartitionViewStep.cpp').read_text()
        schema['properties']['defaultPartitionTableType'] = {'enum': ['gpt']}
    jsonschema.validate(yaml.safe_load(config.read_text()), schema)
    print(f'Validated {config.name}')
