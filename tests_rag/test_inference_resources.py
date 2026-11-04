import pytest

from rag_backend.inference_resources import configure_mlx_cache,release_unused_mps


class MX:
    def set_cache_limit(self,size):self.size=size


def test_allocator_limit_requires_valid_explicit_configuration(monkeypatch):
    monkeypatch.delenv('RAG_MLX_CACHE_MB',raising=False)
    mx=MX();assert configure_mlx_cache(mx)['configured'] is False
    monkeypatch.setenv('RAG_MLX_CACHE_MB','128')
    assert configure_mlx_cache(mx)['cache_limit_bytes']==128*1024*1024
    assert mx.size==128*1024*1024
    for value in ('0','9000','nonsense'):
        monkeypatch.setenv('RAG_MLX_CACHE_MB',value)
        with pytest.raises(ValueError):configure_mlx_cache(mx)


def test_unused_mps_release_records_distinct_tensor_and_driver_memory(monkeypatch):
    class MPS:
        driver=1000
        def current_allocated_memory(self):return 100
        def driver_allocated_memory(self):return self.driver
        def empty_cache(self):self.driver=100
    class Torch:mps=MPS()
    monkeypatch.setenv('RAG_MPS_CACHE_POLICY','release')
    result=release_unused_mps(Torch,'mps')
    assert result['before']['driver_bytes']==1000 and result['after']['driver_bytes']==100
    assert result['after']['tensor_bytes']==100
    assert release_unused_mps(Torch,'cpu')['after']['allocator']=='torch_cpu'
