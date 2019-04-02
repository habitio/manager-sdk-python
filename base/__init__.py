try:
    from base import python_logging as pl
    import logging

    # Create the Logger
    logger = logging.getLogger(__name__)

    # Add the Handler to the Logger
    logger.addHandler(pl.logger_handler)

    logger.critical('STARTING MANAGER')
    logger.notice("\n\n\n{}\n\n\n".format("===" * 45))
    logger.info("Completed configuring logger!")
except Exception as e:
    print('Error: {}'.format(e))
    exit()
