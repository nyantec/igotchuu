# Copyright © 2022 nyantec GmbH <oss@nyantec.com>
# Written by Vika Shleina <vsh@nyantec.com>
#
# Provided that these terms and disclaimer and all copyright notices
# are retained or reproduced in an accompanying document, permission
# is granted to deal in this work without restriction, including un‐
# limited rights to use, publicly perform, distribute, sell, modify,
# merge, give away, or sublicence.
#
# This work is provided "AS IS" and WITHOUT WARRANTY of any kind, to
# the utmost extent permitted by applicable law, neither express nor
# implied; without malicious intent or gross negligence. In no event
# may a licensor, author or contributor be held liable for indirect,
# direct, other damage, loss, or other issues arising in any way out
# of dealing in the work, even if advised of the possibility of such
# damage or existence of a defect, except proven that it results out
# of said person's immediate fault when using the work as intended.
import ctypes
import ctypes.util
import enum

# Mount helper
libc = ctypes.CDLL(ctypes.util.find_library('c'), use_errno=True)
libc.mount.argtypes = (ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_ulong, ctypes.c_char_p)

# Mount flags are copied from linux kernel headers
class MountFlags(enum.IntFlag):
    #define MS_RDONLY        1      /* Mount read-only */
    MS_RDONLY = 1
    #define MS_NOSUID        2      /* Ignore suid and sgid bits */
    MS_NOSUID = 2
    #define MS_NODEV         4      /* Disallow access to device special files */
    MS_NODEV = 4
    #define MS_NOEXEC        8      /* Disallow program execution */
    MS_NOEXEC = 8
    #define MS_SYNCHRONOUS  16      /* Writes are synced at once */
    MS_SYNCHRONOUS = 16
    #define MS_REMOUNT      32      /* Alter flags of a mounted FS */
    MS_REMOUNT = 32
    #define MS_MANDLOCK     64      /* Allow mandatory locks on an FS */
    MS_MANDLOCK = 64
    #define MS_DIRSYNC      128     /* Directory modifications are synchronous */
    MS_DIRSYNC = 128
    #define MS_NOSYMFOLLOW  256     /* Do not follow symlinks */
    MS_NOSYMFOLLOW = 256
    #define MS_NOATIME      1024    /* Do not update access times. */
    MS_NOATIME = 1024
    #define MS_NODIRATIME   2048    /* Do not update directory access times */
    MS_NODIRATIME = 2048
    #define MS_BIND         4096
    MS_BIND = 4096
    #define MS_MOVE         8192
    MS_MOVE = 8192
    #define MS_REC          16384
    MS_REC = 16384
    #define MS_SILENT       32768
    MS_SILENT = 32768
    #define MS_POSIXACL     (1<<16) /* VFS does not apply the umask */
    MS_POSIXACL = 1 << 16
    #define MS_UNBINDABLE   (1<<17) /* change to unbindable */
    MS_UNBINDABLE = 1 << 17
    #define MS_PRIVATE      (1<<18) /* change to private */
    MS_PRIVATE = 1 << 18
    #define MS_SLAVE        (1<<19) /* change to slave */
    MS_SLAVE = 1 << 19
    #define MS_SHARED       (1<<20) /* change to shared */
    MS_SHARED = 1 << 20
    #define MS_RELATIME     (1<<21) /* Update atime relative to mtime/ctime. */
    MS_RELATIME = 1 << 21
    #define MS_KERNMOUNT    (1<<22) /* this is a kern_mount call */
    MS_KERNMOUNT = 1 << 22
    #define MS_I_VERSION    (1<<23) /* Update inode I_version field */
    MS_I_VERSION = 1 << 23
    #define MS_STRICTATIME  (1<<24) /* Always perform atime updates */
    MS_STRICTATIME = 1 << 24
    #define MS_LAZYTIME     (1<<25) /* Update the on-disk [acm]times lazily */
    MS_LAZYTIME = 1 << 25


def mount(source, target, fs=None, flags=0, options=None):
    if fs is not None:
        fs = fs.encode()
    if options is not None:
        options = options.encode()
    ret = libc.mount(source.encode(), target.encode(), fs, int(flags), options)
    if ret < 0:
        errno = ctypes.get_errno()
        raise OSError(
            errno,
            f"Error mounting {source} on {target}: {os.strerror(errno)}"
        )
