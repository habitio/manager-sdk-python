try:
    import os
    from base.logger_base import settings, logger

    logger.critical('STARTING MANAGER')
    logger.notice("\n\n\n{}\n\n\n".format("===" * 45))
    logger.info("Completed configuring logger!")
except Exception as e:
    print('Error: {}'.format(e))
    os._exit(1)
