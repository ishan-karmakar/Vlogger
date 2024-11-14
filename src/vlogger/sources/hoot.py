from vlogger.sources import Source, SourceType, wpilog
import logging, os, tempfile
import shutil
logger = logging.getLogger(__name__)

class Hoot(Source):
    SOURCE_TYPE = SourceType.HISTORICAL

    def __init__(self, target_fields, file, args):
        if not file or not file.endswith(".hoot"):
            raise ValueError
        
        owlet = shutil.which(args.owlet or "owlet")
        if owlet:
            logger.debug(f"Using owlet at {owlet}")
        else:
            logger.error("Could not find 'owlet' in PATH or given owlet executable does not exist")
            raise ValueError

        self.tempdir = tempfile.mkdtemp()
        out = os.path.join(self.tempdir, "hoot.wpilog")
        os.system(f"{owlet} {file} {out} -f wpilog")

        self.wpilog = wpilog.WPILog(target_fields, out, args)

    def __iter__(self):
        return iter(self.wpilog)
    
    def close(self):
        self.wpilog.close()
        shutil.rmtree(self.tempdir)