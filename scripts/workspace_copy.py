"""Conservative offline filesystem copy/inventory. Reports contain no filenames/content."""
import hashlib
import json
import os
from pathlib import Path
import stat

MAX_BYTES = 5*1024**3-32*1024**2
MAX_ENTRIES = 90000


class CopyError(Exception):
    pass


def entries(root):
    root=Path(root)
    device=root.lstat().st_dev
    def walk(path,relative):
        info=path.lstat()
        if info.st_dev != device:
            raise CopyError('migration_nested_mount_unsupported')
        if not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode)):
            raise CopyError('migration_file_type_unsupported')
        try:
            if not hasattr(os,'listxattr'):raise CopyError('migration_xattrs_unverifiable')
            if os.listxattr(path,follow_symlinks=False):
                raise CopyError('migration_xattrs_unsupported')
        except (NotImplementedError,OSError):
            raise CopyError('migration_xattrs_unverifiable') from None
        yield path,relative,info
        if stat.S_ISDIR(info.st_mode):
            for child in sorted(path.iterdir(),key=lambda item:os.fsencode(item.name)):
                yield from walk(child,child.name if relative=='.' else relative+'/'+child.name)
    yield from walk(root,'.')


def inventory(root,max_bytes=MAX_BYTES,max_entries=MAX_ENTRIES):
    digest=hashlib.sha256();seen={};total=0;count=0
    for path,relative,info in entries(root):
        count+=1
        if count>max_entries:raise CopyError('migration_entry_limit')
        record=[relative,stat.S_IFMT(info.st_mode),stat.S_IMODE(info.st_mode),info.st_uid,info.st_gid,info.st_mtime_ns]
        if stat.S_ISLNK(info.st_mode):record.append(os.readlink(path))
        elif stat.S_ISREG(info.st_mode):
            key=(info.st_dev,info.st_ino)
            if key in seen:record.extend(['hardlink',seen[key]])
            else:
                seen[key]=relative;total+=info.st_size
                if total>max_bytes:raise CopyError('migration_size_limit')
                content=hashlib.sha256()
                fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
                with os.fdopen(fd,'rb') as stream:
                    opened=os.fstat(stream.fileno())
                    if (opened.st_dev,opened.st_ino,opened.st_size,opened.st_mtime_ns)!=(info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns):
                        raise CopyError('migration_source_changed')
                    while True:
                        chunk=stream.read(1024**2)
                        if not chunk:break
                        content.update(chunk)
                    final=os.fstat(stream.fileno())
                    if (final.st_size,final.st_mtime_ns)!=(info.st_size,info.st_mtime_ns):raise CopyError('migration_source_changed')
                record.extend([info.st_size,content.hexdigest()])
        encoded=json.dumps(record,ensure_ascii=True,separators=(',',':')).encode()
        digest.update(len(encoded).to_bytes(8,'big'));digest.update(encoded)
    return {'digest':digest.hexdigest(),'entries':count,'logical_bytes':total}


def metadata(path,info):
    current=path.lstat()
    if (current.st_uid,current.st_gid)!=(info.st_uid,info.st_gid):
        os.chown(path,info.st_uid,info.st_gid,follow_symlinks=False)
    if not stat.S_ISLNK(info.st_mode):os.chmod(path,stat.S_IMODE(info.st_mode))
    os.utime(path,ns=(info.st_atime_ns,info.st_mtime_ns),follow_symlinks=False)
    if not stat.S_ISLNK(info.st_mode):
        flags=os.O_RDONLY|os.O_NOFOLLOW|(os.O_DIRECTORY if stat.S_ISDIR(info.st_mode) else 0)
        fd=os.open(path,flags)
        try:os.fsync(fd)
        finally:os.close(fd)


def copy_verified(source,target):
    source,target=Path(source),Path(target)
    before=inventory(source)
    if target.is_symlink() or not target.is_dir() or any(target.iterdir()):raise CopyError('migration_target_not_empty')
    hardlinks={};directories=[]
    for path,relative,info in entries(source):
        output=target if relative=='.' else target/relative
        if stat.S_ISDIR(info.st_mode):
            if relative!='.':output.mkdir(mode=0o700)
            directories.append((output,info))
        elif stat.S_ISLNK(info.st_mode):
            output.symlink_to(os.readlink(path));metadata(output,info)
        else:
            key=(info.st_dev,info.st_ino)
            if key in hardlinks:os.link(hardlinks[key],output)
            else:
                hardlinks[key]=output
                source_fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
                target_fd=os.open(output,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
                with os.fdopen(source_fd,'rb') as reader,os.fdopen(target_fd,'wb') as writer:
                    while True:
                        chunk=reader.read(1024**2)
                        if not chunk:break
                        writer.write(chunk)
                    writer.flush();os.fsync(writer.fileno())
            metadata(output,info)
    for output,info in reversed(directories):metadata(output,info)
    if inventory(source)!=before or inventory(target)!=before:raise CopyError('migration_verification_failed')
    return before
