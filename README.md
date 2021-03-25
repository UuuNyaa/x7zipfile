# x7zipfile
x7zipfile is a thin [7-zip](https://www.7-zip.org/) extract command wrapper for Python.

## Features
- The interface follows the style of [zipfile](https://docs.python.org/3/library/zipfile.html).
- Archive operations are handled by executing external tool: 7z, 7za or 7zr.
- Works with single file.
- Supports extract and list operations.
- **Not** supports compress operations.
- Supports archive formats that can be processed by the 7z command.
- Supports Unicode filenames.
- Supports password-protected archives.

## Installation
### Requirements
 - Python **3.7** or later
 - 7-zip **16** or later

### Download
 - Download x7zipfile from [the github code page](https://github.com/UuuNyaa/x7zipfile/blob/main/src/x7zipfile.py)
   - https://github.com/UuuNyaa/x7zipfile/blob/main/src/x7zipfile.py

### Install
1. ***Place the `x7zipfile.py`*** file where you want.
2. ***Install 7-zip***.
    - Windows: https://www.newsgroupreviews.com/7-zip-installation.html
    - Linux: run `sudo {apt,yum,dnf,snap} install p7zip-full`

## Usage

### Simple extract example
```python
import x7zipfile

with x7zipfile.x7ZipFile('myarchive.7z') as zipfile:
    for info in zipfile.infolist():
        print(info.filename, info.file_size)
        if info.filename == 'README':
            zipfile.extract(info)
```

### Dynamic module load example
```python
import importlib

namespace = 'x7zipfile'
loader = importlib.machinery.SourceFileLoader(namespace, '/path/to/x7zipfile.py')
x7zipfile = loader.load_module(namespace)
```