import getpass
import grp
import os
import pwd

import psutil


def get_memory_usage():
    try:
        tot_m, used_m, free_m = map(int, os.popen('/usr/bin/free -t -m').readlines()[-1].split()[1:])
    except Exception as e:
        return -1, -1, -1

    return tot_m, used_m, free_m


def get_system_summary():
    return {
        "boot_time": psutil.boot_time(),
        "users": psutil.users(),
        "cpu_count": psutil.cpu_count(),
        "cpu_percent": psutil.cpu_percent(),
        "cpu_loadavg": psutil.getloadavg(),
        "cpu_loadavg_perc": [x / psutil.cpu_count() * 100 for x in psutil.getloadavg()],
        "mem_virt": dict(psutil.virtual_memory()._asdict()),
        "mem_swap": dict(psutil.swap_memory()._asdict()),
        "mem_virt_percent": psutil.virtual_memory().percent,
        "mem_avail_percent": psutil.virtual_memory().available * 100 / psutil.virtual_memory().total,
    }


def get_all_disk_usage():
    return {
        "/": get_disk_usage("/"),
    }


def get_disk_usage(path):
    try:
        return psutil.disk_usage(path)
    except Exception as e:
        return None


# def get_pidinfo(name: str):
#     pid_file = os.path.join(config.TMP_DIR, 'run', f"{name}.pid")
#     os.makedirs(os.path.dirname(pid_file), exist_ok=True)
#     try:
#         pid = file_get_contents(pid_file)
#         pid = int(str(pid).strip())
#         if pid < 1:
#             return ValueError("Invalid PID")
#
#         exists = psutil.pid_exists(int(pid))
#         return pid, exists, pid_file
#     except Exception as ex:
#         pass
#     return None


def get_system_report():
    def _stat(path):
        try:
            return os.stat(path)
        except Exception as e:
            return str(e)

    def _dirinfo(dir_path):
        return {
            "path": dir_path,
            "exists": os.path.exists(dir_path),
            "is_mount": os.path.ismount(dir_path),
            "is_link": os.path.islink(dir_path),
            "is_dir": os.path.isdir(dir_path),
            # "is_writeable": probe_is_dir_writeable(dir_path),
            # "is_writeable2": is_dir_writeable_eager(dir_path),
            # "stat": _stat(dir_path)
        }

    def _fileinfo(file_path):
        return {
            "path": file_path,
            "exists": os.path.exists(file_path),
            "is_mount": os.path.ismount(file_path),
            "is_link": os.path.islink(file_path),
            "is_file": os.path.isfile(file_path),
            # "stat": _stat(file_path)
        }

    def _getlogin():
        try:
            return os.getlogin()
        except Exception as e:
            return str(e)

    def _getpass():
        try:
            return getpass.getuser()
        except Exception as e:
            return str(e)

    def _getpwuid():
        try:
            return pwd.getpwuid(os.getuid())[0]
        except Exception as e:
            return str(e)

    def _getuid():
        try:
            return os.getuid()
        except Exception as e:
            return str(e)

    def _getexpanduser():
        try:
            return os.path.expanduser('~')
        except Exception as e:
            return str(e)

    def _getgroupids():
        try:
            return os.getgroups()
        except Exception as e:
            return str(e)

    def _getgroupnames():
        try:
            return [grp.getgrgid(g).gr_name for g in os.getgroups()]
        except Exception as e:
            return str(e)

    data = {
        "system": get_system_summary(),
        "disk_usage": get_all_disk_usage(),
        "user": {
            "envuser": os.environ.get("USERNAME"),
            "uid": _getuid(),
            "login": _getlogin(),
            "expanduser": _getexpanduser(),
            "getpass": _getpass(),
            "pwuid": _getpwuid(),
            "groupids": _getgroupids(),
            "groupnames": _getgroupnames()
        },
        "directories": {
        },
        "files": {
        },
    }
    # dump the env variables
    data.update({"env": dict(os.environ)})
    return data
