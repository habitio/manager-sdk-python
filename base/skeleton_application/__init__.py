from base.common.skeleton_base import SkeletonBase
from .router import *
from .webhook import *

class SkeletonApplication(SkeletonBase):

     def upstream(self, mode, case, sender, data=None):
        """
        *** MANDATORY ***
        Invoked when Muzzley platform intends to communicate with the manager to read/update information.

        Receives,
            mode        - 'r' or 'w'
            case        - A dictionary with keys 'channel_id', 'component' and 'property'.
            data        - data if any sent by Muzzley's platform.
            sender      - A dictionary with keys 'client_id' and 'owner_id'.

        """
        return NotImplemented

SkeletonBase.register(SkeletonApplication)
