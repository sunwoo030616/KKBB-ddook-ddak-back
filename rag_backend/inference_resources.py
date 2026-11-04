"""Opt-in allocator policies and clearly scoped device telemetry."""
import os


def configure_mlx_cache(mx):
    value=os.getenv('RAG_MLX_CACHE_MB')
    if value is None:return {'cache_limit_bytes':None,'configured':False}
    try:mb=int(value)
    except ValueError:raise ValueError('invalid_mlx_cache_mb') from None
    if not 32<=mb<=2048:raise ValueError('mlx_cache_mb_outside_32_2048')
    mx.set_cache_limit(mb*1024*1024)
    return {'cache_limit_bytes':mb*1024*1024,'configured':True}


def mlx_memory(mx):
    return {'allocator':'mlx','active_bytes':mx.get_active_memory(),
            'cached_bytes':mx.get_cache_memory(),'process_peak_bytes':mx.get_peak_memory(),
            'scope':'MLX allocator only; not total process or system memory.'}


def mps_memory(torch,device):
    if device!='mps':return {'allocator':'torch_cpu','scope':'MPS telemetry not applicable.'}
    return {'allocator':'torch_mps','tensor_bytes':torch.mps.current_allocated_memory(),
            'driver_bytes':torch.mps.driver_allocated_memory(),
            'scope':'PyTorch MPS allocator/driver only; not total system memory.'}


def release_unused_mps(torch,device):
    policy=os.getenv('RAG_MPS_CACHE_POLICY','retain')
    if policy not in ('retain','release'):raise ValueError('unsupported_mps_cache_policy')
    before=mps_memory(torch,device)
    if policy=='release' and device=='mps':torch.mps.empty_cache()
    return {'policy':policy,'before':before,'after':mps_memory(torch,device)}
