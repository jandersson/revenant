import logging.config
import pathlib
import yaml


class ClientLogger:
    def _init_logger(self):
        log_conf_path = pathlib.Path(__file__).parents[0] / "logging_config.yaml"
        with open(log_conf_path, "r") as stream:
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
