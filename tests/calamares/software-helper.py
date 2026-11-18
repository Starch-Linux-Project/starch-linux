"""Fake transaction for the isolated native UI test; never installs software."""
import json
from pathlib import Path
import sys
import time

request = json.load(sys.stdin)
name = request['name']
with Path('/tmp/starch-software-test.log').open('a') as log:
    log.write(f'start {name}\n')
    log.flush()
    with Path('/var/log/starch-installer.log').open('a') as output:
        output.write(f'downloading {name}\n')
    time.sleep(0.7)
    log.write(f'end {name}\n')
if name == 'missing':
    print('Warning: simulated repository failure')
    sys.exit(1)
