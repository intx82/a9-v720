import logging

class log:
    def __init__(self, log_prefix: str = '') -> None:
        self._log = logging.getLogger(log_prefix)
        _stdout_hnd = logging.StreamHandler()
        _fmt = f"%(asctime)s  [%(levelname)7.7s] [{log_prefix}] %(message)s"
        _stdout_hnd.setFormatter(logging.Formatter(_fmt))
        self._log.addHandler(_stdout_hnd)
        self._log.setLevel(logging.DEBUG)

    def dbg(self, msg, *args, **kwargs):
        if self._log is not None:
            self._log.debug(msg, *args, **kwargs)

    def info(self, msg, *args, **kwargs):
        if self._log is not None:
            self._log.info(msg, *args, **kwargs)

    def warn(self, msg, *args, **kwargs):
        if self._log is not None:
            self._log.warning(msg, *args, **kwargs)

    def err(self, msg, *args, **kwargs):
        if self._log is not None:
            self._log.error(msg, *args, **kwargs)