try:
    import logging
    from base.settings import Settings
    from base import python_logging as pl

    settings = Settings()

    log_level = (100 + 9-int(settings.config_log["level"]))
    pl.setup_loglevel()
    logger_handler = pl.setup_logger_handler(settings.log_path, log_level)

    logger = logging.getLogger(__name__)
    logger.addHandler(logger_handler)

    logger.critical('STARTING MANAGER')
    logger.notice("\n\n\n{}\n\n\n".format("==="*45))
    logger.info("Completed configuring logger!")
except Exception as e:
    print('Error: {}'.format(e))
    exit()
