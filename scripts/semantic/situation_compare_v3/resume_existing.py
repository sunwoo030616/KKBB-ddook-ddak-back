"""Continue an already seeded run without rewriting any saved rows."""
from pathlib import Path
path=Path(__file__).with_name('continue_measured.py');source=path.read_text()
start=source.index('assert not a.output.exists()');end=source.index('sys.argv=',start)
source=source[:start]+"assert a.output.exists()\n"+source[end:]
exec(compile(source,str(path),'exec'),{'__file__':str(path),'__name__':'__main__'})
