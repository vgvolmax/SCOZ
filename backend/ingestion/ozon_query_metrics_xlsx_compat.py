from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

def prepare_query_metrics_read_copy(original_path:Path,read_copy_path:Path)->None:
 if read_copy_path.exists():raise FileExistsError(read_copy_path)
 try:
  with ZipFile(original_path) as source, ZipFile(read_copy_path,'x',ZIP_DEFLATED) as target:
   for info in source.infolist():
    data=source.read(info.filename)
    if info.filename=='xl/styles.xml':data=data.replace(b'horizontal="Left"',b'horizontal="left"').replace(b'horizontal="Right"',b'horizontal="right"')
    target.writestr(info,data)
 except Exception:
  read_copy_path.unlink(missing_ok=True);raise
