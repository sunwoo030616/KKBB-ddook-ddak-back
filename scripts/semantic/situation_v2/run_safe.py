"""New-run entry point with nullable metric display; original frozen runner retained for audit."""
from pathlib import Path
path=Path(__file__).with_name('run.py')
source=path.read_text()
before="{row['score']['precision']:.2f} R={row['score']['recall']:.2f}"
assert source.count(before)==1
source=source.replace(before,"{row['score']['precision']} R={row['score']['recall']}")
exec(compile(source,str(path),'exec'),{'__file__':str(path),'__name__':'__main__'})
