from vlogger.sources import Source, wpilog
import logging, os, tempfile
import shutil
logger = logging.getLogger(__name__)

class Hoot(Source):
    def __init__(self, file, regex_listeners, **kwargs):
        if not file.endswith(".hoot"):
            raise ValueError("File does not end in .hoot")

        owlet = shutil.which(kwargs.get("owlet", "owlet"))
        if owlet:
            logger.debug(f"Using owlet at {owlet}")
        else:
            raise FileNotFoundError("Could not find 'owlet' in PATH or given owlet executable does not exist")

        self.tempdir = tempfile.mkdtemp()
        out = os.path.join(self.tempdir, "hoot.wpilog")
        os.system(f"{owlet} {file} {out} -f wpilog")

        self.wpilog = wpilog.WPILog(out, regex_listeners, **kwargs)

    def __iter__(self):
        return iter(self.wpilog)
    
    def close(self):
        self.wpilog.close()
        shutil.rmtree(self.tempdir)