from vlogger import wpilog
import logging, os, tempfile
import shutil
from urllib.parse import ParseResult, urlparse
logger = logging.getLogger(__name__)

class Hoot(wpilog.WPILog):
    SCHEME = "hoot"

    def __init__(self, ident: ParseResult, regexes, **kwargs):
        owlet = shutil.which(kwargs.get("owlet", "owlet"))
        if owlet:
            logger.debug(f"Using owlet at {owlet}")
        else:
            raise FileNotFoundError("Could not find 'owlet' in PATH or given owlet executable does not exist")

        self.tempdir = tempfile.mkdtemp()
        out = os.path.join(self.tempdir, "hoot.wpilog")
        os.system(f"{owlet} {ident.path} {out} -f wpilog")

        super(Hoot, self).__init__(urlparse(f"wpilog:///{out}"), regexes, **kwargs)

    def __exit__(self, exception_type, exception_value, exception_traceback):
        super(Hoot, self).__exit__(exception_type, exception_value, exception_traceback)
        shutil.rmtree(self.tempdir)