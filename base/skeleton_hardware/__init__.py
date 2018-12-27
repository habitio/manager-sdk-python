import traceback
from base.common.skeleton_base import SkeletonBase

import logging
logger = logging.getLogger(__name__)


class SkeletonHardware(SkeletonBase):

    def validate_confirmation_hash(self, data):
        try:
            hw_validation_hash = data['confirmation-hash']
            channeltemplate_id = data['channel-template']

            channel_template_data = self.get_channeltemplate_data(channeltemplate_id)
            is_valid = hw_validation_hash == channel_template_data['confirmation_hash']

            return is_valid

        except Exception:
            logger.error('Error on hardware validate_confirmation_hash'.format(traceback.format_exc(limit=5)))

        return False


SkeletonBase.register(SkeletonHardware)
