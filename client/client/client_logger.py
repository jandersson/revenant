import logging.config
import yaml


class ClientLogger:
    def _init_logger(self):
        with open("./logging_config.yaml", "r") as stream:
            config = yaml.load(stream, Loader=yaml.FullLoader)

        logging.config.dictConfig(config)

    @property
    def log(self):
        """Shamelessly copied from Airflow"""
        try:
            return self._log
        except AttributeError:
            self._init_logger()
            self._log = logging.root.getChild(self.__class__.__module__ + "." + self.__class__.__name__)
            return self._log
