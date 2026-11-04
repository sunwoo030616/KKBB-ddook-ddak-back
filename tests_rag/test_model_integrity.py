import hashlib

import pytest

from rag_backend.model_integrity import verify_snapshot


def fixture(tmp_path):
    data=b'synthetic model bytes';(tmp_path/'model.safetensors').write_bytes(data)
    return {'files':{'model.safetensors':{'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}}}


def test_hash_verified_then_reused_and_same_size_drift_rejected(tmp_path):
    manifest=fixture(tmp_path)
    assert verify_snapshot(tmp_path,manifest)['files_checked']==1
    assert verify_snapshot(tmp_path,manifest)['files_reused']==1
    (tmp_path/'model.safetensors').write_bytes(b'X'*len(b'synthetic model bytes'))
    with pytest.raises(ValueError,match='hash_mismatch'):verify_snapshot(tmp_path,manifest)


def test_changed_expected_hash_cannot_reuse_old_verification(tmp_path):
    manifest=fixture(tmp_path);verify_snapshot(tmp_path,manifest)
    manifest['files']['model.safetensors']['sha256']='0'*64
    with pytest.raises(ValueError,match='hash_mismatch'):verify_snapshot(tmp_path,manifest)


@pytest.mark.parametrize('name',['../outside','/absolute','dir/../../outside','dir\\outside'])
def test_manifest_paths_cannot_escape_snapshot(tmp_path,name):
    with pytest.raises(ValueError,match='invalid_model_manifest_path'):
        verify_snapshot(tmp_path,{'files':{name:{'bytes':1,'sha256':'0'*64}}})


def test_symlink_outside_snapshot_is_rejected(tmp_path):
    model=tmp_path/'model';model.mkdir();(tmp_path/'outside').write_bytes(b'x')
    (model/'weights').symlink_to(tmp_path/'outside')
    with pytest.raises(ValueError,match='outside_snapshot'):
        verify_snapshot(model,{'files':{'weights':{'bytes':1,'sha256':hashlib.sha256(b'x').hexdigest()}}})
