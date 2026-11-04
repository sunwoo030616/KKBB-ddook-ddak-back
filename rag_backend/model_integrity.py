"""Verify local weight/tokenizer files before model loading, with bounded stat-key reuse."""
from collections import OrderedDict
import hashlib
from pathlib import Path,PurePosixPath
from threading import Lock

_verified=OrderedDict()
_lock=Lock()


def verify_snapshot(path,manifest):
    root=Path(path).resolve()
    files=manifest.get('files')
    if not isinstance(files,dict) or not files:raise ValueError('model_file_manifest_required')
    checked=0;reused=0
    with _lock:
        for name,expected in files.items():
            relative=PurePosixPath(name)
            if relative.is_absolute() or '..' in relative.parts or '\\' in name:
                raise ValueError('invalid_model_manifest_path')
            target=(root/name).resolve()
            if not target.is_relative_to(root) or not target.is_file():raise ValueError('model_artifact_missing_or_outside_snapshot')
            before=target.stat();sha=expected.get('sha256');size=expected.get('bytes')
            if type(size) is not int or size!=before.st_size or not isinstance(sha,str) or len(sha)!=64:
                raise ValueError('model_artifact_metadata_mismatch')
            key=(str(target),before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns,sha)
            if key in _verified:
                _verified.move_to_end(key);reused+=1;continue
            hasher=hashlib.sha256()
            with target.open('rb') as handle:
                for block in iter(lambda:handle.read(8*1024*1024),b''):hasher.update(block)
            after=target.stat()
            if (before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)!=(after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns):
                raise ValueError('model_artifact_changed_during_verification')
            if hasher.hexdigest()!=sha:raise ValueError('model_artifact_hash_mismatch')
            _verified[key]=True;checked+=1
            while len(_verified)>64:_verified.popitem(last=False)
    return {'files_checked':checked,'files_reused':reused}
