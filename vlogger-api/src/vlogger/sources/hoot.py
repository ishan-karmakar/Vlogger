from vlogger.sources import Source, wpilog
import logging, os, tempfile
import shutil
logger = logging.getLogger(__name__)

class Hoot(wpilog.WPILog):
    def __init__(self, file, regexes, **kwargs):
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

        super(Hoot, self).__init__(out, regexes, **kwargs)

    def __exit__(self, exception_type, exception_value, exception_traceback):
        super(Hoot, self).__exit__(exception_type, exception_value, exception_traceback)
        shutil.rmtree(self.tempdir)