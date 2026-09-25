# Capture Tool

`finqalab_capture.py` — mitmproxy addon + CLI that captures Finqalab HTTP and
WebSocket traffic into SQLite.

**Full documentation: [../07-capture-tool.md](../07-capture-tool.md).**
**Methodology and why the obvious approach fails:
[../01-capture-approach.md](../01-capture-approach.md).**

```bash
python doc/reverse/tools/finqalab_capture.py --duration 300
```

> ⚠️ **The database this writes contains live credentials, JWTs, CNIC and mobile
> numbers, IBANs, and order numbers.** `.gitignore` excludes `*.db`, but keep the
> output outside the repository to be safe. Change any password that ends up in
> a capture, and delete the file when you are done.

Captures are only ever taken from an account you own, on a device you control.
