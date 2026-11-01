# Contributing

Use an isolated checkout and synthetic projects. Do not run tests against production projects or stop shared inference services.

```bash
python3 -m unittest discover -s tests -t . -p 'test_*.py'
for f in tests/frontend/test_*.js; do node "$f" || exit 1; done
python3 scripts/export_release.py --output /tmp/shotdesk-candidate
```

Python tests use controlled HTTP services, not GPU quality review. Optional historical tests requiring non-distributed upstream originals are skipped in the public candidate. Current structured storyboard, portable adapter, setup tools and queue tests remain covered. Changes to generation require a bounded real-service check, recorded separately.

Include version, installation method, service type, reproduction steps and sanitized task errors in bug reports. Do not post credentials or full user project data. Original contributions are covered by LICENSE (MIT). Preserve third-party notices and do not add material without redistribution rights.
