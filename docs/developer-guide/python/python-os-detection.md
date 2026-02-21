# Detecting the Operating System in Python

```text
>>> import os

>>> os.name
'posix'

>>> import platform

>>> platform.system()
'Linux'

>>> platform.release()
'2.6.22-15-generic'
```


## Linux (64 bit) + WSL

|                          | x86_64        | aarch64        |
|--------------------------|--------------|---------------|
| os.name                  | posix        | posix         |
| sys.platform             | linux        | linux         |
| platform.system()        | Linux        | Linux         |
| sysconfig.get_platform() | linux-x86_64 | linux-aarch64 |
| platform.machine()       | x86_64       | aarch64       |
| platform.architecture()  | ('64bit', '')| ('64bit', 'ELF') |

---

## Windows (64 bit)

(with 32-bit column running in the 32-bit subsystem)

### Official Python installer

|                          | 64 bit                 | 32 bit                 |
|--------------------------|------------------------|------------------------|
| os.name                  | nt                     | nt                     |
| sys.platform             | win32                  | win32                  |
| platform.system()        | Windows                | Windows                |
| sysconfig.get_platform() | win-amd64              | win32                  |
| platform.machine()       | AMD64                  | AMD64                  |
| platform.architecture()  | ('64bit','WindowsPE')  | ('64bit','WindowsPE')  |

---

### msys2

|                          | 64 bit                  | 32 bit                  |
|--------------------------|-------------------------|-------------------------|
| os.name                  | posix                   | posix                   |
| sys.platform             | msys                    | msys                    |
| platform.system()        | MSYS_NT-10.0            | MSYS_NT-10.0-WOW        |
| sysconfig.get_platform() | msys-2.11.2-x86_64      | msys-2.11.2-i686        |
| platform.machine()       | x86_64                  | i686                    |
| platform.architecture()  | ('64bit','WindowsPE')   | ('32bit','WindowsPE')   |

---

### msys2 (mingw-w64 python)

|                          | mingw-w64-x86_64-python3 | mingw-w64-i686-python3 |
|--------------------------|---------------------------|-------------------------|
| os.name                  | nt                        | nt                      |
| sys.platform             | win32                     | win32                   |
| platform.system()        | Windows                   | Windows                 |
| sysconfig.get_platform() | mingw                     | mingw                   |
| platform.machine()       | AMD64                     | AMD64                   |
| platform.architecture()  | ('64bit','WindowsPE')     | ('32bit','WindowsPE')   |

---

### Cygwin

|                          | 64 bit                  | 32 bit                  |
|--------------------------|-------------------------|-------------------------|
| os.name                  | posix                   | posix                   |
| sys.platform             | cygwin                  | cygwin                  |
| platform.system()        | CYGWIN_NT-10.0          | CYGWIN_NT-10.0-WOW      |
| sysconfig.get_platform() | cygwin-3.0.1-x86_64     | cygwin-3.0.1-i686       |
| platform.machine()       | x86_64                  | i686                    |
| platform.architecture()  | ('64bit','WindowsPE')   | ('32bit','WindowsPE')   |


### Links


- https://stackoverflow.com/questions/1854/how-to-identify-which-os-python-is-running-on
- https://docs.python.org/3/library/platform.html